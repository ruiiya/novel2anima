"""Generate Hasumi's 60-shot sunrise track plan.

Usage: python act_tools/generators/gen_hasumi_track.py
Writes data/plans/act30_hasumi_track_60.json and .md.
No database writes; run seed_plan.py separately after review.
"""
import argparse
import json
import pathlib
import sqlite3

import pathlib as _p, sys as _s
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[1]))
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[2] / "etl"))
import act_quality as aq

DB = "db/novel_anima.db"
OUT = pathlib.Path("data/plans/act30_hasumi_track_60.json")
MD = OUT.with_suffix(".md")

PHASES = {
    "arrival": "Arrival",
    "warmup": "Warm-up",
    "sprint_starts": "Sprint starts",
    "hurdles": "Hurdles",
    "relay": "Relay",
    "cooldown": "Cooldown",
    "rest": "Rest",
}

BASE = [
    "gym_uniform", "white_clothing", "blue_buruma",
    "underboob_cutout", "sideboob_cutout", "underboob", "sideboob",
    "white_sneakers", "midriff", "navel", "no_bra", "panties_under_buruma",
]
HAIR = ["high_ponytail", "black_hairband"]
BODY = ["athletic_female", "toned_stomach", "thick_thighs"]


def S(n, phase, action, expression, pose, camera, motion, purpose, primary, caption):
    return dict(n=n, phase=phase, action=action, expression=expression, pose=pose,
                camera=camera, motion=motion, purpose=purpose, primary=primary,
                caption=caption)


