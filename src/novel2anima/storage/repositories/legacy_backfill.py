"""Deterministic relational backfill for Novel2Anima V4 (PR-02).

This module only reads legacy rows and writes additive V4 projection tables:

* ``project_document_revision`` from the legacy ``project`` row;
* ``character_identity_revision`` from ``character_profile.identity_json``;
* ``outfit_revision`` + ``outfit_item`` from ``character_profile.outfit_json``;
* ``shot_spec_revision`` from ``shot.shot_spec_json``;
* ``shot_participant`` from explicit participants plus ``shot.character_id``;
* ``shot_interaction`` only where actor/target/action are explicitly present;
* ``shot_outfit_binding`` only for exact tag-set matches.

Anything missing, ambiguous or invalid becomes a ``reconciliation_item``.  In
particular, a multi-participant shot with no explicit actor/target is *not*
inferred from participant order, gender, gaze or tags.

The operation is idempotent and runs in one transaction.  ``dry_run`` performs
the same work and then rolls it back.  The live DB is refused unless the caller
explicitly opts in; normal use is a staging copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from novel2anima.storage.migrations import (
    applied_migrations,
    backup_database,
    connect,
    is_live_database,
)

LEGACY_PROJECT_SCHEMA = "legacy-project/1"
LEGACY_OUTFIT_SCHEMA = "legacy-outfit/1"
BACKFILL_VERSION = "pr-02/1"
MAX_PARTICIPANTS = 8
OUTFIT_METADATA_KEYS = {"source", "assumed"}
ROLE_MAP = {
    "participant": "subject",
    "subject": "subject",
    "support": "support",
    "background": "background",
}
REQUIRED_TABLES = {
    "project",
    "character_profile",
    "act",
    "shot",
    "tag",
    "project_document_revision",
    "character_identity_revision",
    "outfit_revision",
    "outfit_item",
    "shot_spec_revision",
    "shot_participant",
    "shot_interaction",
    "shot_outfit_binding",
    "reconciliation_item",
    "n2a_schema_migration",
}
REQUIRED_MIGRATIONS = {"007_reconciliation_queue"}


class BackfillError(RuntimeError):
    """Raised when the staging database is not safe to backfill."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _short_hash(value: str) -> str:
    return _sha256_text(value)[:12]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _inc(bucket: dict[str, int], key: str, amount: int = 1) -> None:
    bucket[key] = bucket.get(key, 0) + amount


def _count(report: dict, section: str, key: str, amount: int = 1) -> None:
    _inc(report["counts"][section], key, amount)


def _new_report(db_path: Path, dry_run: bool, project_ids: Sequence[int] | None) -> dict:
    return {
        "schema_version": "n2a-backfill-report/1",
        "backfill_version": BACKFILL_VERSION,
        "database": str(db_path),
        "dry_run": bool(dry_run),
        "project_ids": list(project_ids) if project_ids else None,
        "started_at_utc": _utc_now(),
        "finished_at_utc": None,
        "status": "running",
        "counts": {
            "project_documents": {"inserted": 0, "skipped": 0, "conflicts": 0},
            "identities": {"inserted": 0, "skipped": 0, "conflicts": 0, "invalid": 0},
            "outfits": {
                "revisions_inserted": 0,
                "revisions_skipped": 0,
                "revisions_conflicts": 0,
                "items_inserted": 0,
                "items_skipped": 0,
                "variant_name_lists": 0,
            },
            "shot_specs": {"inserted": 0, "skipped": 0, "conflicts": 0, "invalid": 0},
            "participants": {"inserted": 0, "skipped": 0, "conflicts": 0, "shots": 0},
            "interactions": {"inserted": 0, "skipped": 0, "conflicts": 0},
            "outfit_bindings": {
                "inserted": 0,
                "skipped": 0,
                "conflicts": 0,
                "unmatched": 0,
                "missing": 0,
                "ambiguous": 0,
            },
        },
        "reconciliation": {
            "inserted": 0,
            "existing": 0,
            "by_rule": {},
            "by_severity": {},
        },
        "checks": None,
        "backup": None,
        "errors": [],
    }


def _queue(
    connection: sqlite3.Connection,
    report: dict,
    *,
    gap_key: str,
    domain: str,
    rule_code: str,
    severity: str = "warning",
    project_id: int | None = None,
    act_id: int | None = None,
    shot_id: int | None = None,
    character_id: int | None = None,
    entity_table: str | None = None,
    entity_id: int | None = None,
    evidence: dict[str, Any] | None = None,
) -> None:
    """Insert one idempotent reconciliation item."""
    evidence_json = _canonical_json(evidence or {})
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO reconciliation_item(
          gap_key, domain, severity, project_id, act_id, shot_id, character_id,
          entity_table, entity_id, rule_code, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gap_key,
            domain,
            severity,
            project_id,
            act_id,
            shot_id,
            character_id,
            entity_table,
            entity_id,
            rule_code,
            evidence_json,
        ),
    )
    if cursor.rowcount:
        _inc(report["reconciliation"], "inserted")
        _inc(report["reconciliation"]["by_rule"], rule_code)
        _inc(report["reconciliation"]["by_severity"], severity)
    else:
        _inc(report["reconciliation"], "existing")


def _database_checks(connection: sqlite3.Connection) -> dict:
    quick = [row[0] for row in connection.execute("PRAGMA quick_check").fetchmany(21)]
    foreign_keys = [list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchmany(21)]
    return {
        "quick_check": quick,
        "quick_check_ok": quick == ["ok"],
        "foreign_key_violations_first_20": foreign_keys,
        "foreign_key_ok": not foreign_keys,
    }


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _assert_schema(connection: sqlite3.Connection) -> None:
    missing = [table for table in sorted(REQUIRED_TABLES) if not _table_exists(connection, table)]
    if missing:
        raise BackfillError(f"staging DB is missing required tables: {', '.join(missing)}")
    applied = applied_migrations(connection)
    missing_migrations = sorted(REQUIRED_MIGRATIONS - set(applied))
    if missing_migrations:
        raise BackfillError(
            "staging DB is missing required migrations: " + ", ".join(missing_migrations)
        )


def _parse_object(raw: Any) -> tuple[dict | None, str]:
    if raw is None:
        return None, "null"
    if not isinstance(raw, str):
        return None, "not_text"
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None, "invalid_json"
    if not isinstance(value, dict):
        return None, "not_object"
    return value, "ok"


def _project_filter(project_ids: Sequence[int] | None) -> tuple[str, tuple[int, ...]]:
    if not project_ids:
        return "", ()
    placeholders = ",".join("?" for _ in project_ids)
    return f" WHERE project_id IN ({placeholders})", tuple(project_ids)


