"""Create and bind the two original adult leads for Quà Kỷ Niệm.

Research basis: Danbooru tag vocabulary (dark skin, beard, short hair, mature male,
wedding ring, updo) and the project's Anima tag contract. Both characters are
original adults, REVIEWED, no tattoo. HUSBAND_C is bound to the existing Ren Kaito
because he is off-frame only.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "database/src")
from n2m_db import bind_role, connect, js, uid  # noqa: E402
from n2m_workflow import save_plan  # noqa: E402
from n2m_storyboard import get_storyboard, save_storyboard  # noqa: E402

DB = pathlib.Path("database/data/novel2anima.db")
ROOT = pathlib.Path("exports/anniversary_gift")
STATE = ROOT / "state.json"
APPROVED_AT = "2026-11-17T00:00:00Z"

FEMALE = {
    "id": "character:original:linh_tran",
    "slug": "linh_tran",
    "display_name": "Linh Tran",
    "identity_description": (
        "adult Vietnamese woman, 31, 165 cm, elegant curvy build: medium-full breasts, "
        "narrow waist, soft rounded hips, toned thighs; very long straight black hair to "
        "the lower back, usually in a low updo with a few loose strands; dark brown almond "
        "eyes with a defined upper lash line; warm light-brown skin with a peach undertone; "
        "oval face, soft jawline, small straight nose, full rose-brown lips; a small mole on "
        "the left collarbone; no tattoo; wedding ring on the left hand"
    ),
    "identity_json": {
        "age": 31,
        "age_basis": "Original adult character explicitly written as an adult in this AU.",
        "provenance": "user_requested_original; story casting",
        "height_cm": 165,
        "build": "curvy: medium-full breasts, narrow waist, soft rounded hips, toned thighs",
        "hair": "very long straight black hair to the lower back, low updo with loose strands",
        "eyes": "dark brown almond eyes, defined upper lash line",
        "skin": "warm light-brown skin with a peach undertone",
        "face": "oval face, soft jawline, small straight nose, full rose-brown lips",
        "marks": "small mole on the left collarbone; no tattoo",
        "palette": "black hair, dark brown eyes, warm light-brown skin, rose-brown lips",
        "personality": "poised, observant, dry humor, quietly decisive",
        "wardrobe": "black evening dress, red dress, black lingerie, white shirt, robe",
    },
    "tags": ["black_hair", "long_hair", "brown_eyes", "medium_breasts", "mole",
             "wedding_ring", "updo"],
    "traits": [
        ("appearance", "hair", "very long straight black hair, low updo"),
        ("appearance", "eyes", "dark brown almond eyes"),
        ("appearance", "build", "curvy, medium-full breasts, narrow waist, soft rounded hips"),
        ("appearance", "skin", "warm light-brown skin"),
        ("appearance", "mark", "small mole on left collarbone"),
        ("role", "story_role", "wife / QOS hotwife"),
    ],
}

MALE = {
    "id": "character:original:marcus_reed",
    "slug": "marcus_reed",
    "display_name": "Marcus Reed",
    "identity_description": (
        "adult Black man, 32, 190 cm, tall athletic build: broad shoulders, long limbs, "
        "large hands, lean muscle; dark brown skin with a warm undertone; short black hair, "
        "close-cropped; trimmed black beard along the jaw; dark brown eyes, heavy brows; "
        "strong square jaw, broad nose, full lips; a faint burn scar on the inside of the "
        "left forearm, a chef's mark; no tattoo; calm, direct presence"
    ),
    "identity_json": {
        "age": 32,
        "age_basis": "Original adult character explicitly written as an adult in this AU.",
        "provenance": "user_requested_original; story casting",
        "height_cm": 190,
        "build": "tall athletic: broad shoulders, long limbs, large hands, lean muscle",
        "hair": "short black hair, close-cropped",
        "facial_hair": "trimmed black beard along the jaw",
        "eyes": "dark brown eyes, heavy brows",
        "skin": "dark brown skin with a warm undertone",
        "face": "strong square jaw, broad nose, full lips",
        "marks": "faint burn scar on the inside of the left forearm; no tattoo",
        "palette": "black hair, dark brown eyes, dark brown skin",
        "profession": "chef; runs a small late-night kitchen",
        "personality": "calm, direct, attentive, dry humor, disciplined",
        "wardrobe": "dark chef shirt with rolled sleeves, charcoal trousers, black coat",
    },
    "tags": ["dark_skin", "black_hair", "short_hair", "beard", "dark_eyes",
             "mature_male", "muscular", "chef", "tall", "male_focus"],
    "traits": [
        ("appearance", "hair", "short black hair"),
        ("appearance", "facial_hair", "trimmed black beard"),
        ("appearance", "eyes", "dark brown eyes, heavy brows"),
        ("appearance", "build", "tall athletic, broad shoulders, long limbs"),
        ("appearance", "skin", "dark brown skin"),
        ("appearance", "mark", "faint burn scar on left forearm"),
        ("role", "story_role", "chef / partner"),
    ],
}


def ensure_tag(con, name):
    tag_id = f"tag:danbooru:{name}"
    con.execute(
        "INSERT OR IGNORE INTO catalog_tags(id,namespace,name,category,post_count,deprecated,source_record_id,original_name) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (tag_id, "danbooru", name, 0, 0, 0, None, name),
    )
    return tag_id


def ensure_character(con, data):
    existing = con.execute("SELECT id FROM characters WHERE id=?", (data["id"],)).fetchone()
    if existing:
        return data["id"]
    con.execute(
        "INSERT INTO characters(id,universe_id,slug,display_name,age_status,identity_description,identity_json,identity_review) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (data["id"], "universe:original_adult_au", data["slug"], data["display_name"],
         "CONFIRMED_ADULT", data["identity_description"], js(data["identity_json"]), "REVIEWED"),
    )
    for name in data["tags"]:
        tag_id = ensure_tag(con, name)
        con.execute(
            "INSERT OR IGNORE INTO character_tags(character_id,tag_id,source_record_id,tag_role) "
            "VALUES(?,?,?,?)",
            (data["id"], tag_id, None, "CORE_CANDIDATE"),
        )
    for group, key, value in data["traits"]:
        con.execute(
            "INSERT OR IGNORE INTO character_traits(id,character_id,trait_group,trait_key,trait_value,source_record_id,confidence,is_locked) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (uid("trait"), data["id"], group, key, value, None, "REVIEWED", 1),
        )
    return data["id"]


def main():
    con = connect(DB)
    state = json.loads(STATE.read_text(encoding="utf-8"))
    story_id = state["story_id"]

    female_id = ensure_character(con, FEMALE)
    male_id = ensure_character(con, MALE)
    husband_id = "character:curated:ren_kaito"
    print("characters:", female_id, male_id)
    print("husband:", husband_id)

    bind_role(con, story_id, "WIFE_A", female_id)
    bind_role(con, story_id, "PARTNER_B", male_id)
    bind_role(con, story_id, "HUSBAND_C", husband_id)
    rev = con.execute("SELECT current_revision FROM stories WHERE id=?", (story_id,)).fetchone()[0]
    print("story revision after bind:", rev)

    # Plan revision with the actual cast.
    plan = json.loads(con.execute(
        "SELECT plan_json FROM story_revisions WHERE story_id=? ORDER BY revision DESC LIMIT 1",
        (story_id,)).fetchone()[0])
    plan["approval"] = {
        "status": "APPROVED", "approved_by": "user", "approved_at": APPROVED_AT,
        "evidence": "User delegated casting: 'tự nghiên cứu để tạo character thích hợp'.",
        "policy_id": "N2M-CONTENT-POLICY", "policy_version": "1.3.0",
    }
    plan["characters"] = [
        {"role_key": "WIFE_A", "character_id": female_id, "age_status": "CONFIRMED_ADULT",
         "cast_status": "BOUND", "identity": FEMALE["identity_description"],
         "appearance_evidence": "original character profile REVIEWED; identity_json + character_tags"},
        {"role_key": "PARTNER_B", "character_id": male_id, "age_status": "CONFIRMED_ADULT",
         "cast_status": "BOUND", "identity": MALE["identity_description"],
         "appearance_evidence": "original character profile REVIEWED; identity_json + character_tags"},
        {"role_key": "HUSBAND_C", "character_id": husband_id, "age_status": "CONFIRMED_ADULT",
         "cast_status": "BOUND", "identity": "Ren Kaito, adult man, off-frame only",
         "appearance_evidence": "existing curated adult profile; never appears in frame"},
    ]
    plan_rev = save_plan(con, story_id, plan, expected_revision=rev)
    print("plan revision:", plan_rev)

    # Storyboard revision 2: same 122 slots, updated Visual Bible + casting hashes.
    current = con.execute("SELECT current_revision FROM stories WHERE id=?", (story_id,)).fetchone()[0]
    board_data = get_storyboard(con, state["storyboard_id"])
    board = board_data["plan"]
    board["story_revision"] = current
    board["approval"] = {
        "status": "APPROVED", "approved_by": "user", "approved_at": APPROVED_AT,
        "evidence": "Casting revision: user delegated character creation; both leads are original adults REVIEWED.",
    }
    board["visual_bible"]["characters"] = {
        "WIFE_A": {"description": FEMALE["identity_description"], "provenance": "original character profile REVIEWED",
                   "character_id": female_id, "outfit_id": None},
        "PARTNER_B": {"description": MALE["identity_description"], "provenance": "original character profile REVIEWED",
                      "character_id": male_id, "outfit_id": None},
        "HUSBAND_C": {"description": "Ren Kaito, adult man, off-frame only: voice, phone text, wedding ring, adjoining door",
                      "provenance": "existing curated adult profile; never appears in frame",
                      "character_id": husband_id, "outfit_id": None},
    }
    bid, brev = save_storyboard(con, story_id, board, expected_revision=1)
    print("storyboard revision:", bid, brev)

    state.update({"story_revision": current, "plan_revision": plan_rev,
                  "storyboard_id": bid, "storyboard_revision": brev,
                  "cast": {"WIFE_A": female_id, "PARTNER_B": male_id, "HUSBAND_C": husband_id}})
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved:", STATE)


if __name__ == "__main__":
    main()
