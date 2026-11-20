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

CH = {
    "neru": dict(id="character:storyaura_danbooru_csv:274d102a637d3abe60", name="Neru",
                 anchors=["blonde hair", "long hair", "yellow eyes", "halo", "small breasts", "twintails"]),
    "hifumi": dict(id="character:storyaura_danbooru_csv:12691c32b36f325864", name="Hifumi",
                   anchors=["black hair", "long hair", "yellow eyes", "halo", "small breasts", "ahoge"]),
    "serika": dict(id="character:storyaura_danbooru_csv:a91a42e8fd324139b5", name="Serika",
                   anchors=["black hair", "twintails", "red eyes", "halo", "small breasts", "cat ears"]),
    "kayoko": dict(id="character:storyaura_danbooru_csv:938121e1cabcdd8cd1", name="Kayoko",
                   anchors=["black hair", "long hair", "red eyes", "halo", "small breasts", "hairband"]),
    "koharu": dict(id="character:storyaura_danbooru_csv:39a40cfa73a53922be", name="Koharu",
                   anchors=["pink hair", "long hair", "yellow eyes", "halo", "small breasts", "wings"]),
}
PARTNER_OF = {"neru": "serika", "hifumi": "koharu", "serika": "kayoko", "kayoko": "koharu", "koharu": "neru"}

BASE_OUTFIT = {
    "neru": (["cleaning uniform", "white shirt", "red skirt", "armband", "black gloves"], ["white shirt"]),
    "hifumi": (["school uniform", "blazer", "white shirt", "red ribbon", "pleated skirt"], ["blazer"]),
    "serika": (["school uniform", "white shirt", "blue skirt", "necktie", "cardigan"], ["white shirt"]),
    "kayoko": (["school uniform", "black jacket", "white shirt", "red tie", "black skirt"], ["black jacket"]),
    "koharu": (["school uniform", "white shirt", "red skirt", "cross strap", "white gloves"], ["white shirt"]),
}

V = lambda place, short, floor, lean, light, loc, lighting: dict(
    place=place, place_short=short, floor=floor, lean_on=lean, light_word=light,
    location_tags=loc, lighting=lighting)

