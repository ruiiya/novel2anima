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

def entry(char_id, name, anchors, full, core, closure, bottom, venue, hook, held="none"):
    return dict(char_id=char_id, name=name, anchors=anchors, full=full, core=core,
                closure=closure, bottom=bottom, venue=venue, hook=hook, held=held)

V = lambda place, short, floor, lean, light, loc, lighting: dict(
    place=place, place_short=short, floor=floor, lean_on=lean, light_word=light,
    location_tags=loc, lighting=lighting)

HINA = ["white hair", "purple hair", "very long hair", "long hair", "pink eyes", "horns", "halo", "large breasts"]
TOKI = ["blonde hair", "blue eyes", "long hair", "halo", "headband", "large breasts"]
SEIA = ["white hair", "very long hair", "yellow eyes", "halo", "large breasts"]
MARI = ["black hair", "long hair", "yellow eyes", "halo", "large breasts"]
ASUNA = ["blonde hair", "blue eyes", "long hair", "halo", "hair over one eye", "large breasts"]

STORIES = [
 ("hina_festival_hall", "Hina", "character:storyaura_danbooru_csv:c01d9b091031e09fe3", HINA,
  ["school uniform", "white coat", "black skirt", "black gloves", "tie", "sleeveless"],
  ["school uniform"], "coat buttons", "skirt",
  V("the crowded school festival hallway", "the hallway", "the linoleum floor", "the lockers",
    "hallway light", ["indoors", "school hallway", "festival posters", "lockers", "crowd", "blurry background"],
    ["fluorescent light", "bright", "even"]),
  "students part around her without looking up", "her clipboard", "festival hall"),
 ("hina_pool_lane", "Hina", "character:storyaura_danbooru_csv:c8928fbd0927343e1a", HINA,
  ["one-piece swimsuit", "white swimsuit", "halterneck", "bare shoulders"],
  ["one-piece swimsuit"], "halter strap", "swimsuit",
  V("the municipal indoor pool at noon", "the pool", "the wet tiles", "the starting block",
    "pool reflections", ["indoors", "swimming pool", "lanes", "wet tiles", "crowd", "blurry background"],
    ["skylight", "bright", "water reflections"]),
  "swimmers surface and dive again behind her", "her swim cap", "pool deck"),
 ("hina_gala_lobby", "Hina", "character:storyaura_danbooru_csv:d76aa63e3e6565a229", HINA,
  ["white dress", "backless dress", "bare shoulders", "long dress", "high heels"],
  ["white dress"], "back zipper", "dress",
  V("the hotel gala lobby at noon", "the lobby", "the marble floor", "the reception desk",
    "window light", ["indoors", "hotel lobby", "marble floor", "glass wall", "crowd", "blurry background"],
    ["daylight", "bright", "window light"]),
  "guests in suits cross behind her with drinks", "her clutch", "gala lobby"),
 ("hina_dorm_corridor", "Hina", "character:storyaura_danbooru_csv:08ba0d0802f20e63bc", HINA,
  ["pajamas", "sleepwear", "loose pajamas", "barefoot", "short sleeves"],
  ["pajamas"], "pajama buttons", "pajamas",
  V("the sunlit dorm corridor", "the corridor", "the wooden floor", "the window frame",
    "morning sun", ["indoors", "dorm corridor", "windows", "wooden floor", "crowd", "blurry background"],
    ["morning sun", "bright", "warm light"]),
  "roommates slip past her in towels and slippers", "her mug", "dorm corridor"),
 ("hina_shrine_steps", "Hina", "character:storyaura_danbooru_csv:5f6ba6b57fc81d72a0", HINA,
  ["kimono", "furisode", "japanese clothes", "obi", "hair ornament"],
  ["kimono"], "obi knot", "kimono",
  V("the crowded shrine steps on new year noon", "the steps", "the stone steps", "the torii gate",
    "winter sun", ["outdoors", "shrine", "stone steps", "torii", "crowd", "blurry background"],
    ["daylight", "bright", "soft sun"]),
  "worshippers climb past her with paper charms", "her charm", "shrine steps"),
 ("toki_maid_atrium", "Toki", "character:storyaura_danbooru_csv:ce589f89ce5a16df44", TOKI,
  ["maid", "maid uniform", "apron", "black dress", "headband", "white gloves"],
  ["maid uniform"], "apron ties", "dress",
  V("the mall atrium outside a maid cafe", "the atrium", "the polished tile", "the cafe counter",
    "atrium light", ["indoors", "shopping mall", "atrium", "glass roof", "crowd", "blurry background"],
    ["daylight", "bright", "even"]),
  "a queue of customers waits and does not look", "her tray", "mall atrium"),
 ("toki_casino_floor", "Toki", "character:storyaura_danbooru_csv:4bfb69e1f3d1347f56", TOKI,
  ["playboy bunny", "black leotard", "strapless leotard", "detached collar", "white gloves", "wrist cuffs"],
  ["black leotard"], "collar clasp", "leotard",
  V("the casino floor lit by noon windows", "the casino", "the carpet", "the roulette table",
    "window light", ["indoors", "casino", "card tables", "large windows", "crowd", "blurry background"],
    ["daylight", "bright", "warm light"]),
  "players stack chips and never turn their heads", "her tray", "casino floor"),
 ("toki_school_gate", "Toki", "character:storyaura_danbooru_csv:bf945d9ec8c5978879", TOKI,
  ["school uniform", "blazer", "pleated skirt", "white shirt", "red tie"],
  ["school uniform"], "blazer buttons", "skirt",
  V("the school gate plaza at noon", "the gate", "the paving stones", "the gate pillar",
    "noon sun", ["outdoors", "school gate", "paving stones", "trees", "crowd", "blurry background"],
    ["daylight", "bright", "hard light"]),
  "students stream past her toward the gate", "her bag", "school gate"),
 ("seia_cathedral_plaza", "Seia", "character:storyaura_danbooru_csv:c1933f10f0e4014b1e", SEIA,
  ["white dress", "veil", "long dress", "bare shoulders", "halo"],
  ["white dress"], "dress lacing", "dress",
  V("the cathedral plaza at noon", "the plaza", "the flagstones", "the fountain rim",
    "noon sun", ["outdoors", "plaza", "cathedral", "flagstones", "fountain", "crowd", "blurry background"],
    ["daylight", "bright", "soft sun"]),
  "pilgrims and tourists fill the square behind her", "her prayer book", "cathedral plaza"),
 ("seia_resort_pool", "Seia", "character:storyaura_danbooru_csv:5e902234838dcf51f9", SEIA,
  ["bikini", "white bikini", "halterneck", "bare shoulders"],
  ["bikini"], "halter tie", "bikini",
  V("the resort pool deck at noon", "the pool deck", "the wet stone", "the pool ladder",
    "water reflections", ["outdoors", "resort pool", "loungers", "water", "crowd", "blurry background"],
    ["sunlight", "high key", "water reflections"]),
  "guests float past on inflatable rings", "her sun hat", "pool deck"),
 ("seia_promenade_market", "Seia", "character:storyaura_danbooru_csv:b7fb7fa22f95bda5f0", SEIA,
  ["sundress", "floral print", "off shoulder", "straw hat"],
  ["sundress"], "dress buttons", "dress",
  V("the seaside promenade market at noon", "the promenade", "the boardwalk", "the railing",
    "sea light", ["outdoors", "promenade", "market stalls", "railing", "sea", "crowd", "blurry background"],
    ["daylight", "bright", "sea reflections"]),
  "vendors call prices over her shoulder", "her straw hat", "promenade"),
 ("seia_temple_market", "Seia", "character:storyaura_danbooru_csv:54787f6023b2430541", SEIA,
  ["kimono", "furisode", "japanese clothes", "obi", "hair ornament"],
  ["kimono"], "obi knot", "kimono",
  V("the temple market street at noon", "the market street", "the paving stones", "the stall frame",
    "noon sun", ["outdoors", "market street", "stalls", "lanterns", "crowd", "blurry background"],
    ["daylight", "bright", "soft sun"]),
  "shoppers crowd the stalls on both sides", "her paper fan", "market street"),
 ("seia_palace_courtyard", "Seia", "character:storyaura_danbooru_csv:237fc3be4bd61a89f7", SEIA,
  ["harem outfit", "veil", "bare midriff", "gold jewelry", "sheer fabric"],
  ["harem outfit"], "veil clasp", "harem pants",
  V("the palace courtyard fountain at noon", "the courtyard", "the inlaid floor", "the fountain edge",
    "court light", ["indoors", "palace courtyard", "fountain", "tiled floor", "crowd", "blurry background"],
    ["daylight", "bright", "warm light"]),
  "courtiers pass in pairs and speak of nothing", "her fan", "courtyard"),
 ("mari_cathedral_aisle", "Mari", "character:storyaura_danbooru_csv:66b7afcb1e9d6bd540", MARI,
  ["nun", "habit", "white headdress", "rosary", "black dress"],
  ["nun"], "habit clasp", "habit",
  V("the cathedral aisle crowded after noon mass", "the cathedral", "the stone floor", "the pew end",
    "stained glass light", ["indoors", "cathedral", "pews", "stained glass", "crowd", "blurry background"],
    ["colored light", "bright", "window light"]),
  "the congregation files out around her", "her rosary", "cathedral"),
 ("mari_track_stadium", "Mari", "character:storyaura_danbooru_csv:46aeff05e98dabdce1", MARI,
  ["track uniform", "sports bra", "bloomers", "track jacket", "sneakers"],
  ["track uniform"], "jacket zipper", "shorts",
  V("the running track at noon", "the track", "the red track", "the lane rope",
    "noon sun", ["outdoors", "stadium", "running track", "grandstand", "crowd", "blurry background"],
    ["daylight", "hard light", "bright"]),
  "runners pass her lane and keep their pace", "her stopwatch", "track"),
 ("mari_public_pool", "Mari", "character:storyaura_danbooru_csv:f5f7468374c6cc9edc", MARI,
  ["school swimsuit", "one-piece swimsuit", "white swimsuit", "name tag"],
  ["school swimsuit"], "shoulder strap", "swimsuit",
  V("the public pool lanes at noon", "the pool", "the wet tiles", "the lane divider",
    "pool light", ["indoors", "public pool", "lanes", "wet tiles", "crowd", "blurry background"],
    ["skylight", "bright", "water reflections"]),
  "a whistle blows and the next heat dives in", "her goggles", "pool"),
 ("mari_concert_lobby", "Mari", "character:storyaura_danbooru_csv:ec20ed564a34f461a1", MARI,
  ["idol clothes", "frilled dress", "stage costume", "white gloves", "hair ornament"],
  ["idol clothes"], "costume hooks", "dress",
  V("the concert hall lobby at noon", "the lobby", "the polished floor", "the poster wall",
    "lobby light", ["indoors", "concert hall", "lobby", "posters", "crowd", "blurry background"],
    ["daylight", "bright", "even"]),
  "fans queue for posters and do not turn around", "her microphone", "concert lobby"),
 ("asuna_beach_bar", "Asuna", "character:storyaura_danbooru_csv:49d3fd967e15c21ae5", ASUNA,
  ["school uniform", "white jacket", "blue skirt", "necktie", "white gloves"],
  ["school uniform"], "jacket buttons", "skirt",
  V("the beach bar at noon", "the beach bar", "the sanded floor", "the bar rail",
    "sea light", ["outdoors", "beach bar", "sand", "sea", "crowd", "blurry background"],
    ["sunlight", "high key", "bright"]),
  "the bar crowd shouts over the surf", "her glass", "beach bar"),
 ("asuna_cabana_pool", "Asuna", "character:storyaura_danbooru_csv:a775ce10b67406a53e", ASUNA,
  ["playboy bunny", "black leotard", "strapless leotard", "detached collar", "white gloves", "wrist cuffs"],
  ["black leotard"], "collar clasp", "leotard",
  V("the hotel pool cabanas at noon", "the cabanas", "the wet stone", "the cabana post",
    "pool light", ["outdoors", "hotel pool", "cabanas", "loungers", "crowd", "blurry background"],
    ["sunlight", "high key", "water reflections"]),
  "guests order drinks two steps away", "her tray", "pool cabanas"),
 ("asuna_arcade_street", "Asuna", "character:storyaura_danbooru_csv:47b0a4c551d4218ba6", ASUNA,
  ["school uniform", "white shirt", "blue skirt", "ribbon", "cardigan"],
  ["school uniform"], "cardigan buttons", "skirt",
  V("the shopping arcade street at noon", "the arcade", "the tiled street", "the shop pillar",
    "arcade light", ["outdoors", "shopping street", "arcade", "shop fronts", "crowd", "blurry background"],
    ["daylight", "bright", "even"]),
  "shoppers drift between the stalls behind her", "her shopping bag", "arcade"),
]

