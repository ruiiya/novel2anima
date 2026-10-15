#!/usr/bin/env python3
"""Read-only V4 Novel2Anima SQLite coverage audit; does not fabricate missing data.

Usage: python tools/sqlite_coverage_audit.py /path/to/novel_anima.db [--output report.json]
Requires Python stdlib only. Returns 2 for missing schema or integrity failure, 1 for
missing/unreadable database. Prints JSON even when counts are zero.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

DATA_TABLES = [
    "source_snapshot", "tag", "tag_source", "tag_alias", "tag_role",
    "tag_relation", "tag_content_label", "visual_concept", "concept_tag",
    "concept_relation", "model_profile", "project", "character_profile",
    "act", "shot", "generation",
]
FTS_TABLE = "visual_concept_fts"
SOURCES = {
    "danbooru_taxonomy", "anima_tag_index", "anima_wardrobe", "anima_tools",
    "danbooru_implications",
}


def colset(con: sqlite3.Connection, table: str) -> set[str]:
    # Called only for fixed known table names, not interpolated external input.
    return {str(row[1]) for row in con.execute(f"PRAGMA table_info({table})")}


def grouped(con: sqlite3.Connection, table: str, column: str, limit: int = 100) -> list[dict]:
    if column not in colset(con, table):
        return []
    sql = (f'SELECT "{column}", COUNT(*) FROM "{table}" '
           f'GROUP BY "{column}" ORDER BY COUNT(*) DESC LIMIT ?')
    return [{"value": v, "count": n} for v, n in con.execute(sql, (limit,))]


def audit(path: Path) -> tuple[dict, int]:
    report: dict = {"database": str(path), "auditType": "read_only_v4_coverage",
                    "schema": {}, "rows": {}, "dimensions": {},
                    "checks": {}, "warnings": [], "errors": []}
    if not path.is_file():
        report["errors"].append("SQLITE_DB_NOT_FOUND: do not mistake a skill ZIP for a populated DB")
        return report, 1
    try:
        con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
        con.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error as exc:
        report["errors"].append(f"CANNOT_OPEN_SQLITE_READ_ONLY: {exc}")
        return report, 1
    try:
        meta = {name: (typ, sql) for name, typ, sql in con.execute(
            "SELECT name, type, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
        missing = [t for t in [*DATA_TABLES, FTS_TABLE] if t not in meta]
        report["schema"]["requiredDataTables"] = len(DATA_TABLES)
        report["schema"]["missing"] = missing
        report["schema"]["present"] = [t for t in [*DATA_TABLES, FTS_TABLE] if t in meta]
        report["schema"]["ftsIsVirtual"] = bool(
            FTS_TABLE in meta and "VIRTUAL TABLE" in (meta[FTS_TABLE][1] or "").upper())
        if missing:
            report["errors"].append(f"SCHEMA_MISSING: {', '.join(missing)}")
        if FTS_TABLE in meta and not report["schema"]["ftsIsVirtual"]:
            report["errors"].append("FTS_NOT_VIRTUAL")

        for name in DATA_TABLES:
            if name not in meta:
                continue
            try:
                report["rows"][name] = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            except sqlite3.Error as exc:
                report["errors"].append(f"UNREADABLE_TABLE {name}: {exc}")
        if FTS_TABLE in meta:
            try:
                report["rows"][FTS_TABLE] = con.execute(
                    f'SELECT COUNT(*) FROM "{FTS_TABLE}"').fetchone()[0]
            except sqlite3.Error as exc:
                report["errors"].append(f"FTS_QUERY_ERROR: {exc}")
        try:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            report["checks"]["integrity"] = integrity
            if integrity != "ok":
                report["errors"].append("SQLITE_INTEGRITY_ERROR")
            fk_issues = con.execute("PRAGMA foreign_key_check").fetchall()
            report["checks"]["foreignKeyIssues"] = len(fk_issues)
            if fk_issues:
                report["errors"].append("SQLITE_FK_ERRORS")
            con.execute("SELECT json_valid('{\"ok\":true}')").fetchone()
            report["checks"]["jsonAvailable"] = True
        except sqlite3.Error as exc:
            report["errors"].append(f"SQLITE_CHECK_ERROR: {exc}")

        for table, dimension in [
            ("source_snapshot", "source_key"), ("tag_role", "role"),
            ("tag_content_label", "scope"), ("visual_concept", "review_status"),
            ("visual_concept", "content_scope"), ("visual_concept", "kind"),
            ("tag_relation", "relation"), ("concept_relation", "relation"),
            ("shot", "status"), ("generation", "decision"),
        ]:
            if table in meta:
                report["dimensions"][f"{table}.{dimension}"] = grouped(con, table, dimension)

        if "source_snapshot" in meta and "source_key" in colset(con, "source_snapshot"):
            detected = {d["value"] for d in report["dimensions"].get(
                "source_snapshot.source_key", [])}
            missing_sources = sorted(SOURCES - detected)
            report["checks"]["missingExpectedSourceKeys"] = missing_sources
            if missing_sources:
                report["warnings"].append("SOURCE_FAMILIES_NOT_SEEN: " + ", ".join(missing_sources))
        if "tag" in meta and report["rows"].get("tag", 0) == 0:
            report["warnings"].append("EMPTY_DICTIONARY: DB may be schema-only")
        if "visual_concept" in meta and "concept_tag" in meta:
            try:
                mapped = con.execute("""SELECT COUNT(DISTINCT ct.concept_id)
                    FROM concept_tag ct JOIN visual_concept c ON c.id=ct.concept_id""").fetchone()[0]
                report["checks"]["conceptsWithTags"] = mapped
                report["checks"]["conceptsWithoutTags"] = max(
                    0, report["rows"].get("visual_concept", 0) - mapped)
            except sqlite3.Error as exc:
                report["warnings"].append(f"CONCEPT_MAPPING_QUERY_SKIPPED: {exc}")
        if "tag_role" in meta and {"tag_id", "role"}.issubset(colset(con, "tag_role")):
            try:
                report["checks"]["tagsWithMultipleRoles"] = con.execute(
                    "SELECT COUNT(*) FROM (SELECT tag_id FROM tag_role GROUP BY tag_id HAVING COUNT(DISTINCT role)>1)"
                ).fetchone()[0]
            except sqlite3.Error as exc:
                report["warnings"].append(f"MULTI_ROLE_QUERY_SKIPPED: {exc}")
        if "tag" in meta and "concept_tag" in meta and "tag_id" in colset(con, "concept_tag"):
            try:
                report["checks"]["tagsWithoutConceptMapping"] = con.execute(
                    "SELECT COUNT(*) FROM tag t WHERE NOT EXISTS "
                    "(SELECT 1 FROM concept_tag ct WHERE ct.tag_id=t.id)"
                ).fetchone()[0]
            except sqlite3.Error as exc:
                report["warnings"].append(f"RAW_FALLBACK_COUNT_SKIPPED: {exc}")
        if FTS_TABLE in meta and "visual_concept" in meta:
            if report["rows"].get("visual_concept", 0) != report["rows"].get(FTS_TABLE, 0):
                report["warnings"].append("FTS_COUNT_MISMATCH: verify external-content index/triggers")
        # Those stage integration facts cannot be proven from schema-only inspection.
        report["checks"]["retrievalApiExercised"] = False
        report["checks"]["rankerBenchmarked"] = False
        report["checks"]["comfyUiBenchmarked"] = False
        report["checks"]["importIdempotencyExercised"] = False
        report["warnings"].append("CODE_INTEGRATION_UNVERIFIED: DB counts do not prove retrieval/ranking/feedback code uses every table")
        report["result"] = "FAIL" if report["errors"] else ("WARN" if report["warnings"] else "PASS")
        return report, 2 if report["errors"] else 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_db", type=Path, help="Existing V4 SQLite path (read-only)")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    report, status = audit(args.sqlite_db)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
