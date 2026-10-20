import argparse, json, pathlib, sqlite3

import pathlib as _p, sys as _s
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[1]))
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[2] / "etl"))
OUT_DIR = pathlib.Path("data/plans")
DRY_RUN = False

def plan_path(name):
    return OUT_DIR / name

import act_quality as aq

DB = "db/novel_anima.db"
PH = ["arrival", "undress", "foreplay", "position_a", "position_b", "climax", "afterglow"]
BASE = ["white_bikini", "micro_bikini", "string_bikini", "side-tie_bikini",
        "underboob", "sideboob", "cleavage", "midriff", "navel"]
BG = "indoors, library, bookshelf, night, moonlight, window, dust"
MALE_LINE = "1boy, faceless_male, topless_male, black_pants, muscular_male"
MALE_ATTRS = ["faceless_male", "topless_male", "black_pants", "muscular_male"]

ACTS = [
 dict(no=35, slug="azusa", name="Azusa", tag="azusa_(swimsuit)_(blue_archive)",
  attrs=["white_hair", "very_long_hair", "hair_between_eyes", "crossed_bangs", "ahoge",
         "purple_eyes", "halo", "white_wings", "angel_wings", "feathered_wings",
         "hair_flower", "small_breasts"],
  title="Azusa - Giao keo dem (Trinity)",
  idea=("Adult AU: Azusa stays behind in the old Trinity library in an identical white micro string bikini. "
        "Disciplined control breaks under a faceless adult partner: kneeling oral, missionary with legs up, "
        "prone bone, mating press, creampie, afterglow."),
  style="with rigid discipline",
  actions="""walking looking_around closing_door standing hands_on_hips head_tilt hand_in_hair adjusting_clothes
undressing bikini_pull one_breast_out nipple_slip bikini_aside spread_legs sitting fingering
kneeling fellatio deepthroat paizuri kiss breast_sucking cunnilingus fingering kiss neck_kiss
missionary missionary legs_up missionary missionary kiss missionary legs_up missionary missionary missionary missionary
prone_bone prone_bone prone_bone prone_bone prone_bone hair_pull hand_on_head prone_bone prone_bone prone_bone prone_bone prone_bone
mating_press mating_press mating_press orgasm cum_in_pussy excessive_cum
after_sex cum_drip sitting looking_back""",
  poses={15:"sitting",16:"sitting",17:"kneeling",18:"kneeling",19:"kneeling",20:"kneeling",
         21:"kneeling",22:"kneeling",23:"kneeling",24:"sitting",25:"sitting",26:"sitting",
         27:"lying",39:"on_stomach",51:"lying",54:"lying",55:"lying",56:"lying",
         57:"sitting",58:"sitting",59:"sitting"}),
 dict(no=36, slug="hifumi", name="Hifumi", tag="hifumi_(swimsuit)_(blue_archive)",
  attrs=["light_brown_hair", "long_hair", "twintails", "low_twintails", "yellow_eyes",
         "halo", "small_breasts"],
  title="Hifumi - Gio hoc dem (Trinity)",
  idea=("Adult AU: Hifumi sneaks into the old Trinity library in an identical white micro string bikini. "
        "Cheerful teasing turns shameless with a faceless adult partner: standing sex against the shelves, "
        "leg lift, cowgirl, reverse cowgirl, creampie, afterglow."),
  style="with bright shamelessness",
  actions="""walking waving closing_door stretching hands_on_hips head_tilt adjusting_clothes hand_in_hair
undressing bikini_pull one_breast_out nipple_slip bikini_aside spread_legs sitting_on_desk fingering
standing kiss neck_kiss breast_sucking fellatio deepthroat paizuri breast_sucking cunnilingus fingering
standing_sex against_wall standing_sex standing_sex kiss standing_sex leg_lift standing_sex standing_sex against_wall standing_sex standing_sex
cowgirl_position cowgirl_position reverse_cowgirl_position cowgirl_position cowgirl_position breast_sucking cowgirl_position upright_straddle cowgirl_position reverse_cowgirl_position cowgirl_position cowgirl_position
reverse_cowgirl_position cowgirl_position cowgirl_position orgasm cum_in_pussy excessive_cum
after_sex cum_drip sitting_on_desk looking_back""",
  poses={15:"sitting",16:"sitting",21:"kneeling",22:"kneeling",23:"kneeling",24:"kneeling",
         25:"kneeling",26:"kneeling",39:"kneeling",40:"kneeling",41:"kneeling",42:"kneeling",
         43:"kneeling",44:"kneeling",45:"kneeling",46:"standing",47:"kneeling",48:"kneeling",
         49:"kneeling",50:"kneeling",51:"kneeling",52:"kneeling",53:"kneeling",54:"sitting",
         55:"sitting",56:"sitting",57:"sitting",58:"sitting",59:"sitting"}),
 dict(no=37, slug="koharu", name="Koharu", tag="koharu_(swimsuit)_(blue_archive)",
  attrs=["pink_hair", "long_hair", "twintails", "low_twintails", "bangs", "pink_eyes",
         "halo", "black_wings", "low_wings", "feathered_wings", "small_breasts"],
  title="Koharu - Mat na dem (Trinity)",
  idea=("Adult AU: Koharu is caught after curfew in the old Trinity library, wearing an identical white micro string bikini. "
        "Panic melts into need with a faceless adult partner: kneeling oral, missionary, full nelson, "
        "mating press, overwhelmed orgasm, creampie, afterglow."),
  style="while panicking and melting",
  actions="""walking looking_around closing_door hands_on_hips head_tilt adjusting_clothes hand_in_hair standing
undressing bikini_pull one_breast_out nipple_slip bikini_aside spread_legs sitting fingering
kneeling fellatio deepthroat paizuri breast_sucking kiss breast_sucking cunnilingus fingering neck_kiss
missionary missionary legs_up missionary kiss missionary missionary missionary spread_legs missionary missionary missionary
full_nelson full_nelson full_nelson full_nelson full_nelson full_nelson full_nelson full_nelson full_nelson full_nelson full_nelson full_nelson
mating_press mating_press mating_press orgasm cum_in_pussy excessive_cum
after_sex cum_drip sitting looking_back""",
  poses={15:"sitting",16:"sitting",17:"kneeling",18:"kneeling",19:"kneeling",20:"kneeling",
         21:"kneeling",22:"kneeling",23:"kneeling",24:"sitting",25:"sitting",26:"sitting",
         27:"lying",39:"lying",40:"lying",41:"lying",42:"lying",43:"lying",44:"lying",
         45:"lying",46:"lying",47:"lying",48:"lying",49:"lying",50:"lying",51:"lying",
         52:"lying",53:"lying",54:"lying",55:"lying",56:"lying",57:"sitting",58:"sitting",
         59:"sitting"}),
 dict(no=38, slug="ui", name="Ui", tag="ui_(swimsuit)_(blue_archive)",
  attrs=["black_hair", "very_long_hair", "ponytail", "purple_hairband", "hair_between_eyes",
         "purple_eyes", "bags_under_eyes", "halo", "small_breasts"],
  title="Ui - Trang sach dem (Trinity)",
  idea=("Adult AU: Ui stays late cataloguing in the old Trinity library, wearing an identical white micro string bikini. "
        "Sleepy indifference turns hungry with a faceless adult partner: oral, bent over the desk, doggystyle, "
        "spooning, lotus, creampie, afterglow."),
  style="with sleepy hunger",
  actions="""walking holding_book sitting_on_desk adjusting_clothes head_tilt hand_in_hair hands_on_hips standing
undressing bikini_pull one_breast_out nipple_slip bikini_aside spread_legs sitting_on_desk fingering
standing kiss neck_kiss breast_sucking fellatio deepthroat paizuri breast_sucking cunnilingus fingering
doggystyle doggystyle bent_over doggystyle doggystyle hair_pull doggystyle doggystyle doggystyle doggystyle doggystyle doggystyle
spooning spooning spooning leg_lift spooning spooning spooning spooning spooning spooning spooning spooning
lotus_position lotus_position lotus_position orgasm cum_in_pussy excessive_cum
after_sex cum_drip sitting_on_desk looking_back""",
  poses={3:"sitting",4:"sitting",5:"sitting",6:"sitting",7:"sitting",15:"sitting",16:"sitting",
         21:"kneeling",22:"kneeling",23:"kneeling",24:"kneeling",25:"kneeling",26:"kneeling",
         39:"lying",40:"lying",41:"lying",42:"lying",43:"lying",44:"lying",45:"lying",
         46:"lying",47:"lying",48:"lying",49:"lying",50:"lying",51:"sitting",52:"sitting",
         53:"sitting",54:"sitting",55:"sitting",56:"sitting",57:"sitting",58:"sitting",
         59:"sitting"}),
 dict(no=39, slug="seia", name="Seia", tag="seia_(blue_archive)",
  attrs=["blonde_hair", "very_long_hair", "long_hair", "fox_ears", "fox_tail",
         "animal_ear_fluff", "yellow_eyes", "parted_bangs", "halo", "hair_flower",
         "small_breasts"],
  title="Seia - Tra dem (Trinity)",
  idea=("Adult AU: Seia waits alone in the old Trinity library in an identical white micro string bikini. "
        "Serene prophecy turns greedy with a faceless adult partner: standing sex against the wall, leg lift, "
        "suspended congress, upright straddle, cowgirl, creampie, afterglow."),
  style="with serene greed",
  actions="""walking looking_around closing_door hands_on_hips head_tilt adjusting_clothes hand_in_hair standing
undressing bikini_pull one_breast_out nipple_slip bikini_aside spread_legs sitting fingering
standing kiss neck_kiss breast_sucking fellatio deepthroat paizuri breast_sucking cunnilingus fingering
against_wall standing_sex standing_sex standing_sex leg_lift standing_sex standing_sex standing_sex standing_sex standing_sex standing_sex standing_sex
suspended_congress suspended_congress upright_straddle suspended_congress suspended_congress suspended_congress suspended_congress suspended_congress suspended_congress suspended_congress suspended_congress suspended_congress
cowgirl_position cowgirl_position cowgirl_position orgasm cum_in_pussy excessive_cum
after_sex cum_drip sitting looking_back""",
  poses={15:"sitting",16:"sitting",21:"kneeling",22:"kneeling",23:"kneeling",24:"kneeling",
         25:"kneeling",26:"kneeling",39:"standing",40:"standing",41:"sitting",42:"standing",
         43:"standing",44:"standing",45:"standing",46:"standing",47:"standing",48:"standing",
         49:"standing",50:"standing",51:"kneeling",52:"kneeling",53:"kneeling",54:"sitting",
         55:"sitting",56:"sitting",57:"sitting",58:"sitting",59:"sitting"}),
]

