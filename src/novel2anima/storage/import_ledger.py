"""PR-03 external import ledger and runner.

The runner discovers source files below an explicit ``source_root``, hashes each
file once, assigns a stable classification + parser version, and writes one
idempotent ledger row per ``(relative_path, sha256, parser_version)``.  Each file
is parsed inside its own SQLite savepoint so a malformed file becomes a staged
``blocked`` row while the rest of the batch continues.

Important boundaries:

* no process working-directory lookup: the caller must supply ``source_root``;
* no live DB writes unless ``allow_live=True`` is explicitly passed;
* no ``asset_blob`` media writes in PR-03;
* no raw catalog cache is claimed as migrated merely because it was skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from novel2anima.storage.migrations import (
    backup_database,
    connect,
    is_live_database,
)

from .importers.base import (
    CLASS_ASSET,
    CLASS_CATALOG,
    CLASS_DATABASE,
    CLASS_GENERATED,
    CLASS_LLM_SCAFFOLD,
    CLASS_PLAN,
    CLASS_PROMPT,
    CLASS_REPORT,
    CLASS_REVIEW,
    CLASS_ROSTER,
    CLASS_SOURCE,
    CLASS_UNKNOWN,
    CLASS_WARDROBE,
    CLASS_WORKSPACE,
    ParseError,
    SourceFile,
    STATUS_BLOCKED,
    STATUS_IMPORTED,
    STATUS_SKIPPED,
    blocked,
    canonical_json,
    sha256_file,
    skipped,
    utc_now,
)
from .importers import (
    AssetParser,
    CatalogParser,
    PlanParser,
    PromptParser,
    ReviewParser,
    RosterParser,
    WardrobeParser,
)

IMPORT_VERSION = "pr-03/1"
POLICY_PARSER_VERSION = "policy/1"
MANIFEST_PATH = "data/sources/manifest.json"

PARSERS = {
    CLASS_PLAN: PlanParser(),
    CLASS_PROMPT: PromptParser(),
    CLASS_REVIEW: ReviewParser(),
    CLASS_WARDROBE: WardrobeParser(),
    CLASS_ROSTER: RosterParser(),
    CLASS_CATALOG: CatalogParser(),
    CLASS_ASSET: AssetParser(),
}

CLASS_PRIORITY = {
    CLASS_PLAN: 0,
    CLASS_ROSTER: 1,
    CLASS_WARDROBE: 2,
    CLASS_CATALOG: 3,
    CLASS_PROMPT: 4,
    CLASS_REVIEW: 5,
    CLASS_ASSET: 6,
    CLASS_SOURCE: 7,
    CLASS_WORKSPACE: 8,
    CLASS_REPORT: 9,
    CLASS_LLM_SCAFFOLD: 10,
    CLASS_DATABASE: 11,
    CLASS_GENERATED: 12,
    CLASS_UNKNOWN: 13,
}

TOP_LEVEL_EXCLUDED = {".git", ".pytest_cache", "dist", "evidence"}
ANY_LEVEL_EXCLUDED = {
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".venv",
    "node_modules",
}
REQUIRED_TABLES = {
    "project",
    "act",
    "shot",
    "shot_spec_revision",
    "project_document_revision",
    "character_profile",
    "shot_prompt_revision",
    "shot_prompt_spec",
    "qa_run",
    "qa_issue",
    "qa_run_source",
    "n2a_setting_revision",
    "source_snapshot",
    "reconciliation_item",
    "import_batch",
    "import_file_ledger",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"}


class ImportLedgerError(RuntimeError):
    """A global failure that must stop the batch before any commit."""


def classify_path(relative_path: str) -> str:
    rel = relative_path.replace("\\", "/")
    low = rel.lower()
    name = Path(rel).name
    suffix = Path(rel).suffix.lower()

    if rel.startswith("data/plans/") and low.endswith(".json"):
        return CLASS_PLAN
    if rel.startswith("act_specs/") and low.endswith(".json"):
        return CLASS_PLAN
    if rel.startswith("act_specs/"):
        return CLASS_SOURCE
    if rel.startswith("765/") and Path(rel).parent.as_posix() == "765" and name.startswith("plan-") and low.endswith(".json"):
        return CLASS_PLAN
    if rel.startswith("data/reviews/") and low.endswith(".json"):
        return CLASS_REVIEW
    if rel.startswith("data/wardrobe/") and low.endswith(".json"):
        return CLASS_WARDROBE
    if rel.startswith("data/characters/") and low.endswith(".json"):
        return CLASS_ROSTER
    if rel == "765/idolmaster-profiles-13.json":
        return CLASS_ROSTER
    if rel.startswith("data/sources/"):
        return CLASS_CATALOG
    if (rel.startswith("prompts/") or rel.startswith("765/prompts/")) and low.endswith(".txt"):
        return CLASS_PROMPT
    if suffix in IMAGE_EXTENSIONS:
        return CLASS_ASSET
    if rel == "db/import_report.json":
        return CLASS_REPORT
    if rel.startswith("db/") and name.startswith("novel_anima.db"):
        return CLASS_DATABASE
    if rel.startswith("llm/prompts/") or rel.startswith("llm/schemas/"):
        return CLASS_LLM_SCAFFOLD
    if rel.startswith("765/test-batch"):
        return CLASS_REPORT
    if rel.startswith("765/"):
        return CLASS_WORKSPACE
    if rel.startswith(("docs/", "src/", "etl/", "tests/", "sql/", "scripts/", "skills/", "act_tools/")):
        return CLASS_SOURCE
    if rel in {".gitattributes", ".gitignore", "README.md"}:
        return CLASS_SOURCE
    return CLASS_UNKNOWN


def parser_version_for(classification: str) -> str:
    parser = PARSERS.get(classification)
    return parser.parser_version if parser else POLICY_PARSER_VERSION


def _sort_key(source: SourceFile) -> tuple:
    classification = classify_path(source.relative_path)
    priority = CLASS_PRIORITY.get(classification, 99)
    if classification == CLASS_CATALOG:
        return (priority, 0 if source.relative_path == MANIFEST_PATH else 1, source.relative_path)
    return (priority, 0, source.relative_path)


def _excluded_directory(relative_dir: str) -> bool:
    if not relative_dir:
        return False
    parts = Path(relative_dir).parts
    if parts[0] in TOP_LEVEL_EXCLUDED:
        return True
    if any(part in ANY_LEVEL_EXCLUDED for part in parts):
        return True
    if len(parts) >= 2 and parts[0] == "db" and parts[1] == "backup":
        return True
    return False


def discover_sources(root: Path) -> tuple[list[SourceFile], list[str], list[str], list[dict]]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ImportLedgerError(f"source root is not a directory: {root}")
    sources: list[SourceFile] = []
    skipped_directories: list[str] = []
    skipped_symlinks: list[str] = []
    policy_skipped_files: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        current_rel = current.relative_to(root).as_posix()
        if current_rel == ".":
            current_rel = ""
        kept_dirs = []
        for dirname in sorted(dirnames):
            child = current / dirname
            child_rel = child.relative_to(root).as_posix()
            if _excluded_directory(child_rel):
                skipped_directories.append(child_rel)
                continue
            if child.is_symlink():
                skipped_symlinks.append(child_rel)
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current / filename
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                skipped_symlinks.append(rel)
                continue
            classification = classify_path(rel)
            if classification == CLASS_DATABASE:
                # The canonical SQLite file is the destination, not an external
                # source.  PR-00 already hashes it; PR-03 must not read/hash a
                # live DB that another process may have locked.
                policy_skipped_files.append(
                    {
                        "relative_path": rel,
                        "classification": classification,
                        "reason": "canonical database is the destination; hashed by PR-00 inventory, not an import source",
                    }
                )
                continue
            try:
                size = path.stat().st_size
                digest = sha256_file(path)
            except OSError as exc:
                raise ImportLedgerError(f"cannot read source file {rel}: {exc}") from exc
            sources.append(SourceFile(root=root, relative_path=rel, sha256=digest, size_bytes=size))

    if not sources:
        raise ImportLedgerError(f"no files found below source root: {root}")
    sources.sort(key=_sort_key)
    return sources, sorted(skipped_directories), sorted(skipped_symlinks), policy_skipped_files


def _policy_outcome(source: SourceFile, classification: str):
    if classification == CLASS_SOURCE:
        return skipped(
            "source_controlled_git_file",
            details={"policy": "source code, docs, SQL and tests stay in git; not data BLOBs"},
        )
    if classification == CLASS_WORKSPACE:
        return skipped(
            "legacy_workspace_not_imported",
            details={"policy": "tracked data is imported; loose workspace scripts/docs are historical"},
        )
    if classification == CLASS_REPORT:
        return skipped(
            "legacy_report_not_authoritative",
            details={"policy": "historical/generated reports are not canonical runtime inputs"},
        )
    if classification == CLASS_LLM_SCAFFOLD:
        if source.size_bytes == 0:
            return skipped(
                "empty_llm_scaffold",
                details={"policy": "zero-byte LLM placeholders must not become active templates"},
            )
        return skipped(
            "llm_scaffold_requires_pr_06",
            details={"policy": "LLM instructions require PR-06 validation/approval"},
        )
    if classification == CLASS_DATABASE:
        return skipped(
            "canonical_database_not_an_import_source",
            details={"policy": "the SQLite database is the destination, not an external source"},
        )
    if classification == CLASS_GENERATED:
        return skipped("generated_artifact", details={})
    return blocked(
        "unclassified_source",
        details={"suffix": Path(source.relative_path).suffix.lower()},
    )


def _process_source(source: SourceFile, connection: sqlite3.Connection):
    classification = classify_path(source.relative_path)
    parser = PARSERS.get(classification)
    if parser is None:
        return _policy_outcome(source, classification)
    return parser.parse(source, connection)


def _ledger_values(source: SourceFile, outcome, batch_id: int) -> tuple:
    verified = outcome.verified_sha256 or (source.sha256 if source.was_read else None)
    return (
        batch_id,
        source.relative_path,
        source.sha256,
        source.size_bytes,
        classify_path(source.relative_path),
        outcome.target_table,
        outcome.target_pk,
        parser_version_for(classify_path(source.relative_path)),
        outcome.status,
        outcome.exception,
        verified,
        canonical_json(outcome.details),
        utc_now() if outcome.status == STATUS_IMPORTED else None,
    )


def _upsert_ledger(connection: sqlite3.Connection, source: SourceFile, outcome, batch_id: int) -> None:
    connection.execute(
        """
        INSERT INTO import_file_ledger(
          import_batch_id, source_relative_path, source_sha256, source_bytes,
          classified_as, target_table, target_pk, parser_version, status,
          exception, verified_sha256, details_json, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_relative_path, source_sha256, parser_version) DO UPDATE SET
          import_batch_id = excluded.import_batch_id,
          source_bytes = excluded.source_bytes,
          classified_as = excluded.classified_as,
          target_table = excluded.target_table,
          target_pk = excluded.target_pk,
          status = excluded.status,
          exception = excluded.exception,
          verified_sha256 = excluded.verified_sha256,
          details_json = excluded.details_json,
          checked_at = CURRENT_TIMESTAMP,
          imported_at = CASE
            WHEN excluded.status = 'imported'
              THEN COALESCE(import_file_ledger.imported_at, CURRENT_TIMESTAMP)
            ELSE import_file_ledger.imported_at
          END
        """,
        _ledger_values(source, outcome, batch_id),
    )


def _exception_outcome(exc: Exception):
    if isinstance(exc, ParseError):
        return blocked(exc.code, details={"message": exc.message})
    if isinstance(exc, sqlite3.IntegrityError):
        return blocked("database_integrity_error", details={"message": str(exc)})
    return blocked("unexpected_error", details={"message": f"{type(exc).__name__}: {exc}"})


def _database_checks(connection: sqlite3.Connection) -> dict:
    quick = [row[0] for row in connection.execute("PRAGMA quick_check").fetchmany(21)]
    foreign_keys = [list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchmany(21)]
    return {
        "quick_check": quick,
        "quick_check_ok": quick == ["ok"],
        "foreign_key_violations_first_20": foreign_keys,
        "foreign_key_ok": not foreign_keys,
    }


def _require_tables(connection: sqlite3.Connection) -> None:
    present = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = sorted(REQUIRED_TABLES - present)
    if missing:
        raise ImportLedgerError(
            "import ledger schema is not ready; apply migrations 005-008 to the staging DB. "
            f"Missing tables: {', '.join(missing)}"
        )


def _summary(batch_key: str, counts: dict, skipped_directories: list[str], policy_skipped_files: list[dict]) -> dict:
    return {
        "import_version": IMPORT_VERSION,
        "batch_key": batch_key,
        "files": counts["files"],
        "bytes": counts["bytes"],
        "by_status": counts["by_status"],
        "by_classification": counts["by_classification"],
        "by_parser_version": counts["by_parser_version"],
        "blocked_files": len(counts["blocked"]),
        "excluded_directories": skipped_directories,
        "policy_skipped_files": policy_skipped_files,
    }


def run_import(
    db_path: Path,
    source_root: Path,
    *,
    dry_run: bool = False,
    allow_live: bool = False,
    batch_key: str | None = None,
) -> dict:
    db_path = db_path.resolve()
    source_root = source_root.resolve()
    if not db_path.is_file():
        raise ImportLedgerError(f"database not found: {db_path}")
    if is_live_database(db_path) and not allow_live:
        raise ImportLedgerError(
            "refusing to import into the live database; use a staging copy "
            "(pass allow_live=True only after an approved cutover plan)"
        )
    if not source_root.is_dir():
        raise ImportLedgerError(f"source root not found: {source_root}")

    sources, skipped_directories, skipped_symlinks, policy_skipped_files = discover_sources(source_root)
    batch_key = batch_key or (
        "legacy-import:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    started = utc_now()
    connection = connect(db_path)
    connection.row_factory = sqlite3.Row
    report: dict = {
        "schema_version": "n2a-import-report/1",
        "import_version": IMPORT_VERSION,
        "database": str(db_path),
        "source_root": str(source_root),
        "dry_run": bool(dry_run),
        "batch_key": batch_key,
        "batch_id": None,
        "started_at_utc": started,
        "finished_at_utc": None,
        "status": "running",
        "excluded_directories": skipped_directories,
        "skipped_symlinks": skipped_symlinks,
        "policy_skipped_files": policy_skipped_files,
        "counts": None,
        "files": [],
        "blocked": [],
        "checks": None,
        "error": None,
    }
    try:
        _require_tables(connection)
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            "INSERT INTO import_batch(import_key, status, summary_json) "
            "VALUES (?, 'running', '{}')",
            (batch_key,),
        )
        batch_id = cursor.lastrowid
        report["batch_id"] = batch_id

        by_status: Counter = Counter()
        by_classification: Counter = Counter()
        by_parser: Counter = Counter()
        target_rows: Counter = Counter()
        blocked_files: list[dict] = []
        file_payloads: list[dict] = []

        for index, source in enumerate(sources, start=1):
            classification = classify_path(source.relative_path)
            parser_version = parser_version_for(classification)
            connection.execute("SAVEPOINT file_import")
            try:
                outcome = _process_source(source, connection)
                _upsert_ledger(connection, source, outcome, batch_id)
                connection.execute("RELEASE SAVEPOINT file_import")
            except Exception as exc:  # noqa: BLE001 - every file has a staged status
                connection.execute("ROLLBACK TO SAVEPOINT file_import")
                connection.execute("RELEASE SAVEPOINT file_import")
                outcome = _exception_outcome(exc)
                _upsert_ledger(connection, source, outcome, batch_id)

            by_status[outcome.status] += 1
            by_classification[classification] += 1
            by_parser[parser_version] += 1
            if outcome.status == STATUS_IMPORTED and outcome.target_table:
                inserted = outcome.details.get("inserted")
                if inserted is None:
                    inserted = outcome.details.get("snapshots_inserted", 1)
                target_rows[outcome.target_table] += int(inserted)
            payload = {
                "relative_path": source.relative_path,
                "sha256": source.sha256,
                "bytes": source.size_bytes,
                "classification": classification,
                "parser_version": parser_version,
                "status": outcome.status,
                "target_table": outcome.target_table,
                "target_pk": outcome.target_pk,
                "exception": outcome.exception,
                "verified_sha256": outcome.verified_sha256
                or (source.sha256 if source.was_read else None),
                "details": outcome.details,
            }
            file_payloads.append(payload)
            if outcome.status == STATUS_BLOCKED:
                blocked_files.append(
                    {
                        "relative_path": source.relative_path,
                        "classification": classification,
                        "exception": outcome.exception,
                        "details": outcome.details,
                    }
                )

        counts = {
            "files": len(sources),
            "bytes": sum(source.size_bytes for source in sources),
            "by_status": dict(sorted(by_status.items())),
            "by_classification": dict(sorted(by_classification.items())),
            "by_parser_version": dict(sorted(by_parser.items())),
            "target_rows": dict(sorted(target_rows.items())),
            "blocked": blocked_files,
        }
        summary_json = canonical_json(
            _summary(batch_key, counts, skipped_directories, policy_skipped_files)
        )
        connection.execute(
            "UPDATE import_batch SET status = 'succeeded', completed_at = ?, summary_json = ? "
            "WHERE id = ?",
            (utc_now(), summary_json, batch_id),
        )
        checks = _database_checks(connection)
        checks["ledger_rows"] = connection.execute(
            "SELECT count(*) FROM import_file_ledger"
        ).fetchone()[0]
        checks["ledger_distinct_paths"] = connection.execute(
            "SELECT count(DISTINCT source_relative_path) FROM import_file_ledger"
        ).fetchone()[0]
        checks["batch_status"] = "succeeded"
        checks["persisted"] = not dry_run
        if not checks["quick_check_ok"] or not checks["foreign_key_ok"]:
            raise ImportLedgerError(
                "post-import database checks failed: "
                f"{checks['quick_check']} / {checks['foreign_key_violations_first_20']}"
            )
        if dry_run:
            connection.rollback()
            report["status"] = "dry_run"
        else:
            connection.commit()
            report["status"] = "ok"
        report["counts"] = counts
        report["files"] = file_payloads
        report["blocked"] = blocked_files
        report["checks"] = checks
    except Exception as exc:
        connection.rollback()
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        connection.close()
        report["finished_at_utc"] = utc_now()
    return report


def verify_ledger(db_path: Path, source_root: Path) -> dict:
    db_path = db_path.resolve()
    source_root = source_root.resolve()
    if not db_path.is_file():
        raise ImportLedgerError(f"database not found: {db_path}")
    sources, skipped_directories, skipped_symlinks, policy_skipped_files = discover_sources(source_root)
    connection = connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _require_tables(connection)
        checks = _database_checks(connection)
        rows = connection.execute(
            "SELECT source_relative_path, source_sha256, source_bytes, classified_as, "
            "parser_version, status, exception FROM import_file_ledger"
        ).fetchall()
        current: dict[str, SourceFile] = {source.relative_path: source for source in sources}
        indexed = {
            (row["source_relative_path"], row["source_sha256"], row["parser_version"]): row
            for row in rows
        }
        missing: list[dict] = []
        mismatched: list[dict] = []
        for source in sources:
            classification = classify_path(source.relative_path)
            parser_version = parser_version_for(classification)
            row = indexed.get((source.relative_path, source.sha256, parser_version))
            if row is None:
                missing.append(
                    {
                        "relative_path": source.relative_path,
                        "sha256": source.sha256,
                        "parser_version": parser_version,
                    }
                )
                continue
            if row["source_bytes"] != source.size_bytes or row["classified_as"] != classification:
                mismatched.append(
                    {
                        "relative_path": source.relative_path,
                        "expected_bytes": source.size_bytes,
                        "ledger_bytes": row["source_bytes"],
                        "expected_classification": classification,
                        "ledger_classification": row["classified_as"],
                    }
                )
        stale = [
            row["source_relative_path"]
            for row in rows
            if row["source_relative_path"] not in current
        ]
        checks["ledger_rows"] = len(rows)
        checks["current_sources"] = len(sources)
        checks["missing"] = missing
        checks["mismatched"] = mismatched
        checks["stale_paths"] = stale
        status = (
            "ok"
            if not missing
            and not mismatched
            and not stale
            and checks["quick_check_ok"]
            and checks["foreign_key_ok"]
            else "failed"
        )
        return {
            "schema_version": "n2a-import-ledger-verification/1",
            "database": str(db_path),
            "source_root": str(source_root),
            "status": status,
            "excluded_directories": skipped_directories,
            "skipped_symlinks": skipped_symlinks,
            "policy_skipped_files": policy_skipped_files,
            "checks": checks,
            "by_status": {
                status: count
                for status, count in connection.execute(
                    "SELECT status, count(*) FROM import_file_ledger GROUP BY status"
                )
            },
            "by_classification": {
                classification: count
                for classification, count in connection.execute(
                    "SELECT classified_as, count(*) FROM import_file_ledger "
                    "GROUP BY classified_as"
                )
            },
        }
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Staging SQLite database (never the live DB)")
    parser.add_argument(
        "--source-root",
        required=True,
        help="Explicit root for data/plans, prompts/, 765/, db/import_report.json, etc.",
    )
    parser.add_argument("--report", help="Write the JSON import report")
    parser.add_argument("--dry-run", action="store_true", help="Roll back all writes after validating")
    parser.add_argument("--allow-live", action="store_true", help="Only for an approved cutover drill")
    parser.add_argument("--batch-key", help="Override the generated idempotency batch key")
    parser.add_argument("--backup", help="Backup created before writing")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    backup_path = None
    if not args.no_backup and not args.dry_run:
        if args.backup:
            backup_path = Path(args.backup)
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = db_path.resolve().parent / f"pre_import_{db_path.stem}_{stamp}.db"

    try:
        if backup_path is not None:
            backup_database(db_path, backup_path)
        report = run_import(
            db_path,
            Path(args.source_root),
            dry_run=args.dry_run,
            allow_live=args.allow_live,
            batch_key=args.batch_key,
        )
    except Exception as exc:  # noqa: BLE001 - CLI must emit a durable failure report
        failure = {
            "schema_version": "n2a-import-report/1",
            "import_version": IMPORT_VERSION,
            "status": "failed",
            "database": str(db_path.resolve()),
            "source_root": str(Path(args.source_root).resolve()),
            "dry_run": bool(args.dry_run),
            "error": f"{type(exc).__name__}: {exc}",
            "generated_at_utc": utc_now(),
        }
        if args.report:
            output = Path(args.report).resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"IMPORT FAILED: {exc}")
        return 1

    if args.report:
        output = Path(args.report).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = report.get("counts") or {}
    print(
        "Import:",
        "status=",
        report.get("status"),
        "batch=",
        report.get("batch_id"),
        "files=",
        counts.get("files"),
        "by_status=",
        counts.get("by_status"),
        "blocked=",
        len(report.get("blocked") or []),
    )
    if report.get("checks"):
        print(
            "Checks: quick_check=",
            report["checks"].get("quick_check_ok"),
            "foreign_keys=",
            report["checks"].get("foreign_key_ok"),
            "ledger_rows=",
            report["checks"].get("ledger_rows"),
        )
    if backup_path is not None:
        print("Backup:", backup_path)
    return 0 if report.get("status") in {"ok", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