VENUES = {
 "festival": V("the crowded school festival hallway", "the hallway", "the linoleum floor", "the lockers",
               "hallway light", ["indoors", "school hallway", "festival posters", "lockers", "crowd", "blurry background"],
               ["fluorescent light", "bright", "even"]),
 "pool": V("the municipal pool deck at noon", "the pool", "the wet tiles", "the starting block",
           "pool reflections", ["indoors", "swimming pool", "lanes", "wet tiles", "crowd", "blurry background"],
           ["skylight", "bright", "water reflections"]),
 "gala": V("the hotel gala lobby at noon", "the lobby", "the marble floor", "the reception desk",
           "window light", ["indoors", "hotel lobby", "marble floor", "glass wall", "crowd", "blurry background"],
           ["daylight", "bright", "window light"]),
 "shrine": V("the crowded shrine steps at noon", "the steps", "the stone steps", "the torii gate",
             "winter sun", ["outdoors", "shrine", "stone steps", "torii", "crowd", "blurry background"],
             ["daylight", "bright", "soft sun"]),
 "atrium": V("the mall atrium outside a cafe", "the atrium", "the polished tile", "the cafe counter",
             "atrium light", ["indoors", "shopping mall", "atrium", "glass roof", "crowd", "blurry background"],
             ["daylight", "bright", "even"]),
 "casino": V("the casino floor lit by noon windows", "the casino", "the carpet", "the roulette table",
             "window light", ["indoors", "casino", "card tables", "large windows", "crowd", "blurry background"],
             ["daylight", "bright", "warm light"]),
 "gate": V("the school gate plaza at noon", "the gate", "the paving stones", "the gate pillar",
           "noon sun", ["outdoors", "school gate", "paving stones", "trees", "crowd", "blurry background"],
           ["daylight", "bright", "hard light"]),
 "plaza": V("the cathedral plaza at noon", "the plaza", "the flagstones", "the fountain rim",
            "noon sun", ["outdoors", "plaza", "cathedral", "flagstones", "fountain", "crowd", "blurry background"],
            ["daylight", "bright", "soft sun"]),
 "resort": V("the resort pool deck at noon", "the pool deck", "the wet stone", "the pool ladder",
             "water reflections", ["outdoors", "resort pool", "loungers", "water", "crowd", "blurry background"],
             ["sunlight", "high key", "water reflections"]),
 "promenade": V("the seaside promenade market at noon", "the promenade", "the boardwalk", "the railing",
                "sea light", ["outdoors", "promenade", "market stalls", "railing", "sea", "crowd", "blurry background"],
                ["daylight", "bright", "sea reflections"]),
 "temple": V("the temple market street at noon", "the market street", "the paving stones", "the stall frame",
             "noon sun", ["outdoors", "market street", "stalls", "lanterns", "crowd", "blurry background"],
             ["daylight", "bright", "soft sun"]),
 "courtyard": V("the palace courtyard fountain at noon", "the courtyard", "the inlaid floor", "the fountain edge",
                "court light", ["indoors", "palace courtyard", "fountain", "tiled floor", "crowd", "blurry background"],
                ["daylight", "bright", "warm light"]),
 "cathedral": V("the cathedral aisle crowded after noon mass", "the cathedral", "the stone floor", "the pew end",
                "stained glass light", ["indoors", "cathedral", "pews", "stained glass", "crowd", "blurry background"],
                ["colored light", "bright", "window light"]),
 "stadium": V("the running track at noon", "the track", "the red track", "the lane rope",
              "noon sun", ["outdoors", "stadium", "running track", "grandstand", "crowd", "blurry background"],
              ["daylight", "hard light", "bright"]),
 "publicpool": V("the public pool lanes at noon", "the pool", "the wet tiles", "the lane divider",
                 "pool light", ["indoors", "public pool", "lanes", "wet tiles", "crowd", "blurry background"],
                 ["skylight", "bright", "water reflections"]),
 "lobby": V("the concert hall lobby at noon", "the lobby", "the polished floor", "the poster wall",
            "lobby light", ["indoors", "concert hall", "lobby", "posters", "crowd", "blurry background"],
            ["daylight", "bright", "even"]),
 "beach": V("the beach bar at noon", "the beach bar", "the sanded floor", "the bar rail",
            "sea light", ["outdoors", "beach bar", "sand", "sea", "crowd", "blurry background"],
            ["sunlight", "high key", "bright"]),
 "arcade": V("the shopping arcade street at noon", "the arcade", "the tiled street", "the shop pillar",
             "arcade light", ["outdoors", "shopping street", "arcade", "shop fronts", "crowd", "blurry background"],
             ["daylight", "bright", "even"]),
}