EXPR = {
 "arrival": [["smile","looking_at_viewer"],["closed_eyes","smile"],["blush","looking_down"],["determined","half-closed_eyes"]],
 "undress": [["blush","parted_lips"],["biting_lip","half-closed_eyes"],["open_mouth","blush"],["smile","looking_down"]],
 "foreplay": [["half-closed_eyes","open_mouth"],["biting_lip","blush"],["ahegao","tongue_out"],["closed_eyes","parted_lips"]],
 "position_a": [["open_mouth","ahegao"],["biting_lip","half-closed_eyes"],["rolling_eyes","tongue_out"],["blush","parted_lips"]],
 "position_b": [["ahegao","rolling_eyes"],["open_mouth","blush"],["tongue_out","half-closed_eyes"],["biting_lip","parted_lips"]],
 "climax": [["ahegao","rolling_eyes","tongue_out"],["open_mouth","arched_back"],["half-closed_eyes","blush"]],
 "afterglow": [["exhausted","smile"],["half-closed_eyes","blush"],["closed_eyes","smile"]],
}
CAM = [["full_body"],["cowboy_shot"],["upper_body"],["from_side"],["from_below"],["from_above"],["pov"],["close-up"]]
MOT = [["sweat","motion_blur"],["trembling","emphasis_lines"],["flying_sweatdrops"],["steam"]]
NOTES = {
 "arrival": ["Moonlight catches the white strings.","She listens for footsteps.","The empty shelves swallow the sound.","Her halo glows faintly."],
 "undress": ["Water-dark fabric turns transparent.","A string slips off her shoulder.","The bikini clings to every curve.","Her nipples print through the wet white."],
 "foreplay": ["The faceless man pulls the string aside.","Her thighs shine with wetness.","She takes him deep, eyes watering.","His mouth works between her legs."],
 "position_a": ["He pushes in slow and deep.","Her breasts bounce with each thrust.","The shelf edge digs into her back.","She clenches around him."],
 "position_b": ["The angle makes her cry out.","Her hips meet every stroke.","She is bent nearly double.","Her toes curl off the floor."],
 "climax": ["She comes hard around him.","His cum floods her and drips out.","She shakes through the last wave."],
 "afterglow": ["Cum runs down her thigh.","She catches her breath on the floor.","The white bikini hangs loose around her."],
}

