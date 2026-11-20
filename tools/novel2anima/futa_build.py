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


FUTA = ["futanari", "penis", "testicles", "masturbation"]
STORIES = [
 dict(slug="tsurugi_futa_chapel", title="Futa Chapel - Tsurugi",
      char_id="character:storyaura_danbooru_csv:fe2e3673780079dd0f", name="Tsurugi",
      anchors=["black hair", "very long hair", "long hair", "red eyes", "halo", "red halo",
               "black wings", "low wings", "black halo", "large breasts", "blunt bangs"],
      place="the chapel hall at noon", short="the chapel", seat="the chapel pew", light="stained light",
      loc=["indoors", "chapel", "hall", "pews", "stained glass", "crowd", "blurry background"],
      lighting=["daylight", "bright", "stained light"],
      top="a black sailor dress", skirt="a black torn skirt", legs="black thighhighs",
      tie="her red ribbon", extra="her armband",
      stages={
        "s1": ["black sailor dress", "sailor collar", "red neckerchief", "black skirt", "black thighhighs",
               "black boots", "torn clothes"],
        "s2": ["black sailor dress", "open clothes", "black skirt", "black thighhighs", "no bra"] + FUTA,
        "s3": ["black skirt", "black thighhighs", "breasts out", "no bra"] + FUTA + ["erection"],
        "s4": ["completely nude", "nipples", "navel", "barefoot"] + FUTA + ["cum"],
        "s5": ["black sailor dress", "covered", "sweat", "cum on body"] + FUTA}),
 dict(slug="hasumi_futa_cloister", title="Futa Cloister - Hasumi",
      char_id="character:storyaura_danbooru_csv:57cfe11b439e765bf2", name="Hasumi",
      anchors=["black hair", "very long hair", "long hair", "red eyes", "halo", "red halo",
               "black wings", "low wings", "huge breasts", "large breasts", "black choker", "ponytail"],
      place="the cloister walk at noon", short="the cloister", seat="the cloister bench", light="court light",
      loc=["indoors", "cloister", "stone arches", "courtyard", "crowd", "blurry background"],
      lighting=["daylight", "bright", "soft light"],
      top="a black shirt", skirt="a long black skirt", legs="black thighhighs",
      tie="her red neckerchief", extra="her garter straps",
      stages={
        "s1": ["black shirt", "white sailor collar", "red neckerchief", "black long skirt", "black thighhighs",
               "garter straps", "black choker"],
        "s2": ["black shirt", "open clothes", "black long skirt", "black thighhighs", "garter straps",
               "no bra"] + FUTA,
        "s3": ["black long skirt", "black thighhighs", "garter straps", "breasts out", "no bra"] + FUTA + ["erection"],
        "s4": ["completely nude", "nipples", "navel", "barefoot"] + FUTA + ["cum"],
        "s5": ["black shirt", "covered", "sweat", "cum on body"] + FUTA}),
 dict(slug="mashiro_futa_garden", title="Futa Garden - Mashiro",
      char_id="character:storyaura_danbooru_csv:ffdd244f510c7263ad", name="Mashiro",
      anchors=["black hair", "long hair", "purple eyes", "halo", "winged halo", "red halo",
               "black wings", "low wings", "black choker", "short hair"],
      place="the convent garden at noon", short="the garden", seat="the garden bench", light="noon light",
      loc=["outdoors", "convent garden", "hedges", "fountain", "crowd", "blurry background"],
      lighting=["daylight", "bright", "soft sun"],
      top="a black sailor shirt", skirt="a black pleated skirt", legs="black thighhighs",
      tie="her red ribbon", extra="her justice armband",
      stages={
        "s1": ["black sailor shirt", "sailor collar", "red armband", "black pleated skirt", "black thighhighs",
               "black choker"],
        "s2": ["black sailor shirt", "open clothes", "black pleated skirt", "black thighhighs", "no bra"] + FUTA,
        "s3": ["black pleated skirt", "black thighhighs", "breasts out", "no bra"] + FUTA + ["erection"],
        "s4": ["completely nude", "nipples", "navel", "barefoot"] + FUTA + ["cum"],
        "s5": ["black sailor shirt", "covered", "sweat", "cum on body"] + FUTA}),
]

