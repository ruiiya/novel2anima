"""Blind plans compile with placeholder cast and no canon identity."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
import build_story_plan


class BlindPlan(unittest.TestCase):
    def test_placeholder_cast_compiles_clean(self):
        spec = json.loads((ROOT / "act_specs" / "blind_duo_placeholder.json")
                          .read_text(encoding="utf-8-sig"))
        plan, issues = build_story_plan.build(spec)
        self.assertEqual([i for i in issues if i.level == "ERROR"], [])
        self.assertTrue(plan["blind_mode"])
        cast = {ch["code"] for ch in plan["characters"]}
        for ch in plan["characters"]:
            self.assertEqual(ch["role"], "placeholder")
            self.assertIs(ch["adult"], True)
            self.assertNotIn("identity_tags", ch["identity_json"])
            self.assertFalse([a for a in ch["identity_json"]["attributes"]
                              if "(" in a or ")" in a])
        self.assertEqual([shot["n"] for shot in plan["shots"]], [1, 2])
        self.assertEqual([shot["participants"] for shot in plan["shots"]],
                         [["LEAD", "PARTNER_A"], ["PARTNER_A"]])
        for shot in plan["shots"]:
            self.assertLessEqual(set(shot["participants"]), cast)
        self.assertEqual(plan["shots"][0]["sequence"]["actor"], "LEAD")
        self.assertEqual(plan["shots"][0]["sequence"]["target"], "PARTNER_A")


if __name__ == "__main__":
    unittest.main()
