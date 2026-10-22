#!/usr/bin/env python3
"""Versioned SQLite migration runner for Novel2Anima.

Design rules (V4 P2/PR-01):
- every migration is a file under sql/migrations with a stable version (stem);
- the SHA-256 of the exact bytes is stored with the applied version;
- a changed already-applied file aborts instead of silently drifting;
- each migration runs in a transaction, with foreign_keys=ON and busy_timeout;
- the live database path is refused unless the caller explicitly opts in;
- callers should pass a staging copy and keep a backup made before apply.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS n2a_schema_migration (
  version TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class MigrationError(RuntimeError):
    """Raised when a migration cannot be discovered, verified or applied."""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sha256: str
    sql: str


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def discover_migrations(directory: Path) -> list[Migration]:
    directory = directory.resolve()
    if not directory.is_dir():
        raise MigrationError(f"migrations directory not found: {directory}")
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        if path.name.startswith("_"):
            continue
        raw = path.read_bytes()
        migrations.append(
            Migration(
                version=path.stem,
                path=path,
                sha256=_sha256_bytes(raw),
                sql=raw.decode("utf-8"),
            )
        )
    if not migrations:
        raise MigrationError(f"no .sql migrations found in {directory}")
    versions = [item.version for item in migrations]
    if len(set(versions)) != len(versions):
        raise MigrationError("duplicate migration versions")
    return migrations


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", "", sql)
    return sql.strip()


def split_statements(sql: str) -> list[str]:
    """Split a migration into complete statements, keeping trigger bodies intact."""
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            if _strip_sql_comments(buffer):
                statements.append(buffer.strip())
            buffer = ""
    if buffer.strip() and _strip_sql_comments(buffer):
        # SQLite accepts a final statement without a semicolon; keep it explicit.
        statements.append(buffer.strip())
    if not statements:
        raise MigrationError("migration contains no executable statements")
    return statements


def is_live_database(path: Path) -> bool:
    resolved = path.resolve()
    return resolved.name.lower() == "novel_anima.db" and resolved.parent.name.lower() == "db"


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def ensure_migration_table(connection: sqlite3.Connection) -> None:
    connection.executescript(BOOTSTRAP_SQL)
    connection.commit()


def applied_migrations(connection: sqlite3.Connection) -> dict[str, str]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='n2a_schema_migration'"
    ).fetchone()
    if not exists:
        return {}
    return {
        row[0]: row[1]
        for row in connection.execute("SELECT version, sha256 FROM n2a_schema_migration ORDER BY version")
    }


def backup_database(source: Path, destination: Path) -> Path:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination:
        raise MigrationError("backup destination must differ from source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise MigrationError(f"backup destination already exists: {destination}")
    src = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()
    return destination


def _check_database(connection: sqlite3.Connection) -> dict:
    integrity = [row[0] for row in connection.execute("PRAGMA integrity_check").fetchmany(21)]
    foreign_keys = [list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchmany(21)]
    return {
        "integrity_check": integrity,
        "integrity_ok": integrity == ["ok"],
        "foreign_key_violations_first_20": foreign_keys,
        "foreign_key_ok": not foreign_keys,
    }


def apply_migrations(
    db_path: Path,
    migrations_dir: Path,
    *,
    allow_live: bool = False,
    backup_path: Path | None = None,
    dry_run: bool = False,
) -> dict:
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise MigrationError(f"database not found: {db_path}")
    if is_live_database(db_path) and not allow_live:
        raise MigrationError(
            "refusing to migrate the live database; use a staging copy "
            "(pass --allow-live only after an approved cutover plan)"
        )

    migrations = discover_migrations(migrations_dir)
    started = datetime.now(timezone.utc).isoformat()
    report: dict = {
        "database": str(db_path),
        "migrations_dir": str(migrations_dir.resolve()),
        "started_at_utc": started,
        "dry_run": bool(dry_run),
        "backup": None,
        "discovered": [{"version": item.version, "sha256": item.sha256} for item in migrations],
        "applied": [],
        "skipped": [],
        "pending": [],
        "pending_before": [],
        "checks": None,
        "status": "running",
    }

    if backup_path is not None and not dry_run:
        report["backup"] = str(backup_database(db_path, backup_path))

    connection = connect(db_path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        ensure_migration_table(connection)
        applied = applied_migrations(connection)
        pending: list[Migration] = []
        for migration in migrations:
            existing = applied.get(migration.version)
            if existing is not None:
                if existing != migration.sha256:
                    raise MigrationError(
                        f"checksum drift for {migration.version}: "
                        f"db={existing} file={migration.sha256}"
                    )
                report["skipped"].append({"version": migration.version, "sha256": migration.sha256})
            else:
                pending.append(migration)
                report["pending"].append({"version": migration.version, "sha256": migration.sha256})
                report["pending_before"].append({"version": migration.version, "sha256": migration.sha256})

        if dry_run:
            report["status"] = "dry_run"
            report["checks"] = _check_database(connection)
            return report

        for migration in pending:
            started_at = time.time()
            try:
                connection.execute("BEGIN IMMEDIATE")
                for statement in split_statements(migration.sql):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO n2a_schema_migration(version, sha256) VALUES (?, ?)",
                    (migration.version, migration.sha256),
                )
                connection.commit()
            except Exception as exc:  # noqa: BLE001 - surface a stable migration error
                connection.rollback()
                raise MigrationError(f"migration {migration.version} failed: {exc}") from exc
            report["applied"].append(
                {
                    "version": migration.version,
                    "sha256": migration.sha256,
                    "duration_seconds": round(time.time() - started_at, 3),
                }
            )

        report["pending"] = []
        report["checks"] = _check_database(connection)
        if not report["checks"]["integrity_ok"] or not report["checks"]["foreign_key_ok"]:
            report["status"] = "failed"
            raise MigrationError(
                "post-migration checks failed: "
                f"{report['checks']['integrity_check']} / "
                f"{report['checks']['foreign_key_violations_first_20']}"
            )
        report["status"] = "ok"
        return report
    finally:
        connection.close()
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Staging SQLite database (never the live DB)")
    parser.add_argument("--migrations", default="sql/migrations")
    parser.add_argument("--backup", help="Backup path created before apply")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-live", action="store_true", help="Only for an approved cutover drill")
    parser.add_argument("--report", help="Write the JSON report")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    backup_path = None
    if not args.no_backup and not args.dry_run:
        if args.backup:
            backup_path = Path(args.backup)
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = db_path.resolve().parent / f"pre_migration_{db_path.stem}_{stamp}.db"

    try:
        report = apply_migrations(
            db_path,
            Path(args.migrations),
            allow_live=args.allow_live,
            backup_path=backup_path,
            dry_run=args.dry_run,
        )
    except MigrationError as exc:
        failure = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error": str(exc),
            "database": str(db_path.resolve()),
            "migrations_dir": str(Path(args.migrations).resolve()),
            "dry_run": bool(args.dry_run),
        }
        if args.report:
            output = Path(args.report).resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"MIGRATION FAILED: {exc}")
        return 1

    if args.report:
        Path(args.report).resolve().parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).resolve().write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        "Migrations:",
        "status=",
        report["status"],
        "applied=",
        len(report["applied"]),
        "skipped=",
        len(report["skipped"]),
        "pending_before=",
        len(report["pending_before"]),
        "pending=",
        len(report["pending"]),
    )
    if report.get("checks"):
        print(
            "Checks: integrity=",
            report["checks"]["integrity_ok"],
            "foreign_keys=",
            report["checks"]["foreign_key_ok"],
        )
    if report.get("backup"):
        print("Backup:", report["backup"])
    return 0 if report["status"] in {"ok", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