SHOTS = [
    S(1, "arrival", ["walking", "hand_on_own_hip"], ["smile", "looking_at_viewer"],
      "standing", ["wide_shot"], ["wind", "floating_hair"], "setup", "walking",
      "Hasumi walks onto the empty track at sunrise, one hand on her hip."),
    S(2, "arrival", ["adjusting_clothes", "hands_on_hips"], ["determined", "smile"],
      "standing", ["full_body"], ["floating_hair", "wind"], "setup", "adjusting_clothes",
      "She stops in lane four and looks down the straight."),
    S(3, "arrival", ["tying_hair", "stretching_arms"], ["closed_eyes", "smile"],
      "standing", ["cowboy_shot"], ["floating_hair", "wind"], "transition", "tying_hair",
      "She gathers her long black hair into a high ponytail."),
    S(4, "arrival", ["adjusting_clothes", "hand_on_own_hip"], ["blush", "parted_lips"],
      "standing", ["upper_body"], ["wind", "floating_hair"], "setup", "adjusting_clothes",
      "She settles the cut gym top; the underboob and side cutouts sit exactly as intended."),

    S(5, "warmup", ["stretching", "arm_up"], ["closed_eyes", "smile"],
      "standing", ["portrait"], ["wind", "floating_hair"], "action", "stretching",
      "Neck and shoulder rolls loosen her up."),
    S(6, "warmup", ["cross-body_stretch", "stretching"], ["smile", "closed_eyes"],
      "standing", ["upper_body"], ["emphasis_lines", "wind"], "action", "cross-body_stretch",
      "She pulls one arm across her chest and holds."),
    S(7, "warmup", ["stretching_arms", "arm_up"], ["determined", "closed_eyes"],
      "standing", ["cowboy_shot"], ["emphasis_lines", "floating_hair"], "action", "stretching_arms",
      "Overhead triceps stretch, elbow high."),
    S(8, "warmup", ["stretching", "hands_on_hips"], ["determined", "looking_at_viewer"],
      "standing", ["full_body"], ["wind", "floating_hair"], "action", "stretching",
      "Torso twists, ponytail swinging behind her."),
    S(9, "warmup", ["stretching", "hands_on_hips"], ["smile", "looking_down"],
      "standing", ["full_body"], ["emphasis_lines", "wind"], "action", "stretching",
      "Hip circles, slow and deliberate."),
    S(10, "warmup", ["stretching_legs", "stretching"], ["determined", "parted_lips"],
      "standing", ["from_side"], ["emphasis_lines", "wind"], "action", "stretching_legs",
      "Standing quad stretch, heel drawn up behind her."),
    S(11, "warmup", ["stretching_legs", "leaning_forward"], ["determined", "looking_down"],
      "standing", ["from_side"], ["emphasis_lines", "wind"], "action", "stretching_legs",
      "Calf stretch against the rail, hips square."),
    S(12, "warmup", ["forward_fold", "stretching"], ["closed_eyes", "parted_lips"],
      "standing", ["from_side"], ["emphasis_lines", "wind"], "action", "forward_fold",
      "She folds forward, hands reaching toward the lane line."),
    S(13, "warmup", ["jumping", "outstretched_arms"], ["grin", "open_mouth"],
      "standing", ["full_body"], ["flying_sweatdrops", "motion_blur"], "action", "jumping",
      "Jumping jacks at an easy count."),
    S(14, "warmup", ["running", "high_knees_(exercise)"], ["determined", "open_mouth"],
      "standing", ["from_side"], ["motion_blur", "flying_sweatdrops"], "action", "running",
      "High-knee drill, knees snapping up."),
    S(15, "warmup", ["running", "jumping"], ["determined", "smile"],
      "standing", ["cowboy_shot"], ["motion_blur", "speed_lines"], "action", "running",
      "A-skip drill down the straight."),
    S(16, "warmup", ["hands_on_hips", "head_tilt"], ["smile", "closed_eyes"],
      "standing", ["full_body"], ["wind", "floating_hair"], "action", "hands_on_hips",
      "She shakes out her arms and legs, ready for the blocks."),

    S(17, "sprint_starts", ["walking", "starting_block"], ["determined", "looking_down"],
      "standing", ["wide_shot"], ["wind", "floating_hair"], "transition", "walking",
      "She walks to the starting blocks."),
    S(18, "sprint_starts", ["crouching_start", "starting_block"], ["determined", "parted_lips"],
      "crouching", ["from_side"], ["emphasis_lines", "wind"], "action", "crouching_start",
      "She settles into the blocks, fingers on the line."),
    S(19, "sprint_starts", ["crouching_start", "starting_block"], ["determined", "looking_down"],
      "crouching", ["from_behind"], ["emphasis_lines", "wind"], "action", "crouching_start",
      "Set position: hips high, weight forward."),
    S(20, "sprint_starts", ["stand_up", "sprinting"], ["open_mouth", "determined"],
      "standing", ["from_side"], ["motion_blur", "speed_lines"], "action", "sprinting",
      "She explodes out of the blocks."),
    S(21, "sprint_starts", ["sprinting", "running"], ["determined", "open_mouth"],
      "standing", ["from_side"], ["speed_lines", "motion_blur"], "action", "sprinting",
      "Thirty meters: arms driving, ponytail streaming."),
    S(22, "sprint_starts", ["sprinting", "running"], ["determined", "parted_lips"],
      "standing", ["from_behind"], ["motion_blur", "flying_sweatdrops"], "action", "sprinting",
      "Sixty meters, holding top speed."),
    S(23, "sprint_starts", ["sprinting", "finish_line"], ["grin", "open_mouth"],
      "standing", ["from_side"], ["speed_lines", "motion_blur"], "action", "sprinting",
      "She snaps through the finish line."),
    S(24, "sprint_starts", ["jogging", "heavy_breathing"], ["open_mouth", "blush"],
      "standing", ["cowboy_shot"], ["flying_sweatdrops", "motion_blur"], "reaction", "jogging",
      "She decelerates, chest heaving."),
    S(25, "sprint_starts", ["hands_on_knees", "panting"], ["exhausted", "half-closed_eyes"],
      "standing", ["from_side"], ["flying_sweatdrops", "emphasis_lines"], "reaction", "hands_on_knees",
      "Hands on knees, catching her breath."),
    S(26, "sprint_starts", ["wiping_sweat", "hands_on_hips"], ["smile", "exhausted"],
      "standing", ["upper_body"], ["wind", "floating_hair"], "transition", "wiping_sweat",
      "She wipes her brow and looks back at the blocks."),

    S(27, "hurdles", ["walking", "hurdle"], ["determined", "smile"],
      "standing", ["wide_shot"], ["wind", "floating_hair"], "transition", "walking",
      "She walks to the row of hurdles."),
    S(28, "hurdles", ["jogging", "hurdle"], ["determined", "looking_down"],
      "standing", ["from_side"], ["motion_blur", "flying_sweatdrops"], "action", "jogging",
      "Approach the first hurdle at a controlled pace."),
    S(29, "hurdles", ["jumping", "hurdle"], ["determined", "open_mouth"],
      "standing", ["from_below"], ["motion_blur", "speed_lines"], "action", "jumping",
      "Takeoff: lead leg up, trail leg folding."),
    S(30, "hurdles", ["jumping", "hurdle"], ["open_mouth", "determined"],
      "standing", ["from_side"], ["speed_lines", "motion_blur"], "action", "jumping",
      "She clears the first hurdle cleanly."),
    S(31, "hurdles", ["jumping", "running", "hurdle"], ["determined", "parted_lips"],
      "standing", ["from_behind"], ["flying_sweatdrops", "motion_blur"], "action", "jumping",
      "Landing stride, already driving to the next one."),
    S(32, "hurdles", ["running", "hurdle"], ["determined", "looking_down"],
      "standing", ["cowboy_shot"], ["motion_blur", "flying_sweatdrops"], "action", "running",
      "Three steps between hurdles."),
    S(33, "hurdles", ["jumping", "hurdle"], ["open_mouth", "determined"],
      "standing", ["dutch_angle"], ["motion_blur", "speed_lines"], "action", "jumping",
      "Second takeoff, hips square."),
    S(34, "hurdles", ["jumping", "hurdle"], ["grin", "open_mouth"],
      "standing", ["from_below"], ["speed_lines", "flying_sweatdrops"], "action", "jumping",
      "Mid-air over the second hurdle, arms balanced."),
    S(35, "hurdles", ["running", "jumping", "hurdle"], ["determined", "parted_lips"],
      "standing", ["from_side"], ["motion_blur", "flying_sweatdrops"], "action", "running",
      "Clear and land, weight rolling forward."),
    S(36, "hurdles", ["running", "hurdle", "jumping"], ["determined", "open_mouth"],
      "standing", ["from_behind"], ["speed_lines", "motion_blur"], "action", "running",
      "Third approach, rhythm locked."),
    S(37, "hurdles", ["jumping", "hurdle"], ["determined", "open_mouth"],
      "standing", ["wide_shot"], ["motion_blur", "speed_lines"], "action", "jumping",
      "Final hurdle, full extension."),
    S(38, "hurdles", ["jogging", "heavy_breathing", "hurdle"], ["exhausted", "panting"],
      "standing", ["cowboy_shot"], ["flying_sweatdrops", "motion_blur"], "reaction", "jogging",
      "She jogs out of the last landing, breathing hard."),

    S(39, "relay", ["walking", "relay_baton"], ["smile", "looking_down"],
      "standing", ["wide_shot"], ["wind", "floating_hair"], "transition", "walking",
      "She walks to the baton on the bench."),
    S(40, "relay", ["holding_baton", "picking_up"], ["determined", "looking_down"],
      "standing", ["from_side"], ["emphasis_lines", "wind"], "action", "holding_baton",
      "She picks up the baton and checks its weight."),
    S(41, "relay", ["holding_relay_baton", "looking_down"], ["determined", "smile"],
      "standing", ["upper_body"], ["wind", "floating_hair"], "action", "holding_relay_baton",
      "Grip set, baton laid across her palm."),
    S(42, "relay", ["jogging", "holding_relay_baton"], ["determined", "looking_down"],
      "standing", ["from_side"], ["motion_blur", "flying_sweatdrops"], "action", "jogging",
      "Baton carry drill at jog pace."),
    S(43, "relay", ["sprinting", "holding_relay_baton"], ["determined", "open_mouth"],
      "standing", ["from_behind"], ["speed_lines", "motion_blur"], "action", "sprinting",
      "Full-speed carry down the straight."),
    S(44, "relay", ["reaching_out", "holding_relay_baton"], ["determined", "looking_down"],
      "standing", ["cowboy_shot"], ["emphasis_lines", "wind"], "action", "reaching_out",
      "Shadow exchange: arm out, baton forward."),
    S(45, "relay", ["sprinting", "holding_relay_baton", "looking_back"], ["grin", "open_mouth"],
      "standing", ["from_side"], ["motion_blur", "speed_lines"], "action", "sprinting",
      "She turns and sprints back the other way."),
    S(46, "relay", ["reaching_out", "holding_relay_baton"], ["determined", "parted_lips"],
      "standing", ["from_behind"], ["emphasis_lines", "flying_sweatdrops"], "action", "reaching_out",
      "Second exchange rep, hand steady."),
    S(47, "relay", ["sprinting", "running", "holding_relay_baton"], ["open_mouth", "determined"],
      "standing", ["from_side"], ["speed_lines", "motion_blur"], "action", "sprinting",
      "Another full-speed baton run."),
    S(48, "relay", ["finish_line", "holding_relay_baton"], ["grin", "open_mouth"],
      "standing", ["wide_shot"], ["motion_blur", "flying_sweatdrops"], "action", "finish_line",
      "She crosses the line with the baton."),
    S(49, "relay", ["jogging", "holding_relay_baton", "heavy_breathing"], ["open_mouth", "blush"],
      "standing", ["cowboy_shot"], ["flying_sweatdrops", "motion_blur"], "reaction", "jogging",
      "She slows to a jog, baton still in hand."),
    S(50, "relay", ["hands_on_knees", "holding_relay_baton", "panting"], ["exhausted", "half-closed_eyes"],
      "standing", ["from_side"], ["flying_sweatdrops", "emphasis_lines"], "reaction", "hands_on_knees",
      "Hands on knees again, baton dangling from her fingers."),

    S(51, "cooldown", ["stretching_legs", "stretching"], ["closed_eyes", "smile"],
      "standing", ["full_body"], ["emphasis_lines", "wind"], "action", "stretching_legs",
      "Standing quad stretch, slower this time."),
    S(52, "cooldown", ["cross-body_stretch", "stretching"], ["smile", "closed_eyes"],
      "standing", ["upper_body"], ["emphasis_lines", "wind"], "action", "cross-body_stretch",
      "Cross-body stretch, shoulders dropping."),
    S(53, "cooldown", ["forward_fold", "stretching"], ["closed_eyes", "parted_lips"],
      "standing", ["from_side"], ["emphasis_lines", "wind"], "action", "forward_fold",
      "Forward fold, hands hanging toward the track."),
    S(54, "cooldown", ["sitting_on_ground", "stretching_legs"], ["exhausted", "smile"],
      "sitting", ["full_body"], ["wind", "floating_hair"], "action", "sitting_on_ground",
      "She sits on the track and stretches her legs out."),
    S(55, "cooldown", ["sitting_on_ground", "stretching_legs"], ["closed_eyes", "smile"],
      "sitting", ["from_side"], ["emphasis_lines", "wind"], "action", "stretching_legs",
      "Seated hamstring stretch, chest over her knees."),
    S(56, "cooldown", ["stand_up", "stretching_arms", "arms_up"], ["smile", "closed_eyes"],
      "standing", ["cowboy_shot"], ["emphasis_lines", "wind"], "transition", "stand_up",
      "She stands and reaches overhead."),

    S(57, "rest", ["sitting_on_bench", "towel_around_neck", "drinking_water"], ["smile", "closed_eyes"],
      "sitting", ["full_body"], ["wind", "floating_hair"], "result", "sitting_on_bench",
      "On the bench, towel around her neck, she drinks from a bottle."),
    S(58, "rest", ["sitting_on_bench", "leaning_back", "towel_around_neck", "heavy_breathing"],
      ["exhausted", "smile"], "sitting", ["cowboy_shot"], ["wind", "floating_hair"], "result", "leaning_back",
      "She leans back, eyes closed, letting the sunrise warm her."),
    S(59, "rest", ["stand_up", "stretching_arms", "towel_around_neck"], ["smile", "closed_eyes"],
      "standing", ["full_body"], ["emphasis_lines", "wind"], "transition", "stand_up",
      "She stands and stretches once more, towel still on her shoulders."),
    S(60, "rest", ["walking", "looking_back", "over_shoulder", "towel_around_neck"],
      ["wink", "smile"], "standing", ["from_behind"], ["wind", "floating_hair"], "result", "walking",
      "She walks off the track, then glances back over her shoulder with a wink."),
]


