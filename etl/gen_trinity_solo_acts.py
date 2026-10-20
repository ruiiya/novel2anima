import json, pathlib, sqlite3

import act_quality as aq

DB = "db/novel_anima.db"
BASE = ["school_uniform", "white_shirt", "cropped_shirt", "black_blazer",
        "black_skirt", "black_pleated_skirt", "underboob", "sideboob",
        "cleavage", "midriff", "bare_stomach", "navel", "no_bra",
        "no_panties", "black_thighhighs"]
BG = "indoors, library, bookshelf, night, moonlight, window, dust"

ACTS = [
  dict(no=35, slug="azusa", name="Azusa", tag="azusa_(blue_archive)",
  attrs=["white_hair","very_long_hair","hair_between_eyes","crossed_bangs","ahoge",
         "purple_eyes","halo","white_wings","angel_wings","feathered_wings",
         "hair_flower","small_breasts"],
  title="Azusa - Giao keo dem (Trinity)",
  idea=("Adult AU solo: Azusa stays behind in the old Trinity library in a cut Trinity uniform, no bra, no panties. "
        "Discipline breaks into fingering, spread pussy, vibrator and dildo play, orgasm, afterglow. No sex."),
  style="with rigid discipline",
  actions="""walking looking_around closing_door standing hands_on_hips head_tilt hand_in_hair adjusting_clothes
undressing clothes_pull shirt_lift skirt_lift skirt_aside spread_legs sitting touching_self
kneeling touching_self fingering clitoral_stimulation masturbation spread_legs spread_pussy presenting touching_self fingering
fingering clitoral_stimulation spread_pussy fingering masturbation spread_legs fingering clitoral_stimulation fingering spread_pussy fingering trembling
vibrator object_insertion vibrator dildo object_insertion dildo vibrator object_insertion dildo vibrator dildo object_insertion
orgasm female_ejaculation orgasm female_ejaculation orgasm afterglow
sitting lying looking_back walking""",
  poses={15:"sitting",16:"sitting",17:"kneeling",18:"sitting",19:"sitting",20:"sitting",
         21:"sitting",22:"sitting",23:"sitting",24:"sitting",25:"sitting",26:"sitting",
         27:"lying",39:"lying",51:"lying",57:"sitting",58:"lying",59:"sitting"}),
  dict(no=36, slug="hifumi", name="Hifumi", tag="hifumi_(blue_archive)",
  attrs=["light_brown_hair","long_hair","twintails","low_twintails","yellow_eyes",
         "halo","small_breasts"],
  title="Hifumi - Gio hoc dem (Trinity)",
  idea=("Adult AU solo: Hifumi sneaks into the old Trinity library in a cut Trinity uniform, no bra, no panties. "
        "Cheerful teasing turns shameless with self-touch, desk masturbation, vibrator and dildo play, orgasm, afterglow. No sex."),
  style="with bright shamelessness",
  actions="""walking waving closing_door stretching hands_on_hips head_tilt adjusting_clothes hand_in_hair
undressing clothes_pull shirt_lift skirt_lift skirt_aside spread_legs sitting touching_self
standing touching_self spread_legs fingering clitoral_stimulation presenting spread_pussy masturbation fingering touching_self
sitting_on_desk spread_legs fingering clitoral_stimulation spread_pussy fingering presenting_pussy masturbation fingering spread_legs clitoral_stimulation trembling
vibrator vibrator object_insertion dildo sitting_on_desk object_insertion dildo vibrator object_insertion dildo vibrator object_insertion
orgasm female_ejaculation orgasm orgasm female_ejaculation afterglow
sitting_on_desk stretching looking_back walking""",
  poses={15:"sitting",16:"sitting",17:"standing",27:"sitting",39:"sitting",
         51:"sitting",57:"sitting"}),
  dict(no=37, slug="koharu", name="Koharu", tag="koharu_(blue_archive)",
  attrs=["pink_hair","long_hair","twintails","low_twintails","bangs","pink_eyes",
         "halo","black_wings","low_wings","feathered_wings","small_breasts"],
  title="Koharu - Mat na dem (Trinity)",
  idea=("Adult AU solo: Koharu is caught after curfew in the old Trinity library in a cut Trinity uniform, no bra, no panties. "
        "Panic melts into fingering, spread pussy, floor masturbation, vibrator and dildo play, orgasm, afterglow. No sex."),
  style="while panicking and melting",
  actions="""walking looking_around closing_door hands_on_hips head_tilt adjusting_clothes hand_in_hair standing
undressing clothes_pull shirt_lift skirt_lift skirt_aside spread_legs sitting touching_self
sitting spread_legs touching_self fingering clitoral_stimulation spread_pussy presenting masturbation fingering trembling
lying spread_legs fingering spread_pussy clitoral_stimulation fingering masturbation spread_legs presenting_pussy fingering spread_pussy trembling
vibrator object_insertion dildo vibrator object_insertion dildo vibrator object_insertion dildo vibrator object_insertion dildo
female_ejaculation orgasm female_ejaculation orgasm female_ejaculation afterglow
sitting lying looking_back walking""",
  poses={15:"sitting",16:"sitting",17:"sitting",18:"sitting",19:"sitting",20:"sitting",
         21:"sitting",22:"sitting",23:"sitting",24:"sitting",25:"sitting",26:"sitting",
         27:"lying",39:"lying",51:"lying",57:"sitting",58:"lying",59:"sitting"}),
  dict(no=38, slug="ui", name="Ui", tag="ui_(blue_archive)",
  attrs=["black_hair","very_long_hair","ponytail","purple_hairband","hair_between_eyes",
         "purple_eyes","bags_under_eyes","halo","small_breasts"],
  title="Ui - Trang sach dem (Trinity)",
  idea=("Adult AU solo: Ui stays late cataloguing in the old Trinity library in a cut Trinity uniform, no bra, no panties. "
        "Sleepy indifference turns hungry with desk fingering, bent-over spread pussy, vibrator and dildo play, orgasm, afterglow. No sex."),
  style="with sleepy hunger",
  actions="""walking holding_book sitting_on_desk adjusting_clothes head_tilt hand_in_hair hands_on_hips standing
undressing clothes_pull shirt_lift skirt_lift skirt_aside spread_legs sitting_on_desk touching_self
sitting_on_desk touching_self fingering spread_legs clitoral_stimulation presenting spread_pussy masturbation fingering trembling
standing bent_over spread_legs fingering clitoral_stimulation spread_pussy fingering presenting_pussy masturbation fingering spread_pussy trembling
vibrator object_insertion dildo vibrator object_insertion dildo vibrator object_insertion dildo vibrator object_insertion dildo
orgasm orgasm female_ejaculation orgasm female_ejaculation afterglow
sitting_on_desk stretching looking_back walking""",
  poses={3:"sitting",4:"sitting",5:"sitting",6:"sitting",7:"sitting",15:"sitting",16:"sitting",
         17:"sitting",27:"standing",39:"sitting",51:"sitting",57:"sitting"}),
 dict(no=39, slug="seia", name="Seia", tag="seia_(blue_archive)",
  attrs=["blonde_hair","very_long_hair","long_hair","fox_ears","fox_tail",
         "animal_ear_fluff","yellow_eyes","parted_bangs","halo","hair_flower",
         "small_breasts"],
  title="Seia - Tra dem (Trinity)",
  idea=("Adult AU solo: Seia waits alone in the old Trinity library in a cut Trinity uniform, no bra, no panties. "
        "Serene prophecy turns greedy with kneeling fingering, spread pussy, vibrator and dildo play, orgasm, afterglow. No sex."),
  style="with serene greed",
  actions="""walking looking_around closing_door hands_on_hips head_tilt adjusting_clothes hand_in_hair standing
undressing clothes_pull shirt_lift skirt_lift skirt_aside spread_legs sitting touching_self
standing touching_self fingering clitoral_stimulation spread_legs presenting spread_pussy masturbation fingering trembling
kneeling spread_legs fingering clitoral_stimulation spread_pussy fingering presenting_pussy masturbation fingering spread_legs spread_pussy trembling
dildo object_insertion vibrator dildo vibrator object_insertion vibrator dildo object_insertion vibrator object_insertion dildo
orgasm female_ejaculation female_ejaculation orgasm female_ejaculation afterglow
sitting stretching looking_back walking""",
  poses={15:"sitting",16:"sitting",17:"standing",18:"standing",19:"standing",20:"standing",
         21:"standing",22:"standing",23:"standing",24:"standing",25:"standing",26:"standing",
         27:"kneeling",39:"kneeling",51:"kneeling",57:"sitting"}),
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
 "arrival": ["Moonlight catches the cut uniform.","She listens for footsteps.","The empty shelves swallow the sound.","Her halo glows faintly."],
 "undress": ["The wet white shirt turns transparent.","She pulls the skirt higher.","The blazer slips off one shoulder.","Her nipples print through the wet shirt."],
 "foreplay": ["Her own fingers slide under the skirt.","Her thighs shine with wetness.","She spreads herself open.","She bites her lip and keeps going."],
 "position_a": ["Two fingers curl inside her.","Her hips rock against her hand.","She holds herself open.","Her thighs shake."],
 "position_b": ["The vibrator hums against her.","The dildo slides in slow.","She pushes it deeper.","Her back arches off the floor."],
 "climax": ["She comes hard.","She squirts across her thighs.","She shakes through the last wave."],
 "afterglow": ["Her thighs are slick.","She catches her breath.","The cut uniform hangs loose."],
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
    if n >= 9:
        o += ["wet_clothes", "see-through", "wet_shirt",
              "nipples_visible_through_clothing", "nipple_outline",
              "shirt_lift", "skirt_lift"]
    if 17 <= n <= 50:
        o += ["open_shirt", "skirt_aside"]
    if 39 <= n <= 50:
        o = [x for x in o if x not in ("black_skirt", "black_pleated_skirt")]
    if n >= 51 and n <= 56:
        o = []
    if n >= 57:
        o = BASE + ["shirt_lift", "skirt_aside"]
    return list(dict.fromkeys(o))


def body_state(n):
    b = []
    if n >= 17:
        b += ["nipples", "pussy"]
    if n >= 39 and n <= 50:
        b += ["bottomless"]
    if n >= 51 and n <= 56:
        b += ["completely_nude"]
    if n >= 57:
        b += ["afterglow"]
    return list(dict.fromkeys(b))

def state(n):
    if n == 0: return "dry cut Trinity uniform, no bra, no panties"
    if n <= 8: return "cut Trinity uniform, dry, no bra, no panties"
    if n <= 16: return "uniform soaked see-through, nipples visible, sweat sheen"
    if n <= 26: return "shirt open, breasts out, skirt aside, pussy exposed, wet fingers"
    if n <= 38: return "shirt open, skirt aside, pussy wet, fingers working"
    if n <= 50: return "bottomless, toy inserted, sweat, trembling"
    if n <= 53: return "nude, flushed, on the edge"
    if n <= 56: return "nude, orgasm, wet thighs"
    return "uniform loose, afterglow, wet thighs"

def cast(n):
    o = ["small_breasts","slim","pale_skin","thighs"]
    if n >= 9: o += ["sweat","shiny_skin","sweatdrop","wet_hair"]
    if n >= 14: o += ["pussy_juice","blush"]
    if n >= 20: o += ["pussy_juice_drip"]
    if n >= 39: o += ["sex_toy","vibrator","dildo","object_insertion"]
    if n >= 48: o += ["trembling"]
    if n in (51,52,53,54,55,56): o += ["orgasm","female_ejaculation","ahegao"]
    if n >= 57: o += ["afterglow","pussy_juice_trail"]
    return list(dict.fromkeys(o))

def build(a):
    acts = a["actions"].split()
    assert len(acts) == 60, (a["slug"], len(acts))
    shots, prev = [], None
    for n, primary in enumerate(acts, 1):
        ph = phase(n)
        pose = aq.pose_for(primary, a["poses"].get(n))
        expr = aq.clean_expression(EXPR[ph][(n-1) % len(EXPR[ph])], [primary])
        seq = {"purpose": "setup" if n <= 8 else ("transition" if n == 17 else
                ("result" if n >= 51 else "action")),
               "actor": "GIRL", "primaryAction": primary, "eventId": "%s:%d" % (ph, n)}
        if prev: seq["poseBefore"] = prev
        seq["poseAfter"] = pose
        prev = pose
        note = NOTES[ph][(n-1) % len(NOTES[ph])]
        cap = aq.caption(a["name"], primary, note)
        shots.append({"n": n, "phase": ph, "beat": "%s: %s" % (ph, cap),
          "purpose": seq["purpose"], "outfit": outfit(n), "body_state": body_state(n),
          "action": [primary], "props": aq.props_for(cap),
          "expression": expr, "pose": [pose], "camera": CAM[(n*3) % len(CAM)],
          "motion": MOT[(n*5) % len(MOT)], "cast": cast(n), "caption": cap,
          "carry": state(n-1), "delta": "action: %s; state: %s" % (primary, state(n)),
          "sequence": seq, "participants": ["GIRL"],
          "background_line": BG,
          "scene": {"location": "old Trinity library", "tags": BG.split(", ")}})
    return {
      "project": {"title": a["title"], "idea": a["idea"], "content_profile": "nsfw",
        "style_json": {"style": "anime, danbooru tags + short natural caption",
          "background": "old Trinity library at night", "aspect": "1:1",
          "render": "Anima Base 2B + anima-turbo-4step v3, 4 steps, CFG 1, er_sde"}},
      "quality_line": "masterpiece, best quality, anime style",
      "safety_tag": "explicit", "background_line": BG, "nl": False,
      "characters": [{"code": "GIRL", "name": a["name"], "gender": "girl",
         "identity_line": "1girl, solo, %s, blue_archive, %s" % (a["tag"], ", ".join(a["attrs"])),
         "identity_json": {"identity_tags": [a["tag"], "blue_archive"],
           "attributes": a["attrs"] + ["1girl"], "adult": True,
           "adult_note": "Adult AU default.",
           "note": "%s (Blue Archive, Trinity), adult AU." % a["name"]},
         "outfit_json": {"default": BASE, "wet": outfit(17), "nude": []}}],
      "act": {"act_no": 1, "title": a["title"],
        "outline": "arrival 1-8 -> undress 9-16 -> solo foreplay 17-26 -> fingering 27-38 -> toy 39-50 -> climax 51-56 -> afterglow 57-60.",
        "revision": 1, "status": "planned",
        "phase_contract": aq.phase_contract([
          ("arrival", 8, "dressed", False), ("undress", 8, "undress", False),
          ("foreplay", 10, "undress", True), ("position_a", 12, "undress", True),
          ("position_b", 12, "undress", True), ("climax", 6, "nude", True),
          ("afterglow", 4, "afterglow", False)])},
      "prompt_file": "prompts/act%d_%s_trinity_60.txt" % (a["no"], a["slug"]),
      "shots": shots}

def check(p):
    names = set()
    for ch in p["characters"]:
        names.update(ch["identity_json"].get("identity_tags", []))
        names.update(ch["identity_json"].get("attributes", []))
        for refs in ch["outfit_json"].values(): names.update(refs)
    for s in p["shots"]:
        for k in ("outfit","action","expression","pose","camera","motion","cast"): names.update(s.get(k, []))
    con = sqlite3.connect(DB)
    miss = [n for n in sorted(names) if not con.execute("select 1 from tag where canonical_name=?", (n,)).fetchone()]
    con.close()
    return miss

def md(a, p):
    out = pathlib.Path("data/plans/act%d_%s_trinity_60.md" % (a["no"], a["slug"]))
    lines = ["# " + p["project"]["title"], "",
      "- Plan: `data/plans/act%d_%s_trinity_60.json`" % (a["no"], a["slug"]),
      "- Prompt: `%s`" % p["prompt_file"], "- So shot: **60**",
      "- Nhan vat: **%s** (`%s`), adult AU" % (a["name"], a["tag"]),
      "- Trang phuc: `school_uniform`, `white_shirt`, `black_blazer`, `black_skirt`, `black_thighhighs`, `no_bra`, `no_panties`",
      "- Boi canh: `library`, `bookshelf`, `night`, `moonlight`",
      "- Noi dung: solo masturbation, toy, orgasm; khong sex.", "",
      "## Logline", "", a["idea"], "", "## Shots", "",
      "| # | Phase | Pose | Action | Expression | Caption |", "|---:|---|---|---|---|---|"]
    for s in p["shots"]:
        lines.append("| %d | %s | %s | %s | %s | %s |" % (s["n"], s["phase"], ", ".join(s["pose"]),
            ", ".join(s["action"]), ", ".join(s["expression"]), s["caption"]))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

for a in ACTS:
    p = build(a)
    miss = check(p)
    if miss: raise SystemExit("act%d missing tags: %s" % (a["no"], miss))
    out = pathlib.Path("data/plans/act%d_%s_trinity_60.json" % (a["no"], a["slug"]))
    out.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    md(a, p)
    print("wrote %s (%d shots)" % (out, len(p["shots"])))
