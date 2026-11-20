import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(r"C:\Users\user\Desktop\novel2anima")
PY = sys.executable
env = dict(os.environ, PYTHONIOENCODING="utf-8")

def cli(*args):
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"FAIL {args}\n{r.stdout}\n{r.stderr}")
    out = r.stdout.strip()
    if out.startswith("{"):
        return json.loads(out)["result"]
    return out

STORIES = [
    {
        "dir": "indigo_boudoir_raiden",
        "title": "Indigo Boudoir - Raiden Shogun",
        "char": ("raiden_shogun", "character:storyaura_danbooru_csv:7ccbdb7864aec63e51", "Raiden Shogun"),
        "anchors": ["purple hair", "very long hair", "braided ponytail", "purple eyes", "mole under eye", "purple nails"],
        "wardrobe": ["purple kimono", "obi", "bridal gauntlets"],
        "premise": "A storm-lashed night in Tenshukaku. Raiden Shogun alone in her private tatami room lets the storm in, then lets the kimono fall. Thunder is the only witness.",
        "locations": "tatami room, shoji screens, storm rain outside",
        "events": [
            ("She undoes the obi and lets the purple kimono slip from one shoulder, breathing in the storm air.", "The kimono hangs loose; her shoulder and collarbone are bare. Her expression is unreadable."),
            ("She opens the kimono fully and stands nude on the tatami, hair unbound, letting the lightning paint her skin.", "Fully nude, she does not flinch at the thunder. Her hand rests at her hip."),
            ("She kneels on the tatami and touches herself slowly, back arched, mouth parted.", "Her breathing breaks rhythm with the rain. Hair clings to her cheek."),
            ("She rocks back on her heels, one hand braced on the floor, thighs parted, hips moving against her own hand.", "Her head falls back; thunder drowns the sound she makes."),
            ("Spent, she lies on her side in the loose kimono, chest still rising hard, watching the rain.", "The storm eases. The kimono covers almost nothing."),
        ],
    },
    {
        "dir": "hotel_noir_kafka",
        "title": "Hotel Noir - Kafka",
        "char": ("kafka_honkai_star_rail", "character:storyaura_danbooru_csv:298dfbd96422456ec9", "Kafka"),
        "anchors": ["purple hair", "long hair", "purple eyes", "hair between eyes", "purple gloves", "sunglasses on head"],
        "wardrobe": ["white shirt", "black jacket", "black shorts", "high-waist shorts", "pince-nez"],
        "premise": "A rented room, one lamp, one bottle. Kafka takes her time undressing for nobody but herself, and the mirror keeps the record.",
        "locations": "hotel room, velvet armchair, tall mirror, amber lamp",
        "events": [
            ("She shrugs the black jacket off onto the chair and opens the white shirt button by button, gloves still on.", "The shirt hangs open over bare skin; the jacket is abandoned behind her."),
            ("She drops the shirt, steps out of the shorts, and stands nude before the mirror, adjusting nothing.", "Completely nude except the gloves. Her reflection looks back with the same boredom."),
            ("She sits on the bed's edge, one glove at her mouth, the other hand between her thighs.", "Her eyes half close; the wine glass tips, forgotten, in her other hand."),
            ("She lies back across the sheets, knees up, gloves still on, moving with a slow patience that is entirely deliberate.", "The sheets twist under her; the lamp catches the sweat at her throat."),
            ("She sits up, pours what is left of the wine, and looks at the camera as if it were a late guest.", "Afterglow. Gloves off, hair down, sheets ruined."),
        ],
    },
    {
        "dir": "casino_backroom_yelan",
        "title": "Casino Backroom - Yelan",
        "char": ("yelan_genshin_impact", "character:storyaura_danbooru_csv:64079b3a9f649e8e5b", "Yelan"),
        "anchors": ["black hair", "short hair", "bob cut", "green eyes", "diagonal bangs"],
        "wardrobe": ["slit dress", "bare shoulders", "earrings", "dice"],
        "premise": "After the house closes, Yelan stays behind the green felt with a pair of dice and no one to gamble against.",
        "locations": "casino backroom, green felt table, smoke, single overhead lamp",
        "events": [
            ("She leans on the felt table and pulls the slit of her dress higher, dice cupped in one hand.", "One leg is bare to the hip; the dice rattle against her palm."),
            ("She lets the dress fall and stands nude against the table's edge, weighing the dice one last time.", "Completely nude, dice still in hand. The felt is the only colour left."),
            ("She bends over the table, hair spilling across the felt, and rolls.", "The dice scatter. Her back is a long line under the lamp."),
            ("She lies back across the green felt, dice pressed to her stomach, thighs apart, and lets the numbers land where they land.", "Her body arches; the dice slide off her hip and stop."),
            ("She sits in the dealer's chair, wrapped in nothing but smoke, and slides the dice back across the felt.", "Afterglow. The lamp hums. She is already counting the next hand."),
        ],
    },
    {
        "dir": "rain_glass_acheron",
        "title": "Rain Glass - Acheron",
        "char": ("acheron_honkai_star_rail", "character:storyaura_danbooru_csv:f06b71419760db2f0f", "Acheron"),
        "anchors": ["purple hair", "very long hair", "streaked hair", "hair over one eye", "purple eyes", "leg tattoo"],
        "wardrobe": ["white coat", "black shorts", "black gloves", "black choker", "single bare shoulder"],
        "premise": "A high window, a city that will not stop raining. Acheron stands on the wrong side of the glass and lets the water do the talking.",
        "locations": "empty upper floor, floor-to-ceiling rain-streaked window, cold blue backlight",
        "events": [
            ("She lets the white coat slide off one shoulder and presses her palm flat to the rain-streaked glass.", "The coat hangs from one arm; the glass fogs under her hand."),
            ("She steps out of the coat and the shorts and stands nude against the glass, backlit by the city.", "Nude silhouette through wet glass. Her tattoo is the only line that matters."),
            ("She leans her forehead and chest to the cold glass, hands sliding down, breath fogging the surface.", "Water runs down the glass on both sides of her."),
            ("She turns, presses her back to the window, and lets the cold take her weight as her hand moves.", "Her head tips back; the rain outside keeps its rhythm."),
            ("She sinks to the floor with the coat across her lap, watching the rain thin out.", "Afterglow in blue. The glass keeps her outline."),
        ],
    },
    {
        "dir": "unit_maintenance_2b",
        "title": "Unit Maintenance - 2B",
        "char": ("2b_nier_automata", "character:storyaura_danbooru_csv:dd56d4042045cef1d2", "2B"),
        "anchors": ["white hair", "short hair", "black blindfold", "black hairband", "mole under mouth"],
        "wardrobe": ["highleg leotard", "black gloves", "thigh boots", "juliet sleeves"],
        "premise": "A sterile white maintenance bay, one android, and a diagnostic she never logs. The blindfold stays on.",
        "locations": "white maintenance bay, steel table, softbox light, surgical clean",
        "events": [
            ("She peels the leotard down from her shoulders and lets the juliet sleeves fall back, blindfold still in place.", "The leotard hangs at her waist; her chest is bare and her posture does not change."),
            ("She steps out of the leotard entirely and stands nude in the white room, boots still on.", "Completely nude except boots, gloves and blindfold. Diagnostic lights run across her."),
            ("She sits on the steel table and touches herself with the same precision she gives any system check.", "Her jaw tightens. The blindfold hides whether she is watching anything."),
            ("She lies back on the table, knees up, boots braced on the steel, and works herself to the edge without a sound.", "The table is cold. Her breathing is the only telemetry."),
            ("She sits up, pulls the leotard back to her waist, and waits for the room to finish its scan.", "Afterglow, fully composed, blindfold still on."),
        ],
    },
]

