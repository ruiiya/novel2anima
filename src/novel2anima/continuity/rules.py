"""Continuity inference policy v0.4 (single source).

Provenance: extracted verbatim from infer_state v0.3, a hypothesis for
adult-shot continuity. Rules are policy, not taxonomy: change them here, bump
RULES_VERSION, and keep `python -m novel2anima.continuity.inference` in report mode until reviewed.

The algorithm stays deterministic Python; only the data lives in this module so
`infer_state.py` cannot drift from tests or other consumers.
"""
RULES_VERSION = "v0.4"

GENITAL = {"pussy_juice", "pussy_juice_trail", "pussy_juice_drip", "pussy_juice_stain",
           "pussy_juice_puddle", "pussy_juice_on_fingers", "fingering", "masturbation",
           "cunnilingus", "tribadism", "double_dildo", "strap-on", "mating_press", "missionary",
           "doggystyle", "cowgirl_position", "upright_straddle", "standing_sex", "prone_bone", "spooning",
           "sex", "vaginal", "sex_from_behind", "penis_grab", "fellatio"}
FINGERS = {"fingering", "masturbation", "pussy_juice_on_fingers"}
STRONG = {"orgasm", "female_ejaculation", "ahegao", "mating_press", "torogao", "rolling_eyes"}
EJAC = {"female_ejaculation"}
SWEAT = {"sweat", "heavy_breathing", "panting", "sweatdrop", "wet_hair"}
SALIVA = {"saliva", "drooling", "pussy_juice_on_fingers"}
KISS = {"french_kiss", "tongue", "cunnilingus"}
BITE = {"biting", "bite_mark", "bite_mark_on_shoulder", "bite_mark_on_neck"}
SCRATCH = {"scratching", "clawing", "scratches"}
TREMBLE = {"trembling", "shaking"}
ROPE = {"rope", "crotch_rope", "chain", "chain_leash", "leash", "shackles", "handcuffs", "bondage"}
OWNERSHIP = {"body_writing", "slave_tattoo"}
SEMEN = {"cum_in_pussy", "cum_overflow", "cum_pool", "cumdrip", "cum_in_womb", "cum_on_stomach", "cum_in_ass"}
BELLY = {"pregnant", "implied_pregnancy", "stomach_bulge", "big_belly", "pregnancy_mark"}
LACTATION = {"lactation", "projectile_lactation", "milk", "breast_milking", "milking"}
IMPACT = {"stomach_punch", "punching", "slapping", "slap_mark", "kicking", "headlock",
           "pinching_another's_belly", "belly_grab"}
SPANK = {"spanking", "spanked", "spanked_mark", "red_ass", "welts"}
WHIP = {"whip", "whip_marks", "riding_crop", "cattle_prod"}
PIERCED = {"piercing", "nipple_piercing", "nipple_rings", "navel_piercing", "clitoris_piercing",
           "labia_piercing", "labia_ring", "barbell_piercing", "multiple_piercings", "belly_chain"}
TOY = {"sex_toy", "vibrator", "dildo", "double_dildo", "strap-on", "strap_on"}
AFTER = {"after_sex", "afterglow"}