def sweat_tags(n):
    if n <= 4:
        return []
    if n <= 7:
        return ["sweatdrop"]
    if n <= 13:
        return ["sweat", "shiny_skin", "sweatdrop"]
    if n <= 17:
        return ["sweat", "shiny_skin", "sweaty_breasts", "sweatdrop"]
    if n <= 30:
        return ["sweat", "shiny_skin", "sweaty_breasts", "sweaty_thighs", "dripping_sweat"]
    if n <= 50:
        return ["sweat", "shiny_skin", "sweaty_breasts", "sweaty_underboob",
                "sweaty_thighs", "sweaty_body", "wet_hair", "dripping_sweat"]
    if n <= 56:
        return ["sweat", "shiny_skin", "sweaty_breasts", "sweaty_thighs"]
    return ["sweat", "shiny_skin", "sweaty_breasts", "sweaty_thighs"]


def state(n):
    if n == 0:
        return "clean dry skin, loose long hair, uniform intact"
    hair = "high ponytail" if n >= 3 else "loose long hair"
    if n <= 4:
        wet = "dry"
    elif n <= 7:
        wet = "first sweatdrop"
    elif n <= 13:
        wet = "sweat sheen"
    elif n <= 17:
        wet = "sweaty breasts"
    elif n <= 30:
        wet = "sweaty breasts and thighs, dripping sweat"
    elif n <= 50:
        wet = "soaked body, wet hair, dripping sweat, sweaty underboob"
    else:
        wet = "cooling sweat sheen, still damp"
    return "%s; %s; gym uniform + blue buruma with underboob/sideboob cutouts" % (hair, wet)


