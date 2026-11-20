import json, os, subprocess, sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
DB = ROOT / "database/data/novel2anima.db"
SID = "story_3fbb888ae9c145a98d"
env = dict(os.environ, PYTHONIOENCODING="utf-8")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
beats = list(con.execute('''select b.id beat_id, b.beat_order, e.id event_id from beats b
  join acts a on a.id=b.act_id left join story_events e on e.beat_id=b.id
  where a.story_id=? order by b.beat_order, e.event_order''', (SID,)))
B = {r["beat_order"]: r for r in beats}
assert len(B) == 5, B

SHOTS = [
    # (beat, purpose, role, transition, camera, focus, moment)
    (1, "ESTABLISHING", "ESTABLISH", "START", "wide shot, eye level", "room and storm", "Raiden stands at the shoji in a closed purple kimono, lightning outside."),
    (1, "DETAIL", "DETAIL", "CONTINUOUS", "close-up", "obi knot", "Her fingers find the obi knot at her waist."),
    (1, "ACTION", "INITIATE", "CONTINUOUS", "medium shot, from behind", "hands on the obi", "She pulls the obi loose; the knot gives."),
    (1, "ACTION", "DETAIL", "SAME_MOMENT", "low angle", "obi falling", "The obi slides off her waist and drops."),
    (1, "REACTION", "REACTION", "CONTINUOUS", "close-up, eye level", "her face", "Lightning flashes across her half-closed eyes."),
    (1, "ACTION", "PROLONG", "CAMERA_CUT", "medium shot, from behind", "bare shoulder", "The kimono slips from one shoulder; her back is exposed to the storm light."),
    (1, "DETAIL", "DETAIL", "CONTINUOUS", "extreme close-up", "shoulder and purple nails", "Her purple nails rest against the bare shoulder."),
    (1, "REACTION", "PROLONG", "CAMERA_CUT", "cowboy shot, from behind", "hair over kimono", "Her braided ponytail falls across the half-open kimono."),
    (2, "ESTABLISHING", "PROLONG", "CONTINUOUS", "full body, eye level", "standing figure", "She stands with the kimono open at the chest, breathing in the storm air."),
    (2, "ACTION", "INITIATE", "CONTINUOUS", "upper body", "fabric at shoulders", "She pushes the kimono off both shoulders."),
    (2, "DETAIL", "DETAIL", "CONTINUOUS", "close-up", "fabric at hips", "The kimono pools at her waist."),
    (2, "ACTION", "DETAIL", "SAME_MOMENT", "low angle", "fabric mid-fall", "The last of the silk falls past her thighs."),
    (2, "ESTABLISHING", "PROLONG", "CAMERA_CUT", "full body, from behind", "nude back", "She stands nude before the shoji, storm behind her."),
    (2, "ACTION", "PROLONG", "CAMERA_CUT", "full body, front, eye level", "nude figure", "She turns; her breasts and hips catch the lightning."),
    (2, "DETAIL", "DETAIL", "CONTINUOUS", "extreme close-up", "mole under eye", "Sweat at her temple, the mole under her eye."),
    (2, "DETAIL", "DETAIL", "SAME_MOMENT", "low angle, close", "thighs and bare feet", "Her thighs and bare feet against the tatami."),
    (2, "REACTION", "REACTION", "CONTINUOUS", "close-up", "her eyes", "She looks straight at the viewer, unreadable."),
    (2, "ESTABLISHING", "PROLONG", "CAMERA_CUT", "wide shot, full body", "nude silhouette", "Thunder frames her nude silhouette against the shoji."),
    (3, "ACTION", "INITIATE", "CONTINUOUS", "medium shot, side", "kneeling", "She kneels on the tatami, thighs closed."),
    (3, "DETAIL", "DETAIL", "CONTINUOUS", "close-up", "hands on thighs", "Her hands rest flat on her thighs."),
    (3, "ACTION", "INITIATE", "CONTINUOUS", "medium shot, front", "hand between thighs", "Her hand slides between her thighs."),
    (3, "REACTION", "PROLONG", "CONTINUOUS", "upper body, from below", "back arching", "Her back arches; her head tips back."),
    (3, "ACTION", "PROLONG", "SAME_MOMENT", "side view, full body", "arched spine", "Same moment from the side: her spine curves in the storm light."),
    (3, "DETAIL", "DETAIL", "CONTINUOUS", "extreme close-up", "fingers", "Her fingers glisten."),
    (3, "REACTION", "REACTION", "CONTINUOUS", "close-up", "parted lips", "Her mouth parts; her breathing breaks."),
    (3, "ACTION", "PROLONG", "CAMERA_CUT", "full body, from behind", "spine and hips", "From behind, her hips move against her own hand."),
    (3, "REACTION", "PROLONG", "SAME_MOMENT", "profile, upper body", "chest rising", "Same instant in profile; her chest rises."),
    (3, "DETAIL", "DETAIL", "CONTINUOUS", "extreme close-up", "throat", "Sweat runs down her throat."),
    (4, "ACTION", "PROLONG", "CONTINUOUS", "medium shot, side", "weight shifting back", "She rocks back onto her heels."),
    (4, "DETAIL", "DETAIL", "CONTINUOUS", "close-up", "hand on tatami", "One hand braces on the tatami."),
    (4, "ACTION", "PROLONG", "CAMERA_CUT", "low angle, full body", "thighs parted", "Low angle: her thighs part, knees wide."),
    (4, "ACTION", "DETAIL", "SAME_MOMENT", "low angle, close", "hips", "Same moment, tighter: her hips lift."),
    (4, "ACTION", "PROLONG", "CONTINUOUS", "medium shot, front", "moving hips", "Her hips move, unhurried, against her hand."),
    (4, "DETAIL", "DETAIL", "CONTINUOUS", "extreme close-up", "toes", "Her toes curl against the tatami."),
    (4, "REACTION", "REACTION", "CONTINUOUS", "close-up", "eyes shut", "Her eyes shut; her jaw tightens."),
    (4, "DETAIL", "DETAIL", "SAME_MOMENT", "close-up", "neck and mouth", "Same instant: her mouth opens, throat taut."),
    (4, "CLIMAX", "PEAK", "CONTINUOUS", "full body, from below", "arched body", "Her back arches hard; lightning floods the room."),
    (4, "CLIMAX", "PEAK", "SAME_MOMENT", "wide shot, silhouette", "body against shoji", "Same instant, wide: her silhouette breaks the storm."),
    (4, "CLIMAX", "DETAIL", "CAMERA_CUT", "extreme close-up", "trembling hand", "Her hand trembles where it grips the mat."),
    (4, "DETAIL", "DETAIL", "CONTINUOUS", "close-up", "grip on tatami", "Fingers dig into the weave."),
    (5, "AFTERMATH", "RESOLUTION", "CONTINUOUS", "wide shot", "collapse", "She sinks onto her side on the tatami."),
    (5, "AFTERMATH", "RESOLUTION", "CONTINUOUS", "full body, side", "kimono half covering", "She lies on her side, the kimono across her hip."),
    (5, "DETAIL", "DETAIL", "CONTINUOUS", "close-up", "chest and sweat", "Her chest still rises fast; sweat on her skin."),
    (5, "REACTION", "PROLONG", "CAMERA_CUT", "close-up, from above", "face on the mat", "Her face rests on the tatami, hair spread out."),
    (5, "ACTION", "PROLONG", "CONTINUOUS", "medium shot, from behind", "pulling the kimono", "She pulls the loose kimono over herself."),
    (5, "DETAIL", "DETAIL", "SAME_MOMENT", "close-up", "hand on fabric", "Her hand closes on the silk."),
    (5, "AFTERMATH", "RESOLUTION", "CAMERA_CUT", "wide shot", "room and rain", "Wide: the room, the rain easing beyond the shoji."),
    (5, "AFTERMATH", "RESOLUTION", "CONTINUOUS", "close-up, eye level", "her eyes", "She looks at the viewer one last time."),
]

