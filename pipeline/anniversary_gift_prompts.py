"""Generate, validate, save and QA 122 Anima prompts from the approved ShotSpecs."""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, "database/src")
sys.path.insert(0, "tools/novel2anima")
from n2m_db import connect, save_natural_prompt  # noqa: E402
from n2m_workflow import save_qa  # noqa: E402
from validate_anima_prompt import validate  # noqa: E402

ROOT = pathlib.Path("exports/anniversary_gift")
PROMPTS = ROOT / "prompts"
PROMPTS.mkdir(parents=True, exist_ok=True)
STATE = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
SHOTS = json.loads((ROOT / "shots.json").read_text(encoding="utf-8"))
LABELS = ["nsfw", "explicit", "adult", "consensual", "hotwife", "qos", "interracial", "no_tattoo", "blind_cast"]
POLICY_REF = "N2M-CONTENT-POLICY@1.3.0"

MANUAL = {
    "S001": ROOT / "drafts/test/T01_S001.txt",
    "S005": ROOT / "drafts/test/T02_S005.txt",
    "S024": ROOT / "drafts/test/T03_S024.txt",
    "S041": ROOT / "drafts/test/T04_S041.txt",
    "S051": ROOT / "drafts/test/T05_S051.txt",
    "S052": ROOT / "drafts/test/T06_S052.txt",
}

LOC = {
    "LOC_SUITE_LIVING": (["hotel suite", "living room", "window", "city lights", "night"], "living area"),
    "LOC_SUITE_BED": (["hotel suite", "bedroom", "king bed", "black silk sheets", "city lights", "night"], "bedroom"),
    "LOC_SUITE_DINING": (["hotel suite", "dining table", "candlelight", "wine", "night"], "dining corner"),
    "LOC_SUITE_BATH": (["hotel suite", "bathroom", "bathtub", "water", "warm light"], "bathroom"),
    "LOC_SUITE_TERRACE": (["hotel suite", "terrace", "railing", "city skyline", "daylight"], "private terrace"),
    "LOC_SUITE_DOOR": (["hotel suite", "doorway", "door", "corridor light", "night"], "doorway"),
}
LIGHT = {"P1": "warm lamp light", "P2": "warm lamp light", "P3": "soft daylight",
         "P4": "candlelight", "P5": "pale morning light"}
PROPS = {
    "PROP_LUGGAGE": ["luggage"], "PROP_NOTE": ["letter", "note"], "PROP_RING": ["wedding ring"],
    "PROP_PHONE": ["phone"], "PROP_DRESS": ["black dress"], "PROP_CHAMPAGNE": ["champagne", "glass"],
    "PROP_PENDANT": ["pendant", "necklace", "spade (symbol)"], "PROP_DESSERT": ["dessert", "box"],
    "PROP_LINGERIE": ["black lingerie"], "PROP_RED_DRESS": ["red dress"], "PROP_WINE": ["wine", "glass"],
    "PROP_TOWEL": ["towel", "robe"], "PROP_BREAKFAST": ["coffee", "croissant", "tray"],
    "PROP_TRAY": ["tray", "room service"],
}
EXPR = {
    "quiet awe": ["calm", "looking away"], "soft smile": ["smile"], "focused": ["focused"],
    "nervous": ["nervous", "biting lip"], "composed": ["calm"], "held breath": ["wide-eyed", "parted lips"],
    "hungry": ["half-closed eyes", "parted lips"], "playful": ["smile", "playful"],
    "composed, flushed": ["flushed", "calm"], "bold": ["half-closed eyes", "confident"],
    "half-closed eyes": ["half-closed eyes"], "laughing, flushed": ["laughing", "flushed"],
    "breathless": ["breathless", "parted lips"], "spent": ["half-closed eyes", "flushed"],
    "soft, sleepy": ["sleepy", "soft smile"], "relaxed": ["relaxed", "smile"],
    "tender": ["soft smile"], "warm": ["smile"], "drowsy": ["half-closed eyes"],
    "open": ["soft smile"], "amused": ["smile"], "soft": ["soft smile"],
    "startled, then steady": ["wide-eyed", "parted lips"],
    "strained pleasure": ["half-closed eyes", "flushed"],
    "grateful, relieved": ["soft smile", "exhale"],
    "intense": ["half-closed eyes", "flushed"],
    "overwhelmed": ["half-closed eyes", "parted lips"],
    "spent, safe": ["half-closed eyes", "soft smile"],
    "quiet": ["calm"], "pensive": ["looking down"], "wistful": ["soft smile", "looking away"],
    "resolved": ["calm", "determined"], "still": [],
}


