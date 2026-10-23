"""ActSpec fixtures compile without DB/plans; compile path stays shared."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
import build_story_plan

class ActSpecs(unittest.TestCase):
    def compile(self, name):
        import json
        spec = json.loads((ROOT / "act_specs" / name).read_text(encoding="utf-8-sig"))
        plan, issues = build_story_plan.build(spec)
        self.assertEqual([i for i in issues if i.level == "ERROR"], [])
        return plan

    def test_solo_spec(self):
        plan = self.compile("solo_tea.json")
        self.assertEqual(len(plan["shots"]), 1)
        self.assertEqual(plan["shots"][0]["n"], 1)

    def test_duo_spec(self):
        plan = self.compile("duo_greeting.json")
        self.assertEqual(len(plan["shots"]), 2)
        self.assertEqual(plan["shots"][0]["participants"], ["A", "B"])

    def test_fixtures_are_tracked_source(self):
        names = sorted(p.name for p in (ROOT / "act_specs").glob("*.json"))
        self.assertEqual(names, ["blind_casino_bunny.json", "blind_duo_placeholder.json",
                                 "duo_greeting.json", "solo_tea.json"])

if __name__ == "__main__":
    unittest.main()