assert len(SHOTS) == 48

OUTFITS = {
    "kimono-full": ["purple kimono", "obi", "japanese clothes", "hair ornament"],
    "kimono-loose": ["purple kimono", "obi loose", "off shoulder", "traditional clothes"],
    "kimono-open": ["purple kimono", "open clothes", "breasts out"],
    "nude": ["completely nude", "nipples", "navel", "barefoot"],
    "robe-after": ["purple kimono", "covered", "wet"],
}
outfit_for = {}
for i in range(1, 6): outfit_for[i] = "kimono-full"
for i in range(6, 9): outfit_for[i] = "kimono-loose"
for i in range(9, 13): outfit_for[i] = "kimono-open"
for i in range(13, 42): outfit_for[i] = "nude"
for i in range(42, 49): outfit_for[i] = "robe-after"

plan = {
    "schema_version": 5,
    "story_revision": 2,
    "approval": {"status": "APPROVED",
                 "evidence": "User 2026-11-19: 'shot dài cũng được', explicit tier confirmed; album 48 shot."},
    "visual_bible": {
        "characters": {"LEAD": {
            "description": "Raiden Shogun, adult woman, purple hair in a braided ponytail, purple eyes, mole under the left eye, purple nails",
            "provenance": "catalog character raiden_shogun + character_tags",
            "character_id": "character:storyaura_danbooru_csv:7ccbdb7864aec63e51",
            "outfit_id": None,
            "prompt_tags": ["raiden shogun", "1girl", "solo", "purple hair", "very long hair", "braided ponytail",
                            "purple eyes", "mole under eye", "purple nails", "large breasts"],
            "outfits": {k: {"prompt_tags": v} for k, v in OUTFITS.items()}}},
        "locations": {"tenshukaku-room": {
            "description": "Private tatami room in Tenshukaku: shoji screens on one side, storm and rain beyond, low candle, storm light from the shoji",
            "provenance": "story brief",
            "prompt_tags": ["indoors", "tatami", "shoji", "rain", "thunder", "night", "window", "candlelight"]}},
        "props": {"obi": {"description": "Purple obi sash", "provenance": "story brief", "prompt_tags": ["obi", "sash"]}},
        "styles": {"anime-clean": {"description": "Clean anime linework, cinematic storm lighting",
                                    "provenance": "user choice", "prompt_tags": ["anime style", "cinematic lighting"]}},
    },
    "scenes": {"tatami-storm": {"location_key": "tenshukaku-room", "style_key": "anime-clean",
                                 "time_key": "storm-night", "role_keys": ["LEAD"],
                                 "lighting_tags": ["candlelight", "lightning", "backlighting", "dark"]}},
    "shots": [],
    "coverage": [],
}

