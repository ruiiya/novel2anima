import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
DB = ROOT / "database/data/novel2anima.db"
env = dict(os.environ, PYTHONIOENCODING="utf-8")


def cli(*a):
    r = subprocess.run([sys.executable, *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"FAIL {a}\n{r.stdout}\n{r.stderr}")
    out = r.stdout.strip()
    return json.loads(out)["result"] if out.startswith("{") else out


SLUG = "mika_blessed_pet"
TITLE = "Blessed Pet - Mika"
CHAR_ID = "character:storyaura_danbooru_csv:84c6deec5296f9887b"
NAME = "Mika"
ANCHORS = ["pink hair", "very long hair", "yellow eyes", "halo", "angel wings", "white wings",
           "fake animal ears", "collar", "bell", "tail"]
FULL = ["white dress", "white capelet", "hair flower", "long dress"]
CORE = ["white dress"]
NUDES = ["completely nude", "nipples", "navel", "barefoot"]

VENUE = dict(place="the rooftop garden party at noon", place_short="the garden",
             floor="the wooden deck", lean_on="the planter wall", light_word="noon light",
             location_tags=["outdoors", "rooftop garden", "wooden deck", "planters", "crowd",
                            "blurry background"],
             lighting=["daylight", "bright", "soft sun"])

# (purpose, nrole, transition, camera, focus, pose, moment)
T = [
 ("ESTABLISHING", "ESTABLISH", "START", "full body, eye level", "her and the crowd", "kneeling",
  "{S} kneels on the mat at {place} in {look}, the fake cat ears crooked over her halo."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "ears and halo", "kneeling",
  "The fake ears lean against her halo and the bell rings at her collar."),
 ("REACTION", "REACTION", "CONTINUOUS", "cowboy shot, eye level", "her eyes", "kneeling",
  "She looks up from under her bangs and away."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her hands", "kneeling",
  "Her hands rest flat on her thighs, fingers curled like paws."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, eye level", "her face", "kneeling",
  "Someone in the crowd points; she smiles like a saint."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "the bell", "kneeling",
  "The bell at her collar rings every time she breathes."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from below", "her and the crowd", "kneeling",
  "She settles her weight and keeps kneeling for them."),
 ("REACTION", "PROLONG", "CONTINUOUS", "close-up", "her mouth", "kneeling",
  "She says nothing at all."),
 ("ACTION", "INITIATE", "CONTINUOUS", "full body", "going down", "on all fours",
  "She lowers onto her hands and knees on {floor}."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her palms", "on all fours",
  "Her palms press flat into the deck."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "crawling", "on all fours",
  "She crawls one step toward the watching crowd."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "capelet", "on all fours",
  "The white capelet slips off her shoulder and she lets it."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, eye level", "bare shoulders", "on all fours",
  "Her shoulders roll free, skin bright under the {light_word}."),
 ("ACTION", "INITIATE", "CONTINUOUS", "cowboy shot, eye level", "a hand above her", "on all fours",
  "An unseen hand lifts the leash; she follows it on all fours."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her tail", "on all fours",
  "Her tail lifts and the bell answers it."),
 ("REACTION", "PROLONG", "CAMERA_CUT", "full body, from behind", "from behind", "on all fours",
  "From behind, her hips sway once and stop."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "the dress front", "on all fours",
  "Her fingers find the dress front and pull it loose."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "open dress", "on all fours",
  "The {core} hangs open; her breath lifts her chest."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "crawling half-bare", "on all fours",
  "She crawls on with the dress open, ears still straight up."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from behind", "bare back", "on all fours",
  "From behind, her back is bare above the fallen dress."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her chest", "on all fours",
  "Her nipples harden in the open air."),
 ("ACTION", "PROLONG", "SAME_MOMENT", "close-up, from above", "hand on a breast", "on all fours",
  "She palms her own breast without looking up."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body, eye level", "her thumb", "on all fours",
  "Her thumb drags across the nipple and she keeps her eyes on the deck."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her mouth", "on all fours",
  "Her tongue touches her lower lip."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from below", "rolling over", "on back",
  "She rolls onto her back on the mat and lets her knees fall open."),
 ("ACTION", "INITIATE", "CONTINUOUS", "full body, eye level", "hands at her hip", "on back",
  "She works the {core} down over her hips."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "falling fabric", "on back",
  "The dress slides past her knees to the deck."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, eye level", "nude with ears on", "on back",
  "Nude now, she lies back with the collar, the bell, the tail and the fake ears still on."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "hand on her stomach", "on back",
  "Her hand slides down her stomach and does not stop."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her fingers", "on back",
  "Her fingers find her sex and stay there."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "arched back", "on back",
  "Her back arches off the mat and the bell rings."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her jaw", "on back",
  "Her jaw slackens; the crowd keeps moving."),
 ("ACTION", "INITIATE", "CONTINUOUS", "cowboy shot", "blindfold", "on back",
  "Someone folds a strip of cloth over her eyes."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "the knot", "on back",
  "The blindfold is tied behind her head; the fake ears stay on."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from side", "blind, hand moving", "on back",
  "From the side, blindfolded, her hand keeps moving."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "wet fingers", "on back",
  "Her fingers glisten in the {light_word}; she stops."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "spread legs", "on back",
  "Her knees fall wider and she starts again."),
 ("DETAIL", "DETAIL", "SAME_MOMENT", "upper body, from behind", "shoulder blades", "on back",
  "From behind, her shoulder blades lift with each breath."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from below", "two fingers", "on back",
  "She pushes two fingers deeper and the bell rings faster."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, from above", "her face", "on back",
  "Her head tips back, mouth open, no sound."),
 ("CLIMAX", "PEAK", "CONTINUOUS", "full body, from below", "her hips", "on back",
  "Her hips jerk once against her hand."),
 ("CLIMAX", "DETAIL", "SAME_MOMENT", "close-up", "her throat", "on back",
  "Her eyes shut under the blindfold and her throat works."),
 ("AFTERMATH", "RESOLUTION", "CAMERA_CUT", "full body, eye level", "on her side", "on side",
  "She pulls her hand away and curls onto her side."),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "cowboy shot", "cover and sweat", "on side",
  "Sweat shines on her chest; she pulls the dress over one shoulder."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "wet hand on fabric", "on side",
  "Her hand, still wet, closes on the white fabric."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, from behind", "over the shoulder", "on side",
  "She looks back over her shoulder at the crowd."),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "full body, eye level", "half-covered", "on side",
  "{S} lies half-covered on the mat, breathing hard, ears flat."),
 ("REACTION", "RESOLUTION", "CAMERA_CUT", "close-up, eye level", "her eyes", "on side",
  "She lifts her head, meets the camera, and the fake ears stay on."),
]
assert len(T) == 48