def outfit(n):
    out = list(BASE)
    if n >= 3:
        out += HAIR
    if n >= 57:
        out.append("towel_around_neck")
    return out


def build():
    previous_pose = None
    shots = []
    for row in SHOTS:
        n = row["n"]
        pose = row["pose"]
        seq = {
            "purpose": row["purpose"],
            "actor": "HASUMI",
            "primaryAction": row["primary"],
            "eventId": "%s:%d" % (row["phase"], n),
        }
        if previous_pose is not None:
            seq["poseBefore"] = previous_pose
        seq["poseAfter"] = pose
        shot = {
            "n": n,
            "phase": row["phase"],
            "beat": "%s: %s" % (PHASES[row["phase"]], row["caption"]),
            "purpose": row["purpose"],
            "outfit": outfit(n),
            "body_state": [],
            "action": row["action"],
            "expression": row["expression"],
            "pose": [pose],
            "camera": row["camera"],
            "motion": row["motion"],
            "cast": BODY + sweat_tags(n),
            "props": aq.props_for(row["caption"]),
            "caption": row["caption"],
            "carry": state(n - 1),
            "delta": "action: %s; state: %s" % (row["primary"], state(n)),
            "sequence": seq,
            "participants": ["HASUMI"],
        }
        shots.append(shot)
        previous_pose = pose
    return {
        "project": {
            "title": "Hasumi - Binh minh tren duong chay",
            "idea": "Hasumi solo sunrise track session: arrival and warm-up, sprint starts, hurdles, relay baton drills, cooldown and rest. Modified gym uniform with underboob and sideboob cutouts; sweat continuity; no sexual activity.",
            "content_profile": "nsfw",
            "style_json": {
                "style": "anime, danbooru tags + short natural caption",
                "background": "outdoor athletics track at sunrise",
                "aspect": "1:1",
                "render": "Anima Base 2B + anima-turbo-4step v3, 4 steps, CFG 1, er_sde",
            },
        },
        "quality_line": "masterpiece, best quality, anime style",
        "safety_tag": "sensitive",
        "background_line": "outdoors, track_and_field, running_track, stadium, sunrise, morning, sunlight, blue_sky, depth_of_field",
        "nl": False,
        "characters": [{
            "code": "HASUMI",
            "name": "Hasumi",
            "gender": "girl",
            "identity_line": "1girl, solo, hasumi_(track)_(blue_archive), blue_archive, black_hair, long_hair, red_eyes, halo, white_halo, large_breasts",
            "identity_json": {
                "identity_tags": ["hasumi_(track)_(blue_archive)", "blue_archive"],
                "attributes": ["black_hair", "long_hair", "red_eyes", "halo", "white_halo",
                               "large_breasts", "1girl", "solo"],
                "adult": True,
                "note": "Hanekawa Hasumi (Blue Archive, Trinity) in her track variant; adult AU.",
            },
            "outfit_json": {
                "default": BASE,
                "variants": {"track": BASE + HAIR},
            },
        }],
        "act": {
            "act_no": 1,
            "title": "Hasumi - Binh minh tren duong chay",
            "outline": "arrival/warm-up 1-16 -> sprint starts 17-26 -> hurdles 27-38 -> relay 39-50 -> cooldown 51-56 -> rest 57-60.",
            "revision": 1,
            "status": "planned",
            "phase_contract": [
                {"id": "arrival", "start": 1, "end": 4, "wardrobe": "dressed", "allow_sensitive": False},
                {"id": "warmup", "start": 5, "end": 16, "wardrobe": "dressed", "allow_sensitive": False},
                {"id": "sprint_starts", "start": 17, "end": 26, "wardrobe": "dressed", "allow_sensitive": False},
                {"id": "hurdles", "start": 27, "end": 38, "wardrobe": "dressed", "allow_sensitive": False},
                {"id": "relay", "start": 39, "end": 50, "wardrobe": "dressed", "allow_sensitive": False},
                {"id": "cooldown", "start": 51, "end": 56, "wardrobe": "undress", "allow_sensitive": True},
                {"id": "rest", "start": 57, "end": 60, "wardrobe": "afterglow", "allow_sensitive": False},
            ],
        },
        "prompt_file": "prompts/act30_hasumi_track_60.txt",
        "shots": shots,
    }