for i, (beat, purpose, nrole, transition, camera, focus, moment) in enumerate(SHOTS, 1):
    k = f"S{i:02d}"
    plan["shots"].append({
        "shot_key": k, "shot_order": i, "beat_id": B[beat]["beat_id"], "branch_key": "main",
        "previous_shot_key": None if i == 1 else f"S{i-1:02d}",
        "transition": transition, "purpose": purpose, "narrative_role": nrole,
        "story_time": i, "scene_key": "tatami-storm", "camera": camera, "focus": focus,
        "visual_moment": moment, "role_keys": ["LEAD"], "location_key": "tenshukaku-room",
        "visible_location_tags": ["indoors", "tatami", "shoji", "rain", "night"],
        "prop_keys": ["obi"] if i <= 5 else [], "style_key": "anime-clean",
        "outfit_key": outfit_for[i],
    })
    if transition == "SAME_MOMENT":
        plan["shots"][-1]["story_time"] = plan["shots"][-2]["story_time"]

for i, (beat, purpose, nrole, transition, camera, focus, moment) in enumerate(SHOTS, 1):
    plan["coverage"].append({"event_id": B[beat]["event_id"], "status": "VISUALIZED",
                             "shot_key": f"S{i:02d}", "evidence": f"{moment}"})

base = ROOT / "sources/indigo_boudoir_raiden"
(base / "storyboard_v5.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

r = subprocess.run([sys.executable, "database/src/n2m_workflow.py", "save-storyboard", "--story-id", SID,
                    "--file", str(base / "storyboard_v5.json")], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", env=env)
print(r.returncode, r.stdout[-2000:], r.stderr[-2000:])
