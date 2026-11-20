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


COMMON_TAIL = ["high heels"]

STORIES = [
 dict(slug="saori_maid_cafe", title="Maid Cafe - Saori",
      char_id="character:storyaura_danbooru_csv:f4a35fa3f2d4d24d14", name="Saori",
      anchors=["black hair", "long hair", "blue eyes", "halo", "large breasts", "colored inner hair"],
      place="the maid cafe main floor at noon", short="the cafe", seat="the cafe bench", light="cafe light",
      loc=["indoors", "maid cafe", "tables", "crowd", "blurry background"],
      lighting=["daylight", "bright", "warm light"],
      top="a maid blouse", skirt="a micro maid skirt", legs="white thighhighs",
      tie="her apron ribbon", extra="her headdress",
      stages={
        "s1": ["maid", "maid headdress", "apron", "white blouse", "micro skirt", "white thighhighs",
               "garter belt"] + COMMON_TAIL,
        "s2": ["maid", "apron", "white blouse", "open clothes", "micro skirt", "no bra",
               "white thighhighs", "garter belt"] + COMMON_TAIL,
        "s3": ["maid", "apron", "micro skirt", "white thighhighs", "breasts out", "no bra"] + COMMON_TAIL,
        "s4": ["completely nude", "nipples", "navel", "barefoot"] + COMMON_TAIL,
        "s5": ["maid", "apron", "covered", "sweat", "white thighhighs"] + COMMON_TAIL}),
 dict(slug="atsuko_maid_banquet", title="Maid Banquet - Atsuko",
      char_id="character:storyaura_danbooru_csv:244c832f885eab513e", name="Atsuko",
      anchors=["purple hair", "long hair", "red eyes", "halo", "hair bow", "hair between eyes"],
      place="the hotel banquet hall at noon", short="the banquet hall", seat="the banquet chair",
      light="chandelier light",
      loc=["indoors", "banquet hall", "long table", "chandelier", "crowd", "blurry background"],
      lighting=["daylight", "bright", "warm light"],
      top="a maid blouse", skirt="a micro maid skirt", legs="black thighhighs",
      tie="her apron ribbon", extra="her headdress",
      stages={
        "s1": ["maid", "maid headdress", "apron", "white blouse", "micro skirt", "black thighhighs",
               "garter belt"] + COMMON_TAIL,
        "s2": ["maid", "apron", "white blouse", "open clothes", "micro skirt", "no bra",
               "black thighhighs", "garter belt"] + COMMON_TAIL,
        "s3": ["maid", "apron", "micro skirt", "black thighhighs", "breasts out", "no bra"] + COMMON_TAIL,
        "s4": ["completely nude", "nipples", "navel", "barefoot"] + COMMON_TAIL,
        "s5": ["maid", "apron", "covered", "sweat", "black thighhighs"] + COMMON_TAIL}),
 dict(slug="hiyori_maid_atrium", title="Maid Atrium - Hiyori",
      char_id="character:storyaura_danbooru_csv:4d17f43556a3cda47b", name="Hiyori",
      anchors=["green hair", "aqua hair", "long hair", "green eyes", "halo", "large breasts",
               "hair over one eye", "sun glasses", "side ponytail"],
      place="the shopping mall atrium at noon", short="the atrium", seat="the atrium planter",
      light="skylight",
      loc=["indoors", "shopping mall", "atrium", "escalator", "crowd", "blurry background"],
      lighting=["daylight", "bright", "high key"],
      top="a maid blouse", skirt="a micro maid skirt", legs="white thighhighs",
      tie="her apron ribbon", extra="her headdress",
      stages={
        "s1": ["maid", "maid headdress", "apron", "white blouse", "micro skirt", "white thighhighs",
               "garter belt"] + COMMON_TAIL,
        "s2": ["maid", "apron", "white blouse", "open clothes", "micro skirt", "no bra",
               "white thighhighs", "garter belt"] + COMMON_TAIL,
        "s3": ["maid", "apron", "micro skirt", "white thighhighs", "breasts out", "no bra"] + COMMON_TAIL,
        "s4": ["completely nude", "nipples", "navel", "barefoot"] + COMMON_TAIL,
        "s5": ["maid", "apron", "covered", "sweat", "white thighhighs"] + COMMON_TAIL}),
]