SEX_OVERRIDES = {
    4: dict(action=["adjusting_clothes", "clothing_pull"], expression=["blush", "parted_lips"],
            primaryAction="clothing_pull",
            caption="She pulls the cut top down over her underboob, then lets it ride back up."),
    16: dict(action=["hands_on_hips", "hand_between_legs"], expression=["biting_lip", "half-closed_eyes"],
             purpose="reaction", primaryAction="hand_between_legs",
             caption="She shakes out her legs, then presses a hand between them, feeling the damp buruma."),
    25: dict(action=["hands_on_knees", "hand_between_legs", "panting"], expression=["exhausted", "biting_lip"],
             primaryAction="hand_between_legs",
             caption="Hands on knees, then between her legs; she is soaked."),
    38: dict(action=["jogging", "heavy_breathing", "hand_between_legs"], expression=["exhausted", "biting_lip"],
             primaryAction="hand_between_legs",
             caption="She jogs out of the landing and immediately presses a hand between her thighs."),
    41: dict(action=["holding_relay_baton", "looking_down"], expression=["determined", "biting_lip"],
             primaryAction="holding_relay_baton",
             caption="Grip set; she presses the baton against her underboob as she adjusts it."),
    48: dict(action=["finish_line", "holding_relay_baton"], expression=["grin", "tongue_out"],
             primaryAction="finish_line",
             caption="She crosses the line with the baton and a breathless laugh."),
    50: dict(action=["hands_on_knees", "holding_relay_baton", "panting", "touching_self"],
             expression=["exhausted", "half-closed_eyes"], primaryAction="touching_self",
             caption="Hands on knees, then her fingers slip under the buruma; they come away wet."),
    51: dict(action=["buruma_aside", "touching_self"], expression=["biting_lip", "blush"],
             pose=["standing"], purpose="action", primaryAction="touching_self",
             caption="She hooks the wet buruma aside and touches herself."),
    52: dict(action=["sitting_on_ground", "spread_legs", "touching_self"],
             expression=["half-closed_eyes", "biting_lip"], pose=["sitting", "spread_legs"],
             purpose="action", primaryAction="sitting_on_ground",
             caption="She sits on the track, legs spread, fingers working."),
    53: dict(action=["rubbing", "fingering", "clitoral_stimulation"], expression=["open_mouth", "blush"],
             pose=["sitting", "spread_legs"], purpose="action", primaryAction="fingering",
             caption="Two fingers slide in while her thumb circles her clit."),
    54: dict(action=["fingering", "spread_legs", "trembling"], expression=["biting_lip", "rolling_eyes"],
             pose=["sitting", "spread_legs"], purpose="action", primaryAction="fingering",
             caption="She curls her fingers, thighs shaking."),
    55: dict(action=["lying_down", "spread_legs", "fingering", "clitoral_stimulation",
                     "orgasm", "female_ejaculation", "arched_back", "trembling"],
             expression=["open_mouth", "rolling_eyes", "tongue_out"], pose=["lying", "spread_legs"],
             purpose="result", primaryAction="orgasm",
             caption="She lies back and comes, squirting across her thighs."),
    56: dict(action=["getting_up", "stand_up", "afterglow"], expression=["exhausted", "smile"],
             pose=["standing"], purpose="transition", primaryAction="getting_up",
             caption="She gets up on shaking legs, afterglow slick on her thighs."),
    60: dict(action=["walking", "looking_back", "over_shoulder", "towel_around_neck"],
             expression=["wink", "biting_lip", "smile"], primaryAction="walking",
             caption="She walks off the track, glances back over her shoulder, and licks her lip."),
}

