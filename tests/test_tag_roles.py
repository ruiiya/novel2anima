"""Tag-role overrides and continuity policy share one versioned source."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "etl"))
import act_quality as aq
import build
import infer_state
import state_rules
import story_logic as sl
import tag_roles

class TagRoles(unittest.TestCase):
    def test_build_and_qa_use_same_set(self):
        self.assertIs(build.BODY_STATE_TAGS, tag_roles.BODY_STATE_TAGS)
        self.assertEqual(aq.BODY_TAGS, set(tag_roles.BODY_STATE_TAGS))

    def test_story_logic_superset(self):
        self.assertTrue(set(tag_roles.BODY_STATE_TAGS) <= sl.BODY_STATE_IN_OUTFIT)
        self.assertTrue(sl.NUDE_STATE <= sl.BODY_STATE_IN_OUTFIT)

    def test_role_override(self):
        self.assertEqual(tag_roles.role_for("wet", "outfit"), "body_state")
        self.assertEqual(tag_roles.role_for("white_shirt", "outfit"), "outfit")

class StateRules(unittest.TestCase):
    def test_infer_state_uses_policy_module(self):
        self.assertIs(infer_state.LADDERS, state_rules.LADDERS)
        self.assertIs(infer_state.REFRESH, state_rules.REFRESH)
        self.assertEqual(infer_state.RULES_VERSION, state_rules.RULES_VERSION)

    def test_severity_is_bounded(self):
        self.assertAlmostEqual(state_rules.severity_of(1), 0.5)
        self.assertLessEqual(state_rules.severity_of(99), 0.9)

    def test_outfit_stage_is_monotonic(self):
        levels = [lvl for lvl, _name, _trig in state_rules.OUTFIT_STAGE]
        self.assertEqual(levels, sorted(levels))

if __name__ == "__main__":
    unittest.main()
