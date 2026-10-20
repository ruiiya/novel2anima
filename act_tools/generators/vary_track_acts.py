"""Give the five track acts distinct primary actions and pose sequences.

Run after the plan generators:
  python act_tools/generators/vary_track_acts.py
"""
import json
import pathlib

import pathlib as _p, sys as _s
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[1]))
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[2] / "etl"))
import act_quality as aq

ACTS = [
    {
        "path": "data/plans/act30_hasumi_track_60.json",
        "name": "Hasumi",
        "actions": """walking adjusting_clothes tying_hair hands_on_hips
stretching cross-body_stretch stretching_arms stretching_legs forward_fold jumping_jacks high_knees_(exercise) skipping running jogging stretching_legs head_tilt
walking crouching_start crouching_start sprinting sprinting running finish_line jogging hands_on_knees wiping_sweat
walking jogging jumping vaulting running jumping running jumping sprinting vaulting jogging hands_on_knees
walking holding_baton holding_relay_baton jogging sprinting reaching_out sprinting reaching_out sprinting finish_line jogging hands_on_knees
buruma_aside sitting_on_ground fingering fingering orgasm getting_up
sitting_on_bench leaning_back drinking_water looking_back""",
        "poses": {18: "crouching", 19: "crouching", 52: "sitting", 53: "sitting",
                  54: "sitting", 55: "lying", 57: "sitting", 58: "sitting",
                  59: "sitting"},
        "extra": {52: ["spread_legs"], 53: ["spread_legs"],
                  54: ["spread_legs"], 55: ["spread_legs"]},
        "extra_actions": {54: ["spread_pussy"]},
    },
    {
        "path": "data/plans/act31_karin_track_60.json",
        "name": "Karin",
        "actions": """jogging arms_behind_back adjusting_hair adjusting_clothes
push-ups push-ups plank squat_(exercise) lunge lunging kneeling stretching jumping butt_kick high_knees_(exercise) hands_on_hips
jogging starting_block crouching crouching_start running sprinting running walking crouching stand_up
jogging running vaulting jumping sprinting hurdle jumping vaulting running jumping running crouching
jogging picking_up walking running jumping running reaching_out running walking sprinting walking crouching
clothing_pull kneeling spread_pussy clitoral_stimulation orgasm stand_up
crouching wiping_sweat stretching walking""",
        "poses": {5: "crouching", 6: "crouching", 7: "crouching", 8: "crouching",
                  9: "crouching", 10: "crouching", 11: "kneeling", 12: "kneeling",
                  18: "crouching", 19: "crouching", 20: "crouching", 25: "crouching",
                  38: "crouching", 50: "crouching", 52: "kneeling", 53: "kneeling",
                  54: "kneeling", 55: "sitting", 57: "crouching", 58: "sitting"},
        "extra": {55: ["spread_legs"]},
        "extra_actions": {},
    },
    {
        "path": "data/plans/act32_yuuka_track_60.json",
        "name": "Yuuka",
        "actions": """skipping clothing_pull adjusting_clothes stretching_arms
arm_up stretching_arms stretching_legs forward_fold kneeling sitting stretching head_tilt stand_up stretching_legs walking looking_back
skipping crouching starting_block crouching jogging finish_line sprinting hands_on_knees stand_up head_tilt
skipping jumping running sprinting vaulting running vaulting sprinting jumping running walking stretching
skipping crouching jogging walking running sprinting running jogging reaching_out running hands_on_knees stand_up
sitting_on_ground legs_up touching_self masturbation female_ejaculation afterglow
stretching drinking_water looking_back head_tilt""",
        "poses": {9: "kneeling", 10: "sitting", 11: "sitting", 12: "sitting",
                  18: "crouching", 19: "crouching", 20: "crouching", 40: "crouching",
                  51: "sitting", 52: "sitting", 53: "sitting", 54: "sitting",
                  55: "sitting", 56: "sitting", 57: "sitting", 58: "sitting",
                  59: "sitting", 60: "sitting"},
        "extra": {51: ["spread_legs"], 52: ["spread_legs"],
                  53: ["spread_legs"], 54: ["spread_legs"], 55: ["spread_legs"]},
        "extra_actions": {51: ["buruma_aside"], 53: ["spread_pussy"],
                          54: ["spread_pussy"],
                          55: ["orgasm", "arched_back", "trembling"]},
    },
    {
        "path": "data/plans/act33_mika_track_60.json",
        "name": "Mika",
        "actions": """standing_on_one_leg hands_on_hips arm_up cross-body_stretch
one_leg_raised leg_lift standing_on_one_leg jumping_jacks leg_lift skipping jumping jumping_jacks high_knees_(exercise) head_tilt stretching_arms drinking_water
running sprinting jumping skipping jumping high_knees_(exercise) jumping wiping_sweat drinking_water stretching
running skipping sprinting running jumping vaulting sprinting running vaulting skipping jumping wiping_sweat
running kneeling skipping sprinting skipping jumping skipping jumping skipping jumping stretching wiping_sweat
one_leg_raised rubbing clitoral_stimulation rubbing orgasm afterglow
standing_on_one_leg stretching_legs head_tilt sitting_on_bench""",
        "poses": {1: "standing", 5: "standing", 7: "standing", 40: "kneeling",
                  51: "standing", 52: "standing", 53: "standing",
                  54: "standing", 55: "standing", 57: "standing",
                  58: "sitting", 59: "sitting", 60: "sitting"},
        "extra": {1: ["one_leg_raised"], 5: ["one_leg_raised"],
                  7: ["one_leg_raised"], 51: ["one_leg_raised"],
                  52: ["one_leg_raised"], 53: ["one_leg_raised"],
                  54: ["one_leg_raised"], 55: ["one_leg_raised"],
                  57: ["one_leg_raised"]},
        "extra_actions": {51: ["buruma_aside"], 53: ["spread_pussy"],
                          54: ["touching_self"]},
    },
    {
        "path": "data/plans/act34_asuna_track_60.json",
        "name": "Asuna",
        "actions": """running tying_hair head_tilt stretching
squat_(exercise) lunge lunging skipping butt_kick high_knees_(exercise) forward_fold jumping skipping running stretching adjusting_hair
sprinting running walking hands_on_knees high_knees_(exercise) skipping walking crouching hands_on_hips stretching_legs
sprinting vaulting hurdle skipping hurdle sprinting hurdle skipping hurdle sprinting vaulting drinking_water
sprinting walking running holding_relay_baton jogging jogging walking sprinting jogging walking crouching drinking_water
bent_over fingering masturbation touching_self orgasm afterglow
leaning_back stretching walking stretching_legs""",
        "poses": {5: "crouching", 6: "crouching", 7: "crouching", 24: "crouching", 49: "crouching",
                  52: "kneeling", 53: "kneeling", 54: "kneeling",
                  55: "kneeling", 56: "kneeling", 57: "sitting"},
        "extra": {52: ["all_fours"], 53: ["all_fours"], 54: ["all_fours"],
                  55: ["all_fours"], 56: ["all_fours"]},
        "extra_actions": {51: ["buruma_aside"], 53: ["spread_pussy"],
                          54: ["touching_self"]},
    },
]

