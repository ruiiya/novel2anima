"""Create V4 ShotSpecs and continuity for the 122 approved storyboard slots."""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "database/src")
from n2m_db import connect  # noqa: E402
from n2m_workflow import save_continuity, save_shot  # noqa: E402
from n2m_storyboard import get_storyboard  # noqa: E402

DB = pathlib.Path("database/data/novel2anima.db")
ROOT = pathlib.Path("exports/anniversary_gift")
STATE = ROOT / "state.json"
LABELS = ["nsfw", "explicit", "adult", "consensual", "hotwife", "qos", "interracial", "no_tattoo", "blind_cast"]

WORLD = {
    "LOC_SUITE_LIVING": "in the living area",
    "LOC_SUITE_BED": "on or beside the king bed",
    "LOC_SUITE_DINING": "at the dining table",
    "LOC_SUITE_BATH": "in the bathroom",
    "LOC_SUITE_TERRACE": "on the private terrace",
    "LOC_SUITE_DOOR": "at the suite door",
}
TIME = {"P1": "Friday 20:00-22:00", "P2": "Friday 22:00-02:00",
        "P3": "Saturday 08:00-14:00", "P4": "Saturday 19:00-02:00",
        "P5": "Sunday 08:00-11:00"}
LIGHT = {"P1": "warm lamp and cool city night", "P2": "warm lamp and cool city night",
         "P3": "soft daylight", "P4": "candlelight and warm lamp",
         "P5": "pale morning light"}


def outfit(beat_key, role):
    p, rest = beat_key.split(".")
    b = int(rest[1:])
    if role == "WIFE_A":
        table = {
            "P1": {1: "travel clothes", 2: "robe; black dress still in box",
                   3: "robe; black dress on bed", 4: "robe; pendant in hand",
                   5: "black evening dress", 6: "black evening dress",
                   7: "black evening dress", 8: "black evening dress, unzipped to waist"},
            "P2": {1: "black evening dress, open; black lingerie", 2: "black evening dress, open; black lingerie",
                   3: "black evening dress around waist; black lingerie", 4: "black lingerie, pulled aside",
                   5: "black lingerie, pulled aside", 6: "nude", 7: "nude", 8: "nude"},
            "P3": {1: "white shirt", 2: "white robe", 3: "nude, wet", 4: "white robe, open",
                   5: "nude", 6: "white sheet", 7: "black lingerie", 8: "red dress"},
            "P4": {1: "red dress", 2: "red dress", 3: "red dress", 4: "red dress, strap down",
                   5: "red dress", 6: "red dress around waist", 7: "nude", 8: "nude"},
            "P5": {1: "white shirt", 2: "travel clothes", 3: "nude, wet", 4: "travel clothes",
                   5: "travel clothes", 6: "travel clothes", 7: "travel clothes", 8: "none"},
        }
        return table[p][b]
    if role == "PARTNER_B":
        table = {
            "P1": {8: "rain-damp coat, dark shirt"},
            "P2": {1: "dark shirt", 2: "dark shirt", 3: "dark shirt, open", 4: "dark shirt, open",
                   5: "dark shirt, open", 6: "nude", 7: "nude", 8: "nude"},
            "P3": {2: "white robe", 3: "nude, wet", 4: "white robe", 5: "nude", 6: "white sheet",
                   8: "dark shirt"},
            "P4": {2: "dark shirt", 3: "dark shirt", 4: "dark shirt", 5: "dark shirt",
                   6: "dark shirt, open", 7: "nude", 8: "nude"},
            "P5": {3: "nude, wet", 5: "travel clothes"},
        }
        return table.get(p, {}).get(b, "dark shirt")
    return None


def diff(before, after):
    return {"set": {k: v for k, v in after.items() if before.get(k) != v},
            "remove": [k for k in before if k not in after]}


def door_state(beat_key):
    if beat_key in ("P1.B07", "P1.B08", "P5.B05"):
        return "suite door open"
    if beat_key in ("P5.B07", "P5.B08"):
        return "adjoining door open"
    if beat_key == "P5.B06":
        return "adjoining door closed"
    return "suite door closed"


