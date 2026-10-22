"""PR-08: data-preserving image_path cleanup and 23-table disposition."""
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
sys.path.insert(0, str(ROOT / "scripts/migrations"))
sys.path.insert(0, str(ROOT / "scripts/qa"))

from p8_drop_generation_image_path import rebuild  # noqa: E402
from p8_drop_legacy_authority import rebuild as rebuild_authority  # noqa: E402
from verify_p8_disposition import report  # noqa: E402
from novel2anima.storage.migrations import apply_migrations  # noqa: E402

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


def create_db(root: Path) -> Path:
    db = root / "staging.db"
    con = sqlite3.connect(db)
    con.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
    con.commit()
    con.close()
    migrations = root / "migrations"
    migrations.mkdir()
    for name in (
        "005_db_first.sql", "006_normalization.sql", "007_reconciliation_queue.sql",
        "009_llm_registry.sql", "010_prompt_pinning.sql",
    ):
        shutil.copy2(ROOT / "sql/migrations" / name, migrations / name)
    assert apply_migrations(db, migrations, backup_path=root / "pre.db")["status"] == "ok"
    return db


class Cleanup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = create_db(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_rebuild_preserves_rows_and_removes_image_path(self):
        con = sqlite3.connect(self.db)
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("INSERT INTO project(id,title) VALUES(1,'P1')")
        con.execute(
            "INSERT INTO character_profile(id,project_id,code) VALUES(1,1,'A')"
        )
        con.execute("INSERT INTO act(id,project_id,act_no,title) VALUES(1,1,1,'A')")
        con.execute("INSERT INTO shot(id,act_id,shot_no) VALUES(1,1,1)")
        con.execute(
            "INSERT INTO model_profile(id,code,model_name) VALUES(1,'m','m')"
        )
        con.execute(
            "INSERT INTO generation(id,shot_id,model_profile_id,prompt,seed,image_path,"
            "image_sha256,evaluation_json,decision)"
            " VALUES(1,1,1,'p',7,'old/path.png','abc','{}','approved')"
        )
        con.commit()
        con.close()

        result = rebuild(self.db)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count_before"], result["count_after"])

        con = sqlite3.connect(self.db)
        columns = [row[1] for row in con.execute("PRAGMA table_info(generation)")]
        self.assertNotIn("image_path", columns)
        row = con.execute(
            "SELECT id,seed,image_sha256,decision FROM generation"
        ).fetchone()
        self.assertEqual(row, (1, 7, "abc", "approved"))
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(
            con.execute("SELECT count(*) FROM n2a_schema_migration WHERE version=?",
                        ("011_p8_generation_no_image_path",)).fetchone()[0],
            1,
        )
        self.assertEqual(
            con.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='trigger'"
                " AND name IN ('trg_generation_shot_frozen','trg_generation_provenance_insert')"
            ).fetchone()[0],
            2,
        )
        con.close()

    def test_authority_rebuild_removes_legacy_columns_and_publication(self):
        con = sqlite3.connect(self.db)
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("INSERT INTO project(id,title) VALUES(1,'P1')")
        con.execute("INSERT INTO act(id,project_id,act_no,title) VALUES(1,1,1,'A1')")
        con.execute(
            "INSERT INTO character_profile(id,project_id,code,identity_json,outfit_json)"
            " VALUES(1,1,'C1','{\"name\":\"C1\"}','{\"default\":[\"dress:1\"]}')"
        )
        con.execute(
            "INSERT INTO shot(id,act_id,shot_no,character_id,shot_spec_json)"
            " VALUES(1,1,1,1,'{\"participants\":[{\"code\":\"C1\"}]}')"
        )
        con.commit()
        con.close()

        self.assertEqual(rebuild(self.db)["status"], "ok")
        result = rebuild_authority(self.db)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["dropped_act_publication"])

        con = sqlite3.connect(self.db)
        self.assertEqual(
            [row[1] for row in con.execute("PRAGMA table_info(character_profile)")],
            ["id", "project_id", "code"],
        )
        self.assertNotIn(
            "shot_spec_json", [row[1] for row in con.execute("PRAGMA table_info(shot)")]
        )
        self.assertNotIn(
            "character_id", [row[1] for row in con.execute("PRAGMA table_info(shot)")]
        )
        self.assertEqual(
            con.execute(
                "SELECT count(*) FROM sqlite_master"
                " WHERE type='table' AND name='act_publication'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            json.loads(con.execute(
                "SELECT identity_json FROM character_identity_revision"
            ).fetchone()[0]),
            {"name": "C1"},
        )
        self.assertEqual(
            json.loads(con.execute("SELECT spec_json FROM outfit_revision").fetchone()[0]),
            {"default": ["dress:1"]},
        )
        self.assertEqual(
            json.loads(con.execute("SELECT spec_json FROM shot_spec_revision").fetchone()[0]),
            {"participants": [{"code": "C1"}]},
        )
        self.assertEqual(con.execute("SELECT count(*) FROM shot_participant").fetchone()[0], 1)
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(con.execute("PRAGMA quick_check").fetchone()[0], "ok")
        con.close()

        data = report(self.db)
        self.assertTrue(data["clean"], [
            row["table"] for row in data["tables"]
            if not row["present"] or any(row["duplicate_columns"].values())
        ])

    def test_disposition_covers_every_legacy_table(self):
        data = report(self.db)
        self.assertEqual(data["legacy_table_count"], 23)
        self.assertEqual(data["disposition_count"], 23)
        self.assertEqual(data["missing_from_csv"], [])
        self.assertEqual(data["missing_disposition"], [])
        generation = next(row for row in data["tables"] if row["table"] == "generation")
        self.assertEqual(generation["duplicate_columns"], {"image_path": True})
        docs = (ROOT / "docs/v4/P8_LEGACY_DISPOSITION.md").read_text(encoding="utf-8")
        for row in data["tables"]:
            self.assertIn(row["table"], docs)

    def test_render_module_has_no_image_path_write(self):
        text = (ROOT / "src/novel2anima/render/service.py").read_text(encoding="utf-8")
        self.assertNotIn("image_path", text)


if __name__ == "__main__":
    unittest.main()
