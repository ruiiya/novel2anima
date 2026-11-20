import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
DB = ROOT / "database/data/novel2anima.db"
env = dict(os.environ, PYTHONIOENCODING="utf-8")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

STORIES = [
    ("story_3fbb888ae9c145a98d", "indigo_boudoir_raiden"),
    ("story_bf1edb8c91ef4d709a", "hotel_noir_kafka"),
    ("story_a790370aa95d437690", "casino_backroom_yelan"),
    ("story_6a9f78c5f3164aa8b0", "rain_glass_acheron"),
    ("story_6dece8543bd349dc8b", "unit_maintenance_2b"),
]

FRAMINGS = [("wide shot", "wide shot"), ("cowboy shot", "cowboy shot"), ("upper body", "upper body"),
            ("full body", "full body"), ("close-up", "close-up")]
ANGLES = ["from above", "from below", "from side", "from behind", "three-quarter view"]

def camera_tags(camera):
    low = camera.lower()
    tags = []
    for name, tag in FRAMINGS:
        if name in low:
            tags.append(tag)
            break
    else:
        tags.append("cowboy shot")
    for a in ANGLES:
        if a in low:
            tags.append(a)
    return tags

def cli(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"FAIL {args}\n{r.stdout}\n{r.stderr}")
    out = r.stdout.strip()
    return json.loads(out) if out.startswith("{") else out

def desired(i):
    outfit = ("kimono-full", "kimono-loose", "kimono-open", "nude", "robe-after")
    keys = ["jacket-on", "jacket-off", "shirt-open", "nude", "sheet-after"]
    return outfit, keys

for sid, slug in STORIES:
    if "--force" not in sys.argv and con.execute("select 1 from storyboard_seals s join storyboards b on b.id=s.storyboard_id where b.story_id=?", (sid,)).fetchone():
        print("skip sealed", slug)
        continue
    board = con.execute("select id from storyboards where story_id=? order by revision desc limit 1", (sid,)).fetchone()[0]
    rows = list(con.execute("""select ss.spec_json, ss.beat_id, ss.context_sha256, ss.shot_key, ss.shot_order
        from storyboard_shots ss where ss.storyboard_id=? order by ss.shot_order""", (board,)))
    plan_row = con.execute("select plan_json from storyboards where id=?", (board,)).fetchone()[0]
    plan = json.loads(plan_row)
    outfits = list(plan["visual_bible"]["characters"]["LEAD"]["outfits"].keys())
    events = {r["beat_id"]: r for r in con.execute(
        "select e.beat_id, e.id, e.action from story_events e join beats b on b.id=e.beat_id join acts a on a.id=b.act_id where a.story_id=?", (sid,))}
    scene = plan["scenes"][plan["shots"][0]["scene_key"]]
    base = ROOT / "sources" / slug / "shots"
    base.mkdir(parents=True, exist_ok=True)

    group_of = lambda i: 0 if i <= 5 else 1 if i <= 8 else 2 if i <= 12 else 3 if i <= 41 else 4
    pose_of = lambda i: "standing" if i <= 18 else "kneeling" if i <= 28 else "kneeling arched" if i <= 40 else "lying"
    position_of = lambda i: "by the shoji" if i <= 18 else "center of the room" if i <= 40 else "on the floor"

    def state(i):
        return {"outfit_key": plan["shots"][i - 1]["outfit_key"], "pose": pose_of(i),
                "position": position_of(i), "holding": "none"}

    for r in rows:
        i = r["shot_order"]
        slot = plan["shots"][i - 1]
        shot_key = r["shot_key"]
        ev = events[r["beat_id"]]
        before = state(i - 1) if i > 1 else state(1)
        at = state(i)
        after = at
        at_delta = {"set": {k: v for k, v in at.items() if before.get(k) != v}, "remove": []}
        after_delta = {"set": {}, "remove": []}
        moment_shot = {**before, **at_delta["set"]}
        total_delta = {"set": {k: v for k, v in after.items() if before.get(k) != v}, "remove": []}
        spec = {
            "visual_context_sha256": r["context_sha256"],
            "outfit_key": slot["outfit_key"],
            "camera": slot["camera"], "focus": slot["focus"], "location_key": slot["location_key"],
            "participants": [{"role_key": "LEAD"}],
            "interactions": [{"event_id": ev["id"], "actor_role_key": "LEAD", "target_role_key": None,
                              "action_text": ev["action"]}],
            "prompt_blocks": {
                "prefix": ["masterpiece", "best quality", "explicit"],
                "subjects": ["1girl", "solo"],
                "action": (["undressing"] if before.get("outfit_key") != at.get("outfit_key") else []) +
                          [at["pose"]],
                "camera": camera_tags(slot["camera"]),
                "prose": slot["visual_moment"],
            },
        }
        cont = {"snapshots": [
            {"role_key": None,
             "before": {"location_key": scene["location_key"], "time_key": scene["time_key"]},
             "delta": {"set": {}, "remove": []},
             "after": {"location_key": scene["location_key"], "time_key": scene["time_key"]},
             "moment": {"at_shot": {"location_key": scene["location_key"], "time_key": scene["time_key"]},
                        "at_delta": {"set": {}, "remove": []},
                        "after_delta": {"set": {}, "remove": []}}},
            {"role_key": "LEAD", "before": before, "delta": total_delta, "after": after,
             "moment": {"at_shot": moment_shot, "at_delta": at_delta, "after_delta": after_delta}},
        ]}
        sf = base / f"{shot_key}.shot.json"
        cf = base / f"{shot_key}.cont.json"
        sf.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        cf.write_text(json.dumps(cont, ensure_ascii=False, indent=1), encoding="utf-8")
        res = cli("database/src/n2m_workflow.py", "save-shot", "--beat-id", r["beat_id"],
                  "--shot-key", shot_key, "--file", str(sf), "--event-id", ev["id"])
        shot_id = res["result"][0] if isinstance(res["result"], list) else res["result"]
        cli("database/src/n2m_workflow.py", "save-continuity", "--shot-id", shot_id, "--file", str(cf))
        pr = cli("database/src/n2m_workflow.py", "compile-prompt", "--shot-id", shot_id, "--save")
        print(sid, shot_key, pr.get("status"), pr.get("result", "")[:60] if isinstance(pr.get("result"), str) else "")