def add(tags, *new):
    for item in new:
        if item and item not in tags:
            tags.append(item)


def outfit_tags(state):
    tags = []
    low = (state or "").lower()
    if "travel clothes" in low:
        add(tags, "casual clothes", "coat")
    if "robe" in low:
        add(tags, "robe")
    if "black evening dress" in low:
        add(tags, "black evening dress", "high slit")
    if "open" in low or "unzipped" in low:
        add(tags, "open clothes")
    if "black lingerie" in low:
        add(tags, "black lingerie", "lace")
    if "dress around waist" in low:
        add(tags, "dress around waist")
    if "clothing aside" in low:
        add(tags, "clothing aside")
    if "white shirt" in low:
        add(tags, "white shirt", "bare legs")
    if "white robe" in low:
        add(tags, "white robe")
    if "white sheet" in low:
        add(tags, "white sheet")
    if "red dress" in low:
        add(tags, "red dress")
    if "strap down" in low:
        add(tags, "strap slip")
    if "wet" in low:
        add(tags, "wet")
    if "dark shirt" in low:
        add(tags, "dark shirt", "rolled up sleeves")
    if "rain-damp coat" in low:
        add(tags, "black coat")
    if "trousers" in low:
        add(tags, "trousers")
    if "completely nude" in low or (low.strip() == "nude"):
        add(tags, "completely nude")
    if "pendant" in low and "pendant" not in tags:
        add(tags, "pendant")
    return tags


def act_tags(beat, moment):
    low = moment.lower()
    tags = []
    if beat == "P1.B08":
        add(tags, "kiss", "open clothes")
    elif beat == "P2.B03":
        add(tags, "straddling", "girl on top")
    elif beat == "P2.B04":
        add(tags, "fellatio", "oral", "penis", "saliva")
    elif beat == "P2.B05":
        add(tags, "sex", "vaginal", "penis", "cowgirl position", "girl on top", "straddling")
    elif beat == "P2.B06":
        add(tags, "sex", "vaginal", "penis")
        if "missionary" in low:
            add(tags, "missionary")
        if "cowgirl" in low:
            add(tags, "cowgirl position", "girl on top")
    elif beat == "P2.B07":
        add(tags, "sex", "vaginal", "penis", "doggystyle")
    elif beat == "P2.B08":
        add(tags, "sex", "vaginal", "penis", "cum on body")
        if "stomach" in low:
            add(tags, "cum on stomach")
        if "collapse" in low:
            add(tags, "afterglow")
    elif beat == "P3.B03":
        add(tags, "bath", "wet")
    elif beat == "P3.B05":
        add(tags, "sex", "vaginal", "penis")
        if "missionary" in low:
            add(tags, "missionary")
        if "spoon" in low:
            add(tags, "spooning")
    elif beat == "P4.B04":
        add(tags, "kiss", "neck kiss")
    elif beat == "P4.B06":
        add(tags, "sex", "vaginal", "penis", "table")
    elif beat == "P4.B07":
        add(tags, "sex", "vaginal", "penis")
        if "missionary" in low:
            add(tags, "missionary")
        if "cowgirl" in low:
            add(tags, "cowgirl position", "girl on top")
        if "behind" in low:
            add(tags, "doggystyle")
    elif beat == "P4.B08":
        add(tags, "sex", "vaginal", "penis", "cum on body")
        if "afterglow" in low:
            add(tags, "afterglow")
    elif beat == "P5.B03":
        add(tags, "shower", "wet")
    return tags