def phase(n):
    if n <= 8: return "arrival"
    if n <= 16: return "undress"
    if n <= 26: return "foreplay"
    if n <= 38: return "position_a"
    if n <= 50: return "position_b"
    if n <= 56: return "climax"
    return "afterglow"

def outfit(n):
    o = list(BASE)
    if n >= 9: o += ["wet_clothes","see-through","nipples_visible_through_clothing","nipple_outline"]
    if 17 <= n <= 26: o += ["one_breast_out","bikini_aside"]
    if n >= 27: o = []
    if 33 <= n <= 50: o += ["bikini_around_one_leg"]
    if n >= 57: o = BASE + ["bikini_pull","one_breast_out"]
    return list(dict.fromkeys(o))

def body_state(n):
    b = []
    if n >= 17: b += ["nipples","pussy","pussy_juice"]
    if n >= 27: b += ["topless","bottomless"]
    if 51 <= n <= 56: b += ["completely_nude"]
    if n >= 55: b += ["cum_drip"]
    if n >= 57: b += ["afterglow"]
    return list(dict.fromkeys(b))

def state(n):
    if n == 0: return "dry white micro string bikini, clean skin"
    if n <= 8: return "white micro string bikini, dry, clean skin"
    if n <= 16: return "bikini soaked see-through, nipples visible, sweat sheen"
    if n <= 26: return "bikini pulled aside, breasts out, pussy exposed, wet fingers"
    if n <= 38: return "topless, bottomless, wet with pussy juice, sweat"
    if n <= 50: return "nude, soaked, trembling, pussy juice dripping"
    if n <= 53: return "nude, flushed, on the edge"
    if n <= 56: return "nude, orgasm, cum dripping from pussy"
    return "bikini pulled loose, afterglow, cum on thighs"

