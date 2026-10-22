#!/usr/bin/env python3
"""Create a consistent SQLite backup with the Backup API and verify it.

The source database is opened read-only, so this tool never migrates or
checkpoints the live file. A restore rehearsal copies the backup to a temporary
directory, runs integrity/foreign-key checks and compares table counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HASH_BLOCK = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(HASH_BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


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


def check_database(connection: sqlite3.Connection) -> dict:
    integrity_rows = [row[0] for row in connection.execute("PRAGMA integrity_check").fetchmany(21)]
    fk_rows = [list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchmany(21)]
    return {
        "integrity_check": integrity_rows,
        "integrity_ok": integrity_rows == ["ok"],
        "foreign_key_violations_first_20": fk_rows,
        "foreign_key_ok": not fk_rows,
        "table_counts": table_counts(connection),
    }


def _unique_path(directory: Path, stem: str) -> Path:
    candidate = directory / f"{stem}.db"
    index = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{index:02d}.db"
        index += 1
    return candidate


def backup_database(
    source: Path,
    backup_dir: Path,
    report_path: Path,
    label: str = "pr-00",
    restore_check: bool = True,
) -> dict:
    source = source.resolve(strict=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = _unique_path(backup_dir, f"{label}_{stamp}")

    before = {
        "size_bytes": source.stat().st_size,
        "mtime_ns": source.stat().st_mtime_ns,
        "sha256": sha256_file(source),
    }

    src = connect_readonly(source)
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()

    after = {
        "size_bytes": source.stat().st_size,
        "mtime_ns": source.stat().st_mtime_ns,
        "sha256": sha256_file(source),
    }

    verify = sqlite3.connect(str(backup_path))
    try:
        backup_check = check_database(verify)
    finally:
        verify.close()

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "source": {"path": str(source), **before, "unchanged": before == after},
        "backup": {
            "path": str(backup_path),
            "size_bytes": backup_path.stat().st_size,
            "sha256": sha256_file(backup_path),
            **backup_check,
        },
        "restore_check": None,
        "status": "failed",
    }

    counts_match = before["sha256"] == after["sha256"] and backup_check["integrity_ok"] and backup_check["foreign_key_ok"]
    if restore_check:
        with tempfile.TemporaryDirectory(prefix="n2a-restore-") as temp:
            restored = Path(temp) / "restored.db"
            shutil.copy2(backup_path, restored)
            conn = sqlite3.connect(str(restored))
            try:
                restored_check = check_database(conn)
            finally:
                conn.close()
            restore_ok = (
                restored_check["integrity_ok"]
                and restored_check["foreign_key_ok"]
                and restored_check["table_counts"] == backup_check["table_counts"]
            )
            report["restore_check"] = {
                "restored_copy": str(restored),
                "temp_copy_removed": True,
                **restored_check,
                "table_counts_match": restored_check["table_counts"] == backup_check["table_counts"],
                "ok": restore_ok,
            }
            counts_match = counts_match and restore_ok

    report["status"] = "ok" if counts_match else "failed"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Live SQLite DB (opened read-only)")
    parser.add_argument("--backup-dir", required=True, help="Backup directory (normally db/backup/)")
    parser.add_argument("--report", required=True, help="JSON report path")
    parser.add_argument("--label", default="pr-00", help="Backup filename prefix")
    parser.add_argument("--skip-restore", action="store_true", help="Skip the restore rehearsal")
    args = parser.parse_args(argv)

    report = backup_database(
        Path(args.source),
        Path(args.backup_dir),
        Path(args.report).resolve(),
        label=args.label,
        restore_check=not args.skip_restore,
    )
    print(
        "Backup:",
        report["backup"]["path"],
        "status=",
        report["status"],
        "sha256=",
        report["backup"]["sha256"],
    )
    print("Tables:", len(report["backup"]["table_counts"]), "restore_ok=", (report["restore_check"] or {}).get("ok"))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
