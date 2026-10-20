import json, pathlib, sqlite3

import act_quality as aq

DB = "db/novel_anima.db"
BASE = ["idol_clothes", "white_clothing", "white_shirt", "black_pleated_skirt",
        "black_thighhighs", "headset", "underboob_cutout", "sideboob_cutout",
        "cleavage_cutout", "navel_cutout", "stomach_cutout", "cleavage",
        "midriff", "bare_stomach", "navel", "no_bra", "no_panties"]
BG = "stage, spotlight, stage lights, smoke, confetti, indoors, night"
BACK_BG = "backstage, indoors, night, stage lights"

ACTS = [
 dict(no=40, slug="chise", name="Chise", tag="chise_(blue_archive)",
  attrs=["blue_hair","very_long_hair","side_ponytail","red_eyes","red_horns","horns",
         "halo","hair_flower","hair_ornament","small_breasts"],
  title="Chise - Idol dem (Hyakkiyako)",
  idea=("Adult AU solo idol act: Chise rehearses alone on the empty Hyakkiyako stage in a cut white-and-black idol costume. "
        "Sweat-soaked performance, backstage undress, fingering, toy play, orgasm, afterglow. No sex."),
  style="with festival fire",
  sec=dict(
   arrival=["walking","looking_around","standing","hands_on_hips","head_tilt","adjusting_clothes","hand_in_hair","waving"],
   warmup=["stretching","stretching_arms","singing","holding_microphone","dancing","spinning","jumping","posing"],
   perform=["dancing","singing","holding_microphone","jumping","spinning","dancing","waving","bowing","posing","standing"],
   strip=["walking","undressing","clothes_pull","shirt_lift","skirt_lift","open_shirt","skirt_aside","sitting","spread_legs","touching_self"],
   solo=["fingering","clitoral_stimulation","masturbation","spread_pussy","presenting","fingering","spread_legs","clitoral_stimulation","spread_pussy","fingering"],
   toy=["vibrator","object_insertion","dildo","vibrator","object_insertion","dildo"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","lying","looking_back","walking"]),
  poses={34:"sitting",35:"sitting",36:"sitting",37:"sitting",38:"sitting",39:"sitting",
         40:"sitting",41:"sitting",42:"sitting",43:"sitting",44:"sitting",45:"sitting",
         46:"sitting",47:"sitting",48:"sitting",49:"sitting",50:"sitting",51:"sitting",
         52:"sitting",53:"lying",54:"lying",55:"lying",57:"sitting",58:"lying",59:"sitting"}),
 dict(no=41, slug="shizuko", name="Shizuko", tag="shizuko_(blue_archive)",
  attrs=["brown_hair","very_long_hair","twintails","purple_eyes","animal_ears",
         "fake_animal_ears","halo","hair_flower","hair_ornament","small_breasts"],
  title="Shizuko - Idol dem (Hyakkiyako)",
  idea=("Adult AU solo idol act: Shizuko runs the empty Hyakkiyako stage rehearsal in a cut white-and-black idol costume. "
        "Organized performance, sweat-soaked undress, spread pussy, toy play, orgasm, afterglow. No sex."),
  style="with backstage precision",
  sec=dict(
   arrival=["walking","holding_microphone","looking_around","standing","adjusting_clothes","hands_on_hips","head_tilt","hand_in_hair"],
   warmup=["stretching","singing","dancing","stretching_arms","holding_microphone","waving","bowing","posing"],
   perform=["singing","dancing","spinning","holding_microphone","jumping","dancing","singing","bowing","waving","standing"],
   strip=["walking","undressing","clothes_pull","skirt_lift","shirt_lift","open_shirt","skirt_aside","sitting","spread_legs","touching_self"],
   solo=["touching_self","fingering","spread_pussy","presenting","clitoral_stimulation","masturbation","fingering","spread_legs","spread_pussy","fingering"],
   toy=["vibrator","dildo","object_insertion","vibrator","dildo","object_insertion"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","stretching","looking_back","walking"]),
  poses={34:"sitting",35:"sitting",36:"sitting",37:"sitting",38:"sitting",39:"sitting",
         40:"sitting",41:"sitting",42:"sitting",43:"sitting",44:"sitting",45:"sitting",
         46:"sitting",47:"sitting",48:"sitting",49:"sitting",50:"sitting",51:"sitting",
         52:"sitting",53:"lying",54:"lying",55:"lying",57:"sitting"}),
 dict(no=42, slug="izuna", name="Izuna", tag="izuna_(blue_archive)",
  attrs=["brown_hair","short_hair","fox_ears","fox_tail","animal_ear_fluff","fang",
         "yellow_eyes","halo","hair_ornament","small_breasts"],
  title="Izuna - Idol dem (Hyakkiyako)",
  idea=("Adult AU solo idol act: Izuna turns the empty Hyakkiyako stage into a ninja-idol showcase in a cut white-and-black idol costume. "
        "Jumping choreography, sweat-soaked undress, kneeling fingering, toy play, orgasm, afterglow. No sex."),
  style="with ninja energy",
  sec=dict(
   arrival=["running","jumping","standing","looking_around","hands_on_hips","head_tilt","adjusting_clothes","hand_in_hair"],
   warmup=["stretching","jumping","dancing","spinning","singing","holding_microphone","posing","waving"],
   perform=["dancing","jumping","spinning","singing","dancing","holding_microphone","jumping","bowing","posing","standing"],
   strip=["walking","undressing","clothes_pull","shirt_lift","skirt_lift","open_shirt","skirt_aside","kneeling","spread_legs","touching_self"],
   solo=["fingering","clitoral_stimulation","spread_pussy","presenting","masturbation","fingering","spread_legs","spread_pussy","clitoral_stimulation","fingering"],
   toy=["vibrator","object_insertion","dildo","vibrator","object_insertion","dildo"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["kneeling","sitting","looking_back","walking"]),
  poses={34:"kneeling",35:"kneeling",36:"kneeling",37:"kneeling",38:"kneeling",39:"kneeling",
         40:"kneeling",41:"kneeling",42:"kneeling",43:"kneeling",44:"kneeling",45:"kneeling",
         46:"kneeling",47:"kneeling",48:"kneeling",49:"kneeling",50:"kneeling",51:"kneeling",
         52:"kneeling",53:"lying",54:"lying",55:"lying",57:"kneeling",58:"sitting",59:"kneeling"}),
 dict(no=43, slug="kokona", name="Kokona", tag="kokona_(blue_archive)",
  attrs=["grey_hair","black_hair","multicolored_hair","streaked_hair","very_long_hair",
         "brown_eyes","animal_ears","halo","hair_between_eyes","small_breasts"],
  title="Kokona - Idol dem (Hyakkiyako)",
  idea=("Adult AU solo idol act: Kokona rehearses alone on the empty Hyakkiyako stage in a cut white-and-black idol costume. "
        "Soft choreography, sweat-soaked backstage undress, spread pussy, toy play, orgasm, afterglow. No sex."),
  style="with quiet greed",
  sec=dict(
   arrival=["walking","looking_around","standing","hands_on_hips","head_tilt","hand_in_hair","adjusting_clothes","waving"],
   warmup=["stretching","stretching_arms","singing","dancing","holding_microphone","spinning","bowing","posing"],
   perform=["dancing","singing","holding_microphone","dancing","spinning","jumping","singing","waving","bowing","standing"],
   strip=["walking","undressing","clothes_pull","skirt_lift","shirt_lift","open_shirt","skirt_aside","sitting","spread_legs","touching_self"],
   solo=["fingering","spread_pussy","clitoral_stimulation","masturbation","presenting","fingering","spread_legs","spread_pussy","fingering","clitoral_stimulation"],
   toy=["vibrator","dildo","object_insertion","vibrator","dildo","object_insertion"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","lying","looking_back","walking"]),
  poses={34:"sitting",35:"sitting",36:"sitting",37:"sitting",38:"sitting",39:"sitting",
         40:"sitting",41:"sitting",42:"sitting",43:"sitting",44:"sitting",45:"sitting",
         46:"sitting",47:"sitting",48:"sitting",49:"sitting",50:"sitting",51:"sitting",
         52:"sitting",53:"lying",54:"lying",55:"lying",57:"sitting",58:"lying"}),
 dict(no=44, slug="shuro", name="Shuro", tag="shuro_(blue_archive)",
  attrs=["grey_hair","long_hair","red_eyes","red_halo","halo","small_breasts"],
  title="Shuro - Idol dem (Hyakkiyako)",
  idea=("Adult AU solo idol act: Shuro takes the empty Hyakkiyako stage alone in a cut white-and-black idol costume. "
        "Cold stage presence, sweat-soaked undress, kneeling fingering, toy play, orgasm, afterglow. No sex."),
  style="with cold precision",
  sec=dict(
   arrival=["walking","looking_around","standing","hands_on_hips","head_tilt","adjusting_clothes","hand_in_hair","posing"],
   warmup=["stretching","singing","holding_microphone","dancing","stretching_arms","spinning","jumping","bowing"],
   perform=["singing","dancing","holding_microphone","spinning","dancing","jumping","waving","singing","bowing","standing"],
   strip=["walking","undressing","clothes_pull","shirt_lift","skirt_lift","open_shirt","skirt_aside","kneeling","spread_legs","touching_self"],
   solo=["fingering","clitoral_stimulation","spread_pussy","presenting","masturbation","fingering","spread_legs","spread_pussy","fingering","clitoral_stimulation"],
   toy=["dildo","object_insertion","vibrator","dildo","object_insertion","vibrator"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","lying","looking_back","walking"]),
  poses={34:"kneeling",35:"kneeling",36:"kneeling",37:"kneeling",38:"kneeling",39:"kneeling",
         40:"kneeling",41:"kneeling",42:"kneeling",43:"kneeling",44:"kneeling",45:"kneeling",
         46:"kneeling",47:"kneeling",48:"kneeling",49:"kneeling",50:"kneeling",51:"kneeling",
         52:"kneeling",53:"lying",54:"lying",55:"lying",57:"sitting",58:"lying"}),
]

EXPR = {
 "arrival": [["smile","looking_at_viewer"],["closed_eyes","smile"],["blush","looking_down"],["determined","half-closed_eyes"]],
 "warmup": [["determined","open_mouth"],["closed_eyes","smile"],["smile","looking_at_viewer"],["focused","parted_lips"]],
 "perform": [["smile","looking_at_viewer"],["wink","open_mouth"],["determined","smile"],["closed_eyes","smile"]],
 "strip": [["blush","parted_lips"],["biting_lip","half-closed_eyes"],["open_mouth","blush"],["smile","looking_down"]],
 "solo": [["half-closed_eyes","open_mouth"],["biting_lip","blush"],["ahegao","tongue_out"],["closed_eyes","parted_lips"]],
 "toy": [["ahegao","rolling_eyes"],["open_mouth","blush"],["tongue_out","half-closed_eyes"],["biting_lip","parted_lips"]],
 "climax": [["ahegao","rolling_eyes","tongue_out"],["open_mouth","arched_back"],["half-closed_eyes","blush"],["exhausted","smile"]],
 "after": [["exhausted","smile"],["half-closed_eyes","blush"],["closed_eyes","smile"],["smile","wink"]],
}
CAM = [["full_body"],["cowboy_shot"],["upper_body"],["from_side"],["from_below"],["from_above"],["pov"],["close-up"]]
MOT = [["sweat","motion_blur"],["trembling","emphasis_lines"],["flying_sweatdrops"],["steam"]]
NOTES = {
 "arrival": ["Stage lights click on one by one.","The empty seats wait in the dark.","Her echo answers from the back row.","She checks the mic."],
 "warmup": ["She marks the choreography.","Her voice fills the empty hall.","Sweat starts at her collar.","The beat counts her in."],
 "perform": ["Spotlight hits her face.","She hits the final pose.","Confetti catches the light.","She sings to the empty hall."],
 "strip": ["Backstage, the zipper gives.","The idol costume comes open.","She peels the skirt down.","Cool air finds her skin."],
 "solo": ["Her own fingers slide lower.","She spreads herself open.","Her thighs shine.","She bites her lip."],
 "toy": ["The vibrator hums against her.","The dildo slides in.","She pushes it deeper.","Her back arches."],
 "climax": ["She comes hard.","She squirts across the floor.","She shakes through it."],
 "after": ["Her thighs are slick.","She catches her breath.","The costume hangs loose."],
}
PHASE_NAMES = [("arrival",8),("warmup",8),("perform",10),("strip",10),("solo",10),("toy",6),("climax",4),("after",4)]

def phase_ranges():
    out, n = {}, 1
    for name, count in PHASE_NAMES:
        out[name] = (n, n + count - 1)
        n += count
    return out

def phase_of(n):
    for name, (lo, hi) in phase_ranges().items():
        if lo <= n <= hi:
            return name
    raise ValueError(n)

def outfit(n):
    o = list(BASE)
    if n >= 17: o += ["see-through","wet_clothes","wet_shirt","nipples_visible_through_clothing","nipple_outline"]
    if 27 <= n <= 36: o += ["open_shirt","skirt_aside","shirt_lift","skirt_lift"]
    if 37 <= n <= 46: o = ["black_thighhighs", "headset"]
    if 47 <= n <= 56: o = []
    if n >= 57: o = BASE + ["shirt_lift","skirt_aside"]
    return list(dict.fromkeys(o))


def body_state(n):
    b = []
    if n >= 27: b += ["pussy","pussy_juice","nipples"]
    if 37 <= n <= 46: b += ["topless","bottomless"]
    if 47 <= n <= 56: b += ["completely_nude"]
    if n >= 57: b += ["afterglow"]
    return list(dict.fromkeys(b))

def state(n):
    if n == 0: return "dry cut idol costume, no bra, no panties"
    if n <= 16: return "cut idol costume, sweat sheen, no bra, no panties"
    if n <= 26: return "sweat-soaked costume, see-through shirt, nipples visible"
    if n <= 36: return "open shirt, skirt aside, pussy exposed, wet fingers"
    if n <= 46: return "topless, bottomless, fingering, wet thighs"
    if n <= 52: return "nude, toy inserted, trembling"
    if n <= 56: return "nude, orgasm, wet thighs"
    return "costume loose, afterglow, wet thighs"

def cast(n):
    o = ["idol","small_breasts","slim","pale_skin","thighs"]
    if n >= 9: o += ["sweat","shiny_skin","sweatdrop","wet_hair"]
    if 9 <= n <= 26: o += ["microphone"]
    if n >= 27: o += ["pussy_juice","blush"]
    if n >= 33: o += ["pussy_juice_drip"]
    if n >= 47: o += ["sex_toy","vibrator","dildo","object_insertion"]
    if n >= 51: o += ["trembling"]
    if n >= 53: o += ["orgasm","female_ejaculation","ahegao"]
    if n >= 57: o += ["afterglow","pussy_juice_trail"]
    return list(dict.fromkeys(o))

def build(a):
    acts = []
    for name in ("arrival","warmup","perform","strip","solo","toy","climax","after"):
        acts.extend(a["sec"][name])
    assert len(acts) == 60, (a["slug"], len(acts), [len(a["sec"][k]) for k in ("arrival","warmup","perform","strip","solo","toy","climax","after")])
    shots, prev = [], None
    ranges = phase_ranges()
    for n, primary in enumerate(acts, 1):
        ph = phase_of(n)
        pose = aq.pose_for(primary, a["poses"].get(n))
        expr = aq.clean_expression(EXPR[ph][(n-1) % len(EXPR[ph])], [primary])
        seq = {"purpose": "setup" if ph in ("arrival","warmup") else
                ("result" if n >= 53 else "action"),
               "actor": "GIRL", "primaryAction": primary, "eventId": "%s:%d" % (ph, n)}
        if prev: seq["poseBefore"] = prev
        seq["poseAfter"] = pose
        prev = pose
        note = NOTES[ph][(n-1) % len(NOTES[ph])]
        cap = aq.caption(a["name"], primary, note)
        bg = aq.background_for(ph, BG, BACK_BG)
        shots.append({"n": n, "phase": ph, "beat": "%s: %s" % (ph, cap),
          "purpose": seq["purpose"], "outfit": outfit(n), "body_state": body_state(n),
          "action": [primary], "props": aq.props_for(cap),
          "expression": expr, "pose": [pose], "camera": CAM[(n*3)%len(CAM)],
          "motion": MOT[(n*5)%len(MOT)], "cast": cast(n), "caption": cap,
          "carry": state(n-1), "delta": "action: %s; state: %s" % (primary, state(n)),
          "sequence": seq, "participants": ["GIRL"],
          "background_line": bg,
          "scene": {"location": "empty Hyakkiyako idol stage", "area": ph,
                    "tags": bg.split(", ")}})
    return {
      "project": {"title": a["title"], "idea": a["idea"], "content_profile": "nsfw",
        "style_json": {"style": "anime, danbooru tags + short natural caption",
          "background": "empty Hyakkiyako idol stage at night", "aspect": "1:1",
          "render": "Anima Base 2B + anima-turbo-4step v3, 4 steps, CFG 1, er_sde"}},
      "quality_line": "masterpiece, best quality, anime style",
      "safety_tag": "explicit", "background_line": BG, "nl": False,
      "characters": [{"code": "GIRL", "name": a["name"], "gender": "girl",
         "identity_line": "1girl, solo, %s, blue_archive, %s" % (a["tag"], ", ".join(a["attrs"])),
         "identity_json": {"identity_tags": [a["tag"], "blue_archive"],
           "attributes": a["attrs"] + ["1girl"], "adult": True,
           "adult_note": "Adult AU default.",
           "note": "%s (Blue Archive, Hyakkiyako), adult idol AU." % a["name"]},
         "outfit_json": {"default": BASE, "stage": outfit(17), "nude": []}}],
      "act": {"act_no": 1, "title": a["title"],
        "outline": "arrival 1-8 -> warmup 9-16 -> stage 17-26 -> backstage strip 27-36 -> fingering 37-46 -> toy 47-52 -> climax 53-56 -> afterglow 57-60.",
        "revision": 1, "status": "planned",
        "phase_contract": aq.phase_contract([
          ("arrival", 8, "dressed", False), ("warmup", 8, "dressed", False),
          ("perform", 10, "dressed", False), ("strip", 10, "undress", True),
          ("solo", 10, "undress", True), ("toy", 6, "nude", True),
          ("climax", 4, "nude", True), ("after", 4, "afterglow", False)])},
      "prompt_file": "prompts/act%d_%s_idol_60.txt" % (a["no"], a["slug"]),
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
    out = pathlib.Path("data/plans/act%d_%s_idol_60.md" % (a["no"], a["slug"]))
    lines = ["# " + p["project"]["title"], "",
      "- Plan: `data/plans/act%d_%s_idol_60.json`" % (a["no"], a["slug"]),
      "- Prompt: `%s`" % p["prompt_file"], "- So shot: **60**",
      "- Nhan vat: **%s** (`%s`), adult idol AU" % (a["name"], a["tag"]),
      "- Trang phuc: `idol_clothes`, `white_shirt`, `black_pleated_skirt`, `black_thighhighs`, `headset`, cutouts, `no_bra`, `no_panties`",
      "- Boi canh: `stage`, `spotlight`, `smoke`, `confetti`, `backstage`, `night`",
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
    out = pathlib.Path("data/plans/act%d_%s_idol_60.json" % (a["no"], a["slug"]))
    out.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    md(a, p)
    print("wrote %s (%d shots)" % (out, len(p["shots"])))