BOUNCE_SHOTS = {13, 14, 15, 20, 21, 22, 23, 29, 30, 31, 32, 33, 34, 35, 36, 37, 43, 45, 47}

SEX_NOTES = {
    5: "The thin top drags over her nipples with every roll.",
    6: "The side cutout opens; cool air touches bare skin.",
    7: "Her breasts lift, underboob fully exposed.",
    8: "Her nipples print through the white fabric.",
    9: "The buruma seam presses where she is already damp.",
    10: "Her thigh rubs the slick seam.",
    11: "Bent over, she bares more underboob.",
    12: "The fold pulls the buruma tight.",
    13: "Her breasts bounce hard inside the cut top.",
    14: "Sweat makes the white top see-through.",
    15: "Every landing jolts her chest.",
    16: "The fabric clings to her fingers.",
    17: "The wet seam grinds against her.",
    18: "She grinds once against the seam.",
    19: "The wet patch is visible from behind.",
    20: "Her breasts jerk against the cut top.",
    21: "Every stride rubs the wet fabric.",
    22: "The soaked top leaves nothing hidden.",
    23: "Her thighs are slick.",
    24: "Her hand drifts to her hip.",
    25: "Her fingers come away wet.",
    26: "She cups her breast through the wet top.",
    27: "The buruma is dark with wetness.",
    28: "Each step pulls the seam tighter.",
    29: "Her chest lifts; underboob exposed.",
    30: "Her thighs clamp together.",
    31: "A thread of wetness runs down her thigh.",
    32: "She breathes through her mouth.",
    33: "The wet top rides up.",
    34: "She lets her tongue out, almost laughing.",
    35: "Her hand brushes her crotch on the recovery step.",
    36: "The seam is soaked.",
    37: "Her breasts bounce with the landing.",
    38: "She presses a hand between her thighs.",
    39: "Her wet thighs slide.",
    40: "She is still breathing hard.",
    41: "The baton presses against her underboob.",
    42: "The jog keeps her on edge.",
    43: "The soaked top clings.",
    44: "Her thighs press together.",
    45: "The wet buruma is visible.",
    46: "She loses focus, hand trembling.",
    47: "Every stride rubs.",
    48: "She crosses with a breathless laugh.",
    49: "Her thighs are slick.",
}


