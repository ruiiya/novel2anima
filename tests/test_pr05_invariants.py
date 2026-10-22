"""PR-05 solo/duo interaction, reversible wardrobe and continuity invariants."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.storage.domain_repository import (  # noqa: E402
    DomainError,
    add_continuity_assertion,
    add_interaction,
    add_participant,
    bind_outfit,
    create_identity_revision,
    create_outfit_revision,
    create_shot_spec_revision,
    effective_continuity,
)
from novel2anima.storage.migrations import apply_migrations  # noqa: E402

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_db(root: Path) -> Path:
    db = root / "staging.db"
    con = sqlite3.connect(db)
    con.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
    con.commit()
    con.close()
    migrations = root / "migrations"
    migrations.mkdir()
    for name in ("005_db_first.sql", "006_normalization.sql", "007_reconciliation_queue.sql"):
        shutil.copy2(ROOT / "sql/migrations" / name, migrations / name)
    report = apply_migrations(db, migrations, backup_path=root / "pre.db")
    assert report["status"] == "ok", report
    return db


def fixture(db: Path) -> None:
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("INSERT INTO project(id,title) VALUES(1,'P1')")
        con.execute("INSERT INTO project(id,title) VALUES(2,'P2')")
        con.executemany(
            "INSERT INTO character_profile(id,project_id,code,identity_json,outfit_json)"
            " VALUES(?,?,?,?,?)",
            [
                (1, 1, "ALPHA", dumps({"name": "Alpha"}), "{}"),
                (2, 1, "BETA", dumps({"name": "Beta"}), "{}"),
                (3, 2, "GAMMA", dumps({"name": "Gamma"}), "{}"),
            ],
        )
        con.execute(
            "INSERT INTO act(id,project_id,act_no,title,revision,status)"
            " VALUES(1,1,1,'Act',1,'planned')"
        )
        con.executemany(
            "INSERT INTO shot(id,act_id,shot_no,character_id,shot_spec_json,status)"
            " VALUES(?,?,?,?,?,?)",
            [
                (1, 1, 1, 1, dumps({"participants": ["ALPHA", "BETA"]}), "planned"),
                (2, 1, 2, 1, dumps({"participants": ["ALPHA"]}), "planned"),
            ],
        )
        con.commit()
    finally:
        con.close()


class DomainInvariants(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = create_db(Path(self.temp.name))
        fixture(self.db)
        self.con = sqlite3.connect(self.db)
        self.con.execute("PRAGMA foreign_keys=ON")

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def test_solo_and_duo_participants_are_explicit(self):
        add_participant(self.con, 1, 1, slot_no=1)
        add_participant(self.con, 1, 2, slot_no=2)
        add_participant(self.con, 2, 1, slot_no=1)
        self.con.commit()
        self.assertEqual(
            self.con.execute("SELECT shot_id,character_id FROM shot_participant ORDER BY 1,2").fetchall(),
            [(1, 1), (1, 2), (2, 1)],
        )

    def test_cross_project_participant_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            add_participant(self.con, 1, 3, slot_no=1)
        self.con.rollback()

    def test_headpat_direction_is_not_inferred(self):
        add_participant(self.con, 1, 1, slot_no=1)
        add_participant(self.con, 1, 2, slot_no=2)
        with self.assertRaises(DomainError):
            add_interaction(self.con, 1, 2, None, "headpat")
        with self.assertRaises(DomainError):
            add_interaction(self.con, 1, 3, 1, "headpat")
        first = add_interaction(self.con, 1, 2, 1, "headpat", sort_order=1)
        reverse = add_interaction(self.con, 1, 1, 2, "headpat", sort_order=2)
        self.con.commit()
        rows = self.con.execute(
            "SELECT id,actor_character_id,target_character_id FROM shot_interaction ORDER BY id"
        ).fetchall()
        self.assertEqual(rows, [(first, 2, 1), (reverse, 1, 2)])

    def test_outfit_revision_drift_keeps_anchors_and_parent(self):
        add_participant(self.con, 1, 1, slot_no=1)
        add_participant(self.con, 1, 2, slot_no=2)
        add_participant(self.con, 2, 1, slot_no=1)
        first = create_outfit_revision(
            self.con,
            1,
            {"name": "uniform"},
            [
                {"item_code": "top", "slot": "upper", "garment_type": "shirt",
                 "base_color": "white", "details": {"buttons": 4}},
                {"item_code": "skirt", "slot": "lower", "garment_type": "skirt",
                 "material": "wool"},
            ],
            status="approved",
        )
        bind_outfit(self.con, 1, 1, first)
        bind_outfit(self.con, 2, 1, first)
        self.con.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute(
                "UPDATE outfit_revision SET spec_json=? WHERE id=?",
                (dumps({"name": "changed"}), first),
            )
        self.con.rollback()
        second = create_outfit_revision(
            self.con,
            1,
            {"name": "uniform torn"},
            [{"item_code": "top", "slot": "upper", "garment_type": "shirt",
              "base_color": "white", "details": {"tear": "left"}}],
            status="approved",
        )
        bind_outfit(self.con, 2, 1, second)
        self.con.commit()
        rows = self.con.execute(
            "SELECT shot_id,outfit_revision_id FROM shot_outfit_binding"
            " WHERE character_id=1 ORDER BY shot_id"
        ).fetchall()
        self.assertEqual(rows, [(1, first), (2, second)])

    def test_identity_and_spec_revisions_are_immutable(self):
        identity = create_identity_revision(
            self.con, 1, {"name": "Alpha", "hair": "black"}, status="approved"
        )
        spec = create_shot_spec_revision(
            self.con, 2, {"participants": ["ALPHA"], "action": "standing"}, status="approved"
        )
        self.con.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute(
                "UPDATE character_identity_revision SET identity_json=? WHERE id=?",
                (dumps({"name": "changed"}), identity),
            )
        self.con.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute(
                "UPDATE shot_spec_revision SET spec_json=? WHERE id=?",
                (dumps({"participants": ["ALPHA"], "action": "lying"}), spec),
            )

    def test_user_continuity_outranks_inference(self):
        add_participant(self.con, 2, 1, slot_no=1)
        add_continuity_assertion(
            self.con, 2, 1, "outfit:stage", source="inference",
            value_tag_id=None, state="approved", confidence=0.8,
        )
        add_continuity_assertion(
            self.con, 2, 1, "outfit:stage", source="user",
            value_tag_id=None, state="approved", confidence=1.0,
        )
        self.con.commit()
        effective = effective_continuity(self.con, 2)
        self.assertEqual(effective[(1, "outfit:stage")]["source"], "user")


if __name__ == "__main__":
    unittest.main()
