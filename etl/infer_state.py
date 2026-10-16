"""Infer experimental continuity state (v0.3) and load shot_state / act_continuity.

v0.3 adds decay: a state that is not refreshed by the current shot loses severity and is
removed when it reaches zero (sweat dries faster than a bite mark). Rules remain a
hypothesis; see skills/novel2anima-shot-pipeline/references/continuity-state.md
"""
import argparse, json, sqlite3, sys

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/novel_anima.db")
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    def tid(name):
        r = cur.execute("SELECT id FROM tag WHERE canonical_name=?", (name,)).fetchone()
        if not r:
            print("missing tag: %s" % name, file=sys.stderr)
            sys.exit(1)
        return r[0]

    ladder_ids = {ax: [(lvl, tid(v), pred) for lvl, v, pred in steps] for ax, steps in LADDERS.items()}
    stage_ids = {lvl: (tid(v) if v else None) for lvl, v, _ in OUTFIT_STAGE}

    cur.execute("DELETE FROM shot_state WHERE source LIKE 'inferred:%'")  # khong xoa qa:*
    cur.execute("DELETE FROM act_continuity")

    acts = cur.execute("SELECT id, act_no FROM act ORDER BY act_no").fetchall()
    rows, removals = 0, 0
    for act_id, act_no in acts:
        shots = cur.execute("SELECT shot_no, shot_spec_json FROM shot WHERE act_id=? ORDER BY shot_no",
                            (act_id,)).fetchall()
        counts = {k: 0 for k in ("genital", "fingers", "strong", "ejac", "sweat", "saliva", "kiss",
                                 "bite", "scratch", "tremble", "toy", "rope", "ownership",
                                 "semen", "pregnancy", "lactation", "impact", "spank", "whip", "pierced")}
        flags = {"blush": 0, "bare": 0, "motion": 0, "after": 0, "shoulder": 0}
        live, stage, opening = {}, 0, set()

        def write(shot_no, axis, vtid, sev, since, cause, source):
            cur.execute("INSERT INTO shot_state(shot_id, axis, value_tag_id, severity, since_shot_no,"
                        " cause_shot_no, source) VALUES((SELECT id FROM shot WHERE act_id=? AND shot_no=?),"
                        "?,?,?,?,?,?)", (act_id, shot_no, axis, vtid, sev, since, cause, source))

        for shot_no, spec_json in shots:
            spec = json.loads(spec_json)
            names = set()
            for g in ("outfit", "action", "expression", "pose", "motion", "camera"):
                names |= {t["name"] for t in spec.get(g, [])}
            caption = (spec.get("caption", "") + " " + spec.get("beat", "")).lower()
            if shot_no == shots[0][0]:
                opening = set(names)
            for key, watch in (("genital", GENITAL), ("fingers", FINGERS), ("strong", STRONG), ("ejac", EJAC),
                               ("sweat", SWEAT), ("saliva", SALIVA), ("kiss", KISS), ("bite", BITE),
                               ("scratch", SCRATCH), ("tremble", TREMBLE), ("toy", TOY),
                               ("rope", ROPE), ("ownership", OWNERSHIP), ("semen", SEMEN),
                               ("pregnancy", BELLY), ("lactation", LACTATION), ("impact", IMPACT),
                               ("spank", SPANK), ("whip", WHIP), ("pierced", PIERCED)):
                if names & watch:
                    counts[key] += 1
            if names & {"blush"}:
                flags["blush"] += 1
            if names & {"nipples", "topless", "completely_nude"}:
                flags["bare"] += 1
            if names & {"messy_hair"}:
                flags["motion"] += 1
            if names & AFTER:
                flags["after"] += 1
            if "shoulder" in caption or "vai" in caption:
                flags["shoulder"] = 1

            for axis, steps in ladder_ids.items():
                level, value = 0, None
                for lvl, vtid, pred in steps:
                    if pred(counts, flags) and lvl > level:
                        level, value = lvl, vtid
                watch, decay = REFRESH[axis]
                refreshed = bool(names & watch)
                if value is None:
                    if axis in live:                       # no longer supported by the beat
                        live[axis][4] -= decay
                    continue
                if axis not in live:
                    live[axis] = [value, level, shot_no, shot_no, severity_of(level)]
                elif level > live[axis][1]:
                    live[axis] = [value, level, live[axis][2], shot_no,
                                  max(live[axis][4], severity_of(level))]
                elif refreshed:
                    live[axis][4] = max(live[axis][4], severity_of(level))
                else:
                    live[axis][4] -= decay

            for lvl, _name, trig in OUTFIT_STAGE:
                if lvl > stage and names & set(trig):
                    stage = lvl
            if "outfit:stage" not in live:
                live["outfit:stage"] = [stage_ids[stage], stage, shot_no, shot_no, 0.5]
            elif live["outfit:stage"][1] != stage:
                live["outfit:stage"] = [stage_ids[stage], stage, live["outfit:stage"][2], shot_no, 0.5]

            if stage < 3 and counts["sweat"] >= 1:
                if "outfit:soaked" not in live:
                    live["outfit:soaked"] = [tid("wet_clothes"), 1, shot_no, shot_no, 0.5]
            elif "outfit:soaked" in live:
                _, _, since, _, sev = live.pop("outfit:soaked")
                write(shot_no, "outfit:soaked", None, 0.0, since, shot_no, "inferred:v0.3:removed")
                removals += 1

            for axis in sorted(live):
                vtid, lvl, since, cause, sev = live[axis]
                if axis.startswith("outfit:"):
                    write(shot_no, axis, vtid, sev, since, cause, "inferred:v0.3")
                    rows += 1
                    continue
                if sev <= 1e-9:      # float drift: 0.6 - 0.12*5 is not exactly 0
                    write(shot_no, axis, None, 0.0, since, shot_no, "inferred:v0.3:decayed")
                    del live[axis]
                    removals += 1
                    continue
                write(shot_no, axis, vtid, round(sev, 3), since, cause, "inferred:v0.3")
                rows += 1

        props = sorted(opening & {"choker", "rope", "crotch_rope", "shackles", "handcuffs", "chain_leash",
                                  "leash", "blindfold", "slave_tattoo", "body_writing", "pregnancy_mark"})
        body = sorted((opening & BELLY) | (opening & {"nipples"}))
        fluids = sorted((opening & SEMEN) | (opening & {"saliva", "sweat", "pussy_juice", "female_ejaculation"}))
        for axis, note in (("fluid", "opening frame already shows: " + ", ".join(fluids) if fluids
                            else "act starts clean: no fluids"),
                           ("mark", "opening frame already carries: " + ", ".join(props) if props
                            else "act starts clean: no marks"),
                           ("outfit", "opening frame: " + ", ".join(sorted(set(props) | set(body))) if props or body
                            else "act starts fully dressed"),
                           ("environment", "white background, no set state tracked yet")):
            cur.execute("INSERT INTO act_continuity(act_id, axis, initial_tag_id, notes) VALUES(?,?,NULL,?)",
                        (act_id, axis, note))
    con.commit()
    print("shot_state rows: %d | removals (decay/end of state): %d | acts: %d" % (rows, removals, len(acts)))
    con.close()

if __name__ == "__main__":
    main()