def sexual_state(n):
    if n == 0:
        return "clean dry skin, no bra, panties under buruma, loose long hair"
    hair = "high ponytail" if n >= 3 else "loose long hair"
    if n < 5:
        level = "cutouts, no bra, dry buruma"
    elif n < 14:
        level = "nipple outline, sweat sheen, buruma getting damp"
    elif n < 18:
        level = "top see-through, nipples visible, wet buruma"
    elif n < 24:
        level = "cameltoe, pussy juice, sweat"
    elif n < 31:
        level = "pussy juice on fingers, dripping"
    elif n < 39:
        level = "pussy juice trail, soaked body"
    elif n < 50:
        level = "soaked, pussy juice on fingers, trembling"
    elif n < 55:
        level = "buruma aside, pussy exposed, fingers working"
    elif n == 55:
        level = "orgasm, female ejaculation, afterglow"
    else:
        level = "afterglow, wet thighs, buruma still aside"
    return "%s; %s; gym uniform + blue buruma with underboob/sideboob cutouts" % (hair, level)


def sexualize(plan):
    for shot in plan["shots"]:
        n = shot["n"]
        ov = SEX_OVERRIDES.get(n)
        if ov:
            for key in ("action", "expression", "pose", "purpose", "caption"):
                if key in ov:
                    shot[key] = ov[key]
            shot["sequence"]["purpose"] = shot.get("purpose", shot["sequence"]["purpose"])
            shot["sequence"]["primaryAction"] = ov.get("primaryAction", shot["sequence"]["primaryAction"])

        outfit = shot["outfit"]
        if n >= 14:
            outfit += ["wet_clothes", "see-through"]
        if n >= 18:
            outfit += ["wet_buruma", "cameltoe"]
        if n >= 51:
            outfit += ["buruma_aside", "panties_aside"]
        shot["outfit"] = list(dict.fromkeys(outfit))
        body = shot.setdefault("body_state", [])
        if n >= 51:
            body.append("pussy")
        if n >= 55:
            body.append("afterglow")
        shot["body_state"] = list(dict.fromkeys(body))

        cast = shot["cast"]
        if n >= 5:
            cast.append("nipple_outline")
        if n >= 14:
            cast += ["nipples_visible_through_clothing", "sweaty_underboob"]
        if n >= 24:
            cast.append("pussy_juice")
        if n >= 31:
            cast.append("pussy_juice_drip")
        if n >= 50:
            cast.append("pussy_juice_on_fingers")
        if n >= 54:
            cast.append("trembling")
        if n == 55:
            cast += ["orgasm", "female_ejaculation", "arched_back",
                     "pussy_juice_trail", "pussy_juice_puddle", "afterglow"]
        if n >= 56:
            cast += ["afterglow", "pussy_juice_trail"]
        shot["cast"] = list(dict.fromkeys(cast))

        motion = shot["motion"]
        if n in BOUNCE_SHOTS:
            motion.append("bouncing_breasts")
        shot["motion"] = list(dict.fromkeys(motion))

        if n >= 5:
            note = SEX_NOTES.get(n, "")
            if n == 55:
                note = "Her back arches through the last wave."
            if note and note not in shot["caption"]:
                shot["caption"] = shot["caption"].rstrip(".") + ". " + note
        shot["beat"] = "%s: %s" % (PHASES[shot["phase"]], shot["caption"])

    previous_pose = None
    for shot in plan["shots"]:
        n = shot["n"]
        if previous_pose is None:
            shot["sequence"].pop("poseBefore", None)
        else:
            shot["sequence"]["poseBefore"] = previous_pose
        shot["sequence"]["poseAfter"] = shot["pose"][0]
        previous_pose = shot["pose"][0]
        shot["carry"] = sexual_state(n - 1)
        shot["delta"] = "action: %s; state: %s" % (shot["sequence"]["primaryAction"], sexual_state(n))

    plan["project"]["title"] = "Hasumi - Binh minh uot"
    plan["project"]["idea"] = ("Hasumi solo sunrise track session that escalates into explicit solo masturbation: "
                               "cut gym uniform with no bra, sweat-soaked see-through top, wet blue buruma, "
                               "fingering during cooldown, orgasm, afterglow.")
    plan["safety_tag"] = "explicit"
    plan["act"]["title"] = "Hasumi - Binh minh uot"
    plan["act"]["outline"] = ("arrival/warm-up 1-16 (tease, sweat, nipple outline) -> sprint starts 17-26 "
                              "(wet buruma, pussy juice) -> hurdles 27-38 (rubbing, dripping) -> relay 39-50 "
                              "(soaked, hand between legs) -> cooldown 51-56 (buruma aside, fingering, orgasm) "
                              "-> rest 57-60 (afterglow).")
    return plan


