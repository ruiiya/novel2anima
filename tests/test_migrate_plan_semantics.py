"""Migration stays mechanical and idempotent."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "etl"))
import migrate_plan_semantics as mig


def plan(shots):
    return {"project": {"content_profile": "nsfw"},
            "characters": [{"code": "GIRL", "identity_json": {}}],
            "shots": shots}


class Migrate(unittest.TestCase):
    def test_body_tags_move_to_body_state(self):
        p = plan([{"n": 1, "outfit": ["school_uniform:1", "topless:2"],
                   "action": [], "expression": [], "pose": [], "caption": ""}])
        counts = mig.migrate(p)
        self.assertEqual(p["shots"][0]["outfit"], ["school_uniform:1"])
        self.assertEqual(p["shots"][0]["body_state"], ["topless:2"])
        self.assertEqual(counts["outfit->body_state"], 1)

    def test_idempotent(self):
        p = plan([{"n": 1, "outfit": ["topless:2"], "action": [],
                   "expression": [], "pose": [], "caption": ""}])
        mig.migrate(p)
        self.assertEqual(mig.migrate(p), {})

    def test_standing_floor_action_is_report_only_by_default(self):
        p = plan([{"n": 1, "outfit": [], "pose": ["standing"],
                   "action": ["missionary"], "expression": [], "caption": ""}])
        counts = mig.migrate(p)
        self.assertEqual(p["shots"][0]["pose"], ["standing"])
        self.assertEqual(counts.get("suggest:pose"), 1)

    def test_standing_floor_action_repaired_when_approved(self):
        p = plan([{"n": 1, "outfit": [], "pose": ["standing"],
                   "action": ["missionary"], "expression": [], "caption": ""}])
        mig.migrate(p, apply_semantic=True)
        self.assertEqual(p["shots"][0]["pose"], ["lying"])

    def test_nsfw_sets_adult(self):
        p = plan([])
        mig.migrate(p)
        self.assertIs(p["characters"][0]["identity_json"]["adult"], True)


if __name__ == "__main__":
    unittest.main()
