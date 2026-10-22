"""Verify disposition of all 23 legacy tables and duplicate authority columns.

Usage:
  python scripts/qa/verify_p8_disposition.py --db PATH [--json PATH]
  python scripts/qa/verify_p8_disposition.py --db PATH --require-clean
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAPPING = ROOT / "docs/v4/mappings/LEGACY_23_DB_TABLES.csv"

# table -> (P8 disposition, note)
DISPOSITION = {
    "source_snapshot": ("keep", "import provenance"),
    "tag": ("keep", "canonical catalog"),
    "tag_source": ("keep", "provenance"),
    "tag_alias": ("keep", "winning alias plus conflict table"),
    "tag_role": ("keep", "multi-role catalog"),
    "tag_relation": ("keep", "catalog relation plus source table"),
    "tag_content_label": ("keep", "catalog labels"),
    "visual_concept": ("keep", "concept catalog"),
    "concept_tag": ("keep", "concept mapping"),
    "concept_relation": ("keep", "empty but reserved"),
    "visual_concept_fts": ("keep", "rebuildable FTS index"),
    "model_profile": ("keep", "render model reference"),
    "project": ("keep", "project root"),
    "character_profile": ("transitional", "drop identity_json/outfit_json after all readers use revisions"),
    "act": ("keep", "act root"),
    "shot": ("transitional", "drop character_id/shot_spec_json after all readers use participants/spec revisions"),
    "generation": ("cleanup", "image_path removed; bytes in asset_blob"),
    "shot_state": ("projection", "latest continuity state"),
    "act_continuity": ("keep", "initial act state"),
    "shot_observation": ("projection", "compat until assertion parity"),
    "act_observation": ("projection", "compat until assertion parity"),
    "act_publication": ("transitional", "file export history; not current prompt authority"),
    "shot_finding": ("projection", "latest QA finding"),
}

DUP_COLUMNS = {
    "character_profile": ("identity_json", "outfit_json"),
    "shot": ("character_id", "shot_spec_json"),
    "generation": ("image_path",),
}


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def report(db_path: pathlib.Path) -> dict:
    with MAPPING.open(encoding="utf-8-sig", newline="") as handle:
        legacy = list(csv.DictReader(handle))
    con = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        rows = []
        for item in legacy:
            name = item["old_table"]
            present = name in tables
            count = (
                int(con.execute(f"SELECT count(*) FROM {name}").fetchone()[0])
                if present else 0
            )
            disposition, note = DISPOSITION.get(name, ("unknown", "missing disposition"))
            dup = {}
            if present and name in DUP_COLUMNS:
                cols = table_columns(con, name)
                dup = {col: col in cols for col in DUP_COLUMNS[name]}
            rows.append({
                "table": name,
                "present": present,
                "rows": count,
                "disposition": disposition,
                "note": note,
                "duplicate_columns": dup,
            })
        missing = sorted(set(DISPOSITION) - {row["table"] for row in rows})
        unknown = sorted({row["table"] for row in rows} - set(DISPOSITION))
        return {
            "database": str(db_path.resolve()),
            "legacy_table_count": len(legacy),
            "disposition_count": len(DISPOSITION),
            "missing_from_csv": missing,
            "missing_disposition": unknown,
            "tables": rows,
        }
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, type=pathlib.Path)
    ap.add_argument("--json", type=pathlib.Path)
    ap.add_argument("--require-clean", action="store_true")
    args = ap.parse_args(argv)
    data = report(args.db)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    if data["missing_from_csv"] or data["missing_disposition"]:
        return 2
    if args.require_clean:
        dirty = [
            row for row in data["tables"]
            if row["disposition"] == "transitional"
            or any(row["duplicate_columns"].values())
            or not row["present"]
        ]
        if dirty:
            print("not clean:", [row["table"] for row in dirty], file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
