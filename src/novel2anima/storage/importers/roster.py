"""Character roster JSON importer (PR-03).

The live DB already contains the imported rosters.  PR-03 therefore only:

* verifies exact duplicates and records them;
* blocks and queues any identity/outfit difference instead of overwriting the
  canonical DB row from a file;
* blocks unknown codes rather than guessing a project from filename prefixes.
"""
from __future__ import annotations

import json
import sqlite3

from .base import (
    SourceFile,
    blocked,
    bounded_json,
    duplicate,
    queue_reconciliation,
    sha256_json,
    skipped,
)


def _rows_from(data):
    if isinstance(data, list):
        return data, "list"
    if not isinstance(data, dict):
        return None, None
    if isinstance(data.get("characters"), list):
        return data["characters"], "characters"
    if data and all(isinstance(value, dict) for value in data.values()):
        rows = []
        for code, value in data.items():
            row = dict(value)
            row.setdefault("code", code)
            rows.append(row)
        return rows, "code_map"
    return None, None


class RosterParser:
    classification = "roster"
    parser_version = "roster/1"

    def parse(self, source: SourceFile, connection: sqlite3.Connection):
        data = source.read_json()
        rows, shape = _rows_from(data)
        if rows is None:
            # ba_outfits.json is a generated report, not a roster.
            return skipped(
                "roster_report_not_importable",
                details={"shape": type(data).__name__},
            )

        exact = 0
        mismatches = 0
        missing = 0
        invalid = 0
        queued = 0
        existing = 0
        details_rows: list[dict] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                invalid += 1
                continue
            code = row.get("code")
            if not isinstance(code, str) or not code.strip():
                invalid += 1
                continue
            code = code.strip()
            identity = row.get("identity_json")
            outfit = row.get("outfit_json")
            if not isinstance(identity, dict) or not isinstance(outfit, dict):
                invalid += 1
                details_rows.append({"code": code, "error": "identity_json/outfit_json missing"})
                continue

            matches = connection.execute(
                "SELECT id, project_id, identity_json, outfit_json "
                "FROM character_profile WHERE code = ? ORDER BY project_id, id",
                (code,),
            ).fetchall()
            if not matches:
                missing += 1
                inserted = queue_reconciliation(
                    connection,
                    gap_key=f"roster:{source.sha256}:{code}:missing",
                    domain="identity",
                    rule_code="roster_character_missing",
                    severity="blocked",
                    evidence={
                        "source_path": source.relative_path,
                        "source_sha256": source.sha256,
                        "code": code,
                        "reason": "character code not found in any project",
                    },
                    entity_table="character_profile",
                )
                queued += 1 if inserted else 0
                existing += 0 if inserted else 1
                details_rows.append({"code": code, "status": "missing"})
                continue
            if len(matches) > 1:
                mismatches += 1
                inserted = queue_reconciliation(
                    connection,
                    gap_key=f"roster:{source.sha256}:{code}:ambiguous",
                    domain="identity",
                    rule_code="roster_character_ambiguous",
                    severity="blocked",
                    evidence={
                        "source_path": source.relative_path,
                        "source_sha256": source.sha256,
                        "code": code,
                        "character_ids": [row["id"] for row in matches],
                    },
                )
                queued += 1 if inserted else 0
                existing += 0 if inserted else 1
                details_rows.append({"code": code, "status": "ambiguous"})
                continue

            db_row = matches[0]
            db_identity = json.loads(db_row["identity_json"])
            db_outfit = json.loads(db_row["outfit_json"])
            row_mismatch = False
            for aspect, source_value, database_value in (
                ("identity", identity, db_identity),
                ("outfit", outfit, db_outfit),
            ):
                if source_value == database_value:
                    continue
                row_mismatch = True
                mismatches += 1
                inserted = queue_reconciliation(
                    connection,
                    gap_key=f"roster:{source.sha256}:{code}:{aspect}",
                    domain=aspect,
                    rule_code=f"roster_{aspect}_mismatch",
                    severity="warning",
                    character_id=db_row["id"],
                    evidence={
                        "source_path": source.relative_path,
                        "source_sha256": source.sha256,
                        "code": code,
                        "aspect": aspect,
                        "database_sha256": sha256_json(database_value),
                        "source_value_sha256": sha256_json(source_value),
                        "database_value": bounded_json(database_value),
                        "source_value": bounded_json(source_value),
                    },
                    entity_table="character_profile",
                    entity_id=db_row["id"],
                )
                queued += 1 if inserted else 0
                existing += 0 if inserted else 1
                details_rows.append({"code": code, "status": f"{aspect}_mismatch"})
            if not row_mismatch:
                exact += 1

        details = {
            "shape": shape,
            "rows": len(rows),
            "exact": exact,
            "mismatches": mismatches,
            "missing": missing,
            "invalid": invalid,
            "queued": queued,
            "queue_existing": existing,
            "sample": details_rows[:20],
        }
        if mismatches or missing or invalid:
            return blocked(
                "roster_content_differs_from_db"
                if mismatches
                else "roster_rows_unresolved",
                target_table="character_profile",
                details=details,
            )
        return duplicate(
            target_table="character_profile",
            details=details,
        )