def main():
    con = connect(DB)
    state = json.loads(STATE.read_text(encoding="utf-8"))
    story_id = state["story_id"]
    board_id = state["storyboard_id"]
    board = get_storyboard(con, board_id)
    shots_plan = board["plan"]["shots"]
    slots = board["slots"]
    assert len(shots_plan) == len(slots) == 122, (len(shots_plan), len(slots))

    beat_key_by_id = {v: k for k, v in state["beats"].items()}
    role_key_by_id = {r["id"]: r["role_key"] for r in con.execute(
        "SELECT id,role_key FROM story_roles WHERE story_id=?", (story_id,))}
    chars = board["plan"]["visual_bible"]["characters"]

    last_role = {}
    prev_scene = None
    out = {}
    for slot, shot in zip(slots, shots_plan):
        beat_key = beat_key_by_id[slot["beat_id"]]
        part = beat_key.split(".")[0]
        event_id = state["events"][beat_key]
        event = con.execute("SELECT * FROM story_events WHERE id=?", (event_id,)).fetchone()
        ev_spec = json.loads(event["spec_json"])
        actor_key = role_key_by_id.get(event["actor_role_id"])
        target_key = role_key_by_id.get(event["target_role_id"])
        roles = shot["role_keys"]

        participants = []
        for idx, role in enumerate(roles):
            apparel = outfit(beat_key, role)
            participants.append({
                "role_key": role,
                "spec": {
                    "appearance": chars[role]["description"],
                    "world_position": WORLD[shot["location_key"]],
                    "screen_position": "center" if len(roles) == 1 else ("left" if idx == 0 else "right"),
                    "pose": ev_spec.get("pose", shot["focus"]),
                    "expression": ev_spec.get("expression", "neutral"),
                    "outfit_state": apparel,
                },
            })

        interactions = []
        if roles:
            if actor_key in roles:
                ia_actor, ia_target = actor_key, (target_key if target_key in roles else None)
                action_text, reaction_text = event["action"], event["reaction"]
            else:
                ia_actor, ia_target = roles[0], None
                if beat_key == "P1.B07":
                    action_text = "freezes at the knock and opens the door"
                elif beat_key == "P4.B03":
                    action_text = "answers the suite phone and listens"
                elif beat_key == "P4.B05":
                    action_text = "listens to her husband, thanks him, and exhales"
                elif beat_key == "P5.B07":
                    action_text = "steps through the opened adjoining door"
                else:
                    action_text = shot["focus"]
                reaction_text = event["reaction"]
            interactions.append({
                "event_id": event_id,
                "actor_role_key": ia_actor,
                "target_role_key": ia_target,
                "action_text": action_text,
                "reaction_text": reaction_text,
                "constraints": [
                    "1 man + 1 woman in frame; no third body",
                    "HUSBAND_C off-frame only",
                    "no tattoo",
                    "consensual adult scene",
                    f"shot purpose: {shot['purpose']}",
                    f"visual moment: {shot['focus']}",
                ],
            })

        spec = {
            "schema_version": "n2m.shot.v4",
            "visual_context_sha256": slot["context_sha256"],
            "camera": shot["camera"],
            "focus": shot["focus"],
            "location_key": shot["location_key"],
            "style_key": shot["style_key"],
            "purpose": shot["purpose"],
            "prop_keys": shot["prop_keys"],
            "source_refs": [{"type": "story_event", "id": event_id}],
            "participants": participants,
            "interactions": interactions,
            "intent": {
                "raw_labels": LABELS,
                "constraints": [
                    "1 man + 1 woman in frame; no third body",
                    "HUSBAND_C off-frame only",
                    "no tattoo",
                    "consensual adult scene",
                    f"shot purpose: {shot['purpose']}",
                    f"visual moment: {shot['focus']}",
                ],
            },
            "continuity_revision_note": "initial ShotSpec from storyboard revision 2, plan revision 5",
        }
        shot_id, shot_rev = save_shot(con, slot["beat_id"], slot["shot_key"], spec, event_id)
        out[slot["shot_key"]] = {"shot_id": shot_id, "shot_rev": shot_rev,
                                 "event_id": event_id, "beat_key": beat_key}

        # Continuity: scene snapshot every shot; role snapshot only when present.
        scene = {
            "location_key": shot["location_key"],
            "time": TIME[part],
            "light": LIGHT[part],
            "props": sorted(shot["prop_keys"]),
            "door": door_state(beat_key),
            "bed": "black silk" if part in ("P1", "P2", "P4") else "white sheet",
        }
        scene_before = prev_scene if prev_scene is not None else scene
        snapshots = [{"role_key": None, "before": scene_before,
                      "delta": diff(scene_before, scene), "after": scene}]
        for role in roles:
            apparel = outfit(beat_key, role)
            rs = {
                "outfit": apparel,
                "pose": ev_spec.get("pose", shot["focus"]),
                "expression": ev_spec.get("expression", "neutral"),
                "location_key": shot["location_key"],
                "visible": True,
            }
            before = last_role.get(role, rs)
            snapshots.append({"role_key": role, "before": before,
                              "delta": diff(before, rs), "after": rs})
            last_role[role] = rs
        save_continuity(con, shot_id, {"snapshots": snapshots})
        prev_scene = scene

    (ROOT / "shots.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("shots saved:", len(out))
    print("first:", out["S001"])
    print("last:", out["S122"])
    print("state:", ROOT / "shots.json")


if __name__ == "__main__":
    main()