def cast(n):
    o = ["small_breasts","slim","pale_skin","thighs"]
    if n >= 9: o += ["sweat","shiny_skin","sweatdrop","wet_hair"]
    if n >= 14: o += ["pussy_juice","blush"]
    if n >= 20: o += ["pussy_juice_drip"]
    if n >= 27: o += ["sex","vaginal","penis","hetero","1boy","faceless_male","topless_male"]
    if n >= 48: o += ["trembling"]
    if n in (54,55,56): o += ["orgasm","female_ejaculation","ahegao"]
    if n >= 55: o += ["cum_in_pussy","cum_drip"]
    if n == 56: o += ["excessive_cum","cum_overflow"]
    if n >= 57: o += ["after_sex","afterglow","cum_drip"]
    return list(dict.fromkeys(o))

def male_act(n, primary):
    if n < 17: return []
    if primary in {"standing_sex","against_wall","leg_lift"}: return ["standing"]
    if primary in {"missionary","legs_up","spread_legs","mating_press","full_nelson","prone_bone",
                   "doggystyle","bent_over","spooning","cowgirl_position",
                   "reverse_cowgirl_position","upright_straddle","suspended_congress",
                   "lotus_position"}: return [primary]
    if primary in {"orgasm","cum_in_pussy","excessive_cum","after_sex","cum_drip"}: return ["cum_in_pussy"]
    if n <= 20: return ["standing"]
    if n <= 26: return ["kneeling"]
    return ["standing"]