NUDES = ["completely nude", "nipples", "navel", "barefoot"]
SHOTS = []
for i in range(1, 49):
    SHOTS.append(i)

TEMPLATES = [
 ("ESTABLISHING", "ESTABLISH", "START", "full body, eye level", "her and the crowd",
  "{S} stands at {place} in {look_full}, the noon crowd blurred behind her."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from below", "halo and face",
  "Her halo catches the {light_word} above the crowd."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, eye level", "her eyes",
  "Her eyes flick to the camera and away."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, three-quarter view", "her stance",
  "She rests her weight on one leg, {look_full} tight across her chest."),
 ("ACTION", "PROLONG", "CONTINUOUS", "medium shot, from behind", "her back",
  "From behind, her hair sways as people pass close."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, eye level", "her face",
  "A passer-by brushes her shoulder; she does not step away."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her hand",
  "Her fingers tighten on {held}."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, eye level", "her against the crowd",
  "{S} looks over the crowd and decides to stay."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "shoulder and sleeve",
  "She works the {layer1} off one shoulder."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "fabric at the elbow",
  "The {layer1} slips down to her elbow."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body", "garment falling",
  "She lets the {layer1} drop; {place_short} does not notice."),
 ("REACTION", "PROLONG", "SAME_MOMENT", "cowboy shot, eye level", "bare shoulders",
  "Her shoulders roll free, skin bright under the {light_word}."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "detail",
  "The {closure} hangs loose against her skin."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body, from side", "her chest",
  "She turns her chest to the light and breathes out."),
 ("REACTION", "PROLONG", "CAMERA_CUT", "full body, from below", "her face above the crowd",
  "Someone laughs nearby; her mouth stays flat."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "temple",
  "A bead of sweat at her temple."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "her hands at the front",
  "Her fingers find the {closure} and pull it loose."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "open front",
  "The {core} hangs open; her breath lifts her chest."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "opening clothes",
  "She opens the {core} in the middle of the crowd."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from behind", "bare back",
  "From behind, her back is bare to the waist above the {bottom}."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her chest",
  "Her nipples harden in the air of {place_short}."),
 ("DETAIL", "DETAIL", "SAME_MOMENT", "close-up, from above", "detail",
  "The {core} slides off her shoulder and she lets it."),
 ("ACTION", "PROLONG", "CONTINUOUS", "upper body, eye level", "her hand on her breast",
  "She palms her own breast, watching the crowd pass."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, three-quarter view", "her body",
  "Her thumb drags across the nipple and she smiles at nothing."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "mouth",
  "Her tongue touches her lower lip."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, eye level", "her with the crowd",
  "She turns fully to the camera, {bottom} still on."),
 ("ACTION", "INITIATE", "CONTINUOUS", "full body", "hands at her hip",
  "She works the {bottom} down her hips and lets it slide."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "falling fabric",
  "The {bottom} falls past her knees to the floor."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from behind", "nude back",
  "Nude now, she stands with her back to the crowd, unbothered."),
 ("ACTION", "PROLONG", "CONTINUOUS", "cowboy shot, eye level", "bare feet",
  "She steps out of the last of it, barefoot on {floor}."),
 ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from below", "hips and thighs",
  "Low angle: her hips and thighs fill the frame, bodies passing behind."),
 ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "hand on stomach",
  "Her hand slides down her stomach and does not stop."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her fingers",
  "Her fingers find her sex and stay there."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "her leaning",
  "She leans back against {lean_on} and keeps her hand moving."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up", "jaw",
  "Her jaw slackens; the crowd keeps moving."),
 ("ACTION", "PROLONG", "CAMERA_CUT", "full body, from side", "arched spine",
  "From the side, her spine arches against {lean_on}."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "wet fingers",
  "Her fingers glisten in the {light_word}."),
 ("DETAIL", "DETAIL", "SAME_MOMENT", "upper body, from behind", "shoulder blades",
  "From behind, her shoulder blades lift with each breath."),
 ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "bent knee",
  "She pushes two fingers deeper and her knee bends."),
 ("REACTION", "REACTION", "CONTINUOUS", "close-up, from above", "her face",
  "Her head tips back, mouth open, no sound."),
 ("CLIMAX", "PEAK", "CONTINUOUS", "full body, from below", "hips",
  "Her hips jerk once against her hand."),
 ("CLIMAX", "DETAIL", "SAME_MOMENT", "close-up", "throat",
  "Her eyes shut and her throat works."),
 ("AFTERMATH", "RESOLUTION", "CAMERA_CUT", "full body, eye level", "steadying herself",
  "She pulls her hand away and steadies herself against {lean_on}."),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "cowboy shot", "cover and sweat",
  "Sweat shines on her chest; she pulls the {cover} over one shoulder."),
 ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "wet hand on fabric",
  "Her hand, still wet, closes on the fabric."),
 ("REACTION", "PROLONG", "CAMERA_CUT", "upper body, from behind", "her over the shoulder",
  "She looks back over her shoulder at the crowd."),
 ("AFTERMATH", "RESOLUTION", "CONTINUOUS", "full body, eye level", "half-covered figure",
  "{S} stands half-covered at {place_short}, breathing hard."),
 ("REACTION", "RESOLUTION", "CAMERA_CUT", "close-up, eye level", "her eyes",
  "She meets the camera one last time."),
]
assert len(TEMPLATES) == 48

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

