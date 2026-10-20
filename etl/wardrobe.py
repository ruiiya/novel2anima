# novel2anima P0P1 upgrade
# -*- coding: utf-8 -*-
"""Quy tac dien anh ap cho MOI plan - khong con bang mau hard-code, du lieu nam trong catalog.

Usage (tu seed_plan):
    import wardrobe
    table = wardrobe.colour_table(con)          # doc WC_* concept -> {tag_id: {...}}
    refs  = wardrobe.colorize(refs, table)      # them bien the mau cho tung mon do
    refs  = wardrobe.under_fix(refs, table)     # set den -> noi y den
    wardrobe.lock_poses(parsed, id_of)          # thang tu the dung -> quy -> ngoi -> nam

Bang mau lay tu visual_concept code WC_<do> (+ concept_tag): etl/import_colour_sets.py nap tu
catalog (bien the <mau>_<do> that) va tu cac act da seed (mau dang dung), cue <mau>_clothing cho
do khong co bien the mau (data/wardrobe/colour_cue.json - bo mau chuan bi cho phase 1).
"""
import json

UNDER_NAMES = {"bra", "underwear", "panties", "pasties", "crotchless_panties"}

def colour_of(name):
    for c in ("white", "black", "blue", "red", "pink", "grey", "gray", "brown", "silver",
              "blonde", "purple", "green", "yellow", "orange", "tan"):
        if name.startswith(c + "_"):
            return c, name[len(c) + 1:]
    return None, None

def colour_table(con):
    """{tag_id: {"base": ten do, "chosen": (ten, id)|None, "cue": (ten, id)|None,
                 "options": {mau: (ten, id)}}} - key gom ca tag do goc lan bien the mau."""
    rows = con.execute(
        "SELECT ct.tag_id, ct.usage, ct.priority, t.canonical_name, c.code, c.metadata_json"
        " FROM visual_concept c JOIN concept_tag ct ON ct.concept_id=c.id"
        " JOIN tag t ON t.id=ct.tag_id WHERE c.code LIKE 'WC%'").fetchall()
    groups = {}
    for tag_id, usage, prio, name, code, meta in rows:
        e = groups.setdefault(code, {"base": None, "options": {}, "cue_tag": None, "pick": None})
        if usage == "primary":
            e["base"] = (name, tag_id)
        elif name.endswith("_clothing"):           # cue mau chung (<mau>_clothing), khong phai bien the
            e["cue_tag"] = (name, tag_id)
        else:
            c, _b = colour_of(name)
            if c:
                e["options"][c] = (name, tag_id)
                if prio == 1:                     # priority 1 = mau dang dung cho mon do nay
                    e["pick"] = c
    table = {}
    for code, e in groups.items():
        if not e["base"]:
            continue
        base_name, base_id = e["base"]
        chosen = e["options"].get(e["pick"]) if e["pick"] else None
        entry = {"base": base_name, "options": e["options"], "cue": e["cue_tag"],
                 "chosen": chosen, "base_id": base_id}
        table[base_id] = entry
        for c_name, c_id in e["options"].values():
            table[c_id] = entry          # bien the mau tro ve cung mot mon do
    return table

def colour_pick(entry, wanted):
    """mau muon dung (mau dang dung -> mau theo bo -> cue)"""
    if wanted and wanted in entry["options"]:
        return entry["options"][wanted]
    return entry["chosen"] or (entry["base"], entry["base_id"])

def dominant(refs, table):
    """mau cua ca bo: >=2 mon mot mau thi lay mau do (dung cho cue chung va noi y)"""
    score = 0
    for name, tid in refs:
        e = table.get(tid)
        c, _b = colour_of(name)
        if not c and e and e["chosen"]:
            c, _b = colour_of(e["chosen"][0])
        score += 1 if c == "black" else (-1 if c in ("white", "grey", "gray", "silver") else 0)
    if score >= 2:
        return "black"
    return "white" if score <= -2 else None

def colorize(refs, table, under=None, wanted=None):
    """moi mon do -> bien the mau.

    Priority: explicit shot/act colour (`wanted`) > wardrobe preset/catalog pick >
    cue <mau>_clothing. `wanted` maps item name ("panties") or full tag to a colour.
    """
    out = []
    for name, tid in refs:
        e = table.get(tid)
        if not e:
            out.append((name, tid))
            continue
        if tid != e["base_id"]:                     # da la bien the mau roi
            out.append((name, tid))
            continue
        c, _b = colour_of(name)
        if c:
            out.append((name, tid))
            continue
        want = (wanted or {}).get(name) or (wanted or {}).get(e["base"])
        if want is None and under and name in UNDER_NAMES:
            want = under
        pick = colour_pick(e, want)
        out.append(pick)
        if pick == (e["base"], e["base_id"]) and e["cue"]:
            out.append(e["cue"])
    return list(dict.fromkeys(out))

def under_fix(refs, table, explicit=None):
    """Heuristic only: uncoloured underwear follows the set colour.

    An explicit colour (shot/act), a wardrobe preset or catalog pick always wins, so
    `white_panties` in a black outfit is kept as authored.
    """
    explicit = explicit or set()
    dom = dominant(refs, table)
    if not dom:
        return refs
    out = []
    for name, tid in refs:
        e = table.get(tid)
        decided = e and (colour_of(name)[0] or e.get("chosen") or e["base"] in explicit)
        if e and not decided and e["base"] in UNDER_NAMES and dom in e["options"] \
                and (name, tid) != e["options"][dom]:
            out.append(e["options"][dom])
        else:
            out.append((name, tid))
    return list(dict.fromkeys(out))

STANCE_ORDER = {"standing": 0, "squatting": 1, "crouching": 1, "kneeling": 1,
                "sitting": 2, "sitting_on_chair": 2, "sitting_on_desk": 2,
                "lying": 3, "lying_on_back": 3}
LADDER = {0: "standing", 1: "kneeling", 2: "sitting", 3: "lying"}
NEUTRAL_POSE = {"bending_over", "legs_up", "knees_up", "spread_legs", "hugging_legs",
                "all_fours", "on_stomach", "top-down_bottom-up"}

def lock_poses(parsed, id_of):
    """DEPRECATED read-only compatibility checker. Never mutate actions or poses.

    Previous implementation applied an irreversible standing->lying ladder and
    silently removed action tags. Return only warnings for contradictory stances
    in the SAME frame. Consecutive posture changes are valid narrative events.
    """
    changes = []
    for shot, p in parsed:
        ranked = {n for n, _ in p.get("pose", []) if n in STANCE_ORDER}
        if len({STANCE_ORDER[n] for n in ranked}) > 1:
            changes.append((shot["n"], p.get("phase", ""), ",".join(sorted(ranked)),
                            "multiple conflicting stances; review manually"))
    return changes
