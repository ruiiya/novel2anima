"""infer_state --apply must never touch manual continuity; publication outbox stays pending on failure."""
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from novel2anima.continuity import inference as infer_state
from novel2anima.pipeline import plan_seeder as seed_plan
from novel2anima.continuity import rules as state_rules


def run_sql(con, name):
    con.executescript((ROOT / "sql" / "migrations" / name).read_text(encoding="utf-8"))


def tag_names():
    names = set()
    for _axis, steps in state_rules.LADDERS.items():
        names.update(tag for _lvl, tag, _pred in steps)
    for _lvl, tag, _trig in state_rules.OUTFIT_STAGE:
        if tag:
            names.add(tag)
    return sorted(names)


class InferStateApply(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = str(pathlib.Path(self.dir.name) / "mini.db")
        con = sqlite3.connect(self.db)
        con.executescript(
            "CREATE TABLE act(id INTEGER PRIMARY KEY, act_no INTEGER);"
            "CREATE TABLE shot(id INTEGER PRIMARY KEY, act_id INTEGER REFERENCES act(id),"
            " shot_no INTEGER);"
            "CREATE TABLE shot_spec_revision(shot_id INTEGER, revision INTEGER, spec_json TEXT);"
            "CREATE TABLE tag(id INTEGER PRIMARY KEY, canonical_name TEXT UNIQUE);")
        run_sql(con, "002_shot_state.sql")
        run_sql(con, "004_observation_publication.sql")
        con.executemany("INSERT INTO tag(canonical_name) VALUES(?)", [(n,) for n in tag_names()])
        con.executemany("INSERT INTO act(id, act_no) VALUES(?,?)", [(1, 1), (2, 2)])
        solo = json.dumps({"participants": ["A"], "caption": "", "beat": "", "background": ""})
        duo = json.dumps({"participants": ["A", "B"], "caption": "", "beat": "", "background": ""})
        con.executemany("INSERT INTO shot(id, act_id, shot_no) VALUES(?,?,?)",
                        [(1, 1, 1), (2, 2, 1)])
        con.executemany("INSERT INTO shot_spec_revision(shot_id, revision, spec_json) VALUES(?,1,?)",
                        [(1, solo), (2, duo)])
        con.execute("INSERT INTO shot_state(shot_id, axis, severity, since_shot_no, cause_shot_no, source)"
                    " VALUES(1,'outfit:stage',0.9,1,1,'manual')")
        con.execute("INSERT INTO act_continuity(act_id, axis, notes) VALUES(1,'environment','manual curator notes')")
        con.execute("INSERT INTO shot_observation(shot_id, axis, severity, since_shot_no, cause_shot_no, source)"
                    " VALUES(2,'outfit:stage',0.7,1,1,'inferred:" + state_rules.RULES_VERSION + "')")
        con.commit()
        con.close()

    def tearDown(self):
        self.dir.cleanup()

    def apply(self):
        return subprocess.run([sys.executable, "-m", "novel2anima.continuity.inference",
                               "--db", self.db, "--apply"],
                              capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})

    def rows(self, sql):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()

    def test_apply_keeps_manual_and_skipped_act(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.rows("SELECT source FROM shot_state"), [("manual",)])
        self.assertEqual(self.rows("SELECT notes FROM act_continuity"), [("manual curator notes",)])
        self.assertEqual(len(self.rows("SELECT * FROM act_observation")), 4)
        self.assertTrue(self.rows("SELECT source FROM shot_observation WHERE shot_id=2"))

    def test_apply_is_idempotent(self):
        self.assertEqual(self.apply().returncode, 0)
        first = self.rows("SELECT shot_id, axis, source FROM shot_observation ORDER BY 1,2,3")
        self.assertEqual(self.apply().returncode, 0)
        second = self.rows("SELECT shot_id, axis, source FROM shot_observation ORDER BY 1,2,3")
        self.assertEqual(first, second)

    def test_report_only_writes_nothing(self):
        result = subprocess.run([sys.executable, "-m", "novel2anima.continuity.inference",
                                 "--db", self.db], capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.rows("SELECT count(*) FROM shot_observation"), [(1,)])


if __name__ == "__main__":
    unittest.main()
