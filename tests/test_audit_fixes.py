"""Regression checks for the second audit pass (P0/P1)."""
import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from novel2anima.quality import act_quality as aq
from novel2anima.quality import prompt_rules as check_prompts
from novel2anima.pipeline import plan_seeder as seed_plan
from novel2anima.storage import story_repository as story_db
from novel2anima.story import logic as sl
from novel2anima.wardrobe import rules as wardrobe


def shot(n):
    return {"n": n, "participants": ["GIRL"]}


class PhaseContract(unittest.TestCase):
    def test_gap_is_error(self):
        issues = sl.validate_phase_contract([shot(1), shot(2), shot(3)],
                                            [{"id": "a", "start": 1, "end": 1},
                                             {"id": "b", "start": 3, "end": 3}])
        self.assertIn("PHASE_CONTRACT_GAP", [i.code for i in issues])

    def test_overlap_is_error(self):
        issues = sl.validate_phase_contract([shot(1)], [{"id": "a", "start": 1, "end": 2},
                                                       {"id": "b", "start": 2, "end": 3}])
        self.assertIn("PHASE_CONTRACT_OVERLAP", [i.code for i in issues])

    def test_uncovered_shot_is_error(self):
        issues = sl.validate_phase_contract([shot(1), shot(2)],
                                            [{"id": "a", "start": 2, "end": 2}])
        codes = [i.code for i in issues]
        self.assertIn("PHASE_CONTRACT_GAP", codes)

    def test_phase_mismatch_is_error(self):
        shots = [{"n": 1, "phase": "unknown", "participants": ["GIRL"]}]
        issues = sl.validate_shot_semantics(
            shots, phase_contract=[{"id": "a", "start": 1, "end": 1,
                                    "wardrobe": "dressed", "allow_sensitive": False}])
        self.assertIn("PHASE_CONTRACT_MISMATCH", [i.code for i in issues])


class Props(unittest.TestCase):
    def test_substring_does_not_bind(self):
        self.assertEqual(aq.props_for("The sky darkens over a doorway."), [])

    def test_token_binds(self):
        self.assertEqual(aq.props_for("She pushes the door open."), ["door"])

class StrictGate(unittest.TestCase):
    def test_warn_passes_without_strict(self):
        issues = [sl.Issue("WARN", "w", 1, "d")]
        self.assertEqual(seed_plan.blocked_by(issues), [])

    def test_warn_blocks_under_strict(self):
        issues = [sl.Issue("WARN", "w", 1, "d")]
        self.assertEqual(len(seed_plan.blocked_by(issues, True)), 1)

    def test_error_always_blocks(self):
        issues = [sl.Issue("ERROR", "e", 1, "d")]
        self.assertEqual(len(seed_plan.blocked_by(issues)), 1)

def colour_table(entries, chosen=None):
    table, base_ids = {}, {}
    for base, options in entries:
        base_id = 1000 + len(base_ids)
        entry = {"base": base, "base_id": base_id, "options": {}, "chosen": None, "cue": None}
        table[base_id] = entry
        base_ids[base] = base_id
        for name, tid in options:
            entry["options"][name.split("_")[0]] = (name, tid)
            table[tid] = entry
        if chosen and base in chosen:
            entry["chosen"] = entry["options"][chosen[base]]
    return table, base_ids

class WardrobeColour(unittest.TestCase):
    def setUp(self):
        self.table, self.base = colour_table([
            ("dress", [("black_dress", 1)]),
            ("skirt", [("black_skirt", 2)]),
            ("thighhighs", [("black_thighhighs", 3)]),
            ("panties", [("white_panties", 5), ("black_panties", 6)]),
        ])

    def test_heuristic_repaints_undecided_underwear(self):
        refs = [("black_dress", 1), ("black_skirt", 2),
                ("black_thighhighs", 3), ("panties", self.base["panties"])]
        self.assertEqual(wardrobe.under_fix(refs, self.table)[-1], ("black_panties", 6))

    def test_explicit_colour_is_kept(self):
        refs = [("black_dress", 1), ("black_skirt", 2),
                ("black_thighhighs", 3), ("white_panties", 5)]
        self.assertEqual(wardrobe.under_fix(refs, self.table)[-1], ("white_panties", 5))

    def test_shot_or_act_colour_wins_over_catalog(self):
        table, base_ids = colour_table([("panties", [("white_panties", 5), ("black_panties", 6)])],
                                       chosen={"panties": "black"})
        self.assertEqual(wardrobe.colorize([("panties", base_ids["panties"])], table,
                                           wanted={"panties": "white"}),
                         [("white_panties", 5)])

    def test_unknown_explicit_colour_falls_back_to_catalog(self):
        table, base_ids = colour_table([("panties", [("white_panties", 5), ("black_panties", 6)])],
                                       chosen={"panties": "black"})
        self.assertEqual(wardrobe.colorize([("panties", base_ids["panties"])], table,
                                           wanted={"panties": "purple"}),
                         [("black_panties", 6)])

    def test_outer_garment_needs_explicit_colour(self):
        table, base_ids = colour_table([("skirt", [("black_skirt", 2)])])
        self.assertEqual(wardrobe.colorize([("skirt", base_ids["skirt"])], table),
                         [("skirt", base_ids["skirt"])])

    def test_no_dominant_colour_keeps_refs(self):
        refs = [("black_dress", 1), ("panties", self.base["panties"])]
        self.assertEqual(wardrobe.under_fix(refs, self.table), refs)

    def test_missing_option_keeps_refs(self):
        table, base = colour_table([("dress", [("black_dress", 1)]),
                                    ("skirt", [("black_skirt", 2)]),
                                    ("panties", [("white_panties", 5)])])
        refs = [("black_dress", 1), ("black_skirt", 2), ("panties", base["panties"])]
        self.assertEqual(wardrobe.under_fix(refs, table), refs)