# (purpose, nrole, transition, camera, focus, pose, outfit, moment)
T = [
 ("ESTABLISHING", "ESTABLISH", "START", "full body, eye level", "her and the crowd", "standing", "s1",
  "{S} stands at {place} in {top}, {skirt} and {legs}, the noon crowd blurred behind her."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from below", "her halo", "standing", "s1",
  "Her halo catches the {light} above the crowd."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, eye level", "her eyes", "standing", "s1",
  "Her eyes flick to the camera and away."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her collar", "standing", "s1",
  "Her sailor collar sits flat under the ribbon."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, eye level", "her face", "standing", "s1",
  "A guest bows to her; she does not bow back."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her leg", "standing", "s1",
  "The {legs} hug her thigh."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, three-quarter view", "her hip", "standing", "s1",
  "She shifts her weight; the skirt rides up."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her hand", "standing", "s1",
  "Her fingers tighten at her side."),
 ("ACTION", "INITIATE", "CONTINUOUS", "cowboy shot", "her skirt", "standing", "s1",
  "She pulls the skirt up and the front of it tents."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot", "the bulge", "standing", "s2",
  "The fabric strains at her groin."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body", "the skirt", "standing", "s2",
  "She drags the skirt down past her hips."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "full body", "bare legs", "standing", "s2",
  "The skirt hits the floor; the {legs} are left on her legs."),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, eye level", "the seat", "sitting", "s2",
  "She sits on {seat} and opens her legs."),
 ("REACTION", "PROLONG", "CONTINUOUS", "upper body, eye level", "her face", "sitting", "s2",
  "She looks at the crowd and bites her lip."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her crotch", "sitting", "s2",
  "Her cock pushes out of her underwear, half hard."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body", "her cock", "sitting", "s2",
  "She pulls the underwear aside and lets it stand."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "her shirt", "standing", "s3",
  "She pulls the shirt over her head."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her chest", "standing", "s3",
  "Her breasts are bare; her cock stands from her groin."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "standing nude", "standing", "s3",
  "She stands with her cock out in front of the crowd."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from behind", "her back", "standing", "s3",
  "From behind, her back is bare and her wings spread."),
 ("ACTION", "PROLONG", "SAME_MOMENT", "close-up, from above", "her cock", "standing", "s3",
  "She wraps one hand around the shaft."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body, eye level", "her hand", "standing", "s3",
  "The first slow stroke pulls a bead of precum."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her mouth", "standing", "s3",
  "Her mouth falls open a little."),
 ("ACTION", "INITIATE", "CONTINUOUS", "cowboy shot", "her hand", "kneeling", "s3",
  "She kneels and strokes faster."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her cock", "kneeling", "s3",
  "Precum strings from her tip."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from below", "her hips", "kneeling", "s3",
  "Her hips push into her fist."),
 ("ACTION", "INITIATE", "CONTINUOUS", "full body", "cum", "kneeling", "s4",
  "She comes; the first shot hits her stomach."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "cum", "kneeling", "s4",
  "Streaks of cum slide down her belly."),
 ("ESTABLISHING", "PROLONG", "SAME_MOMENT", "close-up", "her cock", "kneeling", "s4",
  "She keeps stroking through the aftershock."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from behind", "from behind", "on all fours", "s4",
  "She drops onto all fours, her cock hanging between her thighs."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her thighs", "on all fours", "s4",
  "Cum drips from her thigh onto the floor."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "on her knees", "kneeling", "s4",
  "She sits back on her knees and strokes again."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her hand", "kneeling", "s4",
  "Her fist works her cock, still wet."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her jaw", "kneeling", "s4",
  "Her jaw slackens; the crowd keeps moving."),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, eye level", "on her back", "on back", "s4",
  "She lies back on the ground and opens her legs."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her cock", "on back", "s4",
  "Her cock lies hard on her stomach, in her own cum."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from side", "arched back", "on back", "s4",
  "From the side, her spine arches off the ground."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her face", "on back", "s4",
  "Her head tips back, mouth open."),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, eye level", "sitting up", "sitting", "s4",
  "She sits up on {seat} again and jerks herself hard."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "upper body, from behind", "shoulder blades", "sitting", "s4",
  "From behind, her shoulder blades lift with each breath."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from below", "two hands", "sitting", "s4",
  "She uses both hands and her heel slides."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, from above", "her head tipped back", "sitting", "s4",
  "Her head falls back."),
 ("CLIMAX", "PEAK", "CAMERA_CUT", "full body, from below", "her hips", "on back", "s4",
  "She comes again, harder, and it lands across her chest."),
 ("CLIMAX", "DETAIL", "CONTINUOUS", "close-up", "her throat", "on back", "s4",
  "Cum streaks her throat and chin."),
 ("AFTERMATH", "RESOLUTION", "CAMERA_CUT", "full body, eye level", "on her side", "on side", "s5",
  "She curls onto her side, still holding her cock."),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "cowboy shot", "sweat", "on side", "s5",
  "Sweat and cum shine on her; she lifts the shirt over one shoulder."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, from behind", "over the shoulder", "on side", "s5",
  "She looks back over her shoulder at the crowd."),
 ("REACTION", "RESOLUTION", "CAMERA_CUT", "close-up, eye level", "her eyes", "on side", "s5",
  "She meets the camera one last time."),
]
assert len(T) == 48

