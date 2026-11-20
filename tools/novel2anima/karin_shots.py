import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
DB = ROOT / "database/data/novel2anima.db"
env = dict(os.environ, PYTHONIOENCODING="utf-8")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

STORIES = [("story_62004947a855491ca5", "karin_station_rush", "center of the concourse"),
           ("story_7cb6e639fe894dcaac", "karin_pool_bar", "at the bar"),
           ("story_d4f8f286f43f45cda3", "karin_hall_backdrop", "in front of the backdrop")]

FRAMINGS = ["wide shot", "cowboy shot", "upper body", "full body", "close-up"]
ANGLES = ["from above", "from below", "from side", "from behind", "three-quarter view"]

def camera_tags(camera):
    low = camera.lower()
    tags = [f for f in FRAMINGS if f in low][:1] or ["cowboy shot"]
    tags += [a for a in ANGLES if a in low]
    return tags

def cli(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"FAIL {args}\n{r.stdout}\n{r.stderr}")
    out = r.stdout.strip()
    return json.loads(out) if out.startswith("{") else out

for sid, slug, position in STORIES:
    board_id = con.execute("select id from storyboards where story_id=? order by revision desc limit 1",
                           (sid,)).fetchone()[0]
    plan = json.loads(con.execute("select plan_json from storyboards where id=?", (board_id,)).fetchone()[0])
    scene = plan["scenes"][plan["shots"][0]["scene_key"]]
    events = {r["beat_id"]: r for r in con.execute(
        "select e.beat_id, e.id, e.action from story_events e join beats b on b.id=e.beat_id "
        "join acts a on a.id=b.act_id where a.story_id=?", (sid,))}
    prop_key = next((p for s in plan["shots"] for p in s.get("prop_keys", [])), None)
    base = ROOT / "sources" / slug / "shots"
    base.mkdir(parents=True, exist_ok=True)
    prev_outfit = None
    for slot in plan["shots"]:
        i = slot["shot_order"]
        ev = events[slot["beat_id"]]
        holding = prop_key if (prop_key and i <= 8) else "none"
        at = {"outfit_key": slot["outfit_key"], "pose": "standing", "position": position, "holding": holding}
        before = dict(at) if i == 1 else dict(prev_state)
        at_delta = {"set": {k: v for k, v in at.items() if before.get(k) != v}, "remove": []}
        moment_shot = {**before, **at_delta["set"]}
        spec = {
            "visual_context_sha256": con.execute(
                "select context_sha256 from storyboard_shots where storyboard_id=? and shot_key=?",
                (board_id, slot["shot_key"])).fetchone()[0],
            "outfit_key": slot["outfit_key"],
            "camera": slot["camera"], "focus": slot["focus"], "location_key": slot["location_key"],
            "participants": [{"role_key": "LEAD"}],
            "interactions": [{"event_id": ev["id"], "actor_role_key": "LEAD", "target_role_key": None,
                              "action_text": ev["action"]}],
            "prompt_blocks": {
                "prefix": ["masterpiece", "best quality", "explicit"],
                "subjects": ["1girl", "solo"],
                "action": (["undressing"] if prev_outfit and prev_outfit != slot["outfit_key"] else []) + ["standing"],
                "camera": camera_tags(slot["camera"]),
                "prose": slot["visual_moment"],
            },
        }
        scene_state = {"location_key": scene["location_key"], "time_key": scene["time_key"]}
        cont = {"snapshots": [
            {"role_key": None, "before": scene_state, "delta": {"set": {}, "remove": []},
             "after": scene_state,
             "moment": {"at_shot": scene_state, "at_delta": {"set": {}, "remove": []},
                        "after_delta": {"set": {}, "remove": []}}},
            {"role_key": "LEAD", "before": before, "delta": at_delta, "after": at,
             "moment": {"at_shot": moment_shot, "at_delta": at_delta, "after_delta": {"set": {}, "remove": []}}},
        ]}
        sf, cf = base / f"{slot['shot_key']}.shot.json", base / f"{slot['shot_key']}.cont.json"
        sf.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        cf.write_text(json.dumps(cont, ensure_ascii=False, indent=1), encoding="utf-8")
        res = cli("database/src/n2m_workflow.py", "save-shot", "--beat-id", slot["beat_id"],
                  "--shot-key", slot["shot_key"], "--file", str(sf), "--event-id", ev["id"])
        shot_id = res["result"][0] if isinstance(res["result"], list) else res["result"]
        cli("database/src/n2m_workflow.py", "save-continuity", "--shot-id", shot_id, "--file", str(cf))
        pr = cli("database/src/n2m_workflow.py", "compile-prompt", "--shot-id", shot_id, "--save")
        print(slug, slot["shot_key"], pr.get("status"))
        prev_outfit = slot["outfit_key"]
        prev_state = at
