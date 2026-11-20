import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
env = dict(os.environ, PYTHONIOENCODING="utf-8")

STORIES = [("story_62004947a855491ca5", "karin_station_rush"),
           ("story_7cb6e639fe894dcaac", "karin_pool_bar"),
           ("story_d4f8f286f43f45cda3", "karin_hall_backdrop")]

STAGE = {}
for i in range(1, 9): STAGE[i] = 1
for i in range(9, 17): STAGE[i] = 2
for i in range(17, 29): STAGE[i] = 3
for i in range(27, 43): STAGE[i] = 4
for i in range(43, 49): STAGE[i] = 5

# (purpose, narrative_role, transition, camera, focus, moment)
SHOTS = [
    ("ESTABLISHING", "ESTABLISH", "START", "full body, eye level", "her and the crowd",
     "{S} stands at {place} in {look_full}, the noon crowd blurred behind her."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from below", "halo and rabbit ears",
     "Her halo and rabbit ears catch the {light_word} above the crowd."),
    ("REACTION", "REACTION", "CONTINUOUS", "close-up, eye level", "her eyes",
     "Her yellow eyes flick to the camera and away."),
    ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, three-quarter view", "her stance",
     "She rests her weight on one leg, {look_full} tight across her chest."),
    ("ACTION", "PROLONG", "CONTINUOUS", "medium shot, from behind", "ponytail and back",
     "From behind, her ponytail sways as people pass close."),
    ("REACTION", "PROLONG", "SAME_MOMENT", "upper body, eye level", "her face",
     "A passer-by brushes her shoulder; she does not step away."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her hand",
     "Her fingers tighten on {held}."),
    ("ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, eye level", "her against the crowd",
     "{S} looks over the crowd and decides to stay."),
    ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "shoulder and sleeve",
     "She works the {layer1} off one shoulder."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "sleeve at the elbow",
     "The {layer1} slips down to her elbow."),
    ("ACTION", "PROLONG", "CONTINUOUS", "full body", "garment falling",
     "She lets the {layer1} drop; {place_short} does not notice."),
    ("REACTION", "PROLONG", "SAME_MOMENT", "cowboy shot, eye level", "bare shoulders",
     "Her shoulders roll free, skin bright under the {light_word}."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "close-up, from above", "detail",
     "{stage2_detail}."),
    ("ACTION", "PROLONG", "CONTINUOUS", "upper body, from side", "her chest",
     "She turns her chest to the light and breathes out."),
    ("REACTION", "PROLONG", "CAMERA_CUT", "full body, from below", "her face above the crowd",
     "Someone laughs nearby; her mouth stays flat."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "temple",
     "A bead of sweat at her temple."),
    ("ACTION", "INITIATE", "CONTINUOUS", "upper body", "her hands at her throat",
     "Her fingers find the {layer2} and pull it loose."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "open front",
     "The {layer2_result} hangs open; her breath lifts her chest."),
    ("ACTION", "PROLONG", "CONTINUOUS", "full body, eye level", "opening clothes",
     "She opens the {top} in the middle of the crowd."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "cowboy shot, from behind", "bare back",
     "From behind, her back is bare to the waist above the {bottom}."),
    ("DETAIL", "DETAIL", "CONTINUOUS", "close-up", "her chest",
     "Her nipples harden in the air of {place_short}."),
    ("DETAIL", "DETAIL", "SAME_MOMENT", "close-up, from above", "detail",
     "{stage3_detail}."),
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
    ("ACTION", "PROLONG", "SAME_MOMENT", "cowboy shot, eye level", "bare feet",
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
assert len(SHOTS) == 48

ANCHORS = ["dark-skinned female", "rabbit ears", "rabbit tail", "yellow eyes", "black hair",
           "very long hair", "long hair", "purple hair", "ponytail", "large breasts", "halo"]

W = {
    "karin_station_rush": dict(
        scene="station-concourse", location="station-concourse", char=(
            "character:storyaura_danbooru_csv:79568c232a32c03e6e"),
        anchors=ANCHORS,
        outfits=[["school uniform", "cardigan", "white shirt", "collared shirt", "pleated skirt",
                  "bowtie", "blue bowtie", "aqua bowtie", "scrunchie"],
                 ["school uniform", "white shirt", "collared shirt", "pleated skirt", "bowtie",
                  "aqua bowtie", "scrunchie"],
                 ["open shirt", "white shirt", "breasts out", "pleated skirt", "bowtie"],
                 ["completely nude", "nipples", "navel", "barefoot"],
                 ["shirt", "covered", "sweat"]],
        nude_index=3,
        location_tags=["indoors", "train station", "concourse", "marble floor", "skylight",
                       "large windows", "crowd", "blurry background"],
        lighting=["daylight", "hard light", "bright", "skylight"],
        props={"rifle": {"description": "Anti-materiel rifle slung over her shoulder",
                         "provenance": "character_tag: boys anti tank rifle", 
                         "prompt_tags": ["anti-materiel rifle", "rifle", "sniper rifle", "gun"]}},
        prop_key="rifle",
        style=["anime style", "clean lineart", "bright colors", "cinematic lighting"],
        words=dict(S="Karin", place="the noon concourse of the central station",
                   place_short="the concourse",
                   look_full="a school uniform with cardigan, bowtie and pleated skirt",
                   light_word="hard noon light", layer1="cardigan", layer2="shirt buttons",
                   layer2_result="shirt", top="white shirt", bottom="pleated skirt",
                   held="the rifle sling", cover="cardigan", floor="the stone floor",
                   lean_on="the tiled pillar",
                   stage2_detail="The scrunchie on her wrist, the bowtie crooked",
                   stage3_detail="The blue bow of her uniform against bare skin"),
        beat_events=[1, 2, 3, 4, 5]),
    "karin_pool_bar": dict(
        scene="pool-bar", location="pool-bar",
        char=("character:storyaura_danbooru_csv:808a728dec97f549db"),
        anchors=ANCHORS,
        outfits=[["playboy bunny", "black leotard", "strapless leotard", "detached collar",
                  "white gloves", "wrist cuffs", "fake animal ears", "cleavage", "thighs", "ass"],
                 ["playboy bunny", "black leotard", "detached collar", "wrist cuffs", "bare hands",
                  "cleavage", "thighs"],
                 ["playboy bunny", "black leotard", "pulled down", "breasts out", "bare shoulders",
                  "thighs"],
                 ["completely nude", "nipples", "navel", "barefoot"],
                 ["leotard", "off shoulder", "covered", "sweat"]],
        nude_index=3,
        location_tags=["outdoors", "swimming pool", "poolside", "bar counter", "crowd",
                       "water", "white loungers", "blurry background"],
        lighting=["sunlight", "high key", "water reflections", "bright"],
        props={"glass": {"description": "Cocktail glass on the bar", "provenance": "story brief",
                         "prompt_tags": ["cocktail glass", "glass", "drink"]}},
        prop_key="glass",
        style=["anime style", "clean lineart", "bright colors", "cinematic lighting"],
        words=dict(S="Karin", place="the poolside bar at noon", place_short="the pool bar",
                   look_full="a black bunny leotard with detached collar, cuffs and white gloves",
                   light_word="water reflections", layer1="white gloves",
                   layer2="detached collar", layer2_result="leotard",
                   top="leotard", bottom="leotard", held="the cocktail glass",
                   cover="the leotard", floor="the wet tiles", lean_on="the bar counter",
                   stage2_detail="Her bare fingers on the glass, the cuffs still on",
                   stage3_detail="The strap loose at her throat, water on her collarbone"),
        beat_events=[1, 2, 3, 4, 5]),
    "karin_hall_backdrop": dict(
        scene="hall-backdrop", location="exhibition-hall",
        char=("character:storyaura_danbooru_csv:808a728dec97f549db"),
        anchors=ANCHORS + ["number tattoo"],
        outfits=[["playboy bunny", "black leotard", "highleg leotard", "strapless leotard",
                  "detached collar", "white gloves", "wrist cuffs", "number tattoo",
                  "cleavage", "thighs"],
                 ["playboy bunny", "black leotard", "highleg leotard", "number tattoo",
                  "bare hands", "cleavage", "thighs"],
                 ["playboy bunny", "black leotard", "open leotard", "number tattoo",
                  "breasts out", "bare shoulders", "thighs"],
                 ["completely nude", "nipples", "navel", "number tattoo", "barefoot"],
                 ["leotard", "covered", "sweat"]],
        nude_index=3,
        location_tags=["indoors", "convention hall", "exhibition hall", "white backdrop",
                       "polished floor", "skylight", "crowd", "blurry background"],
        lighting=["daylight", "soft skylight", "bright", "even"],
        props={},
        prop_key=None,
        style=["anime style", "clean lineart", "bright colors", "cinematic lighting"],
        words=dict(S="Karin", place="the crowded exhibition hall", place_short="the hall",
                   look_full="a highleg black bunny leotard with detached collar and white gloves",
                   light_word="skylight", layer1="white gloves", layer2="detached collar",
                   layer2_result="leotard", top="highleg leotard", bottom="highleg leotard",
                   held="the edge of the backdrop", cover="the leotard",
                   floor="the polished floor", lean_on="the paper backdrop",
                   stage2_detail="The number tattoo high on her hip, her bare hands",
                   stage3_detail="The number tattoo as the leotard opens"),
        beat_events=[1, 2, 3, 4, 5]),
}

con = sqlite3.connect(ROOT / "database/data/novel2anima.db")
con.row_factory = sqlite3.Row

for sid, slug in STORIES:
    w = W[slug]
    beats = list(con.execute("""select b.id beat_id, b.beat_order, e.id event_id from beats b
        join acts a on a.id=b.act_id left join story_events e on e.beat_id=b.id
        where a.story_id=? order by b.beat_order, e.event_order""", (sid,)))
    assert len(beats) == 5, beats
    B = {r["beat_order"]: r for r in beats}
    # 48 slots -> beat by shot index
    def beat_of(i):
        return 1 if i <= 8 else 2 if i <= 16 else 3 if i <= 26 else 4 if i <= 38 else 5
    outfit_keys = [f"stage{n}" for n in (1, 2, 3, 4, 5)]
    rev = con.execute("select current_revision from stories where id=?", (sid,)).fetchone()[0]
    plan = {
        "schema_version": 5, "story_revision": rev,
        "approval": {"status": "APPROVED",
                     "evidence": "User 2026-11-19: 'ok' for 3 Karin concepts; standing poses, 3:4 portrait, crowded bright locations, explicit tier."},
        "visual_bible": {
            "characters": {"LEAD": {
                "description": "Karin (Blue Archive), adult dark-skinned woman, black hair with purple streaks in a long ponytail, yellow eyes, rabbit ears, rabbit tail, halo",
                "provenance": "catalog character karin + character_tags",
                "character_id": w["char"], "outfit_id": None,
                "prompt_tags": ["karin (blue archive)", "1girl", "solo"] + w["anchors"],
                "outfits": {k: {"prompt_tags": tags} for k, tags in zip(outfit_keys, w["outfits"])}}},
            "locations": {w["location"]: {
                "description": w["words"]["place"], "provenance": "story brief",
                "prompt_tags": w["location_tags"]}},
            "props": w["props"],
            "styles": {"anime-bright": {"description": "Clean bright anime, high-key, crowded public venue",
                                         "provenance": "user choice",
                                         "prompt_tags": w["style"] + ["@anjing"]}},
        },
        "scenes": {w["scene"]: {"location_key": w["location"], "style_key": "anime-bright",
                                 "time_key": "day", "role_keys": ["LEAD"],
                                 "lighting_tags": w["lighting"]}},
        "shots": [], "coverage": [],
    }
    story_time = 0
    for i, (purpose, nrole, transition, camera, focus, moment) in enumerate(SHOTS, 1):
        k = f"S{i:02d}"
        if transition != "SAME_MOMENT":
            story_time += 1
        stage = STAGE[i]
        outfit_key = outfit_keys[stage - 1]
        plan["shots"].append({
            "shot_key": k, "shot_order": i, "beat_id": B[beat_of(i)]["beat_id"], "branch_key": "main",
            "previous_shot_key": None if i == 1 else f"S{i-1:02d}",
            "transition": transition, "purpose": purpose, "narrative_role": nrole,
            "story_time": story_time, "scene_key": w["scene"], "camera": camera, "focus": focus,
            "visual_moment": moment.format(**w["words"]), "role_keys": ["LEAD"],
            "location_key": w["location"], "visible_location_tags": w["location_tags"],
            "prop_keys": [w["prop_key"]] if (w["prop_key"] and i <= 8) else [],
            "style_key": "anime-bright", "outfit_key": outfit_key,
        })
    for i, slot in enumerate(plan["shots"], 1):
        plan["coverage"].append({"event_id": B[beat_of(i)]["event_id"], "status": "VISUALIZED",
                                 "shot_key": slot["shot_key"], "evidence": slot["visual_moment"]})

    base = ROOT / "sources" / slug
    (base / "storyboard_v5.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, "database/src/n2m_workflow.py", "save-storyboard",
                        "--story-id", sid, "--file", str(base / "storyboard_v5.json")],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
    print(slug, r.returncode, r.stdout.strip()[-200:], r.stderr.strip()[-300:])