class Findings(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.execute("CREATE TABLE shot(id INTEGER PRIMARY KEY)")
        self.con.execute("INSERT INTO shot(id) VALUES(1)")
        self.con.executescript(
            pathlib.Path(pathlib.Path(__file__).resolve().parents[1]
                         / "sql/migrations/003_shot_finding.sql").read_text(encoding="utf-8"))

    def test_two_sources_same_rule_survive(self):
        story_db.record_finding(self.con, 1, "xung_dot", "qa:v1", 0.6)
        story_db.record_finding(self.con, 1, "xung_dot", "qa:llm:v1", 0.9)
        rows = self.con.execute("SELECT source FROM shot_finding ORDER BY source").fetchall()
        self.assertEqual([r[0] for r in rows], ["qa:llm:v1", "qa:v1"])

    def test_same_source_rule_updates(self):
        story_db.record_finding(self.con, 1, "xung_dot", "qa:v1", 0.3)
        story_db.record_finding(self.con, 1, "xung_dot", "qa:v1", 0.8)
        rows = self.con.execute("SELECT severity FROM shot_finding").fetchall()
        self.assertEqual(rows, [(0.8,)])


class Publish(unittest.TestCase):
    def test_failed_second_replace_restores_first(self):
        with tempfile.TemporaryDirectory() as td:
            a = pathlib.Path(td) / "a.txt"
            b = pathlib.Path(td) / "b.txt"
            a.write_text("old-a\n", encoding="utf-8")
            b.write_text("old-b\n", encoding="utf-8")
            real = seed_plan.atomic_write
            calls = {"n": 0}

            def flaky(path, text):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError("boom")
                real(path, text)

            seed_plan.atomic_write = flaky
            try:
                with self.assertRaises(OSError):
                    seed_plan.publish_files([(a, "new-a\n"), (b, "new-b\n")])
            finally:
                seed_plan.atomic_write = real
            self.assertEqual(a.read_text(encoding="utf-8"), "old-a\n")
            self.assertEqual(b.read_text(encoding="utf-8"), "old-b\n")

class PromptHygiene(unittest.TestCase):
    def test_event_id_does_not_hide_repeated_shot(self):
        shots = [{"n": i, "participants": ["GIRL"], "action": ["walking"],
                  "expression": ["serious"],
                  "sequence": {"purpose": "action", "eventId": "e%d" % i}}
                 for i in range(1, 5)]
        self.assertIn("NO_STORY_PROGRESS", [i.code for i in sl.validate(shots)])

    def test_act_ends_is_meta_leak(self):
        issues = sl.validate_shot_semantics(
            [{"n": 1, "participants": ["GIRL"], "caption": "Act two ends at the elevator."}])
        self.assertIn("CAPTION_META_LEAK", [i.code for i in issues])

    def test_prompt_body_drops_caption_and_role_clause(self):
        text = "a, b, She reads.. Hasumi: reading"
        self.assertEqual(check_prompts.prompt_body(text, "She reads."), "a, b")

    def test_secondary_identity_is_scoped(self):
        main, scoped = seed_plan.split_identities(
            ["A", "B"], {"A": "1girl, black_hair", "B": "1boy, white_shirt, black_hair"},
            {"1girl", "1boy"})
        self.assertEqual(main, ["black_hair"])
        self.assertEqual(scoped["B"], ["white_shirt"])

    def test_unique_tokens_dedupes_background(self):
        emitted = {"desk"}
        self.assertEqual(seed_plan.take_unique(["desk", "office", "office"], emitted),
                         ["office"])


class CaptionChecks(unittest.TestCase):
    def test_repeated_caption_warns(self):
        shots = [{"n": i, "participants": ["GIRL"], "outfit": ["shirt"],
                  "caption": "She looks back" if i in (2, 5) else "Shot %d" % i}
                 for i in range(1, 6)]
        self.assertIn("REPEATED_CAPTION", [i.code for i in sl.validate_act_level(shots)])

    def test_undress_not_reflected_warns(self):
        shots = [{"n": i, "participants": ["GIRL"], "outfit": ["shirt"],
                  "caption": "She pulls the top off" if i == 3 else "Shot %d" % i}
                 for i in range(1, 6)]
        reached = [(i.code, i.shot) for i in sl.validate_act_level(shots)]
        self.assertIn(("UNDRESS_NOT_REFLECTED", 3), reached)

    def test_caption_prompt_mismatches(self):
        self.assertTrue(check_prompts.caption_prompt_issues(
            "through the open blouse", {"white blouse"}, ["GIRL"], {"GIRL": "girl"}))
        self.assertTrue(check_prompts.caption_prompt_issues(
            "The crowd watches", {"1girl", "solo"}, ["GIRL"], {"GIRL": "girl"}))
        self.assertTrue(check_prompts.caption_prompt_issues(
            "A woman cups her breast", {"1girl", "1boy"}, ["GIRL", "STRANGER_M"],
            {"GIRL": "girl", "STRANGER_M": "boy"}))


if __name__ == "__main__":
    unittest.main()