STAGE = {}
for i in range(1, 9): STAGE[i] = 1
for i in range(9, 17): STAGE[i] = 2
for i in range(17, 29): STAGE[i] = 3
for i in range(29, 43): STAGE[i] = 4
for i in range(43, 49): STAGE[i] = 5

FRAMINGS = ["wide shot", "cowboy shot", "upper body", "full body", "close-up"]
ANGLES = ["from above", "from below", "from side", "from behind", "three-quarter view"]


def camera_tags(camera):
    low = camera.lower()
    tags = [f for f in FRAMINGS if f in low][:1] or ["cowboy shot"]
    return tags + [a for a in ANGLES if a in low]


def stages():
    s2 = list(dict.fromkeys([t for t in FULL if t not in CORE] + ["off shoulder"]))
    s3 = list(CORE) + ["open clothes", "breasts out", "cleavage"]
    s5 = [FULL[0], "off shoulder", "covered", "sweat"]
    return {"stage1": list(FULL), "stage2": s2, "stage3": s3, "stage4": list(NUDES), "stage5": s5}


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
APPROVAL = {"status": "APPROVED",
            "evidence": "User 2026-11-19: 'idea cho 1 nhân vật nữ kiểu petplay' + 'khác nun đi' + 'không cần pose đứng'; Mika angel, adult, fictional, consensual, explicit; rev2 pose tags fixed."}