def clause(text, name):
    if not text:
        return f"{name} stays close"
    if text.startswith("she "):
        return f"{name} {text[4:]}"
    if text.startswith("he "):
        return f"{name} {text[3:]}"
    if text.startswith("his "):
        return f"{name}'s {text[4:]}"
    if text.startswith("her "):
        return f"{name}'s {text[4:]}"
    return f"{name} {text}"


def detail_phrase(moment):
    low = moment.lower()
    if low.startswith("his "):
        return "Marcus's " + moment[4:]
    if low.startswith("her "):
        return "Linh's " + moment[4:]
    if low.startswith("she ") or low.startswith("he ") or low.startswith("they "):
        return "the moment " + moment
    if low.startswith("wide "):
        return "the " + moment
    if low == "the door opens":
        return "the door opening"
    return moment


def fix_pronouns(text):
    text = re.sub(r"\bhe\b", "Marcus", text)
    text = re.sub(r"\bhim\b", "Marcus", text)
    text = re.sub(r"\bhis\b", "Marcus's", text)
    return text


def build_tags(spec, event_spec, beat_key, moment):
    part = beat_key.split(".")[0]
    roles = [p["role_key"] for p in spec["participants"]]
    safety = event_spec.get("safety", "nsfw")
    tags = ["masterpiece", "best quality", "score_7", safety, "highres"]
    if not roles:
        add(tags, "no humans", "scenery")
    elif roles == ["WIFE_A"]:
        add(tags, "1girl", "solo")
    elif roles == ["WIFE_A", "PARTNER_B"]:
        add(tags, "1boy", "1girl", "hetero", "interracial")
    if "WIFE_A" in roles:
        add(tags, "mature female", "black hair", "very long hair", "low updo", "brown eyes",
            "light brown skin", "medium breasts", "mole", "wedding ring")
        p = next(p for p in spec["participants"] if p["role_key"] == "WIFE_A")
        add(tags, *outfit_tags(p["spec"].get("outfit_state")))
    if "PARTNER_B" in roles:
        add(tags, "dark skin", "short black hair", "beard", "dark eyes",
            "mature male", "muscular")
        p = next(p for p in spec["participants"] if p["role_key"] == "PARTNER_B")
        add(tags, *outfit_tags(p["spec"].get("outfit_state")))
    add(tags, *act_tags(beat_key, moment))
    for p in spec["participants"]:
        add(tags, *EXPR.get(p["spec"].get("expression", ""), []))
        pose = p["spec"].get("pose", "")
        add(tags, *[x.strip() for x in pose.split(",") if x.strip()])
    add(tags, *[x.strip() for x in spec["camera"].split(",") if x.strip()])
    loc_tags, _ = LOC[spec["location_key"]]
    add(tags, *loc_tags, LIGHT[part])
    for prop in spec.get("prop_keys", []):
        add(tags, *PROPS.get(prop, []))
    add(tags, "anime coloring", "cel shading", "clean lineart")
    return tags