# (purpose, nrole, transition, camera, focus, pose, outfit, moment)
T = [
 ("ESTABLISHING", "ESTABLISH", "START", "full body, eye level", "her and the crowd", "standing", "s1",
  "{S} stands at {place} in {top}, {skirt} and {legs}, the noon crowd blurred behind her."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from below", "her halo", "standing", "s1",
  "Her halo catches the {light} above the crowd."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, eye level", "her eyes", "standing", "s1",
  "Her eyes flick to the camera and away."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her hand", "standing", "s1",
  "Her fingers tighten at her side."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, eye level", "her face", "standing", "s1",
  "A guest bows to her; she does not bow back."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "{tie}", "standing", "s1",
  "The {tie} sits at her throat above the open collar."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, three-quarter view", "the apron", "standing", "s1",
  "She smooths the apron over her hip and the micro skirt rides higher."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her leg", "standing", "s1",
  "The seam of her {legs} runs straight down her calf."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "{top}", "standing", "s1",
  "She unbuttons {top} down to her waist and pulls it open."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot", "her chest", "standing", "s2",
  "The shirt hangs open; her chest shows under it, no bra."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body", "{tie}", "standing", "s2",
  "She pulls {tie} loose and drops it."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "full body", "falling skirt", "standing", "s2",
  "The skirt slides down; {legs} are left on her legs."),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, eye level", "the seat", "sitting", "s2",
  "She sits on {seat} with the skirt bunched at her waist."),
 ("REACTION", "PROLONG", "CONTINUOUS", "upper body, eye level", "bare shoulders", "sitting", "s2",
  "Her shoulders roll free, skin bright under the {light}."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "her chest", "sitting", "s2",
  "The open shirt frames her breasts; she does not close it."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her {legs}", "sitting", "s2",
  "Her knee turns out and the top of her {legs} shows."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "the shirt", "kneeling", "s3",
  "She kneels and pulls the shirt off her shoulders."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her chest", "kneeling", "s3",
  "Her breasts are bare; only the skirt and {legs} are left."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "on her knees", "kneeling", "s3",
  "She kneels in front of the crowd and keeps her chin up."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from behind", "her back", "kneeling", "s3",
  "From behind, her back is bare down to the skirt at her waist."),
 ("ACTION", "PROLONG", "SAME_MOMENT", "close-up, from above", "her breast", "kneeling", "s3",
  "She palms her own breast, watching a guest walk by."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body, eye level", "her thumb", "kneeling", "s3",
  "Her thumb drags across the nipple and she breathes out."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her mouth", "kneeling", "s3",
  "Her tongue touches her lower lip."),
 ("ACTION", "INITIATE", "CONTINUOUS", "cowboy shot", "under the skirt", "kneeling", "s3",
  "Her hand slips under the skirt at her waist."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her fingers", "kneeling", "s3",
  "Her fingers find her sex under the fabric."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from below", "her hips", "kneeling", "s3",
  "Her hips rock forward against her hand."),
 ("ACTION", "INITIATE", "CONTINUOUS", "full body", "going down", "on all fours", "s4",
  "She drops onto all fours and works the skirt down her hips."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "falling fabric", "on all fours", "s4",
  "The skirt falls past her knees to the ground."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from behind", "nude from behind", "on all fours", "s4",
  "Nude now, she stays on all fours with her back to the crowd."),
 ("ACTION", "INITIATE", "CONTINUOUS", "full body, eye level", "kneeling again", "kneeling", "s4",
  "She sits back on her knees and keeps her hand moving."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her fingers", "kneeling", "s4",
  "Her fingers work slowly between her legs."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her jaw", "kneeling", "s4",
  "Her jaw slackens; the crowd keeps moving."),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, eye level", "on her back", "on back", "s4",
  "She lies back on the ground and opens her knees."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "wet fingers", "on back", "s4",
  "Her fingers glisten in the {light}."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from side", "arched back", "on back", "s4",
  "From the side, her spine arches off the ground."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "her face", "on back", "s4",
  "Her head tips back, mouth open, no sound."),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, eye level", "sitting up", "sitting", "s4",
  "She sits up on {seat} again, legs spread, and goes on."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "upper body, from behind", "shoulder blades", "sitting", "s4",
  "From behind, her shoulder blades lift with each breath."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, from below", "two fingers", "sitting", "s4",
  "She pushes two fingers deeper and her heel slides."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, from above", "her head tipped back", "sitting", "s4",
  "Her head falls back."),
 ("CLIMAX", "PEAK", "CAMERA_CUT", "full body, from below", "her hips", "on back", "s4",
  "She slides off {seat} onto her back and her hips jerk once."),
 ("CLIMAX", "DETAIL", "CONTINUOUS", "close-up", "her throat", "on back", "s4",
  "Her eyes shut and her throat works."),
 ("AFTERMATH", "RESOLUTION", "CAMERA_CUT", "full body, eye level", "on her side", "on side", "s5",
  "She pulls her hand away and curls onto her side."),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "cowboy shot", "sweat", "on side", "s5",
  "Sweat shines on her chest; she lifts the shirt over one shoulder."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "wet hand on fabric", "on side", "s5",
  "Her hand, still wet, closes on the fabric."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, from behind", "over the shoulder", "on side", "s5",
  "She looks back over her shoulder at the crowd."),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "full body, eye level", "half-covered", "on side", "s5",
  "{S} lies half-covered with the apron loose across her, breathing hard."),
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
            "evidence": "User 2026-11-19: group 'Arius Squad' (Saori, Atsuko, Hiyori), concept 'slut', outfit pick '1' slutty maid; adults, fictional, consensual, explicit."}