def check_tags(plan):
    names = set()
    for ch in plan["characters"]:
        for key in ("identity_tags", "attributes"):
            names.update(ch["identity_json"].get(key, []))
        for refs in ch["outfit_json"].values():
            if isinstance(refs, list):
                names.update(refs)
    for shot in plan["shots"]:
        for key in ("outfit", "action", "expression", "pose", "camera", "motion", "cast"):
            names.update(shot.get(key, []))
    names.update(plan["background_line"].split(", "))
    con = sqlite3.connect(DB)
    missing = [n for n in sorted(names) if not con.execute(
        "SELECT 1 FROM tag WHERE canonical_name=?", (n,)).fetchone()]
    con.close()
    return missing


def write_md(plan):
    lines = [
        "# %s" % plan["project"]["title"],
        "",
        "- Plan: `data/plans/act30_hasumi_track_60.json`",
        "- Prompt: `prompts/act30_hasumi_track_60.txt`",
        "- So shot: **60**",
        "- Nhan vat: **Hasumi** (`hasumi_(track)_(blue_archive)`, `blue_archive`), adult AU",
        "- Trang phuc: `gym_uniform`, `blue_buruma`, `underboob_cutout`, `sideboob_cutout`, `underboob`, `sideboob`, `no_bra`, `panties_under_buruma`",
        "- Boi canh: `track_and_field`, `running_track`, `stadium`, `sunrise`, `morning`, `sunlight`",
        "",
        "## Logline",
        "",
        "Hasumi tap mot minh tren san dien kinh luc binh minh trong bo gym cat ro underboob/sideboob, khong mac bra. Mo hoi lam ao trang trong xuyen; buruma xanh uot dan. Co giao duc tang dan tu khoi dong, sprint, vuot rao, baton den cooldown, roi co thu dam va len dinh.",
        "",
        "## Nhip",
        "",
        "| Phase | Shots | Count |",
        "|---|---:|---:|",
        "| Arrival / warm-up | 1-16 | 16 |",
        "| Sprint starts | 17-26 | 10 |",
        "| Hurdles | 27-38 | 12 |",
        "| Relay | 39-50 | 12 |",
        "| Cooldown | 51-56 | 6 |",
        "| Rest | 57-60 | 4 |",
        "",
        "## Continuity",
        "",
        "- Trang phuc khong doi: gym uniform + blue buruma, cutout underboob/sideboob luon lo ro; khong mac bra.",
        "- Toc xoa shot 1-2; high ponytail tu shot 3 den het.",
        "- Mo hoi: kho (1-4) -> sweatdrop (5-7) -> sweat sheen (8-13) -> sweaty breasts (14-17) -> dripping (18-30) -> soaked body + wet hair (31-50) -> cooling sheen (51-60).",
        "- Sexual: nipple outline (5+) -> top see-through (14+) -> wet buruma/cameltoe (18+) -> pussy juice (24+) -> dripping (31+) -> buruma aside (51+) -> fingering (51-55) -> orgasm/female ejaculation (55) -> afterglow (56-60).",
        "- Moi shot co `carry` + `delta`; khong reset mo hoi, toc hay trang phuc.",
        "",
        "## Shot list",
        "",
        "| # | Phase | Pose | Action | Expression | Caption |",
        "|---:|---|---|---|---|---|",
    ]
    for s in plan["shots"]:
        lines.append("| %d | %s | %s | %s | %s | %s |" % (
            s["n"], s["phase"], ", ".join(s["pose"]), ", ".join(s["action"]),
            ", ".join(s["expression"]), s["caption"]))
    lines += ["", "## Kiem tra", "", "- Chua seed; chay `python etl/check_story.py --plan data/plans/act30_hasumi_track_60.json` truoc khi seed.", ""]
    MD.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="data/plans")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    global OUT, MD
    OUT = pathlib.Path(args.output) / "act30_hasumi_track_60.json"
    MD = OUT.with_suffix(".md")
    plan = sexualize(build())
    missing = check_tags(plan)
    if missing:
        raise SystemExit("MISSING TAGS: %s" % ", ".join(missing))
    if args.dry_run:
        print("dry-run: would write %s (%d shots)" % (OUT, len(plan["shots"])))
        return
    OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(plan)
    print("wrote %s (%d shots)" % (OUT, len(plan["shots"])))
    print("wrote %s" % MD)
    print("tag refs ok")


if __name__ == "__main__":
    main()
