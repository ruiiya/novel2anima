"""Synthetic regression checks for the semantic compiler gate."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from novel2anima.story import logic as sl


def shot(**kw):
    base = {"n": 1, "participants": ["GIRL"], "outfit": [], "body_state": [],
            "action": [], "expression": [], "pose": [], "props": [], "caption": ""}
    base.update(kw)
    return base


def codes(issues):
    return [i.code for i in issues]


PHASE = [{"id": "a", "start": 1, "end": 1, "wardrobe": "undress", "allow_sensitive": True}]


class ShotSemantics(unittest.TestCase):
    def test_pose_action_conflict(self):
        issues = sl.validate_shot_semantics(
            [shot(pose=["standing"], action=["missionary"])])
        self.assertIn("POSE_ACTION_CONFLICT", codes(issues))

    def test_standing_masturbation_allowed(self):
        issues = sl.validate_shot_semantics(
            [shot(pose=["standing"], action=["masturbation"])])
        self.assertNotIn("POSE_ACTION_CONFLICT", codes(issues))

    def test_body_tag_in_outfit(self):
        issues = sl.validate_shot_semantics([shot(outfit=["school_uniform", "pussy"])])
        self.assertIn("TAG_ROLE_INVALID", codes(issues))

    def test_closed_eyes_with_gaze(self):
        issues = sl.validate_shot_semantics(
            [shot(expression=["closed_eyes"], action=["looking_at_viewer"])])
        self.assertIn("EYE_GAZE_CONFLICT", codes(issues))

    def test_caption_filler_and_meta(self):
        issues = sl.validate_shot_semantics(
            [shot(caption="She moves slowly during the cooldown.")])
        found = codes(issues)
        self.assertIn("CAPTION_TEMPLATE_FILLER", found)
        self.assertIn("CAPTION_META_LEAK", found)

    def test_unbound_prop(self):
        issues = sl.validate_shot_semantics([shot(caption="She raises the gun.")])
        self.assertIn("PROP_NOT_BOUND", codes(issues))

    def test_bound_prop_ok(self):
        issues = sl.validate_shot_semantics(
            [shot(caption="She raises the gun.", props=["gun"])])
        self.assertNotIn("PROP_NOT_BOUND", codes(issues))

    def test_nude_with_clothing(self):
        issues = sl.validate_shot_semantics(
            [shot(body_state=["completely_nude"], outfit=["black_skirt"])])
        self.assertIn("WARDROBE_STATE_CONFLICT", codes(issues))

    def test_nude_with_accessory_ok(self):
        issues = sl.validate_shot_semantics(
            [shot(body_state=["completely_nude"], outfit=["maid_headdress"])])
        self.assertNotIn("WARDROBE_STATE_CONFLICT", codes(issues))

    def test_phase_dressed_blocks_nudity(self):
        contract = [{"id": "a", "start": 1, "end": 1,
                     "wardrobe": "dressed", "allow_sensitive": False}]
        issues = sl.validate_shot_semantics(
            [shot(body_state=["topless"])], phase_contract=contract)
        self.assertIn("PHASE_EVENT_OUT_OF_BOUNDS", codes(issues))

    def test_phase_undress_allows_partial(self):
        issues = sl.validate_shot_semantics(
            [shot(body_state=["topless"])], phase_contract=PHASE)
        self.assertNotIn("PHASE_EVENT_OUT_OF_BOUNDS", codes(issues))

    def test_phase_undress_blocks_full_nudity(self):
        issues = sl.validate_shot_semantics(
            [shot(body_state=["completely_nude"])], phase_contract=PHASE)
        self.assertIn("PHASE_EVENT_OUT_OF_BOUNDS", codes(issues))

    def test_nude_phase_blocks_clothing(self):
        contract = [{"id": "a", "start": 1, "end": 1,
                     "wardrobe": "nude", "allow_sensitive": True}]
        issues = sl.validate_shot_semantics(
            [shot(body_state=["completely_nude"], outfit=["white_shirt"])],
            phase_contract=contract)
        self.assertIn("WARDROBE_STATE_CONFLICT", codes(issues))

    def test_spatial_conflict(self):
        issues = sl.validate_shot_semantics([shot(background="stage, backstage")])
        self.assertIn("SPATIAL_CONFLICT", codes(issues))


class ActLevel(unittest.TestCase):
    def test_pose_stuck_default(self):
        shots = [shot(n=i, pose=["standing"], action=["missionary" if i % 2 else "walking"])
                 for i in range(1, 8)]
        self.assertIn("POSE_STUCK_DEFAULT", codes(sl.validate_act_level(shots)))

    def test_safety_block(self):
        plan = {"project": {"content_profile": "nsfw"},
                "characters": [{"code": "GIRL", "adult": False}],
                "shots": [shot(n=i) for i in range(1, 6)]}
        self.assertIn("CONTENT_SAFETY_BLOCK", codes(sl.validate_plan(plan)))

    def test_safety_ok_when_adult(self):
        plan = {"project": {"content_profile": "nsfw"},
                "characters": [{"code": "GIRL", "adult": True}],
                "shots": [shot(n=i) for i in range(1, 6)]}
        self.assertNotIn("CONTENT_SAFETY_BLOCK", codes(sl.validate_plan(plan)))


if __name__ == "__main__":
    unittest.main()