def _backfill_project_documents(
    connection: sqlite3.Connection, report: dict, project_ids: Sequence[int] | None
) -> None:
    where, params = _project_filter(project_ids)
    if where:
        where = where.replace("project_id", "id", 1)
    rows = connection.execute(
        "SELECT id, title, idea, content_profile, style_json, created_at FROM project"
        + where
        + " ORDER BY id",
        params,
    ).fetchall()
    report["source_counts"]["projects"] = len(rows)
    for row in rows:
        project_id = row["id"]
        style: Any = {}
        style_state = "ok"
        if row["style_json"]:
            try:
                style = json.loads(row["style_json"])
            except (TypeError, ValueError):
                style_state = "invalid_json"
        body: dict[str, Any] = {
            "schema_version": LEGACY_PROJECT_SCHEMA,
            "title": row["title"],
            "idea": row["idea"],
            "content_profile": row["content_profile"],
            "style": style if style_state == "ok" else None,
            "created_at": row["created_at"],
        }
        if style_state != "ok":
            body["style_raw"] = row["style_json"]
            _queue(
                connection,
                report,
                gap_key=f"project:style_json:{project_id}",
                domain="project",
                rule_code="project_style_json_invalid",
                project_id=project_id,
                entity_table="project",
                entity_id=project_id,
                evidence={"source_column": "style_json", "state": style_state},
            )
        body_json = _canonical_json(body)
        body_sha256 = _sha256_text(body_json)
        existing = connection.execute(
            """
            SELECT id, body_sha256 FROM project_document_revision
            WHERE project_id=? AND scope_key='legacy' AND kind='brief' AND revision=1
            """,
            (project_id,),
        ).fetchone()
        if existing is not None:
            if existing["body_sha256"] == body_sha256:
                _count(report, "project_documents", "skipped")
            else:
                _count(report, "project_documents", "conflicts")
                _queue(
                    connection,
                    report,
                    gap_key=f"project:document_conflict:{project_id}",
                    domain="project",
                    rule_code="project_document_revision_conflict",
                    severity="blocked",
                    project_id=project_id,
                    entity_table="project_document_revision",
                    entity_id=existing["id"],
                    evidence={
                        "existing_sha256": existing["body_sha256"],
                        "candidate_sha256": body_sha256,
                    },
                )
            continue
        provenance = {
            "backfill": BACKFILL_VERSION,
            "source": "legacy_project_row",
            "source_table": "project",
            "source_id": project_id,
        }
        connection.execute(
            """
            INSERT INTO project_document_revision(
              project_id, act_id, scope_key, kind, revision, schema_version,
              body_json, body_sha256, lifecycle, provenance_json
            ) VALUES (?, NULL, 'legacy', 'brief', 1, ?, ?, ?, 'draft', ?)
            """,
            (
                project_id,
                LEGACY_PROJECT_SCHEMA,
                body_json,
                body_sha256,
                _canonical_json(provenance),
            ),
        )
        _count(report, "project_documents", "inserted")


def _backfill_identities(
    connection: sqlite3.Connection, report: dict, project_ids: Sequence[int] | None
) -> None:
    where, params = _project_filter(project_ids)
    rows = connection.execute(
        "SELECT id, project_id, code, identity_json FROM character_profile"
        + where
        + " ORDER BY id",
        params,
    ).fetchall()
    report["source_counts"]["characters"] = len(rows)
    for row in rows:
        character_id = row["id"]
        identity, state = _parse_object(row["identity_json"])
        if identity is None:
            _count(report, "identities", "invalid")
            _queue(
                connection,
                report,
                gap_key=f"identity:invalid_json:{character_id}",
                domain="identity",
                rule_code=f"identity_{state}",
                severity="blocked",
                project_id=row["project_id"],
                character_id=character_id,
                entity_table="character_profile",
                entity_id=character_id,
                evidence={"source_column": "identity_json", "state": state},
            )
            continue
        identity_json = _canonical_json(identity)
        sha256 = _sha256_text(identity_json)
        existing = connection.execute(
            "SELECT id, sha256 FROM character_identity_revision WHERE character_id=? AND revision=1",
            (character_id,),
        ).fetchone()
        if existing is not None:
            if existing["sha256"] == sha256:
                _count(report, "identities", "skipped")
            else:
                _count(report, "identities", "conflicts")
                _queue(
                    connection,
                    report,
                    gap_key=f"identity:revision_conflict:{character_id}",
                    domain="identity",
                    rule_code="identity_revision_conflict",
                    severity="blocked",
                    project_id=row["project_id"],
                    character_id=character_id,
                    entity_table="character_identity_revision",
                    entity_id=existing["id"],
                    evidence={"existing_sha256": existing["sha256"], "candidate_sha256": sha256},
                )
            continue
        connection.execute(
            """
            INSERT INTO character_identity_revision(
              character_id, revision, identity_json, reference_asset_id, sha256, status
            ) VALUES (?, 1, ?, NULL, ?, 'draft')
            """,
            (character_id, identity_json, sha256),
        )
        _count(report, "identities", "inserted")


def _outfit_specs(
    connection: sqlite3.Connection,
    report: dict,
    *,
    character_id: int,
    project_id: int,
    outfit: dict,
) -> list[tuple[str, list[Any]]]:
    """Return deterministic (legacy_key, item list) pairs.

    ``source``/``assumed`` are metadata.  A ``variants`` list contains identity
    variant names, not outfit tags.  A ``variants`` dict contains named outfits.
    """
    specs: list[tuple[str, list[Any]]] = []
    top_keys = [
        key
        for key in outfit
        if key not in OUTFIT_METADATA_KEYS and key != "variants"
    ]
    ordered: list[str] = []
    for preferred in ("default", "nude"):
        if preferred in top_keys:
            ordered.append(preferred)
    ordered.extend(sorted(key for key in top_keys if key not in ordered))
    for key in ordered:
        value = outfit[key]
        if isinstance(value, list):
            specs.append((str(key), value))
        else:
            _queue(
                connection,
                report,
                gap_key=f"outfit:unsupported_key:{character_id}:{_short_hash(str(key))}",
                domain="outfit",
                rule_code="outfit_key_unsupported",
                project_id=project_id,
                character_id=character_id,
                entity_table="character_profile",
                entity_id=character_id,
                evidence={
                    "legacy_key": str(key),
                    "value_type": type(value).__name__,
                },
            )
    variants = outfit.get("variants")
    if isinstance(variants, dict):
        for subkey in sorted(variants):
            value = variants[subkey]
            legacy_key = f"variants.{subkey}"
            if isinstance(value, list):
                specs.append((legacy_key, value))
            else:
                _queue(
                    connection,
                    report,
                    gap_key=f"outfit:unsupported_variant:{character_id}:{_short_hash(legacy_key)}",
                    domain="outfit",
                    rule_code="outfit_variant_unsupported",
                    project_id=project_id,
                    character_id=character_id,
                    entity_table="character_profile",
                    entity_id=character_id,
                    evidence={
                        "legacy_key": legacy_key,
                        "value_type": type(value).__name__,
                    },
                )
    elif isinstance(variants, list):
        # This is a list of Danbooru identity variant names (e.g. swimsuit
        # costumes), not a complete outfit item list.
        _count(report, "outfits", "variant_name_lists")
    elif variants is not None:
        _queue(
            connection,
            report,
            gap_key=f"outfit:variants_unsupported:{character_id}",
            domain="outfit",
            rule_code="outfit_variants_unsupported",
            project_id=project_id,
            character_id=character_id,
            entity_table="character_profile",
            entity_id=character_id,
            evidence={"value_type": type(variants).__name__},
        )
    return specs


