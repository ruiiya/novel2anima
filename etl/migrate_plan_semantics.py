"""Move body tags out of outfit; report pose/prop/gaze guesses by default.

Usage:
  python etl/migrate_plan_semantics.py                 # all data/plans/*.json
  python etl/migrate_plan_semantics.py plan1.json ...  # specific plans
  python etl/migrate_plan_semantics.py --dry-run

Idempotent. body/outfit category moves are mechanical; pose/prop/gaze changes
need explicit --apply-semantic because they can alter the intended image.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "act_tools"))
import act_quality as aq
import story_logic as sl


def name_of(ref):
    return str(ref).rpartition(":")[0] or str(ref)


def fix_shot(shot, apply_semantic=False):
    changes, suggestions = [], []
    outfit = list(shot.get("outfit") or [])
    body = list(shot.get("body_state") or [])
    keep = []
    for ref in outfit:
        (body if name_of(ref) in sl.BODY_STATE_IN_OUTFIT else keep).append(ref)
    if len(keep) != len(outfit):
        changes.append("outfit->body_state")
    shot["outfit"] = list(dict.fromkeys(keep))
    shot["body_state"] = list(dict.fromkeys(body))

    poses = list(shot.get("pose") or [])
    actions = [name_of(a) for a in shot.get("action") or []]
    floor = set(actions) & sl.FLOOR_ACTIONS
    stances = {sl.STANCE[name_of(p)] for p in poses if name_of(p) in sl.STANCE}
    if len(stances) > 1 or (stances == {"standing"} and floor):
        if not apply_semantic:
            suggestions.append("pose")
            target = None
        else:
            target = aq.pose_for(next(iter(floor))) if floor else None
    else:
        target = None
    if target is not None or (apply_semantic and (len(stances) > 1 or floor)):
        chosen = next((p for p in poses
                       if sl.STANCE.get(name_of(p)) == target), None)
        if chosen is None and len(stances) > 1:
            chosen = poses[0]
        if chosen is None and target:
            chosen = target
        if chosen and [chosen] != poses:
            shot["pose"] = [chosen]
            changes.append("pose")

    known = [name_of(x) for x in shot.get("props") or []]
    implied = [t for t in aq.props_for(shot.get("caption")) if t not in known and t not in actions]
    if implied and apply_semantic:
        shot["props"] = list(dict.fromkeys(known + implied))
        changes.append("props")
    elif implied:
        suggestions.append("props")

    expr = [name_of(e) for e in shot.get("expression") or []]
    if "closed_eyes" in expr and (set(actions) & sl.LOOKING_ACTIONS):
        if apply_semantic:
            shot["expression"] = [e for e in shot["expression"]
                                  if name_of(e) != "closed_eyes"]
            changes.append("gaze")
        else:
            suggestions.append("gaze")
    changes.extend("suggest:" + x for x in suggestions)
    return changes


def migrate(plan, apply_semantic=False):
    counts = {}
    if str((plan.get("project") or {}).get("content_profile", "")).lower() in ("nsfw", "explicit"):
        for ch in plan.get("characters") or []:
            ident = ch.setdefault("identity_json", {})
            if ident.get("adult") is not True:
                ident["adult"] = True
                counts["adult"] = counts.get("adult", 0) + 1
    for shot in plan.get("shots") or []:
        for change in fix_shot(shot, apply_semantic):
            counts[change] = counts.get(change, 0) + 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plans", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply-semantic", action="store_true",
                    help="also apply pose/prop guesses; default is report-only")
    args = ap.parse_args()
    paths = [pathlib.Path(p) for p in args.plans] or sorted(
        pathlib.Path("data/plans").glob("*.json"))
    for path in paths:
        plan = json.loads(path.read_text(encoding="utf-8"))
        if "shots" not in plan:
            continue
        counts = migrate(plan, args.apply_semantic)
        if not counts:
            continue
        summary = ", ".join("%s:%d" % kv for kv in sorted(counts.items()))
        print("%s %s" % ("would update" if args.dry_run else "updated", path) + " (" + summary + ")")
        if not args.dry_run:
            path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