W = dict(S=NAME, place=VENUE["place"], floor=VENUE["floor"], light_word=VENUE["light_word"],
         core=CORE[0], look="a " + FULL[0] + " with " + ", ".join(FULL[1:]))
BASE = ROOT / "sources" / SLUG


def existing_sid():
    f = BASE / "story_id.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def seed():
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "story.md").write_text(
        f"{TITLE}\n\n{NAME}, an adult angel, kneels at {VENUE['place']} wearing fake cat ears, a collar and a bell, "
        f"and obeys commands in front of the crowd. Explicit, consensual, fictional.\n", encoding="utf-8")
    sid = existing_sid()
    if sid is None:
        sid = cli("database/src/n2m_db.py", "create-story", "--title", TITLE, "--mode", "NON_BLIND",
                  "--text-file", str(BASE / "story.md"))
        (BASE / "story_id.txt").write_text(sid, encoding="utf-8")
    cli("database/src/n2m_db.py", "add-role", "--story-id", sid, "--key", "LEAD",
        "--description", f"{NAME}, adult angel, petplay")
    cli("database/src/n2m_db.py", "bind-role", "--story-id", sid, "--key", "LEAD",
        "--character-id", CHAR_ID)
    events = [
        (f"{NAME} kneels on the mat in fake cat ears and obeys a command in front of the crowd.", "She smiles like a saint."),
        (f"She crawls on all fours as the leash lifts, the white dress falling open.", "The crowd thinks it is a show."),
        (f"She rolls onto her back and works the dress off her hips.", "Nude with the collar, bell, tail and ears still on."),
        (f"Blindfolded, she touches herself to the edge and stops twice before she finishes.", "The bell rings faster; the crowd keeps moving."),
        (f"Spent, she curls onto her side, pulls the dress over one shoulder and looks into the camera.", "Afterglow in daylight."),
    ]
    plan = {"schema_version": "n2m.story.v1", "story_id": sid, "revision": 1, "approval": APPROVAL,
            "source_refs": [{"type": "user_story", "id": SLUG, "status": "confirmed"}],
            "intent": {"content_profile": "adult", "raw_labels": ["mature", "nsfw", "explicit"],
                       "constraints": ["Solo adult woman, consensual petplay.", "Poses vary: kneeling, all fours, on back, on side.",
                                       "3:4 portrait framing.", "Bright crowded venue.", "Fake ears, collar, bell, tail in every shot."]},
            "characters": [{"character_id": CHAR_ID, "name": NAME, "age_status": "verified_adult",
                            "identity_anchors": ANCHORS}],
            "acts": [{"act_id": "A01", "beats": []}]}
    for i, (a, r) in enumerate(events, 1):
        plan["acts"][0]["beats"].append({"beat_id": f"B{i:02d}",
            "events": [{"event_id": f"E{i:03d}", "actor_id": NAME, "primary_action": a,
                        "target_id": None, "reaction": r}]})
    (BASE / "story_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("database/src/n2m_workflow.py", "save-plan", "--story-id", sid, "--file", str(BASE / "story_plan.json"))
    if con.execute("select count(*) from beats b join acts a on a.id=b.act_id where a.story_id=?", (sid,)).fetchone()[0]:
        return sid
    act_id = cli("database/src/n2m_workflow.py", "add-act", "--story-id", sid, "--order", "1",
                 "--title", "A01", "--summary", VENUE["place"])
    for i, (a, r) in enumerate(events, 1):
        beat_id = cli("database/src/n2m_workflow.py", "add-beat", "--act-id", act_id, "--order", str(i),
                      "--summary", a[:180])
        ev = {"actor_role_key": "LEAD", "target_role_key": None, "action": a, "reaction": r,
              "raw_labels": ["nsfw", "explicit"], "source_fragment": VENUE["place"],
              "spec": {"solo": True, "tier": "explicit", "petplay": True, "fake_ears": True}}
        f = BASE / f"event_{i:02d}.json"
        f.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        cli("database/src/n2m_workflow.py", "add-event", "--beat-id", beat_id, "--order", "1", "--file", str(f))
    return sid


def board(sid, force=False):
    have = con.execute("select id from storyboards where story_id=? order by revision desc limit 1", (sid,)).fetchone()
    if have and not force:
        return have[0]
    rev = con.execute("select current_revision from stories where id=?", (sid,)).fetchone()[0]
    beats = list(con.execute("""select b.id beat_id, b.beat_order, e.id event_id from beats b
        join acts a on a.id=b.act_id left join story_events e on e.beat_id=b.id
        where a.story_id=? order by b.beat_order, e.event_order""", (sid,)))
    B = {r["beat_order"]: r for r in beats}
    plan = {"schema_version": 5, "story_revision": rev, "approval": APPROVAL,
            "visual_bible": {
                "characters": {"LEAD": {"description": f"{NAME}, adult angel, white dress, fake cat ears",
                                        "provenance": "catalog character + character_tags",
                                        "character_id": CHAR_ID, "outfit_id": None,
                                        "prompt_tags": ["mika (blue archive)"] + ANCHORS,
                                        "outfits": {k: {"prompt_tags": v} for k, v in stages().items()}}},
                "locations": {"venue": {"description": VENUE["place"], "provenance": "story brief",
                                        "prompt_tags": VENUE["location_tags"]}},
                "props": {},
                "styles": {"anime-bright": {"description": "Clean bright anime, high-key, crowded public venue",
                                            "provenance": "user choice",
                                            "prompt_tags": ["anime style", "clean lineart", "bright colors",
                                                            "cinematic lighting", "@anjing"]}}},
            "scenes": {"scene-main": {"location_key": "venue", "style_key": "anime-bright",
                                      "time_key": "day", "role_keys": ["LEAD"],
                                      "lighting_tags": VENUE["lighting"]}},
            "shots": [], "coverage": []}
    t = 0
    for i, (purpose, nrole, transition, camera, focus, pose, moment) in enumerate(T, 1):
        k = f"S{i:02d}"
        beat = 1 if i <= 8 else 2 if i <= 16 else 3 if i <= 28 else 4 if i <= 38 else 5
        if transition != "SAME_MOMENT":
            t += 1
        plan["shots"].append({
            "shot_key": k, "shot_order": i, "beat_id": B[beat]["beat_id"], "branch_key": "main",
            "previous_shot_key": None if i == 1 else f"S{i-1:02d}", "transition": transition,
            "purpose": purpose, "narrative_role": nrole, "story_time": t, "scene_key": "scene-main",
            "camera": camera, "focus": focus, "visual_moment": moment.format(**W),
            "role_keys": ["LEAD"], "location_key": "venue",
            "visible_location_tags": VENUE["location_tags"], "prop_keys": [],
            "style_key": "anime-bright", "outfit_key": f"stage{STAGE[i]}", "pose": pose})
        plan["coverage"].append({"event_id": B[beat]["event_id"], "status": "VISUALIZED",
                                 "shot_key": k, "evidence": plan["shots"][-1]["visual_moment"]})
    f = BASE / "storyboard_v5.json"
    f.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return cli("database/src/n2m_workflow.py", "save-storyboard", "--story-id", sid, "--file", str(f))[0]


def shots(sid):
    base = BASE / "shots"
    base.mkdir(parents=True, exist_ok=True)
    board_id = con.execute("select id from storyboards where story_id=? order by revision desc limit 1",
                           (sid,)).fetchone()[0]
    plan = json.loads(con.execute("select plan_json from storyboards where id=?", (board_id,)).fetchone()[0])
    scene = plan["scenes"]["scene-main"]
    events = {r["beat_id"]: r for r in con.execute(
        "select e.beat_id, e.id, e.action from story_events e join beats b on b.id=e.beat_id "
        "join acts a on a.id=b.act_id where a.story_id=?", (sid,))}
    prev_outfit, prev_pose = None, None
    for slot in plan["shots"]:
        ev = events[slot["beat_id"]]
        pose = slot["pose"]
        at = {"outfit_key": slot["outfit_key"], "pose": pose,
              "position": VENUE["place_short"], "holding": "none"}
        before = {"outfit_key": prev_outfit or slot["outfit_key"], "pose": prev_pose or pose,
                  "position": VENUE["place_short"], "holding": "none"}
        at_delta = {"set": {k: v for k, v in at.items() if before.get(k) != v}, "remove": []}
        act = ["blindfold"] if (33 <= plan["shots"].index(slot) + 1 <= 38) else []
        act += [pose]
        spec = {"visual_context_sha256": con.execute(
                    "select context_sha256 from storyboard_shots where storyboard_id=? and shot_key=?",
                    (board_id, slot["shot_key"])).fetchone()[0],
                "outfit_key": slot["outfit_key"], "camera": slot["camera"], "focus": slot["focus"],
                "location_key": slot["location_key"], "participants": [{"role_key": "LEAD"}],
                "interactions": [{"event_id": ev["id"], "actor_role_key": "LEAD", "target_role_key": None,
                                  "action_text": ev["action"]}],
                "prompt_blocks": {"prefix": ["masterpiece", "best quality", "explicit"],
                                  "subjects": ["1girl", "solo"],
                                  "action": (["undressing"] if prev_outfit and prev_outfit != slot["outfit_key"] else []) + act,
                                  "camera": camera_tags(slot["camera"]),
                                  "prose": slot["visual_moment"]}}
        scene_state = {"location_key": scene["location_key"], "time_key": scene["time_key"]}
        snaps = [{"role_key": None, "before": scene_state, "delta": {"set": {}, "remove": []},
                  "after": scene_state,
                  "moment": {"at_shot": scene_state, "at_delta": {"set": {}, "remove": []},
                             "after_delta": {"set": {}, "remove": []}}},
                 {"role_key": "LEAD", "before": before, "delta": at_delta, "after": at,
                  "moment": {"at_shot": {**before, **at_delta["set"]}, "at_delta": at_delta,
                             "after_delta": {"set": {}, "remove": []}}}]
        sf, cf = base / f"{slot['shot_key']}.shot.json", base / f"{slot['shot_key']}.cont.json"
        sf.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        cf.write_text(json.dumps({"snapshots": snaps}, ensure_ascii=False, indent=1), encoding="utf-8")
        res = cli("database/src/n2m_workflow.py", "save-shot", "--beat-id", slot["beat_id"],
                  "--shot-key", slot["shot_key"], "--file", str(sf), "--event-id", ev["id"])
        shot_id = res[0] if isinstance(res, list) else res
        cli("database/src/n2m_workflow.py", "save-continuity", "--shot-id", shot_id, "--file", str(cf))
        cli("database/src/n2m_workflow.py", "compile-prompt", "--shot-id", shot_id, "--save")
        print(SLUG, slot["shot_key"], pose, flush=True)
        prev_outfit, prev_pose = slot["outfit_key"], pose


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    sid = existing_sid()
    if phase in ("all", "seed") or sid is None:
        sid = seed()
        print("SEED", sid, flush=True)
    if phase in ("all", "boards"):
        print("BOARD", board(sid, force="--force" in sys.argv), flush=True)
    if phase in ("all", "shots"):
        shots(sid)
