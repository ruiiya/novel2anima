"""Catalog source manifest/cache importer (PR-03).

Catalog bytes are *not* re-imported blindly in PR-03.  The parser verifies each
manifest entry (size + SHA-256), records per-file provenance in
``source_snapshot``, and marks the raw cache file's import status.  Generated
reports that are not referenced by the manifest are skipped by policy.  Raw
catalog bytes are not copied into ``asset_blob``; only verified provenance is.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .base import (
    SourceFile,
    blocked,
    duplicate,
    imported,
    require_object,
    sha256_file,
    skipped,
)

MANIFEST_PATH = "data/sources/manifest.json"


def _manifest_entries(root: Path) -> dict[str, dict]:
    manifest_file = root / MANIFEST_PATH
    if not manifest_file.is_file():
        return {}
    try:
        manifest = manifest_file.read_text(encoding="utf-8-sig")
        payload = json.loads(manifest)
    except (OSError, UnicodeDecodeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    entries: dict[str, dict] = {}
    for family, info in payload.items():
        if not isinstance(family, str) or not isinstance(info, dict):
            continue
        files = info.get("files")
        if not isinstance(files, dict):
            continue
        revision = str(info.get("revision") or "unversioned")
        for relative, meta in files.items():
            if not isinstance(relative, str) or not isinstance(meta, dict):
                continue
            rel_path = Path(relative)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                continue
            entries[f"data/sources/{family}/{relative}"] = {
                "family": family,
                "relative": relative,
                "revision": revision,
                "meta": meta,
            }
    return entries


def _snapshot_key(family: str, relative: str) -> str:
    return f"legacy_catalog:{family}:{relative}"


class CatalogParser:
    classification = "catalog"
    parser_version = "catalog/1"

    def parse(self, source: SourceFile, connection: sqlite3.Connection):
        if source.relative_path == MANIFEST_PATH:
            return self._parse_manifest(source, connection)
        return self._parse_cache_file(source, connection)

    def _parse_manifest(self, source: SourceFile, connection: sqlite3.Connection):
        payload = require_object(source.read_json(), "source manifest")
        planned: list[dict] = []
        errors: list[dict] = []
        for family, info in payload.items():
            if not isinstance(family, str) or not isinstance(info, dict):
                errors.append({"family": family, "error": "invalid family entry"})
                continue
            files = info.get("files")
            if not isinstance(files, dict):
                errors.append({"family": family, "error": "files must be an object"})
                continue
            revision = str(info.get("revision") or "unversioned")
            for relative, meta in files.items():
                if not isinstance(relative, str) or not isinstance(meta, dict):
                    errors.append({"family": family, "file": relative, "error": "invalid file entry"})
                    continue
                rel_path = Path(relative)
                if rel_path.is_absolute() or ".." in rel_path.parts:
                    errors.append({"family": family, "file": relative, "error": "unsafe path"})
                    continue
                actual_path = source.root / "data/sources" / family / relative
                if not actual_path.is_file():
                    errors.append({"family": family, "file": relative, "error": "missing file"})
                    continue
                actual_sha = sha256_file(actual_path)
                expected_sha = meta.get("sha256")
                expected_bytes = meta.get("bytes")
                if not isinstance(expected_sha, str) or len(expected_sha) != 64:
                    errors.append({"family": family, "file": relative, "error": "invalid sha256"})
                    continue
                if actual_sha != expected_sha:
                    errors.append(
                        {
                            "family": family,
                            "file": relative,
                            "error": "sha256 mismatch",
                            "expected": expected_sha,
                            "actual": actual_sha,
                        }
                    )
                    continue
                if not isinstance(expected_bytes, int) or expected_bytes != actual_path.stat().st_size:
                    errors.append(
                        {
                            "family": family,
                            "file": relative,
                            "error": "byte length mismatch",
                            "expected": expected_bytes,
                            "actual": actual_path.stat().st_size,
                        }
                    )
                    continue
                url = meta.get("url")
                if not isinstance(url, str) or not url:
                    errors.append({"family": family, "file": relative, "error": "missing url"})
                    continue
                planned.append(
                    {
                        "family": family,
                        "relative": relative,
                        "revision": revision,
                        "source_key": _snapshot_key(family, relative),
                        "source_url": url,
                        "sha256": actual_sha,
                        "bytes": actual_path.stat().st_size,
                    }
                )

        if errors:
            return blocked(
                "catalog_manifest_invalid",
                details={"errors": errors[:20], "error_count": len(errors)},
            )
        if not planned:
            return blocked("catalog_manifest_empty")

        conflicts: list[dict] = []
        existing_ids: dict[str, int] = {}
        for entry in planned:
            row = connection.execute(
                "SELECT id, sha256 FROM source_snapshot WHERE source_key = ? AND revision = ?",
                (entry["source_key"], entry["revision"]),
            ).fetchone()
            if row is None:
                continue
            if row["sha256"] != entry["sha256"]:
                conflicts.append(
                    {
                        "source_key": entry["source_key"],
                        "revision": entry["revision"],
                        "database_sha256": row["sha256"],
                        "manifest_sha256": entry["sha256"],
                    }
                )
            else:
                existing_ids[entry["source_key"]] = row["id"]
        if conflicts:
            return blocked(
                "catalog_snapshot_conflict",
                details={"conflicts": conflicts[:20], "conflict_count": len(conflicts)},
            )

        inserted = 0
        target_ids: list[int] = []
        for entry in planned:
            if entry["source_key"] in existing_ids:
                continue
            cursor = connection.execute(
                "INSERT INTO source_snapshot("
                "source_key, source_url, revision, license_note, sha256"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    entry["source_key"],
                    entry["source_url"],
                    entry["revision"],
                    "Imported from data/sources/manifest.json; see upstream license",
                    entry["sha256"],
                ),
            )
            inserted += 1
            target_ids.append(cursor.lastrowid)
            existing_ids[entry["source_key"]] = cursor.lastrowid

        details = {
            "families": len({entry["family"] for entry in planned}),
            "files": len(planned),
            "snapshots_inserted": inserted,
            "snapshots_duplicate": len(planned) - inserted,
            "inserted": inserted,
            "target_ids_sample": (target_ids or list(existing_ids.values()))[:10],
        }
        if inserted:
            return imported(
                target_table="source_snapshot",
                target_pk=target_ids[0],
                details=details,
            )
        return duplicate(
            target_table="source_snapshot",
            target_pk=next(iter(existing_ids.values()), None),
            details=details,
        )

    def _parse_cache_file(self, source: SourceFile, connection: sqlite3.Connection):
        entries = _manifest_entries(source.root)
        entry = entries.get(source.relative_path)
        if entry is None:
            return skipped(
                "catalog_cache_unreferenced",
                details={
                    "reason": "not referenced by data/sources/manifest.json; not claimed as imported",
                },
            )
        meta = entry["meta"]
        expected_sha = meta.get("sha256")
        expected_bytes = meta.get("bytes")
        if expected_sha != source.sha256:
            return blocked(
                "catalog_cache_sha_mismatch",
                details={
                    "expected": expected_sha,
                    "actual": source.sha256,
                    "manifest": MANIFEST_PATH,
                },
            )
        if expected_bytes != source.size_bytes:
            return blocked(
                "catalog_cache_size_mismatch",
                details={"expected": expected_bytes, "actual": source.size_bytes},
            )
        source_key = _snapshot_key(entry["family"], entry["relative"])
        row = connection.execute(
            "SELECT id, sha256 FROM source_snapshot WHERE source_key = ? AND revision = ?",
            (source_key, entry["revision"]),
        ).fetchone()
        if row is None:
            return blocked(
                "catalog_snapshot_missing",
                details={"source_key": source_key, "revision": entry["revision"]},
            )
        if row["sha256"] != source.sha256:
            return blocked(
                "catalog_snapshot_sha_mismatch",
                details={
                    "source_key": source_key,
                    "revision": entry["revision"],
                    "database_sha256": row["sha256"],
                    "file_sha256": source.sha256,
                },
            )
        return duplicate(
            target_table="source_snapshot",
            target_pk=row["id"],
            details={
                "manifest_verified": True,
                "raw_bytes_retained": False,
                "source_key": source_key,
                "revision": entry["revision"],
            },
        )