APPROVAL = {
    "status": "APPROVED",
    "evidence": "User instruction 2026-11-19: 'ok các nhân vật này đều tạo story đi'; explicit tier requested ('mức cao nhất'). Adult fictional characters only.",
}

for idx, s in enumerate(STORIES, 1):
    base = ROOT / "sources" / s["dir"]
    base.mkdir(parents=True, exist_ok=True)
    slug, char_id, char_name = s["char"]
    text = (f"{s['title']}\n\n{s['premise']}\n\n"
            f"Location: {s['locations']}.\n"
            "Solo. Adult, consensual, fictional. Explicit tier.\n")
    (base / "story.md").write_text(text, encoding="utf-8")
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

    plan = {
        "schema_version": "n2m.story.v1",
        "story_id": story_id,
        "revision": 1,
        "approval": APPROVAL,
        "source_refs": [{"type": "user_story", "id": s["dir"], "status": "confirmed"}],
        "intent": {"content_profile": "adult", "raw_labels": ["mature", "nsfw", "explicit"],
                   "constraints": ["Solo shot only; no second character enters frame.",
                                   "Adult fictional character; consensual.",
                                   "Wardrobe delta is progressive and never resets.",
                                   s["premise"]]},
        "characters": [{"character_id": char_id, "name": char_name, "age_status": "verified_adult",
                        "identity_anchors": s["anchors"]}],
        "acts": [{"act_id": "A01", "beats": [
            {"beat_id": f"B{i:02d}", "events": [{"event_id": f"E{i:03d}", "actor_id": char_name,
                                                  "primary_action": a, "target_id": None, "reaction": r}]}
            for i, (a, r) in enumerate(s["events"], 1)]}],
    }
    (base / "story_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("database/src/n2m_workflow.py", "save-plan", "--story-id", story_id, "--file", str(base / "story_plan.json"))
    act_id = cli("database/src/n2m_workflow.py", "add-act", "--story-id", story_id, "--order", "1",
                 "--title", "A01", "--summary", s["premise"])
    for i, (action, reaction) in enumerate(s["events"], 1):
        beat_id = cli("database/src/n2m_workflow.py", "add-beat", "--act-id", act_id,
                      "--order", str(i), "--summary", action[:180])
        ev = {"actor_role_key": "LEAD", "target_role_key": None, "action": action,
              "reaction": reaction, "raw_labels": ["nsfw", "explicit"],
              "source_fragment": s["premise"], "spec": {"solo": True, "tier": "explicit"}}
        evf = base / f"event_{i:02d}.json"
        evf.write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        cli("database/src/n2m_workflow.py", "add-event", "--beat-id", beat_id, "--order", "1", "--file", str(evf))
    print(idx, s["title"], story_id)