FRAMINGS = ["wide shot", "cowboy shot", "upper body", "full body", "close-up"]
ANGLES = ["from above", "from below", "from side", "from behind", "three-quarter view"]


def camera_tags(camera):
    low = camera.lower()
    tags = [f for f in FRAMINGS if f in low][:1] or ["cowboy shot"]
    return tags + [a for a in ANGLES if a in low]


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
APPROVAL = {"status": "APPROVED",
            "evidence": "User 2026-11-19: group 'Trinity Justice Task Force' (Tsurugi, Hasumi, Mashiro), concept 'futa' with self-stroking and cum over the body, outfit 'trang phuc origin' (canon JTF uniform); adults, fictional, consensual, explicit."}


def existing_sid(slug):
    f = ROOT / "sources" / slug / "story_id.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def seed(S):
    slug = S["slug"]
    base = ROOT / "sources" / slug
    base.mkdir(parents=True, exist_ok=True)
    (base / "story.md").write_text(
        f"{S['title']}\n\n{S['name']}, an adult futanari woman in her canon Justice Task Force uniform, stands at "
        f"{S['place']}, strips fully nude in front of the crowd, strokes her cock and comes over her own body. "
        f"Explicit, consensual, fictional.\n", encoding="utf-8")
    sid = existing_sid(slug)
    if sid is None:
        sid = cli("database/src/n2m_db.py", "create-story", "--title", S["title"], "--mode", "NON_BLIND",
                  "--text-file", str(base / "story.md"))
        (base / "story_id.txt").write_text(sid, encoding="utf-8")
    cli("database/src/n2m_db.py", "add-role", "--story-id", sid, "--key", "LEAD",
        "--description", f"{S['name']}, adult futanari woman, canon JTF uniform")
    cli("database/src/n2m_db.py", "bind-role", "--story-id", sid, "--key", "LEAD",
        "--character-id", S["char_id"])
    events = [
        (f"{S['name']} pulls her skirt up at {S['place']} and the front of it tents; she is hard under the cloth.", "Nobody stops her."),
        (f"She drops the skirt, sits on {S['seat']} and pulls her cock out in front of the crowd.", "The crowd blurs behind her."),
        (f"Her shirt comes off; she kneels and strokes her cock, precum at the tip.", "Her breath breaks; she does not stop."),
        (f"She comes on her own stomach, then drops onto all fours and keeps stroking.", "The crowd keeps moving."),
        (f"On her back and then sitting on {S['seat']}, she works herself to a second climax across her chest.", "She finishes in daylight."),
        (f"Spent, she curls onto her side, cum drying on her skin, and looks into the camera.", "Afterglow at noon."),
    ]
    plan = {"schema_version": "n2m.story.v1", "story_id": sid, "revision": 1, "approval": APPROVAL,
            "source_refs": [{"type": "user_story", "id": slug, "status": "confirmed"}],
            "intent": {"content_profile": "adult", "raw_labels": ["mature", "nsfw", "explicit", "futanari"],
                       "constraints": ["Solo adult futanari woman, consensual.",
                                       f"Outfit: canon Justice Task Force uniform ({S['top']}, {S['skirt']}, {S['legs']}).",
                                       "Self-stroking and two cumshots over her own body.",
                                       "Ends nude, cum on skin; poses: standing, sitting, kneeling, all fours, on back, on side.",
                                       "3:4 portrait.", f"Bright crowded venue: {S['place']}."]},
            "characters": [{"character_id": S["char_id"], "name": S["name"], "age_status": "verified_adult",
                            "identity_anchors": S["anchors"]}],
            "acts": [{"act_id": "A01", "beats": []}]}
    for i, (a, r) in enumerate(events, 1):
        plan["acts"][0]["beats"].append({"beat_id": f"B{i:02d}",
            "events": [{"event_id": f"E{i:03d}", "actor_id": S["name"], "primary_action": a,
                        "target_id": None, "reaction": r}]})
    (base / "story_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("database/src/n2m_workflow.py", "save-plan", "--story-id", sid, "--file", str(base / "story_plan.json"))
    if con.execute("select count(*) from beats b join acts a on a.id=b.act_id where a.story_id=?", (sid,)).fetchone()[0]:
        return sid
    act_id = cli("database/src/n2m_workflow.py", "add-act", "--story-id", sid, "--order", "1",
                 "--title", "A01", "--summary", S["place"])
    for i, (a, r) in enumerate(events, 1):
        beat_id = cli("database/src/n2m_workflow.py", "add-beat", "--act-id", act_id, "--order", str(i),
                      "--summary", a[:180])
        ev = {"actor_role_key": "LEAD", "target_role_key": None, "action": a, "reaction": r,
              "raw_labels": ["nsfw", "explicit", "futanari"], "source_fragment": S["place"],
              "spec": {"solo": True, "tier": "explicit", "outfit": "canon JTF uniform"}}
        f = base / f"event_{i:02d}.json"
        f.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        cli("database/src/n2m_workflow.py", "add-event", "--beat-id", beat_id, "--order", "1", "--file", str(f))
    return sid


def board(S, sid, force=False):
    slug = S["slug"]
    base = ROOT / "sources" / slug
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
                "characters": {"LEAD": {"description": f"{S['name']}, adult futanari, canon JTF uniform",
                                        "provenance": "user concept + canon outfit (Blue Archive wiki)",
                                        "character_id": S["char_id"], "outfit_id": None,
                                        "prompt_tags": [S["name"].lower() + " (blue archive)"] + S["anchors"],
                                        "outfits": {k: {"prompt_tags": v} for k, v in S["stages"].items()}}},
                "locations": {"venue": {"description": S["place"], "provenance": "story brief",
                                        "prompt_tags": S["loc"]}},
                "props": {},
                "styles": {"anime-bright": {"description": "Clean bright anime, high-key, crowded public venue",
                                            "provenance": "user choice",
                                            "prompt_tags": ["anime style", "clean lineart", "bright colors",
                                                            "cinematic lighting", "@anjing"]}}},
            "scenes": {"scene-main": {"location_key": "venue", "style_key": "anime-bright",
                                      "time_key": "day", "role_keys": ["LEAD"],
                                      "lighting_tags": S["lighting"]}},
            "shots": [], "coverage": []}
    t = 0
    for i, (purpose, nrole, transition, camera, focus, pose, outfit, moment) in enumerate(T, 1):
        k = f"S{i:02d}"
        beat = 1 if i <= 9 else 2 if i <= 16 else 3 if i <= 26 else 4 if i <= 32 else 5 if i <= 42 else 6
        if transition != "SAME_MOMENT":
            t += 1
        word = dict(S=S["name"], place=S["place"], seat=S["seat"], light=S["light"], top=S["top"],
                    skirt=S["skirt"], legs=S["legs"], tie=S["tie"], extra=S["extra"])
        plan["shots"].append({
            "shot_key": k, "shot_order": i, "beat_id": B[beat]["beat_id"], "branch_key": "main",
            "previous_shot_key": None if i == 1 else f"S{i-1:02d}", "transition": transition,
            "purpose": purpose, "narrative_role": nrole, "story_time": t, "scene_key": "scene-main",
            "camera": camera, "focus": focus, "visual_moment": moment.format(**word),
            "role_keys": ["LEAD"], "location_key": "venue",
            "visible_location_tags": S["loc"], "prop_keys": [],
            "style_key": "anime-bright", "outfit_key": outfit, "pose": pose})
        plan["coverage"].append({"event_id": B[beat]["event_id"], "status": "VISUALIZED",
                                 "shot_key": k, "evidence": plan["shots"][-1]["visual_moment"]})
    f = base / "storyboard_v5.json"
    f.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return cli("database/src/n2m_workflow.py", "save-storyboard", "--story-id", sid, "--file", str(f))[0]