def look_full(e):
    head = e["full"][0]
    extra = [t for t in e["full"][1:4] if t != head]
    return f"a {head} with " + ", ".join(extra) if extra else f"a {head}"

def words(slug, e):
    v = e["venue"]
    removable = next((t for t in e["full"] if t not in e["core"]), e["full"][0])
    return dict(S=e["name"], place=v["place"], place_short=v["place_short"],
                look_full=look_full(e), light_word=v["light_word"], layer1=removable,
                closure=e["closure"], core=e["core"][0], top=e["core"][0],
                bottom=e["bottom"], held=e["held"], cover=e["full"][0],
                floor=v["floor"], lean_on=v["lean_on"])

def outfit_stages(e):
    full = e["full"]
    core = e["core"]
    stage2 = list(dict.fromkeys([t for t in full if t not in core] + ["off shoulder"]))
    stage3 = core + ["open clothes", "breasts out", "cleavage"]
    stage5 = [full[0], "off shoulder", "covered", "sweat"]
    return {"stage1": list(full), "stage2": stage2, "stage3": stage3,
            "stage4": list(NUDES), "stage5": stage5}

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
APPROVAL = {"status": "APPROVED",
            "evidence": "User 2026-11-19: 'ok mỗi nhân vật tạo story riêng cho từng outfit'; standing, 3:4, crowded bright, explicit."}

