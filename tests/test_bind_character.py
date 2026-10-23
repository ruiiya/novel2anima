"""bind_character replaces a placeholder slot with a DB character_profile row."""
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
import bind_character
import build_story_plan


class BindCharacter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self.tmp.name) / "t.db"
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE character_profile (id INTEGER PRIMARY KEY, project_id INT,"
                    " code TEXT, identity_json TEXT, outfit_json TEXT)")
        ident = {"identity_tags": ["hero_(test)", "test_series"], "adult": True,
                 "attributes": ["long_hair", "red_eyes", "1girl"]}
        con.execute("INSERT INTO character_profile VALUES (1,1,?,?,?)",
                    ("hero_test", json.dumps(ident), json.dumps({"default": ["dress"]})))
        con.execute("INSERT INTO character_profile VALUES (2,2,?,?,?)",
                    ("hero_test", json.dumps(ident), "{}"))
        con.commit()
        con.close()
        spec = json.loads((ROOT / "act_specs" / "blind_duo_placeholder.json")
                          .read_text(encoding="utf-8-sig"))
        self.plan, _ = build_story_plan.build(spec)
        self.plan["shots"][0]["expressions"] = {"LEAD": ["blush"], "PARTNER_A": ["smirk"]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_bind_remaps_every_slot_reference(self):
        con = sqlite3.connect(self.db)
        row = bind_character.select_row(con.cursor(), "hero_test", project_id=1)
        con.close()
        self.plan, _ = bind_character.bind(self.plan, "LEAD", row)
        slot = self.plan["characters"][0]
        self.assertEqual(slot["code"], "hero_test")
        self.assertEqual(slot["name"], "Hero")
        self.assertTrue(slot["adult"])
        self.assertIn("adult", slot["identity_line"])
        self.assertIn("hero_(test)", slot["identity_line"])
        shot = self.plan["shots"][0]
        self.assertEqual(shot["participants"], ["hero_test", "PARTNER_A"])
        self.assertEqual(shot["sequence"]["actor"], "hero_test")
        self.assertEqual(list(shot["character_actions"]), ["hero_test", "PARTNER_A"])
        self.assertEqual(list(shot["expressions"]), ["hero_test", "PARTNER_A"])
        self.assertIs(self.plan["blind_mode"], True)

    def test_ambiguous_code_and_non_placeholder_are_refused(self):
        con = sqlite3.connect(self.db)
        with self.assertRaises(ValueError):
            bind_character.select_row(con.cursor(), "hero_test")
        con.close()
        with self.assertRaises(ValueError):
            bind_character.bind(self.plan, "LEAD", {"code": "PARTNER_A"})
        self.plan["characters"][0]["role"] = "cast"
        with self.assertRaises(ValueError):
            bind_character.bind(self.plan, "LEAD", {"code": "x"})


if __name__ == "__main__":
    unittest.main()