# outfit stories: (lead, outfit key, outfit tags, core, slug suffix, venue, title word, variant id)
OUTFITS = [
 ("neru", "base", ["cleaning uniform", "white shirt", "red skirt", "armband", "black gloves"], ["cleaning uniform"],
  "cleaning_court", "festival", "Cleaning Court", "character:storyaura_danbooru_csv:274d102a637d3abe60"),
 ("neru", "bunny", ["playboy bunny", "black leotard", "strapless leotard", "detached collar", "white gloves", "wrist cuffs"],
  ["black leotard"], "bunny_atrium", "casino", "Bunny Atrium", "character:storyaura_danbooru_csv:6c06ae18c61e9f3166"),
 ("neru", "school", ["school uniform", "blazer", "pleated skirt", "white shirt", "red ribbon"],
  ["school uniform"], "school_gate", "gate", "School Gate", "character:storyaura_danbooru_csv:9e1c5b8255dcf563ad"),
 ("neru", "swimsuit", ["one-piece swimsuit", "school swimsuit", "white swimsuit", "name tag"],
  ["one-piece swimsuit"], "pool_lane", "pool", "Pool Lane", "character:storyaura_danbooru_csv:b7c55bd35b37da62cf"),
 ("hifumi", "base", ["school uniform", "blazer", "white shirt", "red ribbon", "pleated skirt"], ["blazer"],
  "plaza_ribbon", "plaza", "Plaza Ribbon", "character:storyaura_danbooru_csv:12691c32b36f325864"),
 ("hifumi", "swimsuit", ["school swimsuit", "one-piece swimsuit", "white swimsuit", "name tag"], ["school swimsuit"],
  "resort_lane", "resort", "Resort Lane", "character:storyaura_danbooru_csv:774c42fc128e63181c"),
 ("hifumi", "cow", ["cow print swimsuit", "bikini", "cow print bikini", "halterneck"], ["cow print swimsuit"],
  "promenade_cow", "promenade", "Promenade Cow", "character:storyaura_danbooru_csv:9f11fed543dea8692f"),
 ("hifumi", "faust", ["faust cosplay", "black robe", "hood", "mask", "gloves"], ["faust cosplay"],
  "temple_faust", "temple", "Temple Faust", "character:storyaura_danbooru_csv:f8e5a745f997c6bc55"),
 ("serika", "base", ["school uniform", "white shirt", "blue skirt", "necktie", "cardigan"], ["white shirt"],
  "courtyard_tie", "courtyard", "Courtyard Tie", "character:storyaura_danbooru_csv:a91a42e8fd324139b5"),
 ("serika", "swimsuit", ["school swimsuit", "one-piece swimsuit", "white swimsuit", "name tag"], ["school swimsuit"],
  "publicpool_lane", "publicpool", "Public Pool Lane", "character:storyaura_danbooru_csv:fbd9ad6618bec6c7a6"),
 ("serika", "idol", ["idol clothes", "frilled dress", "stage costume", "white gloves", "hair ornament"], ["idol clothes"],
  "lobby_stage", "lobby", "Lobby Stage", "character:storyaura_danbooru_csv:561af4d54b75fe29ab"),
 ("serika", "waitress", ["waitress", "apron dress", "white apron", "hair ribbon", "black dress"], ["waitress"],
  "arcade_waitress", "arcade", "Arcade Waitress", "character:storyaura_danbooru_csv:437d2217f1a8964f3f"),
 ("kayoko", "base", ["school uniform", "black jacket", "white shirt", "red tie", "black skirt"], ["black jacket"],
  "cathedral_jacket", "cathedral", "Cathedral Jacket", "character:storyaura_danbooru_csv:938121e1cabcdd8cd1"),
 ("kayoko", "dress", ["black dress", "long dress", "bare shoulders", "hairband", "high heels"], ["black dress"],
  "gala_dress", "gala", "Gala Dress", "character:storyaura_danbooru_csv:91f46b751a186440a3"),
 ("kayoko", "sundress", ["sundress", "floral print", "off shoulder", "straw hat"], ["sundress"],
  "beach_sundress", "beach", "Beach Sundress", "character:storyaura_danbooru_csv:9e7405f856ba5bf306"),
 ("koharu", "base", ["school uniform", "white shirt", "red skirt", "cross strap", "white gloves"], ["white shirt"],
  "shrine_cross", "shrine", "Shrine Cross", "character:storyaura_danbooru_csv:39a40cfa73a53922be"),
 ("koharu", "swimsuit", ["school swimsuit", "one-piece swimsuit", "white swimsuit", "name tag"], ["school swimsuit"],
  "stadium_lane", "stadium", "Stadium Lane", "character:storyaura_danbooru_csv:da8534bf631ab8e5ee"),
]

NUDES = ["completely nude", "nipples", "navel", "barefoot"]
STAGE = {}
for i in range(1, 9): STAGE[i] = 1
for i in range(9, 17): STAGE[i] = 2
for i in range(17, 29): STAGE[i] = 3
for i in range(29, 43): STAGE[i] = 4
for i in range(43, 49): STAGE[i] = 5