def existing_sid(slug):
    f = ROOT / "sources" / slug / "story_id.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


def seed(S):
    slug = S["slug"]
    base = ROOT / "sources" / slug
    base.mkdir(parents=True, exist_ok=True)
    (base / "story.md").write_text(
        f"{S['title']}\n\n{S['name']}, an adult woman in a slutty maid dress with apron and thighhighs, stands at "
        f"{S['place']}, strips fully nude in front of the crowd and touches herself on the ground. "
        f"Explicit, consensual, fictional.\n", encoding="utf-8")
    sid = existing_sid(slug)
    if sid is None:
        sid = cli("database/src/n2m_db.py", "create-story", "--title", S["title"], "--mode", "NON_BLIND",
                  "--text-file", str(base / "story.md"))
        (base / "story_id.txt").write_text(sid, encoding="utf-8")
    cli("database/src/n2m_db.py", "add-role", "--story-id", sid, "--key", "LEAD",
        "--description", f"{S['name']}, adult woman, slutty maid uniform")
    cli("database/src/n2m_db.py", "bind-role", "--story-id", sid, "--key", "LEAD",
        "--character-id", S["char_id"])
    events = [
        (f"{S['name']} unbuttons {S['top']} down to the waist at {S['place']} and lets her chest show, no bra.", "Nobody stops her."),
        (f"She pulls {S['tie']} off, unzips {S['skirt']} and sits on {S['seat']} with it bunched at her waist.", "The crowd blurs behind her."),
        (f"Topless, she kneels and slips her hand under the skirt.", "Her breath breaks; she does not stop."),
        (f"She drops onto all fours, works the skirt off and is fully nude; the apron hangs off one hip.", "The crowd keeps moving."),
        (f"Nude, she touches herself to the edge, moving between knees, back and {S['seat']}.", "She finishes in daylight."),
        (f"Spent, she curls onto her side with her shirt half over her and looks into the camera.", "Afterglow at noon."),
    ]
    plan = {"schema_version": "n2m.story.v1", "story_id": sid, "revision": 1, "approval": APPROVAL,
            "source_refs": [{"type": "user_story", "id": slug, "status": "confirmed"}],
            "intent": {"content_profile": "adult", "raw_labels": ["mature", "nsfw", "explicit"],
                       "constraints": ["Solo adult woman, consensual.",
                                       f"Outfit: slutty maid ({S['top']}, {S['skirt']}, {S['legs']}).",
                                       "Ends fully nude; masturbation included.",
                                       "Poses: standing, sitting, kneeling, all fours, on back, on side.",
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
              "raw_labels": ["nsfw", "explicit"], "source_fragment": S["place"],
              "spec": {"solo": True, "tier": "explicit", "outfit": "slutty maid"}}
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
                "characters": {"LEAD": {"description": f"{S['name']}, adult, slutty maid uniform",
                                        "provenance": "user outfit pick + catalog character",
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