PHRASES = {
    "walking": "walks", "jogging": "jogs", "running": "runs", "sprinting": "sprints",
    "stretching": "stretches", "arm_up": "reaches up",
    "cross-body_stretch": "stretches across her chest", "stretching_arms": "stretches her arms",
    "stretching_legs": "stretches her legs", "forward_fold": "folds forward",
    "jumping": "jumps", "jumping_jacks": "does jumping jacks",
    "high_knees_(exercise)": "drives high knees", "skipping": "skips",
    "butt_kick": "kicks her heels up", "push-ups": "does push-ups",
    "plank": "holds a plank", "squat_(exercise)": "squats", "lunge": "lunges",
    "kneeling": "kneels", "sitting": "sits", "stand_up": "stands up",
    "crouching": "crouches", "starting_block": "sets in the blocks",
    "crouching_start": "crouches into the blocks", "finish_line": "crosses the line",
    "hands_on_knees": "rests her hands on her knees", "wiping_sweat": "wipes sweat",
    "hurdle": "clears a hurdle", "holding_baton": "picks up the baton",
    "holding_relay_baton": "carries the baton", "reaching_out": "reaches out the baton",
    "buruma_aside": "hooks the buruma aside", "sitting_on_ground": "sits on the track",
    "fingering": "fingers herself", "clitoral_stimulation": "circles her clit",
    "rubbing": "rubs herself", "orgasm": "comes", "getting_up": "gets up",
    "afterglow": "basks in the afterglow", "sitting_on_bench": "sits on the bench",
    "leaning_back": "leans back", "drinking_water": "drinks water",
    "looking_back": "looks back", "one_leg_raised": "balances on one leg",
    "clothing_pull": "pulls at the cut top", "adjusting_clothes": "adjusts her uniform",
    "adjusting_hair": "adjusts her hair", "tying_hair": "ties her hair",
    "hands_on_hips": "sets her hands on her hips", "head_tilt": "tilts her head",
    "leg_lift": "lifts a leg",
    "arms_behind_back": "clasps her hands behind her back",
    "jumping_jacks": "does jumping jacks", "lunging": "drops into a lunge",
    "standing_on_one_leg": "stands on one leg", "vaulting": "vaults the hurdle",
    "legs_up": "raises her legs", "bent_over": "bends over the rail",
    "picking_up": "picks up the baton", "spread_pussy": "spreads herself open",
    "masturbation": "masturbates", "female_ejaculation": "squirts",
    "touching_self": "touches herself",
}