def build(a):
    acts = a["actions"].split()
    assert len(acts) == 60, (a["slug"], len(acts))
    shots, prev = [], None
    for n, primary in enumerate(acts, 1):
        ph = phase(n)
        pose = aq.pose_for(primary, a["poses"].get(n))
        expr = aq.clean_expression(EXPR[ph][(n-1) % len(EXPR[ph])], [primary])
        cam = CAM[(n*3) % len(CAM)]
        mot = MOT[(n*5) % len(MOT)]
        duo = n >= 17
        ma = male_act(n, primary)
        seq = {"purpose": "setup" if n <= 8 else ("transition" if n == 17 else
                ("result" if n >= 51 else "action")),
               "actor": "GIRL", "primaryAction": primary, "eventId": "%s:%d" % (ph, n)}
        if prev: seq["poseBefore"] = prev
        seq["poseAfter"] = pose
        prev = pose
        note = NOTES[ph][(n-1) % len(NOTES[ph])]
        cap = aq.caption(a["name"], primary, note)
        shot = {"n": n, "phase": ph, "beat": "%s: %s" % (ph, cap), "purpose": seq["purpose"],
                "outfit": outfit(n), "body_state": body_state(n),
                "props": aq.props_for(cap),
                "action": [primary] + [t for t in ma if t != primary],
                "expression": expr, "pose": [pose], "camera": cam, "motion": mot,
                "cast": cast(n), "caption": cap, "carry": state(n-1),
                "delta": "action: %s; state: %s" % (primary, state(n)),
                "sequence": seq, "participants": ["GIRL","MALE"] if duo else ["GIRL"],
                "character_actions": {"GIRL": [primary], "MALE": ma} if duo and ma else {},
                "character_poses": {"GIRL": [pose]} if duo else {},
                "background_line": BG,
                "scene": {"location": "old Trinity library", "tags": BG.split(", ")}}
        shots.append(shot)
    return {
      "project": {"title": a["title"] + " [bikini]", "idea": a["idea"], "content_profile": "nsfw",
        "style_json": {"style": "anime, danbooru tags + short natural caption",
          "background": "old Trinity library at night", "aspect": "1:1",
          "render": "Anima Base 2B + anima-turbo-4step v3, 4 steps, CFG 1, er_sde"}},
      "quality_line": "masterpiece, best quality, anime style",
      "safety_tag": "explicit", "background_line": BG, "nl": False,
      "characters": [
        {"code": "GIRL", "name": a["name"], "gender": "girl",
         "identity_line": "1girl, solo, %s, blue_archive, %s" % (a["tag"], ", ".join(a["attrs"])),
         "identity_json": {"identity_tags": [a["tag"], "blue_archive"],
           "attributes": a["attrs"] + ["1girl"], "adult": True,
           "adult_note": "Adult AU default.",
           "note": "%s (Blue Archive, Trinity), adult AU." % a["name"]},
         "outfit_json": {"default": BASE, "wet": outfit(17), "nude": []}},
        {"code": "MALE", "name": "faceless adult male", "gender": "boy",
         "identity_line": MALE_LINE,
         "identity_json": {"identity_tags": ["faceless_male"], "attributes": MALE_ATTRS,
           "adult": True, "adult_note": "Adult AU default."},
         "outfit_json": {"default": ["topless_male","black_pants"]}}],
      "act": {"act_no": 1, "title": a["title"] + " [bikini]",
        "outline": "arrival 1-8 -> undress 9-16 -> foreplay 17-26 -> position A 27-38 -> position B 39-50 -> climax 51-56 -> afterglow 57-60.",
        "revision": 1, "status": "planned",
        "phase_contract": aq.phase_contract([
          ("arrival", 8, "dressed", False), ("undress", 8, "undress", True),
          ("foreplay", 10, "undress", True), ("position_a", 12, "undress", True),
          ("position_b", 12, "undress", True), ("climax", 6, "nude", True),
          ("afterglow", 4, "afterglow", False)])},
      "prompt_file": "prompts/act%d_%s_bikini_60.txt" % (a["no"], a["slug"]),
      "shots": shots}

