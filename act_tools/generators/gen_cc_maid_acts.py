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
BASE = ["maid", "maid_headdress", "black_dress", "white_apron", "black_thighhighs",
        "black_boots", "detached_collar", "black_collar", "black_detached_sleeves",
        "navel", "bare_shoulders", "collarbone"]
BG = "server room, computer, monitor, control panel, cables, night, indoors"

ACTS = [
 dict(no=45, slug="neru", name="Neru", tag="neru_(blue_archive)",
  attrs=["orange_hair","pink_hair","short_hair","asymmetrical_bangs","hair_between_eyes","red_eyes","mole","mole_under_eye","rabbit_ears","fake_animal_ears","halo","small_breasts"], body=["small_breasts"],
  title="Neru - Maid drill dem (Millennium)", style="with explosive temper",
  idea="Adult AU solo: Neru runs a midnight C&C maid breach drill in an abandoned Millennium server room, wears only a detached collar and sleeves, everything else bare with pubic hair visible, fingers herself, uses a toy, orgasms. No sex.",
  sec=dict(
   infil=["walking","crouching","looking_around","standing","hands_on_hips","head_tilt","adjusting_clothes","earpiece"],
   breach=["running","door","holding_gun","aiming","crouching","jumping","holding_gun","door"],
   combat=["shooting","aiming","running","jumping","crouching","knife","holding_gun","reloading","shooting","running","aiming","standing"],
   settle=["walking","standing","hands_on_hips","head_tilt","sitting","spread_legs","touching_self","fingering"],
   solo=["spread_legs","touching_self","fingering","clitoral_stimulation","masturbation","spread_pussy","presenting","fingering","spread_legs","spread_pussy","fingering","trembling"],
   toy=["vibrator","object_insertion","dildo","vibrator","object_insertion","dildo"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
 dict(no=46, slug="asuna", name="Asuna", tag="asuna_(blue_archive)",
  attrs=["light_brown_hair","very_long_hair","hair_over_one_eye","blue_eyes","mole","mole_on_breast","rabbit_ears","fake_animal_ears","hair_ribbon","blue_ribbon","halo","large_breasts"],
  body=["large_breasts"], title="Asuna - Maid drill dem (Millennium)", style="with careless confidence",
  idea="Adult AU solo: Asuna breezes through a midnight C&C maid breach drill in an abandoned Millennium server room, wears only a detached collar and sleeves, everything else bare with pubic hair visible, fingers herself, uses a toy, orgasms. No sex.",
  sec=dict(
   infil=["walking","waving","looking_around","standing","hands_on_hips","head_tilt","adjusting_clothes","hand_in_hair"],
   breach=["running","door","holding_gun","aiming","jumping","holding_gun","crouching","standing"],
   combat=["shooting","aiming","running","jumping","holding_gun","knife","shooting","aiming","running","reloading","holding_gun","standing"],
   settle=["walking","stretching","hand_in_hair","sitting","spread_legs","touching_self","fingering","presenting"],
   solo=["touching_self","fingering","spread_pussy","presenting","clitoral_stimulation","masturbation","fingering","spread_legs","spread_pussy","fingering","presenting_pussy","trembling"],
   toy=["vibrator","dildo","object_insertion","vibrator","dildo","object_insertion"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
 dict(no=47, slug="karin", name="Karin", tag="karin_(blue_archive)",
  attrs=["black_hair","very_long_hair","ponytail","sidelocks","dark_skin","dark-skinned_female","yellow_eyes","rabbit_ears","fake_animal_ears","halo","large_breasts"],
  body=["large_breasts"], title="Karin - Maid drill dem (Millennium)", style="with sniper focus",
  idea="Adult AU solo: Karin holds overwatch in a midnight C&C maid breach drill in an abandoned Millennium server room, wears only a detached collar and sleeves, everything else bare with pubic hair visible, fingers herself, uses a toy, orgasms. No sex.",
  sec=dict(
   infil=["walking","crouching","looking_around","standing","aiming","head_tilt","adjusting_clothes","earpiece"],
   breach=["crouching","aiming","holding_gun","shooting","crouching","aiming","standing","running"],
   combat=["aiming","shooting","crouching","holding_gun","reloading","shooting","aiming","running","shooting","crouching","aiming","standing"],
   settle=["walking","crouching","hands_on_hips","kneeling","spread_legs","touching_self","fingering","spread_pussy"],
   solo=["kneeling","spread_legs","fingering","clitoral_stimulation","spread_pussy","masturbation","presenting","fingering","spread_legs","spread_pussy","fingering","trembling"],
   toy=["dildo","object_insertion","vibrator","dildo","object_insertion","vibrator"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["kneeling","looking_back"])),
 dict(no=48, slug="akane", name="Akane", tag="akane_(blue_archive)",
  attrs=["light_brown_hair","brown_hair","long_hair","brown_eyes","glasses","black-framed_eyewear","hair_between_eyes","rabbit_ears","fake_animal_ears","halo","large_breasts"],
  body=["large_breasts"], title="Akane - Maid drill dem (Millennium)", style="with operator calm",
  idea="Adult AU solo: Akane runs comms and a midnight C&C maid breach drill in an abandoned Millennium server room, wears only a detached collar and sleeves, everything else bare with pubic hair visible, fingers herself, uses a toy, orgasms. No sex.",
  sec=dict(
   infil=["walking","typing","looking_around","standing","hands_on_hips","head_tilt","adjusting_clothes","earpiece"],
   breach=["typing","standing","holding_gun","aiming","crouching","running","holding_gun","standing"],
   combat=["shooting","aiming","running","reloading","holding_gun","shooting","crouching","aiming","running","holding_gun","shooting","standing"],
   settle=["walking","typing","sitting","spread_legs","touching_self","fingering","presenting","clitoral_stimulation"],
   solo=["sitting","spread_legs","touching_self","fingering","spread_pussy","clitoral_stimulation","masturbation","presenting","fingering","spread_legs","spread_pussy","trembling"],
   toy=["vibrator","object_insertion","dildo","vibrator","object_insertion","dildo"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
 dict(no=49, slug="toki", name="Toki", tag="toki_(blue_archive)",
  attrs=["blonde_hair","very_long_hair","braid","blue_eyes","rabbit_ears","fake_animal_ears","rabbit_tail","fake_tail","halo","large_breasts"],
  body=["large_breasts"], title="Toki - Maid drill dem (Millennium)", style="with mechanical precision",
  idea="Adult AU solo: Toki executes a midnight C&C maid breach drill in an abandoned Millennium server room, wears only a detached collar and sleeves, everything else bare with pubic hair visible, fingers herself, uses a toy, orgasms. No sex.",
  sec=dict(
   infil=["walking","jumping","looking_around","standing","hands_on_hips","head_tilt","adjusting_clothes","earpiece"],
   breach=["running","jumping","door","holding_gun","aiming","crouching","running","standing"],
   combat=["jumping","running","shooting","aiming","jumping","holding_gun","shooting","running","aiming","reloading","holding_gun","standing"],
   settle=["walking","stretching","hand_in_hair","sitting","spread_legs","touching_self","fingering","presenting"],
   solo=["fingering","clitoral_stimulation","spread_pussy","presenting","masturbation","fingering","spread_legs","spread_pussy","fingering","presenting_pussy","clitoral_stimulation","trembling"],
   toy=["dildo","vibrator","object_insertion","dildo","vibrator","object_insertion"],
   climax=["orgasm","female_ejaculation","orgasm","afterglow"],
   after=["sitting","looking_back"])),
]

PHASE_NAMES=[("infil",8),("breach",8),("combat",12),("settle",8),("solo",12),("toy",6),("climax",4),("after",2)]
EXPR={
 "infil":[["focused","looking_down"],["determined","parted_lips"],["half-closed_eyes","looking_at_viewer"],["smirk","looking_at_viewer"]],
 "breach":[["determined","open_mouth"],["focused","parted_lips"],["smirk","looking_at_viewer"],["open_mouth","blush"]],
 "combat":[["determined","open_mouth"],["focused","parted_lips"],["grin","looking_at_viewer"],["smirk","half-closed_eyes"]],
 "settle":[["blush","parted_lips"],["biting_lip","half-closed_eyes"],["open_mouth","blush"],["smile","looking_down"]],
 "solo":[["half-closed_eyes","open_mouth"],["biting_lip","blush"],["ahegao","tongue_out"],["closed_eyes","parted_lips"]],
 "toy":[["ahegao","rolling_eyes"],["open_mouth","blush"],["tongue_out","half-closed_eyes"],["biting_lip","parted_lips"]],
 "climax":[["ahegao","rolling_eyes","tongue_out"],["open_mouth","arched_back"],["half-closed_eyes","blush"],["exhausted","smile"]],
 "after":[["exhausted","smile"],["half-closed_eyes","blush"]],
}
ADV=["slowly","harder","deeper","shallow","rolling","pinned","urgent","lazy","rough","tender","frantic","steady"]
CAM=[["full_body"],["cowboy_shot"],["upper_body"],["from_side"],["from_below"],["from_above"],["pov"],["close-up"]]
MOT=[["sweat","motion_blur"],["trembling","emphasis_lines"],["flying_sweatdrops"],["steam"]]
NOTES={
 "infil":["Red standby lights line the corridor.","She checks the earpiece.","The server racks hum.","Her boots make no sound."],
 "breach":["The door gives.","She clears the corner.","Smoke rolls through the racks.","Her gun tracks the dark."],
 "combat":["Muzzle flash paints the room.","She reloads without looking.","Her collar snaps with the turn.","She drops behind a rack."],
 "settle":["The collar shifts against bare skin.","Her dress zip gives.","She peels the skirt down.","Cool air finds her skin."],
 "solo":["Her own fingers slide lower.","She spreads herself open.","Her thighs shine.","She bites her lip."],
 "toy":["The vibrator hums.","The dildo slides in.","She pushes it deeper.","Her back arches."],
 "climax":["She comes hard.","She squirts across the floor.","She shakes through it."],
 "after":["Her thighs are slick.","She catches her breath."],
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
 if n<=28: o=list(BASE)
 elif n<=36: o=["maid","black_dress","black_thighhighs","black_boots",
                "detached_collar","black_collar","black_detached_sleeves"]
 else: o=["detached_collar","black_collar","black_detached_sleeves"]
 return list(dict.fromkeys(o))


def body_state(n):
 b=[]
 if 29<=n<=36: b+=["pussy","pussy_juice"]
 if n>=37: b+=["nipples","pussy","pussy_juice","pubic_hair"]
 if n>=49: b+=["completely_nude"]
 if n>=55: b+=["orgasm","female_ejaculation"]
 if n>=59: b+=["afterglow"]
 return list(dict.fromkeys(b))

def state(n):
 if n==0: return "maid dress, apron, boots and collar"
 if n<=16: return "maid dress, apron, boots and collar, dry"
 if n<=28: return "sweaty maid dress, apron, boots and collar"
 if n<=36: return "dress opened, apron removed, collar and sleeves remain"
 if n<=48: return "collar and sleeves only, pussy exposed, wet fingers"
 if n<=54: return "toy inserted, collar and sleeves only"
 if n<=58: return "orgasm, wet thighs, collar and sleeves only"
 return "afterglow, collar and sleeves only"

def cast(n, body):
 o=["slim","pale_skin","thighs"]+body
 if 9<=n<=28: o+=["assault_rifle"]
 if n>=17: o+=["sweat","shiny_skin","sweatdrop","wet_hair"]
 if n>=29: o+=["pussy_juice","blush"]
 if n>=33: o+=["pussy_juice_drip"]
 if 49<=n<=54: o+=["sex_toy","vibrator","dildo","object_insertion"]
 if n>=53: o+=["trembling"]
 if n>=55: o+=["orgasm","female_ejaculation","ahegao"]
 if n>=59: o+=["afterglow","pussy_juice_trail"]
 return list(dict.fromkeys(o))

def build(a):
 acts=[]
 for name,_ in PHASE_NAMES: acts+=a["sec"][name]
 assert len(acts)==60,(a["slug"],len(acts))
 settle_actions=["standing","undressing","clothes_pull","dress_lift",
                 "skirt_lift","open_dress","hands_on_hips","sitting"]
 shots=[]; prev=None
 for n,primary in enumerate(acts,1):
  ph=phase_of(n)
  if ph=="settle": primary=settle_actions[n-29]
  pose=aq.pose_for(primary,a.get("poses",{}).get(n))
  expr=aq.clean_expression(EXPR[ph][(n-1)%len(EXPR[ph])],[primary])
  seq={"purpose":"setup" if ph=="infil" else ("result" if n>=55 else "action"),
       "actor":"GIRL","primaryAction":primary,"eventId":"%s:%d"%(ph,n)}
  if prev: seq["poseBefore"]=prev
  seq["poseAfter"]=pose; prev=pose
  note=NOTES[ph][(n-1)%len(NOTES[ph])]
  cap=aq.caption(a["name"],primary,note)
  props=[t for t in ("earpiece","door","gun","knife") if t in cap.lower()]
  shots.append({"n":n,"phase":ph,"beat":"%s: %s"%(ph,cap),"purpose":seq["purpose"],
    "outfit":outfit(n),"body_state":body_state(n),"props":props,"action":[primary],"expression":expr,
    "pose":[pose],"camera":CAM[(n*3)%len(CAM)],"motion":MOT[(n*5)%len(MOT)],
    "cast":cast(n,a["body"]),"caption":cap,"carry":state(n-1),
    "delta":"action: %s; state: %s"%(primary,state(n)),"sequence":seq,"participants":["GIRL"],
    "background_line":BG,"scene":{"location":"abandoned Millennium server room","tags":BG.split(", ")}})
 return {"project":{"title":a["title"],"idea":a["idea"],"content_profile":"nsfw",
   "style_json":{"style":"anime, danbooru tags + short natural caption","background":"abandoned Millennium server room at night","aspect":"1:1","render":"Anima Base 2B + anima-turbo-4step v3, 4 steps, CFG 1, er_sde"}},
   "quality_line":"masterpiece, best quality, anime style","safety_tag":"explicit","background_line":BG,"nl":False,
   "characters":[{"code":"GIRL","name":a["name"],"gender":"girl",
     "identity_line":"1girl, solo, %s, blue_archive, %s"%(a["tag"],", ".join(a["attrs"])),
     "identity_json":{"identity_tags":[a["tag"],"blue_archive"],"attributes":a["attrs"]+["1girl"],"adult":True,"adult_note":"Adult AU default.","note":"%s (Blue Archive, Millennium C&C), adult AU."%a["name"]},
     "outfit_json":{"default":BASE,"drill":outfit(17),"nude":[]}}],
   "act":{"act_no":1,"title":a["title"],"outline":"infiltration 1-8 -> breach 9-16 -> combat drill 17-28 -> undress 29-36 -> self-touch 37-48 -> toy 49-54 -> climax 55-58 -> afterglow 59-60.","revision":1,"status":"planned",
     "phase_contract":aq.phase_contract([("infil",8,"dressed",False),("breach",8,"dressed",False),("combat",12,"dressed",False),("settle",8,"undress",False),("solo",12,"undress",True),("toy",6,"nude",True),("climax",4,"nude",True),("after",2,"afterglow",False)])},
   "prompt_file":"prompts/act%d_%s_maid_60.txt"%(a["no"],a["slug"]),"shots":shots}

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
 out=plan_path("act%d_%s_maid_60.md"%(a["no"],a["slug"]))
 lines=["# "+p["project"]["title"],"","- Plan: `data/plans/act%d_%s_maid_60.json`"%(a["no"],a["slug"]),
  "- Prompt: `%s`"%p["prompt_file"],"- So shot: **60**","- Nhan vat: **%s** (`%s`), adult AU"%(a["name"],a["tag"]),
  "- Trang phuc: chi co detached collar va detached sleeves; toan than lo, co pubic hair",
  "- Boi canh: server room, computer, monitor, control panel, cables, night",
  "- Phase: infiltration 1-8, breach 9-16, combat drill 17-28, settle 29-36, self-touch 37-48, toy 49-54, climax 55-58, afterglow 59-60",
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
        out = plan_path("act%d_%s_maid_60.json" % (a["no"], a["slug"]))
        if not DRY_RUN:
            out.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
            md(a, p)
        print(("would write " if DRY_RUN else "wrote ") + "%s (%d shots)" % (out, len(p["shots"])))

if __name__ == "__main__":
    main()