# (purpose, nrole, transition, camera, focus, moment, action)
T = [
 ("ESTABLISHING", "ESTABLISH", "START", "full body, eye level", "the pair and the crowd",
  "{A} and {B} stand close at {place} in {look_a} and {look_b}, the noon crowd blurred behind them.",
  "{A} leans her shoulder against {B}"),
 ("REACTION", "PROLONG", "CONTINUOUS", "cowboy shot, eye level", "their faces",
  "{A} looks sideways at {B} and does not blink.", "{A} holds {B}'s eyes"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "their hands",
  "Their fingers find each other between the passing bodies.", "their fingers interlace"),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body, eye level", "two faces close",
  "{A} pulls {B} in by the waist and kisses her in the middle of {place_short}.",
  "{A} pulls {B} by the waist and kisses her"),
 ("REACTION", "PROLONG", "SAME_MOMENT", "close-up", "lips parting",
  "{B} tips her head back and lets it happen.", "{B} tips her head back"),
 ("REACTION", "PROLONG", "CAMERA_CUT", "cowboy shot, from side", "a passer-by",
  "A passer-by brushes past and neither of them turns.", "they ignore the crowd"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "hands on a hip",
  "{A}'s hand slides to the small of {B}'s back and stays.", "{A} presses her hand to {B}'s back"),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, eye level", "the pair",
  "{A} looks over {B}'s shoulder and decides to stay.", "{A} holds {B} close"),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "shoulder and sleeve",
  "{A} works {B}'s {b_layer} off one shoulder.", "{A} slides {B}'s {b_layer} off"),
 ("ACTION", "PROLONG", "CONTINUOUS", "close-up", "fabric at the elbow",
  "The {b_layer} slips to {B}'s elbow and {A} pulls it free.", "{A} pulls the {b_layer} free"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "full body", "garment falling",
  "{B} lets the {b_layer} drop; {place_short} does not notice.", "{B} lets it fall"),
 ("ACTION", "PROLONG", "SAME_MOMENT", "cowboy shot, eye level", "bare shoulders",
  "{B}'s shoulders roll free, skin bright under the {light_word}.", "{A} runs her palms over {B}'s shoulders"),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "the lead's own clothes",
  "{B} returns the favour and opens {A}'s {a_layer}.", "{B} opens {A}'s {a_layer}"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "opening clothes",
  "{A}'s {a_core} hangs open; she does not stop her.", "{B} pushes it open"),
 ("REACTION", "REACTION", "CONTINUOUS", "full body, from below", "their faces",
  "Someone laughs nearby; they both ignore it.", "they ignore the crowd"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "temple",
  "A bead of sweat runs at {B}'s temple.", "{A} brushes the sweat away"),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "hands at the front",
  "{B}'s fingers find {A}'s {a_closure} and pull it loose.", "{B} pulls {A}'s {a_closure} loose"),
 ("ACTION", "PROLONG", "CONTINUOUS", "close-up", "open front",
  "{A}'s {a_core} falls open; her breath lifts her chest.", "{A} lets it fall open"),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "both half-bare",
  "They stand half-bare in the crowd, foreheads almost touching.", "they press their foreheads together"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from behind", "bare backs",
  "From behind, both their backs are bare to the waist.", "{A} runs her hand down {B}'s spine"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "chests together",
  "Their chests press together and neither pulls away.", "their chests press together"),
 ("ACTION", "PROLONG", "SAME_MOMENT", "close-up, from above", "hands between them",
  "{A}'s hand slips between them and {B} inhales.", "{A} slides her hand between them"),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body, eye level", "a hand on a breast",
  "{A} cups {B}'s small breast through the last of the fabric.", "{A} cups {B}'s breast"),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, three-quarter view", "their bodies",
  "{B}'s thumb drags across {A}'s nipple and {A} smiles at nothing.", "{B} drags her thumb across"),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "mouth",
  "{B}'s tongue touches her lower lip and {A} watches it.", "{A} watches {B}'s mouth"),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, eye level", "the pair with the crowd",
  "They turn together, {a_core} and {b_core} still hanging open.", "they turn together"),
 ("ACTION", "INITIATE", "CONTINUOUS", "full body", "hands at a hip",
  "{B} works {A}'s {a_bottom} down over her hips.", "{B} works {A}'s {a_bottom} down"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "falling fabric",
  "The {a_bottom} falls past her knees to the floor.", "{A} steps out of it"),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from behind", "nude backs",
  "Both nude now, they stand with their backs to the crowd.", "they stand back to the crowd"),
 ("ACTION", "PROLONG", "CONTINUOUS", "cowboy shot, eye level", "bare feet",
  "{A} steps out of the last of it and {B} follows, barefoot on {floor}.", "they step out of the last of it"),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from below", "hips and thighs",
  "Low angle: their hips and thighs fill the frame, bodies passing behind.", "they stand pressed together"),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "hand on a stomach",
  "{A}'s hand slides down {B}'s stomach and does not stop.", "{A} slides her hand down"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her fingers",
  "{A}'s fingers find {B} and stay there.", "{A} touches {B}"),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "leaning on the rail",
  "{B} leans back against {lean_on} and pulls {A} in with her.", "{B} pulls {A} against her"),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "jaw",
  "{B}'s jaw slackens; the crowd keeps moving.", "{A} keeps her hand moving"),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, from side", "arched spine",
  "From the side, {B}'s spine arches off {lean_on}.", "{A} holds her by the hip"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "wet fingers",
  "{B}'s fingers glisten in the {light_word}.", "{B} takes {A}'s wrist"),
 ("DETAIL", "DETAIL", "SAME_MOMENT", "upper body, from behind", "shoulder blades",
  "From behind, their shoulders lift with each breath.", "they breathe together"),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "a leg lifted",
  "{A} lifts {B}'s knee to her hip and keeps her hand where it is.", "{A} lifts {B}'s knee"),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, from above", "faces",
  "{B}'s head tips back, mouth open, no sound.", "{B}'s head tips back"),
 ("CLIMAX", "PEAK", "CONTINUOUS", "full body, from below", "both bodies",
  "{B}'s hips jerk hard against {A}'s hand.", "{B} jerks against her hand"),
 ("CLIMAX", "DETAIL", "SAME_MOMENT", "close-up", "throat",
  "Her eyes shut and her throat works; {A} does not let go.", "{A} does not let go"),
 ("AFTERMATH", "RESOLUTION", "CAMERA_CUT", "full body, eye level", "steadying each other",
  "{A} pulls her hand away and holds {B} up against {lean_on}.", "{A} holds {B} up"),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "cowboy shot", "cover and sweat",
  "Sweat shines on both their chests; {B} pulls {a_core} over {A}'s shoulder.", "{B} covers {A}"),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "wet hands on fabric",
  "Their hands, still wet, close on the fabric together.", "their hands close on the fabric"),
 ("REACTION", "PROLONG", "CAMERA_CUT", "upper body, from behind", "over the shoulder",
  "{B} looks back over her shoulder at the crowd, and {A} laughs.", "{B} looks back at the crowd"),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "full body, eye level", "half-covered pair",
  "{A} and {B} stand half-covered at {place_short}, breathing hard.", "they stand half-covered"),
 ("REACTION", "RESOLUTION", "CAMERA_CUT", "close-up, eye level", "their eyes",
  "They look at the camera together, and neither of them moves.", "they hold the camera"),
]
assert len(T) == 48