def check(p):
    names = set()
    for ch in p["characters"]:
        names.update(ch["identity_json"].get("identity_tags", []))
        names.update(ch["identity_json"].get("attributes", []))
        for refs in ch["outfit_json"].values(): names.update(refs)
    for s in p["shots"]:
        for k in ("outfit","action","expression","pose","camera","motion","cast"): names.update(s.get(k, []))
    names.update(p["background_line"].split(", "))
    con = sqlite3.connect(DB)
    miss = [n for n in sorted(names) if not con.execute("select 1 from tag where canonical_name=?", (n,)).fetchone()]
    con.close()
    return miss

def md(a, p):
    if DRY_RUN:
        return
    out = plan_path("act%d_%s_bikini_60.md" % (a["no"], a["slug"]))
    lines = ["# " + p["project"]["title"], "",
      "- Plan: `data/plans/act%d_%s_bikini_60.json`" % (a["no"], a["slug"]),
      "- Prompt: `%s`" % p["prompt_file"], "- So shot: **60**",
      "- Nhan vat: **%s** (`%s`), adult AU" % (a["name"], a["tag"]),
      "- Trang phuc: `white_bikini`, `micro_bikini`, `string_bikini`, `side-tie_bikini`",
      "- Boi canh: `library`, `bookshelf`, `night`, `moonlight`", "", "## Logline", "",
      a["idea"], "", "## Nhip", "", "| Phase | Shots | Count |", "|---|---:|---:|",
      "| Arrival | 1-8 | 8 |", "| Undress | 9-16 | 8 |", "| Foreplay | 17-26 | 10 |",
      "| Position A | 27-38 | 12 |", "| Position B | 39-50 | 12 |",
      "| Climax | 51-56 | 6 |", "| Afterglow | 57-60 | 4 |", "",
      "## Shots", "", "| # | Phase | Pose | Action | Expression | Caption |",
      "|---:|---|---|---|---|---|"]
    for s in p["shots"]:
        lines.append("| %d | %s | %s | %s | %s | %s |" % (s["n"], s["phase"], ", ".join(s["pose"]),
            ", ".join(s["action"]), ", ".join(s["expression"]), s["caption"]))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--output")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    global OUT_DIR, DRY_RUN
    if args.output:
        OUT_DIR = pathlib.Path(args.output)
    DRY_RUN = args.dry_run
    for a in ACTS:
        p = build(a)
        miss = check(p)
        if miss:
            raise SystemExit("act%d missing tags: %s" % (a["no"], miss))
        out = plan_path("act%d_%s_bikini_60.json" % (a["no"], a["slug"]))
        if not DRY_RUN:
            out.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
            md(a, p)
        print(("would write " if DRY_RUN else "wrote ") + "%s (%d shots)" % (out, len(p["shots"])))

if __name__ == "__main__":
    main()