def shots(S, sid):
    slug = S["slug"]
    base = ROOT / "sources" / slug / "shots"
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
        at = {"outfit_key": slot["outfit_key"], "pose": pose, "position": S["short"], "holding": "none"}
        before = {"outfit_key": prev_outfit or slot["outfit_key"], "pose": prev_pose or pose,
                  "position": S["short"], "holding": "none"}
        at_delta = {"set": {k: v for k, v in at.items() if before.get(k) != v}, "remove": []}
        spec = {"visual_context_sha256": con.execute(
                    "select context_sha256 from storyboard_shots where storyboard_id=? and shot_key=?",
                    (board_id, slot["shot_key"])).fetchone()[0],
                "outfit_key": slot["outfit_key"], "camera": slot["camera"], "focus": slot["focus"],
                "location_key": slot["location_key"], "participants": [{"role_key": "LEAD"}],
                "interactions": [{"event_id": ev["id"], "actor_role_key": "LEAD", "target_role_key": None,
                                  "action_text": ev["action"]}],
                "prompt_blocks": {"prefix": ["masterpiece", "best quality", "explicit"],
                                  "subjects": ["1girl", "solo"],
                                  "action": (["undressing"] if prev_outfit and prev_outfit != slot["outfit_key"] else []) + [pose],
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
        print(slug, slot["shot_key"], pose, slot["outfit_key"], flush=True)
        prev_outfit, prev_pose = slot["outfit_key"], pose


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    for S in STORIES:
        sid = existing_sid(S["slug"])
        if phase in ("all", "seed") or sid is None:
            sid = seed(S)
            print("SEED", S["slug"], sid, flush=True)
        if phase in ("all", "boards"):
            print("BOARD", S["slug"], board(S, sid, force="--force" in sys.argv), flush=True)
        if phase in ("all", "shots"):
            shots(S, sid)