STYLE = {
    "Hasumi": "with textbook precision",
    "Karin": "with brute force",
    "Yuuka": "with measured control",
    "Mika": "light on her toes",
    "Asuna": "loose and playful",
}

SUPPORT = {
    "crouching_start": ["starting_block"],
    "holding_baton": ["picking_up"],
    "reaching_out": ["holding_relay_baton"],
    "looking_back": ["over_shoulder"],
    "orgasm": ["female_ejaculation", "arched_back", "trembling"],
}

IMPLIED_POSE = {"crouching", "crouching_start", "starting_block", "kneeling",
                "sitting", "sitting_on_ground", "bent_over", "all_fours", "lying"}

def bridge(previous, current):
    if previous is None or previous == current:
        return None
    return {
        "crouching": "crouch", "kneeling": "kneeling", "sitting": "sitting_down",
        "lying": "lying_down",
        "standing": "getting_up" if previous == "lying" else "stand_up",
    }.get(current)


def caption(name, primary, phase):
    phrase = PHRASES.get(primary, primary.replace("_", " "))
    return "%s %s %s." % (name, phrase, STYLE[name])


def apply_act(item, write=True):
    path = pathlib.Path(item["path"])
    plan = json.loads(path.read_text(encoding="utf-8"))
    seq = item["actions"].split()
    if len(seq) != len(plan["shots"]):
        raise SystemExit("%s: %d actions for %d shots" % (path, len(seq), len(plan["shots"])))
    previous = None
    for shot in plan["shots"]:
        n = shot["n"]
        primary = seq[n - 1]
        pose = item["poses"].get(n, "standing")
        pose_list = [pose] + item["extra"].get(n, [])
        support = SUPPORT.get(primary, []) + item.get("extra_actions", {}).get(n, [])
        if shot["phase"] == "hurdles" and n <= 37 and primary not in {"hurdle", "vaulting"}:
            support.append("hurdle")
        if shot["phase"] == "relay":
            if n == 39:
                support.append("relay_baton")
            elif n == 40:
                support.extend(["picking_up", "holding_baton"])
            else:
                support.append("holding_relay_baton")
        action = [primary] + [t for t in support if t != primary and t not in pose_list]
        cue = bridge(previous, pose)
        if cue and cue not in action and primary not in IMPLIED_POSE:
            action.append(cue)
        shot["action"] = list(dict.fromkeys(action))
        shot["expression"] = aq.clean_expression(shot.get("expression"), [primary])
        shot["pose"] = pose_list
        shot["sequence"]["primaryAction"] = primary
        shot["sequence"]["poseAfter"] = pose
        if previous is None:
            shot["sequence"].pop("poseBefore", None)
        else:
            shot["sequence"]["poseBefore"] = previous
        previous = pose
        shot["caption"] = caption(item["name"], primary, shot["phase"])
        shot["beat"] = "%s: %s" % (shot["phase"], shot["caption"])
        state = shot["delta"].split("; state: ", 1)[1] if "; state: " in shot["delta"] else ""
        shot["delta"] = "action: %s; state: %s" % (primary, state)
    if not write:
        return
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = path.with_suffix(".md")
    lines = md_path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| # | Phase |"))
    end = next((i for i in range(start + 2, len(lines)) if lines[i].startswith("## ")), len(lines))
    table = [
        "| # | Phase | Pose | Action | Expression | Caption |",
        "|---:|---|---|---|---|---|",
    ]
    for shot in plan["shots"]:
        table.append("| %d | %s | %s | %s | %s | %s |" % (
            shot["n"], shot["phase"], ", ".join(shot["pose"]),
            ", ".join(shot["action"]), ", ".join(shot["expression"]), shot["caption"]))
    lines = lines[:start] + table + lines[end:]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("updated %s" % path)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-dir", default="data/plans")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    for item in ACTS:
        item = dict(item, path=str(pathlib.Path(args.plan_dir) / pathlib.Path(item["path"]).name))
        apply_act(item, write=not args.dry_run)
        print(("would update " if args.dry_run else "updated ") + item["path"])


if __name__ == "__main__":
    main()
