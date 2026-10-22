"""Small shared helpers for act/shot generators.

Keep generator-specific storytelling in its config; keep pose, caption,
expression and phase rules here so every generator applies the same minimum.
"""
import re
from novel2anima.catalog.tag_roles import BODY_STATE_TAGS

LOOKING = {"looking_around", "looking_back", "looking_at_viewer", "looking_down",
           "looking_up", "looking_away", "looking_to_the_side"}

BODY_TAGS = set(BODY_STATE_TAGS)

POSE_FOR_ACTION = {
    "sitting": "sitting", "sitting_on_desk": "sitting", "sitting_on_ground": "sitting",
    "sitting_on_chair": "sitting", "kneeling": "kneeling", "crouching": "crouching",
    "lying": "lying", "lying_on_back": "lying", "lying_on_stomach": "lying",
    "spread_legs": "sitting", "fingering": "sitting", "masturbation": "sitting",
    "spread_pussy": "sitting", "presenting": "sitting", "presenting_pussy": "sitting",
    "clitoral_stimulation": "sitting", "object_insertion": "sitting",
    "vibrator": "sitting", "dildo": "sitting", "touching_self": "sitting",
    "missionary": "lying", "legs_up": "lying", "prone_bone": "lying",
    "mating_press": "lying", "cunnilingus": "lying", "spooning": "lying",
    "cowgirl_position": "sitting", "reverse_cowgirl_position": "sitting",
    "upright_straddle": "sitting", "full_nelson": "sitting", "lotus_position": "sitting",
    "doggystyle": "kneeling", "bent_over": "standing", "sex": "lying",
    "standing_sex": "standing", "against_wall": "standing", "leg_lift": "standing",
    "fellatio": "kneeling", "deepthroat": "kneeling", "paizuri": "kneeling",
    "orgasm": "lying", "female_ejaculation": "lying", "afterglow": "sitting",
}

PHRASES = {
    "walking": "walks", "running": "runs", "jogging": "jogs", "sprinting": "sprints",
    "standing": "stands", "sitting": "sits down", "sitting_on_desk": "sits on the desk",
    "sitting_on_ground": "sits on the ground", "kneeling": "kneels",
    "crouching": "crouches", "lying": "lies down", "lying_down": "lies down",
    "stand_up": "stands up", "getting_up": "gets up", "touching_self": "touches herself",
    "fingering": "fingers herself", "masturbation": "masturbates",
    "spread_pussy": "spreads herself open", "presenting": "presents herself",
    "presenting_pussy": "presents her pussy", "clitoral_stimulation": "stimulates herself",
    "object_insertion": "inserts the toy", "vibrator": "uses the vibrator",
    "dildo": "uses the dildo", "orgasm": "climaxes", "female_ejaculation": "squirts",
    "afterglow": "catches her breath", "undressing": "undresses",
    "clothes_pull": "pulls at her clothes", "shirt_lift": "lifts her shirt",
    "skirt_lift": "lifts her skirt", "open_shirt": "opens her shirt",
    "skirt_aside": "pulls her skirt aside", "looking_around": "looks around",
    "looking_back": "looks back", "looking_at_viewer": "looks at the viewer",
    "adjusting_clothes": "adjusts her clothes", "hands_on_hips": "puts her hands on her hips",
    "head_tilt": "tilts her head", "hand_in_hair": "runs a hand through her hair",
    "holding_gun": "holds the gun", "aiming": "aims", "shooting": "shoots",
    "reloading": "reloads", "jumping": "jumps", "spinning": "spins",
    "dancing": "dances", "singing": "sings", "holding_microphone": "holds the microphone",
    "posing": "poses", "bowing": "bows", "waving": "waves", "stretching": "stretches",
    "stretching_arms": "stretches her arms", "stretching_legs": "stretches her legs",
    "walking_away": "walks away", "closing_door": "closes the door",
    "earpiece": "touches her earpiece", "door": "pushes the door",
    "holding_baton": "holds the baton", "picking_up": "picks up the baton",
    "reaching_out": "reaches out", "wiping_sweat": "wipes sweat from her face",
    "drinking_water": "drinks water", "hands_on_knees": "rests her hands on her knees",
}


def pose_for(action, explicit=None):
    implied = POSE_FOR_ACTION.get(str(action))
    if explicit and not (explicit == "standing" and implied and implied != "standing"):
        return explicit
    return implied or "standing"


def describe(action):
    action = str(action)
    return PHRASES.get(action, "performs %s" % action.replace("_", " "))


def caption(name, action, note=""):
    line = "%s %s." % (name, describe(action))
    note = str(note or "").strip()
    if note and note.lower().rstrip(".") not in line.lower():
        line += " " + note
    return line


def clean_expression(expression, actions):
    out = list(expression or [])
    if set(actions or []) & LOOKING:
        out = [x for x in out if x != "closed_eyes"]
    return out


PROP_WORDS = ("door", "earpiece", "gun", "rifle", "knife", "microphone",
              "baton", "vibrator", "dildo", "leash")

def props_for(caption):
    text = str(caption or "").lower()
    return [t for t in PROP_WORDS if re.search(r"\b%s\b" % re.escape(t), text)]

def split_garments(tags):
    outfit, body = [], []
    for tag in tags or []:
        (body if tag in BODY_TAGS else outfit).append(tag)
    return list(dict.fromkeys(outfit)), list(dict.fromkeys(body))


def phase_contract(phases):
    """phases: iterable of (id, count, wardrobe, allow_sensitive)."""
    out, shot = [], 1
    for phase_id, count, wardrobe, allow_sensitive in phases:
        out.append({"id": phase_id, "start": shot, "end": shot + count - 1,
                    "wardrobe": wardrobe, "allow_sensitive": bool(allow_sensitive)})
        shot += count
    return out


def background_for(phase, stage_line, backstage_line):
    if str(phase) in {"back", "backstage", "after", "afterglow", "rest", "cooldown"}:
        return backstage_line
    return stage_line