def story_id_of(base):
    f = base / "story_id.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None

def seed(slug, title, e):
    base = ROOT / "sources" / slug
    base.mkdir(parents=True, exist_ok=True)
    v = e["venue"]
    (base / "story.md").write_text(
        f"{title}\n\n{e['name']} stands in {v['place']} in {look_full(e)} and undresses in plain sight; "
        f"{e['hook']}. Solo, adult, fictional, explicit.\n", encoding="utf-8")
    sid = story_id_of(base)
    if sid is None:
        sid = cli("database/src/n2m_db.py", "create-story", "--title", title,
                  "--mode", "NON_BLIND", "--text-file", str(base / "story.md"))
        (base / "story_id.txt").write_text(sid, encoding="utf-8")
    cli("database/src/n2m_db.py", "add-role", "--story-id", sid, "--key", "LEAD",
        "--description", f"{e['name']}, adult woman, solo")
    cli("database/src/n2m_db.py", "bind-role", "--story-id", sid, "--key", "LEAD",
        "--character-id", e["char_id"])
    plan = {"schema_version": "n2m.story.v1", "story_id": sid, "revision": 1, "approval": APPROVAL,
            "source_refs": [{"type": "user_story", "id": slug, "status": "confirmed"}],
            "intent": {"content_profile": "adult", "raw_labels": ["mature", "nsfw", "explicit"],
                       "constraints": ["Solo; no second character.", "Standing poses only; 3:4 portrait.",
                                       "Bright crowded venue.", f"Outfit: {e['full'][0]}."]},
            "characters": [{"character_id": e["char_id"], "name": e["name"],
                            "age_status": "verified_adult", "identity_anchors": e["anchors"]}],
            "acts": [{"act_id": "A01", "beats": []}]}
    events = [
        (f"She works the {e['full'][0]} off one shoulder at {v['place']}, and {e['hook']}.", "Her skin is bare; the crowd does not slow."),
        (f"She opens the {e['core'][0]} in front of everyone, chest bare.", "Her breath lifts her chest; nobody stops."),
        (f"She rolls the {e['bottom']} down and steps out of it on {v['floor']}.", "Completely nude in the crowd."),
        (f"She leans back against {v['lean_on']} and touches herself slowly.", "Her jaw slackens; the crowd keeps moving."),
        (f"Spent, she pulls the {e['full'][0]} over one shoulder and looks into the camera.", "Afterglow in daylight."),
    ]
    for i, (a, r) in enumerate(events, 1):
        plan["acts"][0]["beats"].append({"beat_id": f"B{i:02d}",
            "events": [{"event_id": f"E{i:03d}", "actor_id": e["name"], "primary_action": a,
                        "target_id": None, "reaction": r}]})
    (base / "story_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("database/src/n2m_workflow.py", "save-plan", "--story-id", sid, "--file", str(base / "story_plan.json"))
    beats = con.execute("select count(*) from beats b join acts a on a.id=b.act_id where a.story_id=?", (sid,)).fetchone()[0]
    if beats:
        return sid
    act_id = cli("database/src/n2m_workflow.py", "add-act", "--story-id", sid, "--order", "1",
                 "--title", "A01", "--summary", v["place"])
    for i, (a, r) in enumerate(events, 1):
        beat_id = cli("database/src/n2m_workflow.py", "add-beat", "--act-id", act_id,
                      "--order", str(i), "--summary", a[:180])
        ev = {"actor_role_key": "LEAD", "target_role_key": None, "action": a, "reaction": r,
              "raw_labels": ["nsfw", "explicit"], "source_fragment": v["place"],
              "spec": {"solo": True, "tier": "explicit", "pose": "standing"}}
        f = base / f"event_{i:02d}.json"
        f.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        cli("database/src/n2m_workflow.py", "add-event", "--beat-id", beat_id, "--order", "1", "--file", str(f))
    return sid

def board(sid, slug, title, e, force=False):
    base = ROOT / "sources" / slug
    have = con.execute("select id from storyboards where story_id=? order by revision desc limit 1", (sid,)).fetchone()
    if have and not force:
        return have[0]
    rev = con.execute("select current_revision from stories where id=?", (sid,)).fetchone()[0]
    beats = list(con.execute("""select b.id beat_id, b.beat_order, e.id event_id from beats b
        join acts a on a.id=b.act_id left join story_events e on e.beat_id=b.id
        where a.story_id=? order by b.beat_order, e.event_order""", (sid,)))
    B = {r["beat_order"]: r for r in beats}
    scene_key = "scene-main"
    outfits = outfit_stages(e)
    w = words(slug, e)
    plan = {"schema_version": 5, "story_revision": rev, "approval": APPROVAL,
            "visual_bible": {
                "characters": {"LEAD": {
                    "description": f"{title.split(' - ')[0]}, adult, {e['full'][0]}",
                    "provenance": "catalog character + character_tags",
                    "character_id": e["char_id"], "outfit_id": None,
                    "prompt_tags": [slug.split("_")[0] + " (blue archive)", "1girl", "solo"] + e["anchors"],
                    "outfits": {k: {"prompt_tags": v} for k, v in outfits.items()}}},
                "locations": {"venue": {"description": e["venue"]["place"],
                                        "provenance": "story brief",
                                        "prompt_tags": e["venue"]["location_tags"]}},
                "props": {e["held"].replace(" ", "-"): {"description": e["held"],
                                                        "provenance": "story brief",
                                                        "prompt_tags": [e["held"]]}},
                "styles": {"anime-bright": {"description": "Clean bright anime, high-key, crowded public venue",
                                            "provenance": "user choice",
                                            "prompt_tags": ["anime style", "clean lineart", "bright colors",
                                                            "cinematic lighting", "@anjing"]}}},
            "scenes": {scene_key: {"location_key": "venue", "style_key": "anime-bright",
                                   "time_key": "day", "role_keys": ["LEAD"],
                                   "lighting_tags": e["venue"]["lighting"]}},
            "shots": [], "coverage": []}
    t = 0
    for i, (purpose, nrole, transition, camera, focus, moment) in enumerate(TEMPLATES, 1):
        k = f"S{i:02d}"
        if transition != "SAME_MOMENT":
            t += 1
        plan["shots"].append({
            "shot_key": k, "shot_order": i, "beat_id": B[1 if i <= 8 else 2 if i <= 16 else 3 if i <= 28 else 4 if i <= 38 else 5]["beat_id"],
            "branch_key": "main", "previous_shot_key": None if i == 1 else f"S{i-1:02d}",
            "transition": transition, "purpose": purpose, "narrative_role": nrole,
            "story_time": t, "scene_key": scene_key, "camera": camera, "focus": focus,
            "visual_moment": moment.format(**w), "role_keys": ["LEAD"], "location_key": "venue",
            "visible_location_tags": e["venue"]["location_tags"],
            "prop_keys": [e["held"].replace(" ", "-")] if i <= 8 else [],
            "style_key": "anime-bright", "outfit_key": f"stage{STAGE[i]}"})
        plan["coverage"].append({"event_id": B[1 if i <= 8 else 2 if i <= 16 else 3 if i <= 28 else 4 if i <= 38 else 5]["event_id"],
                                 "status": "VISUALIZED", "shot_key": k,
                                 "evidence": plan["shots"][-1]["visual_moment"]})
    f = base / "storyboard_v5.json"
    f.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return cli("database/src/n2m_workflow.py", "save-storyboard", "--story-id", sid, "--file", str(f))[0]

def shots(sid, slug, e):
    base = ROOT / "sources" / slug / "shots"
    base.mkdir(parents=True, exist_ok=True)
    board_id = con.execute("select id from storyboards where story_id=? order by revision desc limit 1",
                           (sid,)).fetchone()[0]
    plan = json.loads(con.execute("select plan_json from storyboards where id=?", (board_id,)).fetchone()[0])
    scene = plan["scenes"][plan["shots"][0]["scene_key"]]
    events = {r["beat_id"]: r for r in con.execute(
        "select e.beat_id, e.id, e.action from story_events e join beats b on b.id=e.beat_id "
        "join acts a on a.id=b.act_id where a.story_id=?", (sid,))}
    prop_key = plan["shots"][0]["prop_keys"][0] if plan["shots"][0]["prop_keys"] else None
    prev_outfit, prev_state = None, None
    for slot in plan["shots"]:
        i = slot["shot_order"]
        ev = events[slot["beat_id"]]
        holding = prop_key if (prop_key and i <= 8) else "none"
        at = {"outfit_key": slot["outfit_key"], "pose": "standing",
              "position": e["venue"]["place_short"], "holding": holding}
        before = dict(at) if prev_state is None else dict(prev_state)
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
                                  "action": (["undressing"] if prev_outfit and prev_outfit != slot["outfit_key"] else []) + ["standing"],
                                  "camera": camera_tags(slot["camera"]),
                                  "prose": slot["visual_moment"]}}
        scene_state = {"location_key": scene["location_key"], "time_key": scene["time_key"]}
        cont = {"snapshots": [
            {"role_key": None, "before": scene_state, "delta": {"set": {}, "remove": []}, "after": scene_state,
             "moment": {"at_shot": scene_state, "at_delta": {"set": {}, "remove": []},
                        "after_delta": {"set": {}, "remove": []}}},
            {"role_key": "LEAD", "before": before, "delta": at_delta, "after": at,
             "moment": {"at_shot": {**before, **at_delta["set"]}, "at_delta": at_delta,
                        "after_delta": {"set": {}, "remove": []}}}]}
        sf, cf = base / f"{slot['shot_key']}.shot.json", base / f"{slot['shot_key']}.cont.json"
        sf.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        cf.write_text(json.dumps(cont, ensure_ascii=False, indent=1), encoding="utf-8")
        res = cli("database/src/n2m_workflow.py", "save-shot", "--beat-id", slot["beat_id"],
                  "--shot-key", slot["shot_key"], "--file", str(sf), "--event-id", ev["id"])
        shot_id = res[0] if isinstance(res, list) else res
        cli("database/src/n2m_workflow.py", "save-continuity", "--shot-id", shot_id, "--file", str(cf))
        pr = cli("database/src/n2m_workflow.py", "compile-prompt", "--shot-id", shot_id, "--save")
        print(slug, slot["shot_key"], pr.get("status"), flush=True)
        prev_outfit, prev_state = slot["outfit_key"], at

if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    for slug, name, char_id, anchors, full, core, closure, bottom, venue, hook, held, _label in STORIES:
        e = entry(char_id, name, anchors, full, core, closure, bottom, venue, hook, held)
        title = f"{slug.replace('_', ' ').title()} - {name}"
        if phase in ("all", "seed"):
            sid = seed(slug, title, e)
            print("SEED", slug, sid, flush=True)
        else:
            sid = story_id_of(ROOT / "sources" / slug)
        if phase in ("all", "boards"):
            print("BOARD", slug, board(sid, slug, title, e, force="--force" in sys.argv), flush=True)
        if phase in ("all", "shots"):
            shots(sid, slug, e)
