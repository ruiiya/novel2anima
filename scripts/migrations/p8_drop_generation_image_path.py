"""PR-08 data-preserving rebuild: remove generation.image_path.

The render bytes already live in asset_blob; image_path is a legacy filesystem
pointer and must not remain authoritative. Run on a staging DB first.

Usage:
  python scripts/migrations/p8_drop_generation_image_path.py --db PATH
  python scripts/migrations/p8_drop_generation_image_path.py --db PATH --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

VERSION = "011_p8_generation_no_image_path"
NEW_SCHEMA = """
CREATE TABLE generation_new (
 id INTEGER PRIMARY KEY,
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE CASCADE,
 model_profile_id INTEGER NOT NULL REFERENCES model_profile(id),
 prompt TEXT NOT NULL,
 seed INTEGER,
 image_sha256 TEXT,
 evaluation_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(evaluation_json)),
 decision TEXT NOT NULL DEFAULT 'pending'
  CHECK(decision IN ('pending','approved','rejected')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def script_sha() -> str:
    return hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()


def rebuild(db_path: pathlib.Path, *, allow_live: bool = False, backup: pathlib.Path | None = None) -> dict:
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise SystemExit(f"database not found: {db_path}")
    if db_path.name == "novel_anima.db" and not allow_live:
        raise SystemExit("refusing live db; pass --allow-live only with approval")
    if backup is not None:
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
    con = sqlite3.connect(db_path)
    try:
        columns = [row[1] for row in con.execute("PRAGMA table_info(generation)")]
        if "image_path" not in columns:
            return {"status": "already_clean", "version": VERSION, "database": str(db_path)}
        count_before = int(con.execute("SELECT count(*) FROM generation").fetchone()[0])
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        con.execute(NEW_SCHEMA)
        con.execute(
            "INSERT INTO generation_new"
            "(id,shot_id,model_profile_id,prompt,seed,image_sha256,evaluation_json,decision,created_at)"
            " SELECT id,shot_id,model_profile_id,prompt,seed,image_sha256,evaluation_json,decision,created_at"
            " FROM generation"
        )
        count_after = int(con.execute("SELECT count(*) FROM generation_new").fetchone()[0])
        if count_before != count_after:
            raise RuntimeError(f"generation row count drift: {count_before} -> {count_after}")
        con.execute("DROP TRIGGER IF EXISTS trg_generation_provenance_insert")
        con.execute("DROP TRIGGER IF EXISTS trg_generation_provenance_update")
        con.execute("DROP TABLE generation")
        con.execute("ALTER TABLE generation_new RENAME TO generation")
        con.execute("CREATE INDEX IF NOT EXISTS idx_generation_shot ON generation(shot_id,created_at)")
        con.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_generation_shot_frozen BEFORE UPDATE OF shot_id ON generation"
            " WHEN OLD.shot_id<>NEW.shot_id"
            " BEGIN SELECT RAISE(ABORT,'render cannot be reassigned to another shot'); END"
        )
        con.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_generation_provenance_insert"
            " BEFORE INSERT ON generation_provenance"
            " WHEN (SELECT shot_id FROM generation WHERE id=NEW.generation_id)"
            "   <> (SELECT shot_id FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id)"
            " BEGIN SELECT RAISE(ABORT,'generation and prompt must belong to same shot'); END"
        )
        con.execute(
            "CREATE TRIGGER IF NOT EXISTS trg_generation_provenance_update"
            " BEFORE UPDATE OF generation_id,shot_prompt_revision_id ON generation_provenance"
            " WHEN (SELECT shot_id FROM generation WHERE id=NEW.generation_id)"
            "   <> (SELECT shot_id FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id)"
            " BEGIN SELECT RAISE(ABORT,'generation and prompt must belong to same shot'); END"
        )
        con.execute(
            "INSERT OR REPLACE INTO n2a_schema_migration(version,sha256) VALUES(?,?)",
            (VERSION, script_sha()),
        )
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            raise RuntimeError(f"foreign key violations after rebuild: {fk[:5]}")
        return {
            "status": "ok",
            "version": VERSION,
            "database": str(db_path),
            "count_before": count_before,
            "count_after": count_after,
            "sha256": script_sha(),
        }
    except Exception:
        con.rollback()
        con.execute("PRAGMA foreign_keys=ON")
        raise
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, type=pathlib.Path)
    ap.add_argument("--backup", type=pathlib.Path)
    ap.add_argument("--allow-live", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run:
        con = sqlite3.connect(args.db)
        columns = [row[1] for row in con.execute("PRAGMA table_info(generation)")]
        count = con.execute("SELECT count(*) FROM generation").fetchone()[0]
        con.close()
        print({"database": str(args.db), "generation_rows": count, "has_image_path": "image_path" in columns})
        return 0
    print(rebuild(args.db, allow_live=args.allow_live, backup=args.backup))
    return 0


if __name__ == "__main__":
    sys.exit(main())