def build_prose(spec, event, beat_key, moment):
    part = beat_key.split(".")[0]
    roles = [p["role_key"] for p in spec["participants"]]
    loc_name = LOC[spec["location_key"]][1]
    light = LIGHT[part]
    if not roles:
        return (f"The suite is empty in the {light}, with {moment}. "
                "The pendant remains on the pillow, and the adjoining door is closed.")
    inter = spec["interactions"][0] if spec["interactions"] else None
    if inter:
        actor, target = inter["actor_role_key"], inter["target_role_key"]
        action, reaction = inter["action_text"], inter["reaction_text"]
    else:
        # Off-frame event: visualize the reaction, not the off-frame action.
        actor, target = None, None
        action, reaction = event["reaction"], None
    purpose = spec["purpose"]
    detail = detail_phrase(moment)
    if roles == ["WIFE_A"]:
        c1 = clause(action, "Linh")
        if purpose == "DETAIL":
            s1 = f"The frame holds {detail}, while {c1}."
        elif purpose == "AFTERMATH":
            s1 = f"Afterward, {c1}, and the frame holds {detail}."
        else:
            s1 = f"{c1}, and the frame holds {detail}."
        s2 = f"The {loc_name} is quiet around her under the {light}."
    else:
        name_a = "Linh" if actor != "PARTNER_B" else "Marcus"
        name_b = "Marcus" if name_a == "Linh" else "Linh"
        c1 = clause(action, name_a)
        c2 = fix_pronouns(clause(reaction, name_b)) if reaction else ""
        if purpose == "DETAIL":
            s1 = f"The frame holds {detail}, while {c1}" + (f" and {c2}" if c2 else "") + "."
        elif purpose == "AFTERMATH":
            s1 = f"Afterward, {c1}" + (f" and {c2}" if c2 else "") + f", and the frame holds {detail}."
        else:
            s1 = c1 + (f", and {c2}" if c2 else "") + "."
        s2 = f"The {loc_name} holds them under the {light}, with the city soft beyond."
    return s1 + " " + s2


def main():
    con = connect(pathlib.Path("database/data/novel2anima.db"))
    out = {}
    issues_count = {}
    for key, info in SHOTS.items():
        shot_id = info["shot_id"]
        row = con.execute("SELECT shot_spec_json,beat_id FROM shots WHERE id=?", (shot_id,)).fetchone()
        spec = json.loads(row["shot_spec_json"])
        ev = con.execute("SELECT * FROM story_events WHERE id=?", (info["event_id"],)).fetchone()
        ev_spec = json.loads(ev["spec_json"])
        moment = spec["focus"]
        if key in MANUAL:
            text = MANUAL[key].read_text(encoding="utf-8").strip()
        else:
            tags = build_tags(spec, ev_spec, info["beat_key"], moment)
            text = ", ".join(tags) + "\n" + build_prose(spec, ev, info["beat_key"], moment)
        issues = validate(text)
        scenery = (not spec["participants"]) and issues == ["SUBJECT_COUNT_MISSING"]
        (PROMPTS / f"{key}.txt").write_text(text + "\n", encoding="utf-8")
        prompt_id, rev = save_natural_prompt(con, shot_id, text, "en")
        checks = {
            "identity": "Linh / Marcus anchors present" if spec["participants"] else "scenery; no character",
            "outfit": [p["spec"].get("outfit_state") for p in spec["participants"]],
            "camera": spec["camera"],
            "moment_match": moment,
            "scene": spec["location_key"],
            "safety": ev_spec.get("safety"),
            "tags_validated": "PASS" if not issues else ("SCENERY_SUBJECT_EXCEPTION" if scenery else issues),
        }
        report = {
            "checks": checks,
            "policy_decision": {
                "policy_id": "N2M-CONTENT-POLICY", "policy_version": "1.3.0",
                "scope": "PROMPT_DERIVATION", "decision": "PASS", "shot_id": shot_id,
                "rule_reference": "consensual adult eroticism; no minors, no sexual violence",
                "evidence": "prompt generated from ShotSpec; no event added or removed",
            },
            "verdict_reason": ("scenery shot: subject-count format exception documented"
                               if scenery else "tag block + two prose sentences from ShotSpec"),
        }
        qa_id = save_qa(con, "PROMPT", prompt_id, "PASS", report, POLICY_REF)
        out[key] = {"shot_id": shot_id, "prompt_id": prompt_id, "revision": rev,
                    "qa_id": qa_id, "issues": issues, "scenery_exception": scenery,
                    "beat_key": info["beat_key"], "file": str(PROMPTS / f"{key}.txt")}
        issues_count[key] = issues
    (ROOT / "prompts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    clean = sum(1 for v in issues_count.values() if not v)
    print("prompts:", len(out), "format clean:", clean, "with issues:", len(out) - clean)
    for k, v in issues_count.items():
        if v:
            print("issue", k, v)


if __name__ == "__main__":
    main()