LADDERS = {
    "fluid:vaginal": [(1, "pussy_juice",           lambda n, s: n["genital"] >= 1),
                      (2, "pussy_juice_on_fingers", lambda n, s: n["fingers"] >= 1),
                      (3, "pussy_juice_drip",      lambda n, s: n["genital"] >= 3),
                      (4, "pussy_juice_trail",     lambda n, s: n["strong"] >= 2),
                      (5, "pussy_juice_puddle",    lambda n, s: n["ejac"] >= 1)],
    "fluid:ejaculate": [(1, "female_ejaculation",  lambda n, s: n["ejac"] >= 1)],
    "fluid:saliva": [(1, "saliva",                 lambda n, s: n["saliva"] >= 1),
                     (2, "saliva_trail",           lambda n, s: n["kiss"] >= 1 and n["saliva"] >= 1)],
    "fluid:sweat": [(1, "sweat",                   lambda n, s: n["sweat"] >= 1),
                    (2, "wet_hair",                lambda n, s: n["sweat"] >= 3)],
    "mark:bite": [(1, "bite_mark",                 lambda n, s: n["bite"] >= 1),
                  (2, "bite_mark_on_shoulder",     lambda n, s: n["bite"] >= 1 and s.get("shoulder", 0) >= 1)],
    "mark:scratch": [(1, "scratches",              lambda n, s: n["scratch"] >= 1),
                     (2, "red_skin",               lambda n, s: n["scratch"] >= 2)],
    "mark:rope": [(1, "red_skin",                  lambda n, s: n["rope"] >= 1),
                  (2, "bruise",                    lambda n, s: n["rope"] >= 3)],
    "mark:ownership": [(1, "slave_tattoo",         lambda n, s: n["ownership"] >= 1)],
    "mark:impact": [(1, "slap_mark",               lambda n, s: n["impact"] >= 1),
                    (2, "bruise",                  lambda n, s: n["impact"] >= 2),
                    (3, "bruise_on_stomach",       lambda n, s: n["impact"] >= 5)],
    "mark:spank": [(1, "red_skin",                 lambda n, s: n["spank"] >= 1),
                   (2, "red_ass",                  lambda n, s: n["spank"] >= 2),
                   (3, "welts",                    lambda n, s: n["spank"] >= 6)],
    "mark:whip": [(1, "red_skin",                  lambda n, s: n["whip"] >= 1),
                  (2, "whip_marks",                lambda n, s: n["whip"] >= 2)],
    "mark:piercing": [(1, "nipple_piercing",       lambda n, s: n["pierced"] >= 1),
                      (2, "navel_piercing",        lambda n, s: n["pierced"] >= 3),
                      (3, "belly_chain",           lambda n, s: n["pierced"] >= 6)],
    "fluid:semen": [(1, "cum_in_pussy",            lambda n, s: n["semen"] >= 1),
                    (2, "cum_overflow",            lambda n, s: n["semen"] >= 3),
                    (3, "cum_pool",                lambda n, s: n["semen"] >= 5)],
    "body:pregnancy": [(1, "stomach_bulge",        lambda n, s: n["pregnancy"] >= 1),
                       (2, "pregnant",             lambda n, s: n["pregnancy"] >= 2),
                       (3, "big_belly",            lambda n, s: n["pregnancy"] >= 5)],
    "physiology:lactation": [(1, "lactation",      lambda n, s: n["lactation"] >= 1),
                             (2, "projectile_lactation", lambda n, s: n["lactation"] >= 3)],
    "physiology:flush": [(1, "blush",              lambda n, s: s["blush"] >= 1),
                         (2, "red_skin",           lambda n, s: n["strong"] >= 2)],
    "physiology:nipples": [(1, "nipples",          lambda n, s: s["bare"] >= 1)],
    "physiology:breath": [(1, "heavy_breathing",   lambda n, s: n["sweat"] >= 1),
                          (2, "panting",           lambda n, s: n["genital"] >= 1),
                          (3, "parted_lips",        lambda n, s: n["strong"] >= 1)],
    "hair:mussed": [(1, "messy_hair",              lambda n, s: s["motion"] >= 1),
                    (2, "wet_hair",                lambda n, s: n["sweat"] >= 3)],
    "posture:fatigue": [(1, "trembling",           lambda n, s: n["tremble"] >= 2),
                        (2, "afterglow",           lambda n, s: s["after"] >= 1)],
    "prop:toy": [(1, "sex_toy",                    lambda n, s: n["toy"] >= 1)],
}

# what refreshes a live state, and how fast it fades when the shot does not refresh it
REFRESH = {
    "fluid:vaginal": (GENITAL, 0.05),
    "fluid:ejaculate": (EJAC, 0.05),
    "fluid:saliva": (SALIVA | KISS, 0.12),
    "fluid:sweat": (SWEAT, 0.15),
    "mark:bite": (BITE, 0.03),
    "mark:scratch": (SCRATCH, 0.04),
    "mark:rope": (ROPE, 0.05),
    "mark:ownership": (OWNERSHIP, 0.0),   # a sold lot keeps its number
    "mark:impact": (IMPACT, 0.04),
    "mark:spank": (SPANK, 0.06),
    "mark:whip": (WHIP, 0.03),
    "mark:piercing": (PIERCED, 0.0),   # hardware does not come out
    "fluid:semen": (SEMEN, 0.03),
    "body:pregnancy": (BELLY, 0.0),       # a belly does not go away
    "physiology:lactation": (LACTATION, 0.08),
    "physiology:flush": ({"blush", "red_skin"}, 0.10),
    "physiology:nipples": ({"nipples", "topless", "completely_nude"}, 0.02),
    "physiology:breath": (SWEAT | STRONG, 0.15),
    "hair:mussed": ({"messy_hair", "wet_hair"}, 0.12),
    "posture:fatigue": (TREMBLE | AFTER, 0.08),
    "prop:toy": (TOY, 0.0),          # a dropped toy stays where it was
}

OUTFIT_STAGE = [(0, None, []),
                (1, "undressing", ["open_kimono", "clothes_pull", "undressing", "skirt_lift", "dress_lift",
                                   "strap_slip", "wardrobe_malfunction", "off_shoulder", "unzipped", "bra_pull"]),
                (2, "bottomless", ["topless", "panties", "panties_around_one_leg", "panties_aside", "bottomless"]),
                (3, "completely_nude", ["completely_nude", "nude"])]

def severity_of(level):
    return min(0.9, 0.4 + 0.1 * level)
