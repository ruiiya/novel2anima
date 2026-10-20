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
BASE = ["idol_clothes", "white_clothing", "white_shirt", "black_pleated_skirt",
        "black_thighhighs", "headset", "underboob_cutout", "sideboob_cutout",
        "cleavage_cutout", "navel_cutout", "stomach_cutout", "cleavage",
        "midriff", "bare_stomach", "navel", "no_bra", "no_panties"]
BG = "stage, spotlight, stage lights, smoke, confetti, indoors, night"
BACK_BG = "backstage, indoors, night, stage lights"

ACTS = [
 dict(no=40, slug="chise", name="Chise", tag="chise_(blue_archive)",
  attrs=["blue_hair","very_long_hair","side_ponytail","red_eyes","red_horns","horns","halo","hair_flower","hair_ornament","small_breasts"],
  title="Chise - Idol dem (Hyakkiyako)", style="with festival fire",
  idea="Adult AU solo idol audition-to-encore act: Chise takes the empty Hyakkiyako stage in a cut white-and-black idol costume, then strips backstage for fingering, toy play and orgasm. No sex.",
  sec=dict(
   arrival=["walking","looking_around","standing","hands_on_hips","adjusting_clothes","hand_in_hair"],
   rehearsal=["stretching","dancing","singing","holding_microphone","stretching_arms","posing"],
   sound=["holding_microphone","singing","spinning","waving","bowing","standing"],
   stage=["dancing","singing","jumping","spinning","dancing","holding_microphone","waving","jumping","dancing","bowing","posing","standing"],
   encore=["dancing","singing","waving","bowing","jumping","holding_microphone","posing","standing"],
   back=["walking","undressing","clothes_pull","shirt_lift","skirt_lift","open_shirt","skirt_aside","sitting","spread_legs","touching_self"],
   toy=["fingering","spread_pussy","vibrator","object_insertion","dildo","vibrator"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
 dict(no=41, slug="shizuko", name="Shizuko", tag="shizuko_(blue_archive)",
  attrs=["brown_hair","very_long_hair","twintails","purple_eyes","animal_ears","fake_animal_ears","halo","hair_flower","hair_ornament","small_breasts"],
  title="Shizuko - Idol dem (Hyakkiyako)", style="with backstage precision",
  idea="Adult AU solo idol audition-to-encore act: Shizuko runs the empty Hyakkiyako stage in a cut white-and-black idol costume, then strips backstage for fingering, toy play and orgasm. No sex.",
  sec=dict(
   arrival=["walking","holding_microphone","looking_around","standing","hands_on_hips","head_tilt"],
   rehearsal=["stretching","singing","dancing","holding_microphone","stretching_arms","posing"],
   sound=["singing","holding_microphone","dancing","spinning","bowing","waving"],
   stage=["singing","dancing","spinning","holding_microphone","jumping","dancing","singing","bowing","waving","posing","dancing","standing"],
   encore=["singing","dancing","waving","bowing","spinning","holding_microphone","posing","standing"],
   back=["walking","undressing","clothes_pull","skirt_lift","shirt_lift","open_shirt","skirt_aside","sitting","spread_legs","touching_self"],
   toy=["touching_self","spread_pussy","vibrator","dildo","object_insertion","vibrator"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
 dict(no=42, slug="izuna", name="Izuna", tag="izuna_(blue_archive)",
  attrs=["brown_hair","short_hair","fox_ears","fox_tail","animal_ear_fluff","fang","yellow_eyes","halo","hair_ornament","small_breasts"],
  title="Izuna - Idol dem (Hyakkiyako)", style="with ninja energy",
  idea="Adult AU solo idol audition-to-encore act: Izuna turns the empty Hyakkiyako stage into a ninja-idol showcase in a cut white-and-black idol costume, then strips backstage for kneeling fingering, toy play and orgasm. No sex.",
  sec=dict(
   arrival=["running","jumping","standing","looking_around","hands_on_hips","head_tilt"],
   rehearsal=["stretching","jumping","dancing","spinning","singing","posing"],
   sound=["holding_microphone","jumping","dancing","waving","bowing","standing"],
   stage=["dancing","jumping","spinning","singing","dancing","holding_microphone","jumping","bowing","dancing","posing","waving","standing"],
   encore=["jumping","dancing","singing","bowing","spinning","holding_microphone","posing","standing"],
   back=["walking","undressing","clothes_pull","shirt_lift","skirt_lift","open_shirt","skirt_aside","kneeling","spread_legs","touching_self"],
   toy=["fingering","spread_pussy","vibrator","object_insertion","dildo","vibrator"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["kneeling","looking_back"])),
 dict(no=43, slug="kokona", name="Kokona", tag="kokona_(blue_archive)",
  attrs=["grey_hair","black_hair","multicolored_hair","streaked_hair","very_long_hair","brown_eyes","animal_ears","halo","hair_between_eyes","small_breasts"],
  title="Kokona - Idol dem (Hyakkiyako)", style="with quiet greed",
  idea="Adult AU solo idol audition-to-encore act: Kokona rehearses alone on the empty Hyakkiyako stage in a cut white-and-black idol costume, then strips backstage for fingering, toy play and orgasm. No sex.",
  sec=dict(
   arrival=["walking","looking_around","standing","hands_on_hips","head_tilt","hand_in_hair"],
   rehearsal=["stretching","stretching_arms","singing","dancing","holding_microphone","posing"],
   sound=["singing","dancing","spinning","holding_microphone","bowing","waving"],
   stage=["dancing","singing","holding_microphone","dancing","spinning","jumping","singing","waving","bowing","dancing","posing","standing"],
   encore=["dancing","singing","waving","bowing","jumping","holding_microphone","posing","standing"],
   back=["walking","undressing","clothes_pull","skirt_lift","shirt_lift","open_shirt","skirt_aside","sitting","spread_legs","touching_self"],
   toy=["fingering","spread_pussy","vibrator","dildo","object_insertion","vibrator"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
 dict(no=44, slug="shuro", name="Shuro", tag="shuro_(blue_archive)",
  attrs=["grey_hair","long_hair","red_eyes","red_halo","halo","small_breasts"],
  title="Shuro - Idol dem (Hyakkiyako)", style="with cold precision",
  idea="Adult AU solo idol audition-to-encore act: Shuro takes the empty Hyakkiyako stage alone in a cut white-and-black idol costume, then strips backstage for kneeling fingering, toy play and orgasm. No sex.",
  sec=dict(
   arrival=["walking","looking_around","standing","hands_on_hips","adjusting_clothes","posing"],
   rehearsal=["stretching","singing","holding_microphone","dancing","stretching_arms","posing"],
   sound=["singing","holding_microphone","spinning","dancing","bowing","waving"],
   stage=["singing","dancing","holding_microphone","spinning","dancing","jumping","waving","singing","bowing","dancing","posing","standing"],
   encore=["singing","dancing","waving","bowing","spinning","holding_microphone","posing","standing"],
   back=["walking","undressing","clothes_pull","shirt_lift","skirt_lift","open_shirt","skirt_aside","kneeling","spread_legs","touching_self"],
   toy=["fingering","spread_pussy","dildo","object_insertion","vibrator","dildo"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
]

PHASE_NAMES = [("arrival",6),("rehearsal",6),("sound",6),("stage",12),("encore",8),("back",10),("toy",6),("climax",4),("after",2)]
EXPR = {
 "arrival": [["smile","looking_at_viewer"],["closed_eyes","smile"],["blush","looking_down"],["determined","half-closed_eyes"]],
 "rehearsal": [["determined","open_mouth"],["closed_eyes","smile"],["focused","parted_lips"],["smile","looking_at_viewer"]],
 "sound": [["smile","looking_at_viewer"],["wink","open_mouth"],["determined","smile"],["closed_eyes","smile"]],
 "stage": [["smile","looking_at_viewer"],["wink","open_mouth"],["determined","smile"],["ahegao","tongue_out"]],
 "encore": [["exhausted","smile"],["open_mouth","blush"],["wink","tongue_out"],["closed_eyes","smile"]],
 "back": [["blush","parted_lips"],["biting_lip","half-closed_eyes"],["open_mouth","blush"],["smile","looking_down"]],
 "toy": [["ahegao","rolling_eyes"],["open_mouth","blush"],["tongue_out","half-closed_eyes"],["biting_lip","parted_lips"]],
 "climax": [["ahegao","rolling_eyes","tongue_out"],["open_mouth","arched_back"],["half-closed_eyes","blush"],["exhausted","smile"]],
 "after": [["exhausted","smile"],["half-closed_eyes","blush"]],
}
CAM = [["full_body"],["cowboy_shot"],["upper_body"],["from_side"],["from_below"],["from_above"],["pov"],["close-up"]]
MOT = [["sweat","motion_blur"],["trembling","emphasis_lines"],["flying_sweatdrops"],["steam"]]
NOTES = {
 "arrival": ["Stage lights click on.","The empty seats wait.","Her echo answers.","She checks the mic."],
 "rehearsal": ["She marks the choreography.","Her voice fills the hall.","Sweat starts at her collar.","The beat counts her in."],
 "sound": ["The monitor squeals once.","She tests the chorus.","Spotlight hits her face.","The intro plays again."],
 "stage": ["She hits the first pose.","Confetti catches the light.","Her skirt snaps with the beat.","She sings to the empty hall."],
 "encore": ["She bows, chest heaving.","The last note hangs.","She waves at no one.","Her legs shake."],
 "back": ["Backstage, the zipper gives.","The costume comes open.","She peels the skirt down.","Cool air finds her skin."],
 "toy": ["The vibrator hums.","The dildo slides in.","She pushes it deeper.","Her back arches."],
 "climax": ["She comes hard.","She squirts across the floor.","She shakes through it."],
 "after": ["Her thighs are slick.","She catches her breath."],
}

def ranges():
    out,n={},1
    for name,c in PHASE_NAMES: out[name]=(n,n+c-1); n+=c
    return out

def phase_of(n):
    for name,(lo,hi) in ranges().items():
        if lo<=n<=hi: return name
    raise ValueError(n)

def outfit(n):
    o=list(BASE)
    if n>=7: o+=["see-through","wet_clothes","wet_shirt","nipples_visible_through_clothing","nipple_outline"]
    if 39<=n<=48: o+=["open_shirt","skirt_aside","shirt_lift","skirt_lift"]
    if 49<=n<=58: o=[]
    if n>=59: o=BASE+["shirt_lift","skirt_aside"]
    return list(dict.fromkeys(o))


def body_state(n):
    b=[]
    if n>=39: b+=["pussy","pussy_juice","nipples"]
    if 49<=n<=58: b+=["completely_nude"]
    if n>=59: b+=["afterglow"]
    return list(dict.fromkeys(b))

def state(n):
    if n==0: return "dry cut idol costume, no bra, no panties"
    if n<=18: return "cut idol costume, sweat sheen, no bra, no panties"
    if n<=38: return "soaked costume, see-through shirt, nipples visible"
    if n<=48: return "open shirt, skirt aside, pussy exposed, wet fingers"
    if n<=54: return "nude, toy inserted, trembling"
    if n<=58: return "nude, orgasm, wet thighs"
    return "costume loose, afterglow, wet thighs"

def cast(n):
    o=["idol","small_breasts","slim","pale_skin","thighs"]
    if n>=7: o+=["sweat","shiny_skin","sweatdrop","wet_hair"]
    if 7<=n<=38: o+=["microphone"]
    if n>=39: o+=["pussy_juice","blush"]
    if n>=43: o+=["pussy_juice_drip"]
    if n>=49: o+=["sex_toy","vibrator","dildo","object_insertion"]
    if n>=53: o+=["trembling"]
    if n>=55: o+=["orgasm","female_ejaculation","ahegao"]
    if n>=59: o+=["afterglow","pussy_juice_trail"]
    return list(dict.fromkeys(o))

def build(a):
    acts=[]
    for name,_ in PHASE_NAMES: acts+=a["sec"][name]
    assert len(acts)==60,(a["slug"],len(acts))
    shots=[]; prev=None
    for n,primary in enumerate(acts,1):
        ph=phase_of(n)
        pose=aq.pose_for(primary,a.get("poses",{}).get(n))
        expr=aq.clean_expression(EXPR[ph][(n-1)%len(EXPR[ph])],[primary])
        seq={"purpose":"setup" if ph in ("arrival","rehearsal","sound") else ("result" if n>=55 else "action"),
             "actor":"GIRL","primaryAction":primary,"eventId":"%s:%d"%(ph,n)}
        if prev: seq["poseBefore"]=prev
        seq["poseAfter"]=pose; prev=pose
        note=NOTES[ph][(n-1)%len(NOTES[ph])]
        cap=aq.caption(a["name"],primary,note)
        bg=aq.background_for(ph,BG,BACK_BG)
        shots.append({"n":n,"phase":ph,"beat":"%s: %s"%(ph,cap),"purpose":seq["purpose"],
          "outfit":outfit(n),"body_state":body_state(n),"action":[primary],"props":aq.props_for(cap),"expression":expr,
          "pose":[pose],"camera":CAM[(n*3)%len(CAM)],"motion":MOT[(n*5)%len(MOT)],
          "cast":cast(n),"caption":cap,"carry":state(n-1),
          "delta":"action: %s; state: %s"%(primary,state(n)),"sequence":seq,"participants":["GIRL"],
          "background_line":bg,"scene":{"location":"empty Hyakkiyako idol stage","area":ph,"tags":bg.split(", ")}})
    return {"project":{"title":a["title"]+" [phase]","idea":a["idea"],"content_profile":"nsfw",
      "style_json":{"style":"anime, danbooru tags + short natural caption","background":"empty Hyakkiyako idol stage at night","aspect":"1:1","render":"Anima Base 2B + anima-turbo-4step v3, 4 steps, CFG 1, er_sde"}},
      "quality_line":"masterpiece, best quality, anime style","safety_tag":"explicit","background_line":BG,"nl":False,
      "characters":[{"code":"GIRL","name":a["name"],"gender":"girl",
        "identity_line":"1girl, solo, %s, blue_archive, %s"%(a["tag"],", ".join(a["attrs"])),
        "identity_json":{"identity_tags":[a["tag"],"blue_archive"],"attributes":a["attrs"]+["1girl"],"adult":True,"adult_note":"Adult AU default.","note":"%s (Blue Archive, Hyakkiyako), adult idol AU."%a["name"]},
        "outfit_json":{"default":BASE,"stage":outfit(19),"nude":[]}}],
      "act":{"act_no":1,"title":a["title"]+" [phase]","outline":"audition 1-6 -> rehearsal 7-12 -> soundcheck 13-18 -> stage 19-30 -> encore 31-38 -> backstage 39-48 -> toy 49-54 -> climax 55-58 -> afterglow 59-60.","revision":1,"status":"planned",
        "phase_contract":aq.phase_contract([("arrival",6,"dressed",False),("rehearsal",6,"dressed",False),("sound",6,"dressed",False),("stage",12,"dressed",False),("encore",8,"dressed",False),("back",10,"undress",True),("toy",6,"nude",True),("climax",4,"nude",True),("after",2,"afterglow",False)])},
      "prompt_file":"prompts/act%d_%s_idol_phase_60.txt"%(a["no"],a["slug"]),"shots":shots}

def check(p):
    names=set()
    for ch in p["characters"]:
        names.update(ch["identity_json"].get("identity_tags",[])); names.update(ch["identity_json"].get("attributes",[]))
        for refs in ch["outfit_json"].values(): names.update(refs)
    for s in p["shots"]:
        for k in ("outfit","action","expression","pose","camera","motion","cast"): names.update(s.get(k,[]))
    con=sqlite3.connect(DB)
    miss=[n for n in sorted(names) if not con.execute("select 1 from tag where canonical_name=?",(n,)).fetchone()]
    con.close(); return miss

def md(a, p):
    if DRY_RUN: return
    out=plan_path("act%d_%s_idol_phase_60.md"%(a["no"],a["slug"]))
    lines=["# "+p["project"]["title"],"","- Plan: `data/plans/act%d_%s_idol_phase_60.json`"%(a["no"],a["slug"]),
      "- Prompt: `%s`"%p["prompt_file"],"- So shot: **60**","- Nhan vat: **%s** (`%s`), adult idol AU"%(a["name"],a["tag"]),
      "- Trang phuc: `idol_clothes`, `white_shirt`, `black_pleated_skirt`, `black_thighhighs`, `headset`, cutouts, `no_bra`, `no_panties`",
      "- Boi canh: `stage`, `spotlight`, `smoke`, `confetti`, `backstage`, `night`",
      "- Phase: audition 1-6, rehearsal 7-12, soundcheck 13-18, stage 19-30, encore 31-38, backstage 39-48, toy 49-54, climax 55-58, afterglow 59-60",
      "- Noi dung: solo masturbation, toy, orgasm; khong sex.","","## Logline","",a["idea"],"","## Shots","",
      "| # | Phase | Pose | Action | Expression | Caption |","|---:|---|---|---|---|---|"]
    for s in p["shots"]:
        lines.append("| %d | %s | %s | %s | %s | %s |"%(s["n"],s["phase"],", ".join(s["pose"]),", ".join(s["action"]),", ".join(s["expression"]),s["caption"]))
    out.write_text("\n".join(lines)+"\n",encoding="utf-8")


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
        out = plan_path("act%d_%s_idol_phase_60.json" % (a["no"], a["slug"]))
        if not DRY_RUN:
            out.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
            md(a, p)
        print(("would write " if DRY_RUN else "wrote ") + "%s (%d shots)" % (out, len(p["shots"])))

if __name__ == "__main__":
    main()
