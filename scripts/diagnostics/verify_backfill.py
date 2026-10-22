#!/usr/bin/env python3
"""Read-only verification of the PR-02 relational backfill.

Checks source/target counts, ID preservation, participant parity, explicit-only
interaction direction, exact outfit bindings and the reconciliation queue.
It never writes to the database.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_TABLES = {
    "project_document_revision",
    "character_identity_revision",
    "outfit_revision",
    "outfit_item",
    "shot_spec_revision",
    "shot_participant",
    "shot_interaction",
    "shot_outfit_binding",
    "reconciliation_item",
}


def load_json(raw):
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


def table_counts(connection):
    counts = {}
    for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        name = row[0]
        counts[name] = connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
    return counts


def build_report(db_path: Path) -> dict:
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        counts = table_counts(connection)
        missing_tables = sorted(EXPECTED_TABLES - set(counts))
        integrity = [row[0] for row in connection.execute("PRAGMA quick_check").fetchmany(21)]
        foreign_keys = [list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchmany(21)]
        migrations = [
            {"version": row["version"], "sha256": row["sha256"], "applied_at": row["applied_at"]}
            for row in connection.execute(
                "SELECT version, sha256, applied_at FROM n2a_schema_migration ORDER BY version"
            )
        ]

        project_ids = {
            row[0] for row in connection.execute("SELECT id FROM project")
        }
        document_ids = {
            row[0]
            for row in connection.execute(
                "SELECT project_id FROM project_document_revision "
                "WHERE scope_key='legacy' AND kind='brief' AND revision=1"
            )
        }
        character_ids = {
            row[0] for row in connection.execute("SELECT id FROM character_profile")
        }
        identity_ids = {
            row[0]
            for row in connection.execute(
                "SELECT character_id FROM character_identity_revision WHERE revision=1"
            )
        }
        shot_ids = {row[0] for row in connection.execute("SELECT id FROM shot")}
        spec_ids = {
            row[0]
            for row in connection.execute("SELECT shot_id FROM shot_spec_revision WHERE revision=1")
        }

        participant_bad = []
        missing_primary = []
        multi_participant = 0
        participant_total = 0
        for row in connection.execute(
            """
            SELECT s.id, s.character_id, s.shot_spec_json,
                   (SELECT count(*) FROM shot_participant sp WHERE sp.shot_id=s.id) AS actual
            FROM shot s ORDER BY s.id
            """
        ):
            spec = load_json(row["shot_spec_json"])
            participants = spec.get("participants") if isinstance(spec.get("participants"), list) else []
            expected = len(participants)
            participant_total += expected
            if expected >= 2:
                multi_participant += 1
            if row["actual"] != expected:
                participant_bad.append(
                    {"shot_id": row["id"], "expected": expected, "actual": row["actual"]}
                )
            if row["character_id"] is not None:
                present = connection.execute(
                    "SELECT 1 FROM shot_participant WHERE shot_id=? AND character_id=?",
                    (row["id"], row["character_id"]),
                ).fetchone()
                if not present:
                    missing_primary.append(
                        {"shot_id": row["id"], "character_id": row["character_id"]}
                    )

        interactions_without_source = []
        interaction_by_instruction = Counter()
        for row in connection.execute(
            """
            SELECT si.shot_id, si.actor_character_id, si.target_character_id, si.action_code,
                   si.instruction, s.shot_spec_json
            FROM shot_interaction si JOIN shot s ON s.id=si.shot_id
            """
        ):
            interaction_by_instruction[row["instruction"]] += 1
            spec = load_json(row["shot_spec_json"])
            inter = spec.get("interaction") if isinstance(spec.get("interaction"), dict) else {}
            seq = spec.get("sequence") if isinstance(spec.get("sequence"), dict) else {}
            explicit = (
                inter.get("actor") and inter.get("target") and inter.get("action")
            ) or (
                seq.get("actor") and seq.get("target") and seq.get("primaryAction")
            )
            if not explicit:
                interactions_without_source.append(
                    {
                        "shot_id": row["shot_id"],
                        "actor_character_id": row["actor_character_id"],
                        "target_character_id": row["target_character_id"],
                        "action_code": row["action_code"],
                    }
                )

        binding_bad = []
        for row in connection.execute(
            """
            SELECT b.shot_id, b.character_id, b.outfit_revision_id,
                   s.shot_spec_json, o.character_id AS outfit_character,
                   o.spec_json AS outfit_spec_json
            FROM shot_outfit_binding b
            JOIN shot s ON s.id=b.shot_id
            JOIN outfit_revision o ON o.id=b.outfit_revision_id
            """
        ):
            spec = load_json(row["shot_spec_json"])
            outfit = load_json(row["outfit_spec_json"])
            shot_tags = {
                item["tagId"]
                for item in (spec.get("outfit") or [])
                if isinstance(item, dict) and isinstance(item.get("tagId"), int)
            }
            outfit_tags = {
                item["tag_id"]
                for item in (outfit.get("items") or [])
                if isinstance(item, dict) and isinstance(item.get("tag_id"), int)
            }
            if row["character_id"] != row["outfit_character"] or shot_tags != outfit_tags:
                binding_bad.append(
                    {
                        "shot_id": row["shot_id"],
                        "character_id": row["character_id"],
                        "outfit_character": row["outfit_character"],
                        "shot_tags": sorted(shot_tags),
                        "outfit_tags": sorted(outfit_tags),
                    }
                )

        queue_by_rule = {
            row["rule_code"]: row["n"]
            for row in connection.execute(
                "SELECT rule_code, count(*) AS n FROM reconciliation_item "
                "GROUP BY rule_code ORDER BY n DESC"
            )
        }
        queue_by_domain = {
            row["domain"]: row["n"]
            for row in connection.execute(
                "SELECT domain, count(*) AS n FROM reconciliation_item GROUP BY domain"
            )
        }
        queue_by_severity = {
            row["severity"]: row["n"]
            for row in connection.execute(
                "SELECT severity, count(*) AS n FROM reconciliation_item GROUP BY severity"
            )
        }
        queue_counts = connection.execute(
            "SELECT count(*) AS total, count(DISTINCT gap_key) AS distinct_keys FROM reconciliation_item"
        ).fetchone()
        queue_status = {
            row["status"]: row["n"]
            for row in connection.execute(
                "SELECT status, count(*) AS n FROM reconciliation_item GROUP BY status"
            )
        }

        source_specs = 0
        source_items = 0
        source_parity_bad = []
        for row in connection.execute("SELECT id, outfit_json FROM character_profile"):
            outfit = load_json(row["outfit_json"])
            if not isinstance(outfit, dict):
                continue
            specs = []
            for key, value in outfit.items():
                if key in {"source", "assumed", "variants"}:
                    continue
                if isinstance(value, list):
                    specs.append((key, value))
            variants = outfit.get("variants")
            if isinstance(variants, dict):
                for key, value in variants.items():
                    if isinstance(value, list):
                        specs.append((f"variants.{key}", value))
            source_specs += len(specs)
            source_items += sum(len(values) for _key, values in specs)
            actual_specs = connection.execute(
                "SELECT count(*) FROM outfit_revision WHERE character_id=?", (row["id"],)
            ).fetchone()[0]
            actual_items = connection.execute(
                "SELECT count(*) FROM outfit_item WHERE outfit_revision_id IN "
                "(SELECT id FROM outfit_revision WHERE character_id=?)",
                (row["id"],),
            ).fetchone()[0]
            expected_items = sum(
                len({value.strip() for value in values if isinstance(value, str)})
                for _key, values in specs
            )
            if actual_specs != len(specs) or actual_items != expected_items:
                source_parity_bad.append(
                    {
                        "character_id": row["id"],
                        "expected_specs": len(specs),
                        "actual_specs": actual_specs,
                        "expected_items": expected_items,
                        "actual_items": actual_items,
                    }
                )

        checks = {
            "quick_check": integrity,
            "quick_check_ok": integrity == ["ok"],
            "foreign_key_violations_first_20": foreign_keys,
            "foreign_key_ok": not foreign_keys,
        }
        status = "ok"
        if (
            missing_tables
            or not checks["quick_check_ok"]
            or not checks["foreign_key_ok"]
            or project_ids != document_ids
            or character_ids != identity_ids
            or shot_ids != spec_ids
            or participant_bad
            or missing_primary
            or interactions_without_source
            or binding_bad
            or source_parity_bad
            or queue_counts["total"] != queue_counts["distinct_keys"]
        ):
            status = "failed"
        return {
            "schema_version": "n2a-backfill-verification/1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": str(db_path.resolve()),
            "size_bytes": db_path.stat().st_size,
            "status": status,
            "table_counts": counts,
            "missing_tables": missing_tables,
            "migration_ledger": migrations,
            "checks": checks,
            "parity": {
                "projects": len(project_ids),
                "project_documents": len(document_ids),
                "projects_without_document": sorted(project_ids - document_ids),
                "characters": len(character_ids),
                "identities": len(identity_ids),
                "characters_without_identity": sorted(character_ids - identity_ids),
                "shots": len(shot_ids),
                "shot_specs": len(spec_ids),
                "shots_without_spec": sorted(shot_ids - spec_ids),
                "expected_participants": participant_total,
                "actual_participants": counts.get("shot_participant", 0),
                "participant_parity_mismatches": participant_bad,
                "missing_primary_participants": missing_primary,
                "multi_participant_shots": multi_participant,
                "interactions": counts.get("shot_interaction", 0),
                "interaction_by_instruction": dict(interaction_by_instruction),
                "interactions_without_explicit_source": interactions_without_source,
                "exact_outfit_bindings": counts.get("shot_outfit_binding", 0),
                "binding_parity_mismatches": binding_bad,
                "source_outfit_specs": source_specs,
                "actual_outfit_specs": counts.get("outfit_revision", 0),
                "source_outfit_items": source_items,
                "actual_outfit_items": counts.get("outfit_item", 0),
                "outfit_parity_mismatches": source_parity_bad,
            },
            "reconciliation": {
                "total": queue_counts["total"],
                "distinct_gap_keys": queue_counts["distinct_keys"],
                "by_domain": queue_by_domain,
                "by_severity": queue_by_severity,
                "by_rule": queue_by_rule,
                "by_status": queue_status,
            },
        }
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Backfilled staging database")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = build_report(Path(args.db))
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "Backfill verification:",
        report["status"],
        "checks=",
        report["checks"]["quick_check_ok"] and report["checks"]["foreign_key_ok"],
        "queue=",
        report["reconciliation"]["total"],
        "bindings=",
        report["parity"]["exact_outfit_bindings"],
        "interactions=",
        report["parity"]["interactions"],
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
