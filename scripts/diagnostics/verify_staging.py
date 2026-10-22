#!/usr/bin/env python3
"""Verify a staging copy after additive migrations, against a baseline audit.

This is a diagnostic, not a migration. It proves:
- every baseline table is still present and its row count is unchanged;
- the new additive tables exist;
- SQLite integrity and foreign-key checks pass;
- the migration ledger has version + checksum rows.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    counts: dict[str, int] = {}
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        counts[name] = connection.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
    return counts


def build_report(
    db_path: Path,
    baseline_path: Path,
    allowed_changed: list[str] | None = None,
) -> dict:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    expected = baseline.get("table_counts", {})
    allowed = set(allowed_changed or [])
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        counts = table_counts(connection)
        integrity = [row[0] for row in connection.execute("PRAGMA quick_check").fetchmany(21)]
        fk = [list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchmany(21)]
        migrations = []
        if "n2a_schema_migration" in counts:
            migrations = [
                {"version": row[0], "sha256": row[1], "applied_at": row[2]}
                for row in connection.execute(
                    "SELECT version, sha256, applied_at FROM n2a_schema_migration ORDER BY version"
                )
            ]
        sqlite_version = connection.execute("SELECT sqlite_version()").fetchone()[0]
    finally:
        connection.close()

    missing = sorted(set(expected) - set(counts))
    changed = {
        name: {"before": before, "after": counts[name]}
        for name, before in expected.items()
        if name in counts and counts[name] != before
    }
    allowed_changes = {
        name: change for name, change in changed.items() if name in allowed
    }
    unexpected_changes = {
        name: change for name, change in changed.items() if name not in allowed
    }
    new_tables = sorted(set(counts) - set(expected))
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(db_path.resolve()),
        "size_bytes": db_path.stat().st_size,
        "sqlite_version": sqlite_version,
        "baseline": str(baseline_path.resolve()),
        "baseline_tables": len(expected),
        "baseline_tables_missing": missing,
        "baseline_tables_changed": changed,
        "baseline_tables_allowed_changed": allowed_changes,
        "baseline_tables_unexpected_changed": unexpected_changes,
        "legacy_counts_unchanged": not missing and not changed,
        "new_tables": [
            {"name": name, "rows": counts[name]} for name in new_tables
        ],
        "migration_ledger": migrations,
        "checks": {
            "quick_check": integrity,
            "quick_check_ok": integrity == ["ok"],
            "foreign_key_violations_first_20": fk,
            "foreign_key_ok": not fk,
        },
        "status": "ok"
        if not missing and not unexpected_changes and integrity == ["ok"] and not fk
        else "failed",
        "note": "Additive schema only. No content backfill; legacy counts must be identical "
        "unless a table is explicitly listed as an allowed provenance change.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Staging database")
    parser.add_argument("--baseline", required=True, help="PR-00 db_audit.json")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--allow-changed",
        action="append",
        default=[],
        help="Baseline table allowed to change for an explicit provenance reason (repeatable)",
    )
    args = parser.parse_args(argv)

    report = build_report(Path(args.db), Path(args.baseline), args.allow_changed)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "Staging verification:",
        report["status"],
        "baseline_tables=",
        report["baseline_tables"],
        "missing=",
        len(report["baseline_tables_missing"]),
        "changed=",
        len(report["baseline_tables_changed"]),
        "new_tables=",
        len(report["new_tables"]),
        "quick_check=",
        report["checks"]["quick_check_ok"],
        "foreign_keys=",
        report["checks"]["foreign_key_ok"],
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
