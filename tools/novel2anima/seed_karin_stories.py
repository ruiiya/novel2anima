import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
env = dict(os.environ, PYTHONIOENCODING="utf-8")

def cli(*a):
    r = subprocess.run([sys.executable, *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"FAIL {a}\n{r.stdout}\n{r.stderr}")
    out = r.stdout.strip()
    return json.loads(out)["result"] if out.startswith("{") else out

KARIN = "character:storyaura_danbooru_csv:79568c232a32c03e6e"
KARIN_BUNNY = "character:storyaura_danbooru_csv:808a728dec97f549db"
ANCHORS = ["dark-skinned female", "rabbit ears", "rabbit tail", "yellow eyes", "black hair",
           "very long hair", "long hair", "purple hair", "ponytail", "large breasts", "halo"]

STORIES = [{
    "dir": "karin_station_rush",
    "title": "Station Rush - Karin",
    "char": (KARIN, "Karin"),
    "anchors": ANCHORS,
    "wardrobe": ["school uniform", "cardigan", "pleated skirt", "bowtie", "anti-materiel rifle"],
    "premise": "Noon at the central station, the concourse packed. Karin stands in the current with her rifle slung and undresses in plain sight, because nobody here is looking.",
    "locations": "crowded station concourse, marble columns, skylight, noon crowd",
    "events": [
        ("She shrugs the cardigan off one shoulder and lets it hang from her elbow in the middle of the moving crowd.", "Her shoulder is bare under the skylight; the crowd does not slow."),
        ("She opens the white shirt button by button and pulls the bowtie loose, standing still while people pass.", "The shirt hangs open; her chest is bare to the waist above the pleated skirt."),
        ("She unbuttons the skirt and lets it drop, stepping out of it barefoot on the concourse tiles.", "Completely nude in the crowd, rifle still slung, halo bright above her."),
        ("She leans back against a tiled pillar and touches herself slowly, unhurried, while the noon crowd moves past.", "Her jaw slackens; nobody stops."),
        ("Spent, she pulls the cardigan over one shoulder, breathing hard, and looks straight into the camera.", "Afterglow in daylight. The crowd keeps moving."),
    ],
}, {
    "dir": "karin_pool_bar",
    "title": "Poolside Bar - Karin",
    "char": (KARIN_BUNNY, "Karin"),
    "anchors": ANCHORS,
    "wardrobe": ["playboy bunny", "black leotard", "detached collar", "white gloves", "wrist cuffs"],
    "premise": "The pool bar at noon, full of guests, water flashing on every surface. Karin works through a cocktail and then through her bunny suit, one piece at a time, without leaving her place.",
    "locations": "crowded poolside bar, wet tiles, aqua water, white loungers, noon sun",
    "events": [
        ("She peels the white gloves off finger by finger and drops them on the bar.", "Her bare hands close on the glass; the cuffs stay on."),
        ("She unclips the detached collar and opens the leotard at the chest, standing at the rail.", "Her shoulders and chest are bare above the black leotard."),
        ("She pulls the leotard down her hips and steps out of it onto the wet tiles.", "Completely nude at the pool bar, guests passing behind her."),
        ("She leans back against the bar counter and touches herself in the sun, one leg braced on the rail.", "Water reflections move over her skin; her breathing goes ragged."),
        ("She pulls the leotard up to her waist and stands half-covered, looking over the pool.", "Afterglow, high key, the bar still loud behind her."),
    ],
}, {
    "dir": "karin_hall_backdrop",
    "title": "Hall Backdrop - Karin",
    "char": (KARIN_BUNNY, "Karin"),
    "anchors": ANCHORS + ["number tattoo"],
    "wardrobe": ["playboy bunny", "highleg leotard", "strapless leotard", "detached collar", "white gloves"],
    "premise": "A crowded exhibition hall at midday, white backdrops and skylights. Karin poses for nobody in particular and strips in front of the crowd, the number tattoo on her hip the only label she keeps.",
    "locations": "crowded exhibition hall, white backdrops, polished floor, skylight, visitors",
    "events": [
        ("She strips the white gloves off and tucks them into the leotard's collar at her throat.", "Her bare hands hang at her sides; the number tattoo shows above the highleg cut."),
        ("She unclips the detached collar and lets the leotard slip off one shoulder.", "The highleg leotard hangs open at the chest; her skin is bare to the waist."),
        ("She rolls the leotard down over her hips and steps out of it in front of the backdrop.", "Completely nude on the polished floor, visitors crossing behind her."),
        ("She leans back against the paper backdrop and touches herself, one knee bent, while the hall talks around her.", "Her head tips toward the skylight; the number tattoo moves with her hip."),
        ("She pulls the leotard back up to her waist and stands breathing, looking over the crowd.", "Afterglow under the skylight. The hall goes on."),
    ],
}]

APPROVAL = {"status": "APPROVED",
            "evidence": "User 2026-11-19: 'ok' for 3 Karin concepts, standing poses, 3:4 portrait, crowded bright locations, explicit tier."}

for s in STORIES:
    base = ROOT / "sources" / s["dir"]
    base.mkdir(parents=True, exist_ok=True)
    char_id, char_name = s["char"]
    (base / "story.md").write_text(
        f"{s['title']}\n\n{s['premise']}\n\nLocation: {s['locations']}.\n"
        "Solo. Adult, consensual, fictional. Explicit tier. Standing poses only, 3:4 portrait.\n",
        encoding="utf-8")
    idfile = base / "story_id.txt"
    if idfile.exists():
        story_id = idfile.read_text(encoding="utf-8").strip()
        print("resume", s["title"], story_id)
    else:
        story_id = cli("database/src/n2m_db.py", "create-story", "--title", s["title"],
                       "--mode", "NON_BLIND", "--text-file", str(base / "story.md"))
        idfile.write_text(story_id, encoding="utf-8")
    cli("database/src/n2m_db.py", "add-role", "--story-id", story_id, "--key", "LEAD",
        "--description", f"{char_name}, adult woman, solo")
    cli("database/src/n2m_db.py", "bind-role", "--story-id", story_id, "--key", "LEAD",
        "--character-id", char_id)
    plan = {"schema_version": "n2m.story.v1", "story_id": story_id, "revision": 1,
            "approval": APPROVAL,
            "source_refs": [{"type": "user_story", "id": s["dir"], "status": "confirmed"}],
            "intent": {"content_profile": "adult", "raw_labels": ["mature", "nsfw", "explicit"],
                       "constraints": ["Solo shot only; no second character enters frame.",
                                       "Adult fictional character; consensual.",
                                       "Standing poses only; 3:4 portrait.", s["premise"]]},
            "characters": [{"character_id": char_id, "name": char_name, "age_status": "verified_adult",
                            "identity_anchors": s["anchors"]}],
            "acts": [{"act_id": "A01", "beats": [
                {"beat_id": f"B{i:02d}", "events": [{"event_id": f"E{i:03d}", "actor_id": char_name,
                                                     "primary_action": a, "target_id": None, "reaction": r}]}
                for i, (a, r) in enumerate(s["events"], 1)]}]}
    (base / "story_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("database/src/n2m_workflow.py", "save-plan", "--story-id", story_id, "--file", str(base / "story_plan.json"))
    act_id = cli("database/src/n2m_workflow.py", "add-act", "--story-id", story_id, "--order", "1",
                 "--title", "A01", "--summary", s["premise"])
    for i, (action, reaction) in enumerate(s["events"], 1):
        beat_id = cli("database/src/n2m_workflow.py", "add-beat", "--act-id", act_id,
                      "--order", str(i), "--summary", action[:180])
        ev = {"actor_role_key": "LEAD", "target_role_key": None, "action": action, "reaction": reaction,
              "raw_labels": ["nsfw", "explicit"], "source_fragment": s["premise"],
              "spec": {"solo": True, "tier": "explicit", "pose": "standing"}}
        evf = base / f"event_{i:02d}.json"
        evf.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        cli("database/src/n2m_workflow.py", "add-event", "--beat-id", beat_id, "--order", "1", "--file", str(evf))
    print(s["title"], story_id)