FRAMINGS = ["wide shot", "cowboy shot", "upper body", "full body", "close-up"]
ANGLES = ["from above", "from below", "from side", "from behind", "three-quarter view"]

def camera_tags(camera):
    low = camera.lower()
    tags = [f for f in FRAMINGS if f in low][:1] or ["cowboy shot"]
    return tags + [a for a in ANGLES if a in low]

def stages(full, core):
    s2 = list(dict.fromkeys([t for t in full if t not in core] + ["off shoulder"]))
    s3 = list(core) + ["open clothes", "breasts out", "cleavage"]
    s5 = [full[0], "off shoulder", "covered", "sweat"]
    return {"stage1": list(full), "stage2": s2, "stage3": s3, "stage4": list(NUDES), "stage5": s5}

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
APPROVAL = {"status": "APPROVED",
            "evidence": "User 2026-11-19: 'story láº§n nÃ y cho kiá»ƒu couple 2 ngÆ°á»i' + '2 nhÃ¢n váº­t ná»¯'; small-breast BA cast, standing, 3:4, crowded bright, explicit."}

def sid_of(slug):
    f = ROOT / "sources" / slug / "story_id.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None

def seed(slug, title, lead, partner, full, core, venue, variant_id):
    base = ROOT / "sources" / slug
    base.mkdir(parents=True, exist_ok=True)
    A, B = CH[lead], CH[partner]
    pf, pc = BASE_OUTFIT[partner]
    (base / "story.md").write_text(
        f"{title}\n\n{A['name']} and {B['name']}, both adult women, stand in {venue['place']} and undress each other "
        f"in plain sight while the noon crowd moves past. Explicit, consensual, fictional.\n", encoding="utf-8")
    sid = sid_of(slug)
    if sid is None:
        sid = cli("database/src/n2m_db.py", "create-story", "--title", title,
                  "--mode", "NON_BLIND", "--text-file", str(base / "story.md"))
        (base / "story_id.txt").write_text(sid, encoding="utf-8")
    for key, who in (("LEAD", A), ("PARTNER", B)):
        cli("database/src/n2m_db.py", "add-role", "--story-id", sid, "--key", key,
            "--description", f"{who['name']}, adult woman")
        cli("database/src/n2m_db.py", "bind-role", "--story-id", sid, "--key", key,
            "--character-id", who["id"])
    events = [
        (f"{A['name']} pulls {B['name']} into a kiss at {venue['place']} while the crowd moves past.", "Neither of them steps away."),
        (f"They strip each other out of {full[0]} and {pf[0]}, one piece at a time, still standing.", "Both are half-bare in the crowd."),
        (f"{A['name']} slips her hand between {B['name']}'s thighs and {B['name']} holds on to her.", "Breath breaks between them."),
        (f"{B['name']} leans back against {venue['lean_on']} and {A['name']} works her to the edge.", "The crowd keeps moving."),
        (f"Spent, they stand half-covered and look into the camera together.", "Afterglow in daylight."),
    ]
    plan = {"schema_version": "n2m.story.v1", "story_id": sid, "revision": 1, "approval": APPROVAL,
            "source_refs": [{"type": "user_story", "id": slug, "status": "confirmed"}],
            "intent": {"content_profile": "adult", "raw_labels": ["mature", "nsfw", "explicit"],
                       "constraints": ["Two adult women, consensual, solo couple only.",
                                       "Standing poses only; 3:4 portrait.", "Bright crowded venue."]},
            "characters": [{"character_id": A["id"], "name": A["name"], "age_status": "verified_adult",
                            "identity_anchors": A["anchors"]},
                           {"character_id": B["id"], "name": B["name"], "age_status": "verified_adult",
                            "identity_anchors": B["anchors"]}],
            "acts": [{"act_id": "A01", "beats": []}]}
    for i, (a, r) in enumerate(events, 1):
        plan["acts"][0]["beats"].append({"beat_id": f"B{i:02d}",
            "events": [{"event_id": f"E{i:03d}", "actor_id": A["name"], "primary_action": a,
                        "target_id": B["name"], "reaction": r}]})
    (base / "story_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("database/src/n2m_workflow.py", "save-plan", "--story-id", sid, "--file", str(base / "story_plan.json"))
    if con.execute("select count(*) from beats b join acts a on a.id=b.act_id where a.story_id=?", (sid,)).fetchone()[0]:
        return sid
    act_id = cli("database/src/n2m_workflow.py", "add-act", "--story-id", sid, "--order", "1",
                 "--title", "A01", "--summary", venue["place"])
    for i, (a, r) in enumerate(events, 1):
        beat_id = cli("database/src/n2m_workflow.py", "add-beat", "--act-id", act_id,
                      "--order", str(i), "--summary", a[:180])
        ev = {"actor_role_key": "LEAD", "target_role_key": "PARTNER", "action": a, "reaction": r,
              "raw_labels": ["nsfw", "explicit"], "source_fragment": venue["place"],
              "spec": {"tier": "explicit", "pose": "standing", "couple": True}}
        f = base / f"event_{i:02d}.json"
        f.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        cli("database/src/n2m_workflow.py", "add-event", "--beat-id", beat_id, "--order", "1", "--file", str(f))
    return sid

def board(sid, slug, title, lead, partner, full, core, venue, force=False):
    base = ROOT / "sources" / slug
    have = con.execute("select id from storyboards where story_id=? order by revision desc limit 1", (sid,)).fetchone()
    if have and not force:
        return have[0]
    A, B = CH[lead], CH[partner]
    pf, pc = BASE_OUTFIT[partner]
    rev = con.execute("select current_revision from stories where id=?", (sid,)).fetchone()[0]
    beats = list(con.execute("""select b.id beat_id, b.beat_order, e.id event_id from beats b
        join acts a on a.id=b.act_id left join story_events e on e.beat_id=b.id
        where a.story_id=? order by b.beat_order, e.event_order""", (sid,)))
    Bd = {r["beat_order"]: r for r in beats}
    look_a = f"a {full[0]}"
    look_b = f"a {pf[0]}"
    w = dict(A=A["name"], B=B["name"], place=venue["place"], place_short=venue["place_short"],
             light_word=venue["light_word"], floor=venue["floor"], lean_on=venue["lean_on"],
             a_layer=next((t for t in full if t not in core), full[0]), a_core=core[0],
             a_bottom=core[0], a_closure="front", b_layer=next((t for t in pf if t not in pc), pf[0]),
             b_core=pc[0], look_a=look_a, look_b=look_b)
    plan = {"schema_version": 5, "story_revision": rev, "approval": APPROVAL,
            "visual_bible": {
                "characters": {
                    "LEAD": {"description": f"{A['name']}, adult woman, {full[0]}",
                             "provenance": "catalog character + character_tags",
                             "character_id": A["id"], "outfit_id": None,
                             "prompt_tags": [A["name"].lower() + " (blue archive)"] + A["anchors"],
                             "outfits": {k: {"prompt_tags": v} for k, v in stages(full, core).items()}},
                    "PARTNER": {"description": f"{B['name']}, adult woman, {pf[0]}",
                                "provenance": "catalog character + character_tags",
                                "character_id": B["id"], "outfit_id": None,
                                "prompt_tags": [B["name"].lower() + " (blue archive)"] + B["anchors"],
                                "outfits": {k: {"prompt_tags": v} for k, v in stages(pf, pc).items()}}},
                "locations": {"venue": {"description": venue["place"], "provenance": "story brief",
                                        "prompt_tags": venue["location_tags"]}},
                "props": {},
                "styles": {"anime-bright": {"description": "Clean bright anime, high-key, crowded public venue",
                                            "provenance": "user choice",
                                            "prompt_tags": ["anime style", "clean lineart", "bright colors",
                                                            "cinematic lighting", "@anjing"]}}},
            "scenes": {"scene-main": {"location_key": "venue", "style_key": "anime-bright",
                                      "time_key": "day", "role_keys": ["LEAD", "PARTNER"],
                                      "lighting_tags": venue["lighting"]}},
            "shots": [], "coverage": []}
    t = 0
    for i, (purpose, nrole, transition, camera, focus, moment, action) in enumerate(T, 1):
        k = f"S{i:02d}"
        beat = 1 if i <= 8 else 2 if i <= 16 else 3 if i <= 28 else 4 if i <= 38 else 5
        if transition != "SAME_MOMENT":
            t += 1
        plan["shots"].append({
            "shot_key": k, "shot_order": i, "beat_id": Bd[beat]["beat_id"], "branch_key": "main",
            "previous_shot_key": None if i == 1 else f"S{i-1:02d}", "transition": transition,
            "purpose": purpose, "narrative_role": nrole, "story_time": t, "scene_key": "scene-main",
            "camera": camera, "focus": focus, "visual_moment": moment.format(**w),
            "role_keys": ["LEAD", "PARTNER"], "location_key": "venue",
            "visible_location_tags": venue["location_tags"], "prop_keys": [],
            "style_key": "anime-bright", "outfit_key": f"stage{STAGE[i]}"})
        plan["coverage"].append({"event_id": Bd[beat]["event_id"], "status": "VISUALIZED",
                                 "shot_key": k, "evidence": plan["shots"][-1]["visual_moment"]})
    f = base / "storyboard_v5.json"
    f.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return cli("database/src/n2m_workflow.py", "save-storyboard", "--story-id", sid, "--file", str(f))[0]

def shots(sid, slug, venue):
    base = ROOT / "sources" / slug / "shots"
    base.mkdir(parents=True, exist_ok=True)
    board_id = con.execute("select id from storyboards where story_id=? order by revision desc limit 1",
                           (sid,)).fetchone()[0]
    plan = json.loads(con.execute("select plan_json from storyboards where id=?", (board_id,)).fetchone()[0])
    scene = plan["scenes"]["scene-main"]
    events = {r["beat_id"]: r for r in con.execute(
        "select e.beat_id, e.id, e.action from story_events e join beats b on b.id=e.beat_id "
        "join acts a on a.id=b.act_id where a.story_id=?", (sid,))}
    prev = None
    for slot in plan["shots"]:
        i = slot["shot_order"]
        ev = events[slot["beat_id"]]
        state = {r: {"outfit_key": slot["outfit_key"], "pose": "standing",
                     "position": venue["place_short"], "holding": "none"} for r in ("LEAD", "PARTNER")}
        before = state if prev is None else prev
        snaps = [{"role_key": None, "before": {"location_key": scene["location_key"], "time_key": scene["time_key"]},
                  "delta": {"set": {}, "remove": []},
                  "after": {"location_key": scene["location_key"], "time_key": scene["time_key"]},
                  "moment": {"at_shot": {"location_key": scene["location_key"], "time_key": scene["time_key"]},
                             "at_delta": {"set": {}, "remove": []}, "after_delta": {"set": {}, "remove": []}}}]
        for role in ("LEAD", "PARTNER"):
            b, a = before[role], state[role]
            d = {"set": {k: v for k, v in a.items() if b.get(k) != v}, "remove": []}
            snaps.append({"role_key": role, "before": b, "delta": d, "after": a,
                          "moment": {"at_shot": {**b, **d["set"]}, "at_delta": d,
                                     "after_delta": {"set": {}, "remove": []}}})
        spec = {"visual_context_sha256": con.execute(
                    "select context_sha256 from storyboard_shots where storyboard_id=? and shot_key=?",
                    (board_id, slot["shot_key"])).fetchone()[0],
                "outfit_key": slot["outfit_key"], "camera": slot["camera"], "focus": slot["focus"],
                "location_key": slot["location_key"],
                "participants": [{"role_key": "LEAD"}, {"role_key": "PARTNER"}],
                "interactions": [{"event_id": ev["id"], "actor_role_key": "LEAD",
                                  "target_role_key": "PARTNER", "action_text": ev["action"]}],
                "prompt_blocks": {"prefix": ["masterpiece", "best quality", "explicit"],
                                  "subjects": ["2girls", "yuri", "couple"],
                                  "action": (["undressing"] if prev and prev["LEAD"]["outfit_key"] != slot["outfit_key"] else []) + ["standing"],
                                  "camera": camera_tags(slot["camera"]),
                                  "prose": slot["visual_moment"]}}
        sf, cf = base / f"{slot['shot_key']}.shot.json", base / f"{slot['shot_key']}.cont.json"
        sf.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        cf.write_text(json.dumps({"snapshots": snaps}, ensure_ascii=False, indent=1), encoding="utf-8")
        res = cli("database/src/n2m_workflow.py", "save-shot", "--beat-id", slot["beat_id"],
                  "--shot-key", slot["shot_key"], "--file", str(sf), "--event-id", ev["id"])
        shot_id = res[0] if isinstance(res, list) else res
        cli("database/src/n2m_workflow.py", "save-continuity", "--shot-id", shot_id, "--file", str(cf))
        cli("database/src/n2m_workflow.py", "compile-prompt", "--shot-id", shot_id, "--save")
        print(slug, slot["shot_key"], flush=True)
        prev = state

if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    for lead, ok, full, core, suffix, venue_key, word, variant_id in OUTFITS:
        slug = f"{lead}_{suffix}"
        title = f"{word} - {CH[lead]['name']}"
        partner = PARTNER_OF[lead]
        venue = VENUES[venue_key]
        sid = sid_of(slug)
        if phase in ("all", "seed") or sid is None:
            sid = seed(slug, title, lead, partner, full, core, venue, variant_id)
            print("SEED", slug, sid, flush=True)
        if phase in ("all", "boards"):
            print("BOARD", slug, board(sid, slug, title, lead, partner, full, core, venue,
                                       force="--force" in sys.argv), flush=True)
        if phase in ("all", "shots"):
            shots(sid, slug, venue)
