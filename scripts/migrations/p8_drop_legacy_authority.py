"""PR-08 data-preserving rebuild: remove remaining legacy authority.

Removes:

* ``character_profile.identity_json`` / ``outfit_json``;
* ``shot.character_id`` / ``shot_spec_json``;
* ``act_publication`` (prompt files are export copies, not authority).

Before dropping columns, legacy JSON is copied into canonical revisions when a
revision is absent. Existing canonical rows are never overwritten. Run on a
staging DB first.

Usage:
  python scripts/migrations/p8_drop_legacy_authority.py --db PATH --backup PATH
  python scripts/migrations/p8_drop_legacy_authority.py --db PATH --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

VERSION = "012_p8_no_legacy_authority"

NEW_CHARACTER = """
CREATE TABLE character_profile_new (
 id INTEGER PRIMARY KEY,
 project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
 code TEXT NOT NULL,
 UNIQUE(project_id,code)
)
"""

NEW_SHOT = """
CREATE TABLE shot_new (
 id INTEGER PRIMARY KEY,
 act_id INTEGER NOT NULL REFERENCES act(id) ON DELETE CASCADE,
 shot_no INTEGER NOT NULL CHECK(shot_no > 0),
 action_concept_id INTEGER REFERENCES visual_concept(id),
 expression_concept_id INTEGER REFERENCES visual_concept(id),
 pose_concept_id INTEGER REFERENCES visual_concept(id),
 camera_concept_id INTEGER REFERENCES visual_concept(id),
 signature TEXT,
 content_mode TEXT NOT NULL DEFAULT 'sfw'
  CHECK(content_mode IN ('sfw','nsfw')),
 status TEXT NOT NULL DEFAULT 'planned'
  CHECK(status IN ('draft','planned','approved','generated','rejected','locked')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(act_id,shot_no)
)
"""


def script_sha() -> str:
    return hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def _objects(con: sqlite3.Connection, table: str) -> list[str]:
    rows = con.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type='index'"
        " AND sql IS NOT NULL ORDER BY name",
        (table,),
    ).fetchall()
    return [row[0] for row in rows if "character_id" not in row[0]]


def _triggers_and_views(con: sqlite3.Connection) -> list[tuple[str, str, str]]:
    rows = con.execute(
        "SELECT type,name,sql FROM sqlite_master"
        " WHERE type IN ('trigger','view') AND sql IS NOT NULL ORDER BY rowid"
    ).fetchall()
    return [(str(kind), str(name), str(sql)) for kind, name, sql in rows]


def _backfill(con: sqlite3.Connection) -> None:
    """Copy legacy JSON into canonical revisions before columns disappear."""
    for cid, raw in con.execute(
        "SELECT id,identity_json FROM character_profile WHERE NOT EXISTS"
        " (SELECT 1 FROM character_identity_revision r WHERE r.character_id=character_profile.id)"
    ).fetchall():
        body = _json(json.loads(raw or "{}"))
        con.execute(
            "INSERT INTO character_identity_revision"
            "(character_id,revision,identity_json,sha256,status)"
            " VALUES(?,1,?,?,'approved')",
            (cid, body, _sha(body)),
        )

    for cid, raw in con.execute(
        "SELECT id,outfit_json FROM character_profile WHERE NOT EXISTS"
        " (SELECT 1 FROM outfit_revision r WHERE r.character_id=character_profile.id)"
    ).fetchall():
        body = _json(json.loads(raw or "{}"))
        con.execute(
            "INSERT INTO outfit_revision"
            "(character_id,revision,spec_json,spec_sha256,status)"
            " VALUES(?,1,?,?,'approved')",
            (cid, body, _sha(body)),
        )

    for sid, act_id, raw in con.execute(
        "SELECT id,act_id,shot_spec_json FROM shot WHERE NOT EXISTS"
        " (SELECT 1 FROM shot_spec_revision r WHERE r.shot_id=shot.id)"
    ).fetchall():
        body = _json(json.loads(raw or "{}"))
        con.execute(
            "INSERT INTO shot_spec_revision"
            "(shot_id,revision,spec_json,spec_sha256,status)"
            " VALUES(?,1,?,?,'approved')",
            (sid, body, _sha(body)),
        )

    for sid, character_id in con.execute(
        "SELECT s.id,s.character_id FROM shot s WHERE s.character_id IS NOT NULL"
        " AND NOT EXISTS (SELECT 1 FROM shot_participant p WHERE p.shot_id=s.id)"
    ).fetchall():
        con.execute(
            "INSERT INTO shot_participant(shot_id,character_id,slot_no,scene_role)"
            " VALUES(?,?,1,'subject')",
            (sid, character_id),
        )


def rebuild(
    db_path: pathlib.Path,
    *,
    allow_live: bool = False,
    backup: pathlib.Path | None = None,
) -> dict:
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
        char_cols = _columns(con, "character_profile")
        shot_cols = _columns(con, "shot")
        publication = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='act_publication'"
        ).fetchone()
        drop_char = {"identity_json", "outfit_json"} & char_cols
        drop_shot = {"character_id", "shot_spec_json"} & shot_cols
        if not drop_char and not drop_shot and not publication:
            con.execute(
                "INSERT OR REPLACE INTO n2a_schema_migration(version,sha256) VALUES(?,?)",
                (VERSION, script_sha()),
            )
            con.commit()
            return {
                "status": "already_clean",
                "version": VERSION,
                "database": str(db_path),
                "sha256": script_sha(),
            }

        char_count = int(con.execute("SELECT count(*) FROM character_profile").fetchone()[0])
        shot_count = int(con.execute("SELECT count(*) FROM shot").fetchone()[0])
        pub_count = int(con.execute("SELECT count(*) FROM act_publication").fetchone()[0]) if publication else 0
        char_objects = _objects(con, "character_profile")
        shot_objects = _objects(con, "shot")
        guarded_objects = _triggers_and_views(con)

        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN IMMEDIATE")
        for kind, name, _sql in reversed(guarded_objects):
            if kind == "view":
                con.execute(f'DROP VIEW "{name}"')
            else:
                con.execute(f'DROP TRIGGER "{name}"')
        _backfill(con)

        if drop_char:
            con.execute(NEW_CHARACTER)
            con.execute(
                "INSERT INTO character_profile_new(id,project_id,code)"
                " SELECT id,project_id,code FROM character_profile"
            )
            con.execute("DROP TABLE character_profile")
            con.execute("ALTER TABLE character_profile_new RENAME TO character_profile")
            for sql in char_objects:
                con.execute(sql)

        if drop_shot:
            con.execute(NEW_SHOT)
            con.execute(
                "INSERT INTO shot_new(id,act_id,shot_no,action_concept_id,"
                "expression_concept_id,pose_concept_id,camera_concept_id,signature,"
                "content_mode,status,created_at)"
                " SELECT id,act_id,shot_no,action_concept_id,expression_concept_id,"
                "pose_concept_id,camera_concept_id,signature,content_mode,status,created_at"
                " FROM shot"
            )
            con.execute("DROP TABLE shot")
            con.execute("ALTER TABLE shot_new RENAME TO shot")
            for sql in shot_objects:
                con.execute(sql)

        if publication:
            con.execute("DROP TABLE act_publication")

        for kind, _name, sql in guarded_objects:
            if kind == "trigger":
                con.execute(sql)
        for kind, _name, sql in guarded_objects:
            if kind == "view":
                con.execute(sql)

        con.execute(
            "INSERT OR REPLACE INTO n2a_schema_migration(version,sha256) VALUES(?,?)",
            (VERSION, script_sha()),
        )
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")

        quick = con.execute("PRAGMA quick_check").fetchone()[0]
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        new_char_count = int(con.execute("SELECT count(*) FROM character_profile").fetchone()[0])
        new_shot_count = int(con.execute("SELECT count(*) FROM shot").fetchone()[0])
        if quick != "ok":
            raise RuntimeError(f"quick_check after rebuild: {quick}")
        if fk:
            raise RuntimeError(f"foreign key violations after rebuild: {fk[:5]}")
        if (char_count, shot_count) != (new_char_count, new_shot_count):
            raise RuntimeError(
                "row count drift: character %s->%s shot %s->%s"
                % (char_count, new_char_count, shot_count, new_shot_count)
            )
        return {
            "status": "ok",
            "version": VERSION,
            "database": str(db_path),
            "dropped_character_columns": sorted(drop_char),
            "dropped_shot_columns": sorted(drop_shot),
            "dropped_act_publication": bool(publication),
            "counts": {
                "character_profile": new_char_count,
                "shot": new_shot_count,
                "act_publication_removed": pub_count,
            },
            "quick_check": quick,
            "foreign_key_errors": len(fk),
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
        try:
            print({
                "database": str(args.db),
                "character_columns": sorted(_columns(con, "character_profile")),
                "shot_columns": sorted(_columns(con, "shot")),
                "act_publication": bool(con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='act_publication'"
                ).fetchone()),
                "counts": {
                    "character_profile": con.execute("SELECT count(*) FROM character_profile").fetchone()[0],
                    "shot": con.execute("SELECT count(*) FROM shot").fetchone()[0],
                },
            })
        finally:
            con.close()
        return 0
    print(rebuild(args.db, allow_live=args.allow_live, backup=args.backup))
    return 0


if __name__ == "__main__":
    sys.exit(main())