def _parse_legacy_tag(raw: str) -> tuple[str, int | None]:
    if ":" not in raw:
        return raw.strip(), None
    name, tail = raw.rsplit(":", 1)
    if tail.isdigit():
        return name.strip(), int(tail)
    return raw.strip(), None


def _tag_exists(connection: sqlite3.Connection, tag_id: int, cache: dict[int, bool]) -> bool:
    known = cache.get(tag_id)
    if known is None:
        known = connection.execute("SELECT 1 FROM tag WHERE id=?", (tag_id,)).fetchone() is not None
        cache[tag_id] = known
    return known


def _parse_outfit_items(
    connection: sqlite3.Connection,
    report: dict,
    *,
    character_id: int,
    project_id: int,
    legacy_key: str,
    values: list[Any],
    tag_cache: dict[int, bool],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    for index, raw in enumerate(values):
        if not isinstance(raw, str) or not raw.strip():
            _queue(
                connection,
                report,
                gap_key=(
                    f"outfit:item_invalid:{character_id}:{_short_hash(legacy_key)}:"
                    f"{_short_hash(repr(raw))}"
                ),
                domain="outfit",
                rule_code="outfit_item_invalid",
                project_id=project_id,
                character_id=character_id,
                entity_table="character_profile",
                entity_id=character_id,
                evidence={"legacy_key": legacy_key, "index": index},
            )
            continue
        raw = raw.strip()
        name, tag_id = _parse_legacy_tag(raw)
        if not name:
            _queue(
                connection,
                report,
                gap_key=(
                    f"outfit:item_empty_name:{character_id}:{_short_hash(legacy_key)}:"
                    f"{_short_hash(raw)}"
                ),
                domain="outfit",
                rule_code="outfit_item_empty_name",
                project_id=project_id,
                character_id=character_id,
                entity_table="character_profile",
                entity_id=character_id,
                evidence={"legacy_key": legacy_key, "raw": raw},
            )
            continue
        dedupe_key = (name, tag_id, raw)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        if tag_id is None:
            _queue(
                connection,
                report,
                gap_key=(
                    f"outfit:item_tag_missing:{character_id}:{_short_hash(legacy_key)}:"
                    f"{_short_hash(raw)}"
                ),
                domain="outfit",
                rule_code="outfit_item_tag_missing",
                project_id=project_id,
                character_id=character_id,
                entity_table="character_profile",
                entity_id=character_id,
                evidence={"legacy_key": legacy_key, "raw": raw},
            )
            tag_known = False
        else:
            tag_known = _tag_exists(connection, tag_id, tag_cache)
            if not tag_known:
                _queue(
                    connection,
                    report,
                    gap_key=f"catalog:tag_unknown:{tag_id}",
                    domain="catalog",
                    rule_code="outfit_item_tag_unknown",
                    project_id=project_id,
                    character_id=character_id,
                    entity_table="character_profile",
                    entity_id=character_id,
                    evidence={
                        "tag_id": tag_id,
                        "legacy_key": legacy_key,
                        "raw": raw,
                    },
                )
        items.append(
            {
                "name": name,
                "tag_id": tag_id,
                "tag_known": tag_known,
                "raw": raw,
                "legacy_index": index,
            }
        )
    return items


def _backfill_outfits(
    connection: sqlite3.Connection, report: dict, project_ids: Sequence[int] | None
) -> None:
    where, params = _project_filter(project_ids)
    rows = connection.execute(
        "SELECT id, project_id, code, outfit_json FROM character_profile"
        + where
        + " ORDER BY id",
        params,
    ).fetchall()
    tag_cache: dict[int, bool] = {}
    for row in rows:
        character_id = row["id"]
        project_id = row["project_id"]
        outfit, state = _parse_object(row["outfit_json"])
        if outfit is None:
            _queue(
                connection,
                report,
                gap_key=f"outfit:invalid_json:{character_id}",
                domain="outfit",
                rule_code=f"outfit_{state}",
                severity="blocked",
                project_id=project_id,
                character_id=character_id,
                entity_table="character_profile",
                entity_id=character_id,
                evidence={"source_column": "outfit_json", "state": state},
            )
            continue
        specs = _outfit_specs(
            connection,
            report,
            character_id=character_id,
            project_id=project_id,
            outfit=outfit,
        )
        for revision, (legacy_key, values) in enumerate(specs, start=1):
            items = _parse_outfit_items(
                connection,
                report,
                character_id=character_id,
                project_id=project_id,
                legacy_key=legacy_key,
                values=values,
                tag_cache=tag_cache,
            )
            spec = {
                "schema_version": LEGACY_OUTFIT_SCHEMA,
                "legacy_key": legacy_key,
                "items": [
                    {
                        "name": item["name"],
                        "tag_id": item["tag_id"],
                        "tag_known": item["tag_known"],
                        "raw": item["raw"],
                        "legacy_index": item["legacy_index"],
                    }
                    for item in items
                ],
            }
            spec_json = _canonical_json(spec)
            spec_sha256 = _sha256_text(spec_json)
            existing = connection.execute(
                """
                SELECT id, spec_sha256 FROM outfit_revision
                WHERE character_id=? AND revision=?
                """,
                (character_id, revision),
            ).fetchone()
            if existing is not None:
                if existing["spec_sha256"] == spec_sha256:
                    _count(report, "outfits", "revisions_skipped")
                    _count(report, "outfits", "items_skipped", len(items))
                else:
                    _count(report, "outfits", "revisions_conflicts")
                    _queue(
                        connection,
                        report,
                        gap_key=f"outfit:revision_conflict:{character_id}:{revision}",
                        domain="outfit",
                        rule_code="outfit_revision_conflict",
                        severity="blocked",
                        project_id=project_id,
                        character_id=character_id,
                        entity_table="outfit_revision",
                        entity_id=existing["id"],
                        evidence={
                            "revision": revision,
                            "legacy_key": legacy_key,
                            "existing_sha256": existing["spec_sha256"],
                            "candidate_sha256": spec_sha256,
                        },
                    )
                continue
            cursor = connection.execute(
                """
                INSERT INTO outfit_revision(
                  character_id, revision, spec_json, anchor_asset_id, status, spec_sha256
                ) VALUES (?, ?, ?, NULL, 'draft', ?)
                """,
                (character_id, revision, spec_json, spec_sha256),
            )
            outfit_revision_id = int(cursor.lastrowid)
            _count(report, "outfits", "revisions_inserted")
            used_codes: set[str] = set()
            for index, item in enumerate(items):
                item_code = item["name"]
                if item_code in used_codes:
                    suffix = item["tag_id"] if item["tag_id"] is not None else index + 1
                    item_code = f"{item_code}#{suffix}"
                base_code = item_code
                suffix_no = 2
                while item_code in used_codes:
                    item_code = f"{base_code}#{suffix_no}"
                    suffix_no += 1
                used_codes.add(item_code)
                details = {
                    "legacy_key": legacy_key,
                    "raw": item["raw"],
                    "tag_id": item["tag_id"],
                    "tag_known": item["tag_known"],
                    "legacy_index": item["legacy_index"],
                }
                item_cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO outfit_item(
                      outfit_revision_id, item_code, slot, garment_type,
                      details_json
                    ) VALUES (?, ?, 'unknown', 'legacy_tag', ?)
                    """,
                    (outfit_revision_id, item_code, _canonical_json(details)),
                )
                if item_cursor.rowcount:
                    _count(report, "outfits", "items_inserted")
                else:
                    _count(report, "outfits", "items_skipped")


def _backfill_shot_specs(
    connection: sqlite3.Connection, report: dict, project_ids: Sequence[int] | None
) -> None:
    where, params = _project_filter(project_ids)
    sql = (
        "SELECT s.id, s.act_id, s.shot_spec_json FROM shot s "
        "JOIN act a ON a.id=s.act_id"
        + (where.replace("project_id", "a.project_id") if where else "")
        + " ORDER BY s.id"
    )
    rows = connection.execute(sql, params).fetchall()
    report["source_counts"]["shots"] = len(rows)
    for row in rows:
        shot_id = row["id"]
        spec, state = _parse_object(row["shot_spec_json"])
        if spec is None:
            _count(report, "shot_specs", "invalid")
            _queue(
                connection,
                report,
                gap_key=f"shot:spec_{state}:{shot_id}",
                domain="shot",
                rule_code=f"shot_spec_{state}",
                severity="blocked",
                act_id=row["act_id"],
                shot_id=shot_id,
                entity_table="shot",
                entity_id=shot_id,
                evidence={"source_column": "shot_spec_json", "state": state},
            )
            continue
        spec_json = _canonical_json(spec)
        spec_sha256 = _sha256_text(spec_json)
        existing = connection.execute(
            "SELECT id, spec_sha256 FROM shot_spec_revision WHERE shot_id=? AND revision=1",
            (shot_id,),
        ).fetchone()
        if existing is not None:
            if existing["spec_sha256"] == spec_sha256:
                _count(report, "shot_specs", "skipped")
            else:
                _count(report, "shot_specs", "conflicts")
                _queue(
                    connection,
                    report,
                    gap_key=f"shot:spec_revision_conflict:{shot_id}",
                    domain="shot",
                    rule_code="shot_spec_revision_conflict",
                    severity="blocked",
                    act_id=row["act_id"],
                    shot_id=shot_id,
                    entity_table="shot_spec_revision",
                    entity_id=existing["id"],
                    evidence={
                        "existing_sha256": existing["spec_sha256"],
                        "candidate_sha256": spec_sha256,
                    },
                )
            continue
        connection.execute(
            """
            INSERT INTO shot_spec_revision(
              shot_id, revision, source_document_revision_id, spec_json,
              spec_sha256, status
            ) VALUES (?, 1, NULL, ?, ?, 'draft')
            """,
            (shot_id, spec_json, spec_sha256),
        )
        _count(report, "shot_specs", "inserted")


def _character_indexes(connection: sqlite3.Connection) -> tuple[dict, dict]:
    by_id: dict[int, sqlite3.Row] = {}
    by_project_code: dict[tuple[int, str], list[int]] = defaultdict(list)
    for row in connection.execute("SELECT id, project_id, code FROM character_profile"):
        by_id[row["id"]] = row
        by_project_code[(row["project_id"], row["code"])].append(row["id"])
    return by_id, by_project_code


def _role_to_scene_role(
    connection: sqlite3.Connection,
    report: dict,
    *,
    shot_id: int,
    character_id: int,
    role: Any,
    source: str,
) -> str:
    if role is None:
        _queue(
            connection,
            report,
            gap_key=f"participant:role_missing:{shot_id}:{character_id}",
            domain="participant",
            rule_code="participant_role_missing",
            shot_id=shot_id,
            character_id=character_id,
            evidence={"source": source},
        )
        return "subject"
    normalized = str(role).strip().lower()
    if normalized not in ROLE_MAP:
        _queue(
            connection,
            report,
            gap_key=f"participant:role_unknown:{shot_id}:{character_id}",
            domain="participant",
            rule_code="participant_role_unknown",
            shot_id=shot_id,
            character_id=character_id,
            evidence={"source": source, "role": str(role)},
        )
        return "subject"
    return ROLE_MAP[normalized]


def _participant_candidates(
    connection: sqlite3.Connection,
    report: dict,
    *,
    shot: sqlite3.Row,
    spec: dict,
    project_id: int,
    by_id: dict,
    by_project_code: dict,
) -> list[tuple[int, str, str, str]]:
    """Return explicit participant candidates in stable slot order.

    ``shot.character_id`` is the legacy primary character and is always slot 1.
    Additional participants come only from explicit ``participants[].code``.
    """
    shot_id = shot["id"]
    candidates: list[tuple[int, str, str, str]] = []
    seen_ids: set[int] = set()
    seen_codes: set[str] = set()

    shot_character_id = shot["character_id"]
    primary_is_valid = False
    primary_seen_in_spec = False
    if shot_character_id is None:
        _queue(
            connection,
            report,
            gap_key=f"participant:shot_character_missing:{shot_id}",
            domain="participant",
            rule_code="participant_shot_character_missing",
            project_id=project_id,
            shot_id=shot_id,
            evidence={"source_column": "shot.character_id"},
        )
    if shot_character_id is not None:
        character = by_id.get(shot_character_id)
        if character is None:
            _queue(
                connection,
                report,
                gap_key=f"participant:shot_character_unknown:{shot_id}",
                domain="participant",
                rule_code="participant_shot_character_unknown",
                severity="blocked",
                project_id=project_id,
                shot_id=shot_id,
                evidence={"shot_character_id": shot_character_id},
            )
        elif character["project_id"] != project_id:
            _queue(
                connection,
                report,
                gap_key=f"participant:shot_character_cross_project:{shot_id}",
                domain="participant",
                rule_code="participant_shot_character_cross_project",
                severity="blocked",
                project_id=project_id,
                shot_id=shot_id,
                character_id=shot_character_id,
                evidence={
                    "shot_character_id": shot_character_id,
                    "character_project_id": character["project_id"],
                    "shot_project_id": project_id,
                },
            )
        else:
            candidates.append((shot_character_id, "", "subject", "shot.character_id"))
            seen_ids.add(shot_character_id)
            primary_is_valid = True

    participants = spec.get("participants")
    participants_is_list = isinstance(participants, list)
    if not participants_is_list:
        _queue(
            connection,
            report,
            gap_key=f"participant:list_missing:{shot_id}",
            domain="participant",
            rule_code="participant_list_missing",
            severity="blocked",
            project_id=project_id,
            shot_id=shot_id,
            evidence={"source_field": "participants"},
        )
        participants = []

    for index, participant in enumerate(participants):
        if not isinstance(participant, dict):
            _queue(
                connection,
                report,
                gap_key=f"participant:entry_invalid:{shot_id}:{index}",
                domain="participant",
                rule_code="participant_entry_invalid",
                project_id=project_id,
                shot_id=shot_id,
                evidence={"index": index, "value_type": type(participant).__name__},
            )
            continue
        code = participant.get("code")
        if not isinstance(code, str) or not code.strip():
            _queue(
                connection,
                report,
                gap_key=f"participant:code_missing:{shot_id}:{index}",
                domain="participant",
                rule_code="participant_code_missing",
                project_id=project_id,
                shot_id=shot_id,
                evidence={"index": index},
            )
            continue
        code = code.strip()
        if code in seen_codes:
            _queue(
                connection,
                report,
                gap_key=f"participant:duplicate_code:{shot_id}:{code}",
                domain="participant",
                rule_code="participant_duplicate_code",
                project_id=project_id,
                shot_id=shot_id,
                evidence={"code": code, "index": index},
            )
            continue
        seen_codes.add(code)
        matches = by_project_code.get((project_id, code), [])
        if not matches:
            _queue(
                connection,
                report,
                gap_key=f"participant:unknown_code:{shot_id}:{code}",
                domain="participant",
                rule_code="participant_unknown_code",
                severity="blocked",
                project_id=project_id,
                shot_id=shot_id,
                evidence={"code": code, "index": index},
            )
            continue
        if len(matches) > 1:
            _queue(
                connection,
                report,
                gap_key=f"participant:ambiguous_code:{shot_id}:{code}",
                domain="participant",
                rule_code="participant_ambiguous_code",
                severity="blocked",
                project_id=project_id,
                shot_id=shot_id,
                evidence={"code": code, "matches": matches, "index": index},
            )
            continue
        character_id = matches[0]
        if character_id in seen_ids:
            # The legacy primary character is normally repeated in
            # participants[] as well as shot.character_id.  That is not an
            # ambiguity: the primary was already placed in slot 1.
            if character_id == shot_character_id:
                primary_seen_in_spec = True
                continue
            _queue(
                connection,
                report,
                gap_key=f"participant:duplicate_character:{shot_id}:{character_id}",
                domain="participant",
                rule_code="participant_duplicate_character",
                project_id=project_id,
                shot_id=shot_id,
                character_id=character_id,
                evidence={"code": code, "index": index},
            )
            continue
        seen_ids.add(character_id)
        candidates.append(
            (
                character_id,
                code,
                _role_to_scene_role(
                    connection,
                    report,
                    shot_id=shot_id,
                    character_id=character_id,
                    role=participant.get("role"),
                    source=f"participants[{index}]",
                ),
                f"participants[{index}]",
            )
        )

    if primary_is_valid and participants_is_list and participants and not primary_seen_in_spec:
        _queue(
            connection,
            report,
            gap_key=f"participant:shot_character_not_in_spec:{shot_id}",
            domain="participant",
            rule_code="participant_shot_character_not_in_spec",
            project_id=project_id,
            shot_id=shot_id,
            character_id=shot_character_id,
            evidence={
                "shot_character_id": shot_character_id,
                "participant_codes": [
                    item.get("code")
                    for item in participants
                    if isinstance(item, dict)
                ],
            },
        )

    if not candidates:
        _queue(
            connection,
            report,
            gap_key=f"participant:none:{shot_id}",
            domain="participant",
            rule_code="participant_none",
            severity="blocked",
            project_id=project_id,
            shot_id=shot_id,
            evidence={"shot_character_id": shot_character_id},
        )
    elif len(candidates) > MAX_PARTICIPANTS:
        _queue(
            connection,
            report,
            gap_key=f"participant:too_many:{shot_id}",
            domain="participant",
            rule_code="participant_too_many",
            severity="blocked",
            project_id=project_id,
            shot_id=shot_id,
            evidence={
                "candidate_count": len(candidates),
                "max_participants": MAX_PARTICIPANTS,
            },
        )
        candidates = candidates[:MAX_PARTICIPANTS]
    return candidates


def _backfill_participants(
    connection: sqlite3.Connection, report: dict, project_ids: Sequence[int] | None
) -> None:
    by_id, by_project_code = _character_indexes(connection)
    where, params = _project_filter(project_ids)
    sql = (
        "SELECT s.id, s.act_id, s.character_id, s.shot_spec_json, a.project_id "
        "FROM shot s JOIN act a ON a.id=s.act_id"
        + (where.replace("project_id", "a.project_id") if where else "")
        + " ORDER BY s.id"
    )
    rows = connection.execute(sql, params).fetchall()
    for shot in rows:
        shot_id = shot["id"]
        project_id = shot["project_id"]
        spec, state = _parse_object(shot["shot_spec_json"])
        if spec is None:
            # Already queued by the shot-spec pass; no participants can be
            # derived from a non-object spec.
            _count(report, "participants", "conflicts")
            continue
        _count(report, "participants", "shots")
        candidates = _participant_candidates(
            connection,
            report,
            shot=shot,
            spec=spec,
            project_id=project_id,
            by_id=by_id,
            by_project_code=by_project_code,
        )
        for slot_no, (character_id, _code, scene_role, source) in enumerate(candidates, start=1):
            existing = connection.execute(
                "SELECT slot_no, scene_role FROM shot_participant WHERE shot_id=? AND character_id=?",
                (shot_id, character_id),
            ).fetchone()
            if existing is not None:
                if existing["slot_no"] == slot_no and existing["scene_role"] == scene_role:
                    _count(report, "participants", "skipped")
                else:
                    _count(report, "participants", "conflicts")
                    _queue(
                        connection,
                        report,
                        gap_key=f"participant:row_conflict:{shot_id}:{character_id}",
                        domain="participant",
                        rule_code="participant_row_conflict",
                        severity="blocked",
                        project_id=project_id,
                        shot_id=shot_id,
                        character_id=character_id,
                        entity_table="shot_participant",
                        entity_id=shot_id,
                        evidence={
                            "existing_slot_no": existing["slot_no"],
                            "existing_scene_role": existing["scene_role"],
                            "candidate_slot_no": slot_no,
                            "candidate_scene_role": scene_role,
                        },
                    )
                continue
            slot_owner = connection.execute(
                "SELECT character_id FROM shot_participant WHERE shot_id=? AND slot_no=?",
                (shot_id, slot_no),
            ).fetchone()
            if slot_owner is not None:
                _count(report, "participants", "conflicts")
                _queue(
                    connection,
                    report,
                    gap_key=f"participant:slot_conflict:{shot_id}:{slot_no}",
                    domain="participant",
                    rule_code="participant_slot_conflict",
                    severity="blocked",
                    project_id=project_id,
                    shot_id=shot_id,
                    character_id=character_id,
                    evidence={
                        "slot_no": slot_no,
                        "owner_character_id": slot_owner["character_id"],
                        "source": source,
                    },
                )
                continue
            try:
                connection.execute(
                    """
                    INSERT INTO shot_participant(shot_id, character_id, slot_no, scene_role)
                    VALUES (?, ?, ?, ?)
                    """,
                    (shot_id, character_id, slot_no, scene_role),
                )
            except sqlite3.IntegrityError as exc:
                _count(report, "participants", "conflicts")
                _queue(
                    connection,
                    report,
                    gap_key=f"participant:insert_failed:{shot_id}:{character_id}",
                    domain="participant",
                    rule_code="participant_insert_failed",
                    severity="blocked",
                    project_id=project_id,
                    shot_id=shot_id,
                    character_id=character_id,
                    evidence={"source": source, "error": str(exc)},
                )
                continue
            _count(report, "participants", "inserted")


def _explicit_interaction(spec: dict) -> tuple[dict | None, dict | None]:
    def valid_interaction(value: Any) -> dict | None:
        if not isinstance(value, dict):
            return None
        actor = value.get("actor")
        target = value.get("target")
        action = value.get("action")
        if all(isinstance(item, str) and item.strip() for item in (actor, target, action)):
            return {
                "actor": actor.strip(),
                "target": target.strip(),
                "action": action.strip(),
                "source": "interaction",
            }
        return None

    def valid_sequence(value: Any) -> dict | None:
        if not isinstance(value, dict):
            return None
        actor = value.get("actor")
        target = value.get("target")
        action = value.get("primaryAction")
        if all(isinstance(item, str) and item.strip() for item in (actor, target, action)):
            return {
                "actor": actor.strip(),
                "target": target.strip(),
                "action": action.strip(),
                "source": "sequence",
            }
        return None

    return valid_interaction(spec.get("interaction")), valid_sequence(spec.get("sequence"))


def _backfill_interactions(
    connection: sqlite3.Connection, report: dict, project_ids: Sequence[int] | None
) -> None:
    participants_by_shot: dict[int, set[int]] = defaultdict(set)
    for row in connection.execute("SELECT shot_id, character_id FROM shot_participant"):
        participants_by_shot[row["shot_id"]].add(row["character_id"])
    _by_id, by_project_code = _character_indexes(connection)
    where, params = _project_filter(project_ids)
    sql = (
        "SELECT s.id, s.act_id, s.shot_spec_json, a.project_id "
        "FROM shot s JOIN act a ON a.id=s.act_id"
        + (where.replace("project_id", "a.project_id") if where else "")
        + " ORDER BY s.id"
    )
    for row in connection.execute(sql, params):
        shot_id = row["id"]
        project_id = row["project_id"]
        spec, state = _parse_object(row["shot_spec_json"])
        if spec is None:
            continue
        participant_ids = participants_by_shot.get(shot_id, set())
        explicit, sequence = _explicit_interaction(spec)
        if explicit is not None and sequence is not None:
            if (
                explicit["actor"],
                explicit["target"],
                explicit["action"],
            ) != (
                sequence["actor"],
                sequence["target"],
                sequence["action"],
            ):
                _queue(
                    connection,
                    report,
                    gap_key=f"interaction:source_conflict:{shot_id}",
                    domain="interaction",
                    rule_code="interaction_source_conflict",
                    severity="blocked",
                    project_id=project_id,
                    act_id=row["act_id"],
                    shot_id=shot_id,
                    evidence={"interaction": explicit, "sequence": sequence},
                )
                continue
            source = explicit
        else:
            source = explicit or sequence
        if source is None:
            if len(participant_ids) >= 2:
                _queue(
                    connection,
                    report,
                    gap_key=f"interaction:actor_target_missing:{shot_id}",
                    domain="interaction",
                    rule_code="interaction_actor_target_missing",
                    severity="blocked",
                    project_id=project_id,
                    act_id=row["act_id"],
                    shot_id=shot_id,
                    evidence={
                        "participant_ids": sorted(participant_ids),
                        "interaction": spec.get("interaction"),
                        "sequence": spec.get("sequence"),
                    },
                )
            continue
        actor_matches = by_project_code.get((project_id, source["actor"]), [])
        target_matches = by_project_code.get((project_id, source["target"]), [])
        if len(actor_matches) != 1:
            _queue(
                connection,
                report,
                gap_key=f"interaction:actor_unmapped:{shot_id}",
                domain="interaction",
                rule_code="interaction_actor_unmapped",
                severity="blocked",
                project_id=project_id,
                act_id=row["act_id"],
                shot_id=shot_id,
                evidence={"actor": source["actor"], "matches": actor_matches},
            )
            continue
        if len(target_matches) != 1:
            _queue(
                connection,
                report,
                gap_key=f"interaction:target_unmapped:{shot_id}",
                domain="interaction",
                rule_code="interaction_target_unmapped",
                severity="blocked",
                project_id=project_id,
                act_id=row["act_id"],
                shot_id=shot_id,
                evidence={"target": source["target"], "matches": target_matches},
            )
            continue
        actor_id = actor_matches[0]
        target_id = target_matches[0]
        if actor_id == target_id:
            _queue(
                connection,
                report,
                gap_key=f"interaction:actor_equals_target:{shot_id}",
                domain="interaction",
                rule_code="interaction_actor_equals_target",
                severity="blocked",
                project_id=project_id,
                act_id=row["act_id"],
                shot_id=shot_id,
                character_id=actor_id,
                evidence={"actor": source["actor"], "target": source["target"]},
            )
            continue
        if actor_id not in participant_ids or target_id not in participant_ids:
            _queue(
                connection,
                report,
                gap_key=f"interaction:not_participants:{shot_id}",
                domain="interaction",
                rule_code="interaction_actor_target_not_participants",
                severity="blocked",
                project_id=project_id,
                act_id=row["act_id"],
                shot_id=shot_id,
                evidence={
                    "actor_id": actor_id,
                    "target_id": target_id,
                    "participant_ids": sorted(participant_ids),
                },
            )
            continue
        existing = connection.execute(
            """
            SELECT id, actor_character_id, target_character_id, action_code
            FROM shot_interaction WHERE shot_id=? AND sort_order=1
            """,
            (shot_id,),
        ).fetchone()
        if existing is not None:
            if (
                existing["actor_character_id"] == actor_id
                and existing["target_character_id"] == target_id
                and existing["action_code"] == source["action"]
            ):
                _count(report, "interactions", "skipped")
            else:
                _count(report, "interactions", "conflicts")
                _queue(
                    connection,
                    report,
                    gap_key=f"interaction:row_conflict:{shot_id}",
                    domain="interaction",
                    rule_code="interaction_row_conflict",
                    severity="blocked",
                    project_id=project_id,
                    act_id=row["act_id"],
                    shot_id=shot_id,
                    entity_table="shot_interaction",
                    entity_id=existing["id"],
                    evidence={
                        "existing_actor_character_id": existing["actor_character_id"],
                        "existing_target_character_id": existing["target_character_id"],
                        "existing_action_code": existing["action_code"],
                        "candidate_actor_character_id": actor_id,
                        "candidate_target_character_id": target_id,
                        "candidate_action_code": source["action"],
                    },
                )
            continue
        connection.execute(
            """
            INSERT INTO shot_interaction(
              shot_id, actor_character_id, target_character_id, action_code,
              action_concept_id, body_target, instruction, sort_order
            ) VALUES (?, ?, ?, ?, NULL, NULL, ?, 1)
            """,
            (
                shot_id,
                actor_id,
                target_id,
                source["action"],
                f"legacy:{source['source']}",
            ),
        )
        _count(report, "interactions", "inserted")
        _inc(report["interactions_by_source"], source["source"])


def _outfit_index(connection: sqlite3.Connection) -> dict[int, list[dict[str, Any]]]:
    index: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in connection.execute(
        "SELECT id, character_id, revision, spec_json FROM outfit_revision ORDER BY character_id, revision"
    ):
        spec, _state = _parse_object(row["spec_json"])
        tag_ids: set[int] = set()
        legacy_key = ""
        complete = False
        if spec is not None:
            legacy_key = str(spec.get("legacy_key", ""))
            items = spec.get("items") if isinstance(spec.get("items"), list) else []
            complete = all(
                isinstance(item, dict) and isinstance(item.get("tag_id"), int)
                for item in items
            )
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("tag_id"), int):
                    tag_ids.add(item["tag_id"])
        index[row["character_id"]].append(
            {
                "id": row["id"],
                "revision": row["revision"],
                "legacy_key": legacy_key,
                "tag_ids": frozenset(tag_ids),
                "complete": complete,
            }
        )
    return index


def _shot_outfit_tags(spec: dict) -> set[int]:
    tags: set[int] = set()
    outfit = spec.get("outfit")
    if isinstance(outfit, list):
        for item in outfit:
            if isinstance(item, dict) and isinstance(item.get("tagId"), int):
                tags.add(item["tagId"])
    return tags


def _backfill_outfit_bindings(
    connection: sqlite3.Connection, report: dict, project_ids: Sequence[int] | None
) -> None:
    outfit_index = _outfit_index(connection)
    where, params = _project_filter(project_ids)
    sql = (
        "SELECT sp.shot_id, sp.character_id, s.shot_spec_json, a.project_id "
        "FROM shot_participant sp "
        "JOIN shot s ON s.id=sp.shot_id "
        "JOIN act a ON a.id=s.act_id"
        + (where.replace("project_id", "a.project_id") if where else "")
        + " ORDER BY sp.shot_id, sp.slot_no"
    )
    for row in connection.execute(sql, params):
        shot_id = row["shot_id"]
        character_id = row["character_id"]
        project_id = row["project_id"]
        spec, state = _parse_object(row["shot_spec_json"])
        if spec is None:
            continue
        tags = _shot_outfit_tags(spec)
        candidates = outfit_index.get(character_id, [])
        if not tags:
            _count(report, "outfit_bindings", "missing")
            _queue(
                connection,
                report,
                gap_key=f"outfit:binding_missing:{shot_id}:{character_id}",
                domain="outfit",
                rule_code="outfit_binding_missing",
                project_id=project_id,
                shot_id=shot_id,
                character_id=character_id,
                evidence={
                    "reason": "shot_spec has no outfit tag items",
                    "character_revision_keys": [item["legacy_key"] for item in candidates],
                },
            )
            continue
        matches = [
            item
            for item in candidates
            if item["complete"] and item["tag_ids"] and item["tag_ids"] == tags
        ]
        if not matches:
            _count(report, "outfit_bindings", "unmatched")
            _queue(
                connection,
                report,
                gap_key=f"outfit:binding_unmatched:{shot_id}:{character_id}",
                domain="outfit",
                rule_code="outfit_binding_unmatched",
                severity="blocked",
                project_id=project_id,
                shot_id=shot_id,
                character_id=character_id,
                evidence={
                    "shot_outfit_tag_ids": sorted(tags),
                    "candidate_count": len(candidates),
                    "incomplete_candidate_count": sum(
                        1 for item in candidates if not item["complete"]
                    ),
                    "candidate_keys": [item["legacy_key"] for item in candidates],
                    "candidate_tag_sets": [sorted(item["tag_ids"]) for item in candidates],
                },
            )
            continue
        if len(matches) > 1:
            _count(report, "outfit_bindings", "ambiguous")
            _queue(
                connection,
                report,
                gap_key=f"outfit:binding_ambiguous:{shot_id}:{character_id}",
                domain="outfit",
                rule_code="outfit_binding_ambiguous",
                severity="blocked",
                project_id=project_id,
                shot_id=shot_id,
                character_id=character_id,
                evidence={
                    "shot_outfit_tag_ids": sorted(tags),
                    "matching_revision_ids": [item["id"] for item in matches],
                    "matching_keys": [item["legacy_key"] for item in matches],
                },
            )
            continue
        match = matches[0]
        existing = connection.execute(
            "SELECT outfit_revision_id FROM shot_outfit_binding WHERE shot_id=? AND character_id=?",
            (shot_id, character_id),
        ).fetchone()
        if existing is not None:
            if existing["outfit_revision_id"] == match["id"]:
                _count(report, "outfit_bindings", "skipped")
            else:
                _count(report, "outfit_bindings", "conflicts")
                _queue(
                    connection,
                    report,
                    gap_key=f"outfit:binding_conflict:{shot_id}:{character_id}",
                    domain="outfit",
                    rule_code="outfit_binding_conflict",
                    severity="blocked",
                    project_id=project_id,
                    shot_id=shot_id,
                    character_id=character_id,
                    entity_table="shot_outfit_binding",
                    entity_id=shot_id,
                    evidence={
                        "existing_outfit_revision_id": existing["outfit_revision_id"],
                        "candidate_outfit_revision_id": match["id"],
                    },
                )
            continue
        connection.execute(
            """
            INSERT INTO shot_outfit_binding(shot_id, character_id, outfit_revision_id)
            VALUES (?, ?, ?)
            """,
            (shot_id, character_id, match["id"]),
        )
        _count(report, "outfit_bindings", "inserted")


def run_backfill(
    db_path: Path | str,
    *,
    dry_run: bool = False,
    project_ids: Sequence[int] | None = None,
    allow_live: bool = False,
) -> dict:
    """Run the deterministic backfill in one transaction and return a report."""
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise BackfillError(f"database not found: {db_path}")
    if is_live_database(db_path) and not allow_live:
        raise BackfillError(
            "refusing to backfill the live database; use a staging copy "
            "(pass --allow-live only after an approved cutover plan)"
        )
    selected_project_ids = sorted({int(item) for item in project_ids}) if project_ids else None
    report = _new_report(db_path, dry_run, selected_project_ids)
    report["source_counts"] = {}
    report["interactions_by_source"] = {}
    connection = connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _assert_schema(connection)
        if selected_project_ids:
            placeholders = ",".join("?" for _ in selected_project_ids)
            found = connection.execute(
                f"SELECT count(*) FROM project WHERE id IN ({placeholders})",
                tuple(selected_project_ids),
            ).fetchone()[0]
            if found != len(selected_project_ids):
                raise BackfillError("one or more --project-id values do not exist")
        connection.execute("BEGIN IMMEDIATE")
        _backfill_project_documents(connection, report, selected_project_ids)
        _backfill_identities(connection, report, selected_project_ids)
        _backfill_outfits(connection, report, selected_project_ids)
        _backfill_shot_specs(connection, report, selected_project_ids)
        _backfill_participants(connection, report, selected_project_ids)
        _backfill_interactions(connection, report, selected_project_ids)
        _backfill_outfit_bindings(connection, report, selected_project_ids)
        report["checks"] = _database_checks(connection)
        if not report["checks"]["quick_check_ok"] or not report["checks"]["foreign_key_ok"]:
            raise BackfillError(
                "post-backfill checks failed: "
                f"{report['checks']['quick_check']} / "
                f"{report['checks']['foreign_key_violations_first_20']}"
            )
        if dry_run:
            connection.rollback()
            report["status"] = "dry_run"
        else:
            connection.commit()
            report["status"] = "ok"
        return report
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        report["finished_at_utc"] = _utc_now()


def _write_report(path: Path, report: dict) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Staging SQLite database (never the live DB)")
    parser.add_argument("--report", help="Write the JSON backfill report")
    parser.add_argument("--backup", help="Backup path created before a non-dry run")
    parser.add_argument("--no-backup", action="store_true", help="Skip the automatic pre-backfill backup")
    parser.add_argument("--dry-run", action="store_true", help="Run in a transaction and roll it back")
    parser.add_argument("--allow-live", action="store_true", help="Only for an approved cutover drill")
    parser.add_argument(
        "--project-id",
        action="append",
        type=int,
        dest="project_ids",
        help="Limit the backfill to a project id (repeatable)",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db).resolve()
    backup_path: Path | None = None
    if not args.dry_run and not args.no_backup:
        if args.backup:
            backup_path = Path(args.backup).resolve()
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = db_path.parent / f"pre_backfill_{stamp}.db"
    try:
        if backup_path is not None:
            backup_database(db_path, backup_path)
        report = run_backfill(
            db_path,
            dry_run=args.dry_run,
            project_ids=args.project_ids,
            allow_live=args.allow_live,
        )
        if backup_path is not None:
            report["backup"] = str(backup_path)
        if args.report:
            _write_report(Path(args.report), report)
    except Exception as exc:  # noqa: BLE001 - CLI must surface a stable failure
        failure = {
            "schema_version": "n2a-backfill-report/1",
            "backfill_version": BACKFILL_VERSION,
            "database": str(db_path),
            "dry_run": bool(args.dry_run),
            "status": "failed",
            "error": str(exc),
            "generated_at_utc": _utc_now(),
        }
        if args.report:
            _write_report(Path(args.report), failure)
        print(f"BACKFILL FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        "Backfill:",
        "status=",
        report["status"],
        "dry_run=",
        report["dry_run"],
        "projects=",
        report["source_counts"].get("projects", 0),
        "shots=",
        report["source_counts"].get("shots", 0),
    )
    for section in (
        "project_documents",
        "identities",
        "outfits",
        "shot_specs",
        "participants",
        "interactions",
        "outfit_bindings",
    ):
        print(section + ":", report["counts"][section])
    print(
        "Reconciliation:",
        "inserted=",
        report["reconciliation"]["inserted"],
        "existing=",
        report["reconciliation"]["existing"],
        "by_rule=",
        report["reconciliation"]["by_rule"],
    )
    if report.get("checks"):
        print(
            "Checks: quick_check=",
            report["checks"]["quick_check_ok"],
            "foreign_keys=",
            report["checks"]["foreign_key_ok"],
        )
    if report.get("backup"):
        print("Backup:", report["backup"])
    return 0 if report["status"] in {"ok", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
