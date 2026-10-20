# novel2anima P0P1 upgrade
# -*- coding: utf-8 -*-
"""Generate the 12 Kuoh cosplay acts (act13..act24) -> data/plans/actNN_kuoh_<slug>.json

Per act (~100 shots): chuan bi 5 | 5 outfit blocks x15 | nude 9 | thu dam 20
Rules baked in:
  * moi tag do di kem tag mau (COLOR_PREF): <mau>_<do> neu catalog co, khong thi <mau>_clothing;
    noi y doi mau theo bo (BLACK_UNDER) de khong lot white_panties vao set den
  * tu the di theo thang POSE_ARC / NUDE_ARC / MAST_*: dung -> quy -> ngoi -> nam trong tung
    phase, khong nhay lui; check_plan() assert ca 2 bat bien khi generate
  * every act carries `kuoh_academy_school_uniform` twice (two different sexual cuts)
  * block 3 is the character's own trait outfit in the sexual cut (Asia -> nun, ...)
  * every block ends undressed: bra / panties stated (or explicitly no_bra / no_panties)
  * act ends nude -> masturbation block (base + style + climax + afterglow)

Usage: python act_tools/generators/gen_kuoh_acts.py   then   python etl/seed_plan.py <each plan>
"""
import itertools, json, pathlib, random, sqlite3, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import story_logic
import pathlib as _p, sys as _s
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[1]))
_s.path.insert(0, str(_p.Path(__file__).resolve().parents[2] / "etl"))
import wardrobe   # bang mau + thang tu the nam trong catalog/db, xem etl/wardrobe.py

DB = "db/novel_anima.db"
PLANS = pathlib.Path("data/plans")
ROSTER = pathlib.Path("data/characters/dxd_roster.json")
KUOH = "kuoh_academy_school_uniform"

# outfit families: dressed = tags worn; top/bottom = garment opened/lifted/removed;
# legwear = stays on; spice = extra sexual tags in the undress steps; cues = caption flavour.
F = {
    "KUOH_MICRO": dict(dressed=[KUOH, "shirt", "unbuttoned", "microskirt", "thighhighs", "zettai_ryouiki", "no_bra", "cleavage", "cleavage_cutout"],
                       top="shirt", bottom="microskirt", legwear=["thighhighs"],
                       spice=["downblouse", "nipple_slip", "underboob", "panty_shot"],
                       cues=["Kuoh uniform worn wrong: shirt open to the navel over a bare chest",
                             "micro skirt, thighhighs, nothing under the blouse",
                             "she keeps her school bag on the paper while the hem climbs"]),
    "KUOH_SLUT_BLAZER": dict(dressed=[KUOH, "blazer", "shirt", "unbuttoned", "miniskirt", "thighhighs", "garter_belt", "cleavage", "hair_ribbon"],
                             top="shirt", bottom="miniskirt", legwear=["thighhighs"],
                             spice=["cleavage", "panty_shot", "underboob"],
                             cues=["blazer open, shirt open wider, garter straps above the thighhighs",
                                   "the ribbon is the only thing done up properly",
                                   "she leans over the paper and the garter belt shows under the skirt"]),
    "KUOH_WET": dict(dressed=[KUOH, "shirt", "wet_shirt", "see-through", "no_bra", "miniskirt", "panty_shot", "loafers"],
                     top="shirt", bottom="miniskirt", legwear=["bare_legs"],
                     spice=["see-through", "nipple_slip", "panty_shot"],
                     cues=["she soaked the white shirt first, and now it is see-through everywhere",
                           "the wet uniform clings to her ribs, nipples printed through it",
                           "same for the skirt: nothing hidden any more"]),
    "KUOH_TIGHT": dict(dressed=[KUOH, "shirt", "tight_skirt", "hip_bones", "bare_midriff", "cutout", "thighhighs", "loafers"],
                       top="shirt", bottom="tight_skirt", legwear=["thighhighs"],
                       spice=["cameltoe", "panty_shot", "underboob"],
                       cues=["a skirt cut tight enough to print the seam between her legs",
                             "shirt hitched to the ribs, hip bones on show",
                             "she has to shimmy out of the tight skirt"]),
    "KUOH_UPSKIRT": dict(dressed=[KUOH, "shirt", "microskirt", "upskirt", "panty_shot", "thighhighs", "hair_ribbon", "no_bra"],
                         top="shirt", bottom="microskirt", legwear=["thighhighs"],
                         spice=["upskirt", "panty_shot", "downblouse"],
                         cues=["crouched under the backdrop, skirt riding up to her hips",
                               "the lens gets the view up the skirt without asking",
                               "micro skirt, thighhighs, nothing in between"]),
    "KUOH_BACKLESS": dict(dressed=[KUOH, "shirt", "backless", "off_shoulder", "no_bra", "miniskirt", "cleavage_cutout", "thighhighs"],
                          top="shirt", bottom="miniskirt", legwear=["thighhighs"],
                          spice=["off_shoulder", "cleavage", "panty_shot"],
                          cues=["backless cut of the uniform: shoulder blades and ribs bare",
                                "the shirt is off both shoulders before the first flash",
                                "nothing but thighhighs holds the silhouette together"]),
    "NUN_SEXY": dict(dressed=["nun", "habit", "off_shoulder", "high_slit", "no_bra", "cleavage", "rosary", "thighhighs"],
                     top="habit", bottom="habit", legwear=["thighhighs"],
                     spice=["cleavage", "underboob", "panty_shot"],
                     cues=["Asia in a nun's habit slit to the hip, rosary in hand",
                           "the habit falls open and there is nothing under it",
                           "the cross stays on while everything else comes loose"]),
    "EXORCIST_SEXY": dict(dressed=["cassock", "high_slit", "harness", "gauntlets", "thigh_boots", "cross_necklace"],
                          top="cassock", bottom="cassock", legwear=["thigh_boots"],
                          spice=["cleavage", "cameltoe", "panty_shot"],
                          cues=["fighting cassock split up the thigh, harness across the chest",
                                "gauntlets dropped first, then the cassock torn open",
                                "nothing under the cassock but the harness"]),
    "ANGEL_SEXY": dict(dressed=["white_dress", "angel_wings", "backless", "high_slit", "no_panties", "thighhighs", "cross_necklace"],
                       top="white_dress", bottom="white_dress", legwear=["thighhighs"],
                       spice=["cleavage", "underboob", "panty_shot"],
                       cues=["white wings out, back of the dress open to the waist",
                             "no underwear under the silk, and the slit proves it",
                             "the wings stay spread while the straps come down"]),
    "COUNCIL_SEXY": dict(dressed=["suit", "dress_shirt", "unbuttoned", "no_bra", "tight_skirt", "armband", "thighhighs", "cleavage"],
                         top="dress_shirt", bottom="tight_skirt", legwear=["thighhighs"],
                         spice=["downblouse", "nipple_slip", "panty_shot"],
                         cues=["council suit, shirt open, nothing underneath",
                               "armband still on, blouse open to the waist",
                               "the tight skirt has to be peeled down over her hips"]),
    "KENDO_SEXY": dict(dressed=["kendo", "hakama", "gi", "open_clothes", "no_bra", "bare_midriff", "headband"],
                       top="gi", bottom="hakama", legwear=["bare_legs"],
                       spice=["underboob", "cameltoe", "panty_shot"],
                       cues=["kendo gear worn loose: gi hanging open, hakama riding low",
                             "the gi is open to the sternum, nothing under it",
                             "hakama untied and dragged down, shinai still at her hip"]),
    "CHEER_SEXY": dict(dressed=["cheerleader", "microskirt", "bare_midriff", "no_bra", "sneakers", "hair_ribbon", "cleavage"],
                       top="cheerleader", bottom="microskirt", legwear=["bare_legs"],
                       spice=["underboob", "cameltoe", "panty_shot"],
                       cues=["cheer crop top with nothing under it, skirt cut to the hip",
                             "the top rides up every time she bounces on her trainers",
                             "skirt up, pom-pom dangling from her wrist"]),
    "MAID_SEXY": dict(dressed=["maid", "maid_headdress", "white_apron", "cleavage", "thighhighs", "garter_straps"],
                      top="maid", bottom="maid", legwear=["thighhighs"],
                      spice=["cleavage", "nipple_slip", "panty_shot"],
                      cues=["maid dress cut low and short, apron barely covering the front",
                            "the apron comes untied and the garter straps show",
                            "the dress is unzipped at the back before anything else"]),
    "KIMONO_SEXY": dict(dressed=["kimono", "obi", "high_slit", "off_shoulder", "no_panties", "geta"],
                        top="kimono", bottom="kimono", legwear=["bare_legs"],
                        spice=["cleavage", "underboob", "panty_shot"],
                        cues=["kimono slit to the hip and pulled off one shoulder",
                              "the obi is loosened and there is nothing beneath it",
                              "the collar drops open every time she bows to the lens"]),
    "LIBRARIAN_SEXY": dict(dressed=["librarian", "glasses", "sweater", "unbuttoned", "tight_skirt", "no_bra", "thighhighs"],
                           top="sweater", bottom="tight_skirt", legwear=["thighhighs"],
                           spice=["downblouse", "nipple_slip", "panty_shot"],
                           cues=["library cardigan buttoned once, over nothing",
                                 "glasses stay on, that is the whole point",
                                 "the pencil skirt goes down her legs in one pull"]),
    "JERSEY_SEXY": dict(dressed=["jersey", "shorts", "no_bra", "bare_midriff", "headband", "sneakers", "cameltoe"],
                        top="jersey", bottom="shorts", legwear=["bare_legs"],
                        spice=["underboob", "cameltoe", "panty_shot"],
                        cues=["team jersey with no bra under it, shorts cutting in between her legs",
                              "the jersey comes off over her head in one motion",
                              "shorts off with a shrug, no underwear in sight"]),
    "MIKO_SEXY": dict(dressed=["miko", "detached_sleeves", "no_panties", "thighhighs", "cleavage"],
                      top="miko", bottom="miko", legwear=["thighhighs"],
                      spice=["cleavage", "underboob", "panty_shot"],
                      cues=["shrine dress with nothing under a loose obi",
                            "the detached sleeves come off while she is still posing",
                            "the hem lifts on every turn and there is nothing under it"]),
    "LINGERIE_LACE": dict(dressed=["lingerie", "lace", "garter_belt", "fishnet_pantyhose", "choker", "see-through"],
                          top="lingerie", bottom="lingerie", legwear=["fishnet_pantyhose"],
                          spice=["see-through", "nipple_slip", "cameltoe"],
                          cues=["sheer lace lingerie, garter belt over fishnet tights",
                                "the bra is thin enough to read the nipple through",
                                "everything is lace, nothing hides anything"]),
    "LATEX_BONDAGE": dict(dressed=["bodysuit", "latex", "o-ring", "collar", "leash", "choker", "crotchless_panties", "no_bra"],
                          top="bodysuit", bottom="bodysuit", legwear=["bare_legs"],
                          spice=["cameltoe", "nipple_slip", "panty_shot"],
                          cues=["black latex bodysuit, O-rings, leash clipped to the collar",
                                "the latex is peeled off with the leash still hanging",
                                "crotchless under a suit that is already skin-tight"]),
    "BUNNY": dict(dressed=["playboy_bunny", "leotard", "thighhighs", "garter_straps", "collar", "heels", "no_bra"],
                  top="playboy_bunny", bottom="leotard", legwear=["thighhighs"],
                  spice=["cleavage", "underboob", "cameltoe"],
                  cues=["bunny leotard, collar and heels, garter straps to the thighhighs",
                        "the leotard is unhooked at the collar first",
                        "heels stay on for the whole strip"]),
    "NURSE_SEXY": dict(dressed=["nurse", "microskirt", "see-through", "no_bra", "thighhighs", "pasties"],
                       top="nurse", bottom="microskirt", legwear=["thighhighs"],
                       spice=["see-through", "pasties", "cameltoe"],
                       cues=["nurse dress cut to a micro skirt, pasties instead of a bra",
                             "the dress is sheer under the studio light",
                             "it opens down the front with two fastenings left"]),
    "FISHNET_PASTIES": dict(dressed=["pasties", "fishnets", "microskirt", "choker", "heels", "no_bra", "no_panties"],
                            top="pasties", bottom="microskirt", legwear=["fishnets"],
                            spice=["underboob", "cameltoe", "panty_shot"],
                            cues=["nothing but pasties, fishnets and a micro skirt",
                                  "the skirt is the only garment left and it is coming off",
                                  "no underwear anywhere on her"]),
    "GARTER_DRESS": dict(dressed=["black_dress", "garter_belt", "stockings", "choker", "cleavage", "high_slit"],
                         top="black_dress", bottom="black_dress", legwear=["stockings"],
                         spice=["cleavage", "underboob", "panty_shot"],
                         cues=["short black dress split high, garter belt under the hem",
                               "the dress is unzipped and dropped in one movement",
                               "nothing but garters and stockings left on her"]),
    "APRON_ONLY": dict(dressed=["white_apron", "no_bra", "no_panties", "heels", "choker"],
                       top="white_apron", bottom="white_apron", legwear=["bare_legs"],
                       spice=["cleavage", "underboob", "cameltoe"],
                       cues=["nothing but the apron, tied at the waist, heels on",
                             "the bow at her back is the only fastening left",
                             "she turns around before the apron comes off"]),
    "GYM_SEXY": dict(dressed=["gym_uniform", "gym_shorts", "no_bra", "bare_midriff", "sneakers", "headband", "cameltoe"],
                     top="gym_uniform", bottom="gym_shorts", legwear=["bare_legs"],
                     spice=["underboob", "cameltoe", "panty_shot"],
                     cues=["school gym set worn tight, nothing under the shirt",
                           "the shorts cut high and print the seam between her legs",
                           "still in her trainers when the shirt comes off"]),
    "SWIM_SEXY": dict(dressed=["school_swimsuit", "wet", "see-through", "cameltoe", "barefoot", "no_bra", "no_panties"],
                      top="school_swimsuit", bottom="school_swimsuit", legwear=["barefoot"],
                      spice=["see-through", "cameltoe", "panty_shot"],
                      cues=["school swimsuit, soaking, pressed flat against her body",
                            "straps off the shoulders, the suit starting to roll",
                            "suit rolled to the waist, both breasts bare"]),
    "COMP_SEXY": dict(dressed=["competition_swimsuit", "swim_cap", "goggles", "wet", "cameltoe", "barefoot", "no_bra", "no_panties"],
                      top="competition_swimsuit", bottom="competition_swimsuit", legwear=["barefoot"],
                      spice=["see-through", "cameltoe", "underboob"],
                      cues=["racing swimsuit, cap and goggles still on",
                            "cap off and goggles pushed onto her forehead",
                            "the suit is peeled off the shoulders and down"]),
    "SLINGSHOT_SWIM": dict(dressed=["slingshot_swimsuit", "highleg", "wet", "cameltoe", "barefoot", "no_bra", "no_panties"],
                           top="slingshot_swimsuit", bottom="slingshot_swimsuit", legwear=["barefoot"],
                           spice=["see-through", "cameltoe", "panty_shot"],
                           cues=["slingshot swimsuit, wet, cutting straight between her legs",
                                 "the suit is dragged off one leg at a time, still dripping",
                                 "nothing on her but water at the end of the block"]),
    "MICRO_BIKINI_SWIM": dict(dressed=["micro_bikini", "highleg", "wet", "see-through", "barefoot", "no_bra", "no_panties"],
                              top="micro_bikini", bottom="micro_bikini", legwear=["barefoot"],
                              spice=["see-through", "cameltoe", "underboob"],
                              cues=["micro bikini soaked through and clinging",
                                    "the top comes off first, then the bottom",
                                    "wet fabric leaves marks she does not wipe off"]),
}

# ------------------------------------------------------------------ tag ids
_con = sqlite3.connect(DB)
IDS = {r[0]: r[1] for r in _con.execute("SELECT canonical_name, id FROM tag")}
PC = {r[0]: r[1] for r in _con.execute("SELECT canonical_name, post_count FROM tag")}
pc = lambda name: PC.get(name, 0)
TABLE = wardrobe.colour_table(_con)          # bang mau doc tu db, khong hard-code trong code

def wear(names):
    """ten do -> ref "ten:id" da gan mau theo bang mau cua catalog"""
    refs = []
    for n in names:
        if n not in IDS:
            raise SystemExit("tag not in catalog: %s" % n)
        refs.append((n, IDS[n]))
    refs = wardrobe.under_fix(wardrobe.colorize(refs, TABLE), TABLE)
    return ["%s:%d" % r for r in refs]


def T(name):
    if name not in IDS:
        raise SystemExit("tag not in catalog: %s" % name)
    return "%s:%d" % (name, IDS[name])


def TL(*names):
    return [T(n) for n in dict.fromkeys(names)]


def drop(names, *bad):
    return [n for n in names if n not in bad]

# khoa mau do: bang mau nam trong catalog (WC_* concept) - xem etl/import_colour_sets.py

# ------------------------------------------------------------------ pools
PREP_A = ["posing", "adjusting_clothes", "holding_object", "hand_in_hair", "arms_behind_back",
          "stretching", "hair_flip", "looking_at_viewer", "hand_on_hip", "leg_up", "crossed_legs",
          "skirt_lift"]
DRES_A = ["posing", "arms_up", "clothes_lift", "shirt_lift", "skirt_lift", "hand_on_hip",
          "leaning_forward", "looking_at_viewer", "looking_away", "looking_back", "hair_flip",
          "stretching", "leg_up", "crossed_legs", "holding_clothes", "breast_hold",
          "adjusting_clothes", "bending_over", "crouching", "arms_behind_back"]
UND_B = ["undressing", "clothes_pull", "clothes_lift", "clothes_removed", "dress_lift",
         "skirt_lift", "open_clothes", "partially_undressed", "holding_clothes", "bra_pull",
         "looking_at_viewer"]
UND_C = ["undressing", "clothes_pull", "clothes_removed", "holding_clothes", "partially_undressed",
         "skirt_lift", "panties_off", "covering_breasts", "breast_hold", "arms_behind_back",
         "hair_flip", "stretching", "looking_at_viewer", "hand_on_hip", "posing"]
UND_A = ["undressing", "clothes_pull", "clothes_lift", "clothes_removed", "shirt_lift",
         "skirt_lift", "shirt_pull", "dress_lift", "bra_pull", "open_clothes",
         "partially_undressed", "holding_clothes", "looking_at_viewer"]
NUD_A = ["posing", "covering_breasts", "covering_crotch", "covered_nipples", "arms_behind_back",
         "stretching", "hair_flip", "hand_in_hair", "looking_at_viewer", "hugging_legs",
         "legs_up", "knees_up", "arched_back", "hand_on_hip", "looking_away", "selfie"]
E_SET = ["blush", "half-closed_eyes", "open_mouth", "parted_lips", "smile", "closed_eyes"]
E_SOFT = ["smile", "shy", "blush", "half-closed_eyes", "confident", "seductive_smile", "smug",
          "embarrassed"]
E_HOT = ["blush", "open_mouth", "half-closed_eyes", "parted_lips", "ahegao", "closed_eyes",
         "embarrassed", "smug"]
FRAME_A = ["full_body", "cowboy_shot", "upper_body", "portrait", "lower_body", "wide_shot",
           "close-up"]
ANGLE_A = ["photo_(medium)", "from_below", "from_side", "depth_of_field", "from_above", "pov",
           "backdrop", "from_behind"]
NUDE_EX = ["nipples", "areola", "erect_nipples", "sideboob", "pussy", "wet_pussy", "ass_focus",
           "small_nipples", "underboob", "thighs"]
SKIRT = {"microskirt", "miniskirt", "tight_skirt", "pleated_skirt"}
DRESSY = {"habit", "cassock", "kimono", "yukata", "maid", "nurse", "miko", "black_dress",
          "white_dress", "dress", "playboy_bunny", "leotard", "bodysuit", "latex", "lingerie",
          "white_apron", "school_swimsuit", "competition_swimsuit", "bikini", "micro_bikini",
          "slingshot_swimsuit"}
ACCESSORY = {"choker", "collar", "rosary", "cross_necklace", "hair_ribbon", "ribbon", "necklace",
             "earring", "earrings", "glasses", "hairband", "jewelry", "piercing"}

POSE_MAP = {"lying": "lying", "lying_on_back": "lying", "legs_up": "lying", "sitting": "sitting",
            "sitting_on_chair": "sitting", "sitting_on_desk": "sitting", "knees_up": "sitting",
            "hugging_legs": "sitting", "kneeling": "kneeling", "squatting": "squatting",
            "crouching": "squatting", "bending_over": "bending_over", "spread_legs": "spread_legs"}
STANCE_MAP = {a: p for a, p in POSE_MAP.items()
              if p in ("standing", "kneeling", "squatting", "sitting", "lying", "bending_over")}

# the pose ladder: moi bo do di tu dung -> quy -> ngoi -> nam, khong nhay lui
POSE_ARC = ["standing"] * 8 + ["kneeling"] * 4 + ["sitting"] * 6 + ["lying"] * 4   # 22 = PER_BLOCK
NUDE_ARC = ["kneeling"] * 2 + ["sitting"] * 3 + ["lying"] * 5                      # 10 = NUDE_N
MAST_KNEE = [(9, "squatting"), (7, "kneeling")]        # index trong MAST_BASE
MAST_SIT = [(0, "sitting"), (6, "sitting"), (13, "sitting")]
MAST_LIE = [(i, "lying") for i in (1, 2, 3, 4, 5, 8, 10, 11, 12)]


def actions_for(fam, names):
    """bo cac action khong ton tai trong bo do nay (khong co shirt thi khong shirt_lift...)"""
    f = F[fam]
    base = f["dressed"]
    gone = set()
    if "shirt" not in base:
        gone |= {"shirt_lift", "shirt_pull"}
    if f["bottom"] not in SKIRT:
        gone |= {"skirt_lift"}
    if f["top"] not in DRESSY:
        gone |= {"dress_lift"}
    if "no_bra" in base:
        gone |= {"bra_pull"}
    if "no_panties" in base:
        gone |= {"panties_off"}
    return [n for n in names if n not in gone]


def pose_ok(action, want):
    """action duoc phep dung trong shot co pose 'want' neu no trung tinh hoac cung the"""
    if not want:
        return True
    got = STANCE_MAP.get(action)
    return got is None or got == want

def pose_for(actions, fallback):
    for a in actions:
        if a in POSE_MAP:
            return POSE_MAP[a]
    return fallback


def shuffle(rng, names):
    out = list(names)
    rng.shuffle(out)
    return out


def pool(rng, *pools):
    combos = list(itertools.product(*pools))
    rng.shuffle(combos)
    return combos


def take(pool, n, used, key=lambda x: "|".join(x), ok=lambda x: True):
    """n combos that are self-consistent and whose prompt signature is still unused in this act"""
    out = []
    while len(out) < n:
        x = pool.pop()
        if not ok(x):
            continue
        k = key(x)
        if k in used:
            continue
        used.add(k)
        out.append(x)
    return out


def look_ok(x):
    """no 'eyes closed while looking' contradictions"""
    return not (str(x[0]).startswith("looking") and x[1] == "closed_eyes")


# ------------------------------------------------------------------ wardrobe ladder


def ladder(fam):
    """22 buoc: 1-8 mac do, 9-22 coi dan tung lop. Moi buoc coi deu noi ro bra/panties
    (hoac noi ro la khong co). Do da trut thi khong con tag do do nua."""
    f = F[fam]
    base = list(f["dressed"])
    top, bottom, leg = f["top"], f["bottom"], f["legwear"]
    bra = "no_bra" not in base
    panties = "no_panties" not in base
    spice = [s for s in f["spice"] if (s != "panty_shot" or panties) and (s != "pasties" or bra)]
    base = drop(base, *([] if panties else ["panty_shot"]), *([] if bra else ["pasties"]))
    acc = [t for t in base if t in ACCESSORY]
    bod = [] if bottom == top or bottom in DRESSY else [bottom]
    hem = ["skirt_lift"] if bod else []
    pan = ["panties", "underwear", "panty_shot"] if panties else ["no_panties", "pussy"]
    worn = ["bra", "underwear", "nipple_slip"] if bra \
        else ["no_bra", "cleavage", "underboob", "nipple_slip"]
    under = ["bra", "underwear", "nipple_slip"] if bra else ["no_bra", "topless", "nipples", "sideboob"]
    unhook = ["bra_pull", "breast_hold", "nipple_slip"] if bra \
        else ["topless", "nipples", "erect_nipples"]
    unhook2 = ["bra_pull", "breast_hold", "nipple_slip", "underboob"] if bra \
        else ["topless", "nipples", "erect_nipples", "sideboob"]
    torso = acc + leg + bod + ["topless", "nipples", "breast_hold"] + (["no_bra"] if bra else [])
    bare_top = acc + leg + bod + ["topless", "nipples", "breast_hold", "no_bra"] + hem
    off = bare_top + (["panties_around_one_leg", "panty_shot", "pussy", "thighs"] if panties
                      else ["bottomless", "no_panties", "pussy", "thighs"])
    # buoc cuoi cua ladder van con legwear/accessory (co y: tat giu nguyen ca bo)
    # nen khong duoc tag "completely_nude" - de tag do cho block nude rieng da lat het
    nude = ["bottomless", "topless", "nipples", "no_bra", "no_panties", "pussy", "thighs",
            "navel"] + leg + acc
    out = [base + [spice[i % len(spice)]] for i in range(8)]
    out += [base + ["open_clothes", "clothes_lift"],
            base + ["open_clothes", "partially_undressed"] + worn,
            base + ["clothes_pull", "off_shoulder"] + worn,
            base + ["clothes_pull", "partially_undressed"] + leg + worn,
            acc + leg + bod + under,
            acc + leg + bod + unhook,
            acc + leg + bod + unhook2,
            torso + ["covered_nipples", "arms_behind_back"],
            torso + hem + ["cameltoe", "navel"] + pan,
            torso + hem + ["thighs", "navel"] + pan,
            off + ["navel"],
            off,
            nude + ["covering_crotch"],
            nude]
    return [o + ([spice[k % len(spice)]] if 8 <= k < 20 else []) for k, o in enumerate(out)]


SET_CAP = ["she holds the pose and lets the light do the rest",
           "she checks herself on the monitor glass",
           "she laughs and drops a shoulder an inch",
           "she mouths 'like this?' at the lens",
           "she shifts her weight, hands still busy with the hem",
           "the crew calls out a change and she holds the pose",
           "she leans into the light and tips her chin up",
           "she takes the break as a chance to stretch"]
# UND_CAP index = buoc coi k - 9 (k = 9..22), dung thu tu buoc
UND_CAP = ["the fabric starts to move and the camera holds",
           "she pulls the shirt open and leaves it open",
           "she works it off one shoulder first",
           "then off the other arm, sleeve hanging",
           "it drops to her elbows and stays there",
           "she reaches back to get it loose",
           "she peels it down and lets it go",
           "she lets it hang and keeps her arms low",
           "she lifts the hem an inch, then more",
           "a hand slides under the waistband",
           "she works it down over one hip",
           "she drags it off one leg and leaves it hanging",
           "nothing left on her but her own hands",
           "the pile of clothes ends up out of frame"]
BRA_CAP = {5: "she unhooks it behind her back without looking", 6: "she holds the cup in place for one more frame"}
NOBRA_CAP = {5: "she lets the front fall open and does not cover up",
             6: "her nipples stiffen in the cold studio air"}
NOPAN_CAP = {8: "the hem lifts and there is nothing underneath it at all",
             9: "her hand finds nothing to move out of the way",
             10: "the front hangs open, bare underneath",
             11: "she tips her hips and lets it all show",
             12: "nothing on her but her own hands",
             13: "she kicks the whole pile out of frame at the end"}
PREP_CAP = ["the paper backdrop goes up and she walks on in the {f0}",
            "the crew calls the first setup and she fixes her collar",
            "she turns on the spot so the light catches the outfit",
            "the stylist checks the hem and steps out of frame",
            "she laughs at something off camera, still posed"]
NUDE_CAP = ["the last of it is gone and she stays put, arms loose",
            "she turns once, nothing left to take off",
            "she crosses her arms low and looks down the lens",
            "she stands bare in the cold studio air",
            "the crew goes quiet and the shutter keeps firing",
            "she shakes her hair off her shoulder",
            "she keeps still and lets the lens work",
            "the flash fires and she does not flinch",
            "the lens moves around her and she follows it",
            "she pulls the last pin out of her hair, still naked"]
MAST_BASE = [
    (["sitting", "masturbation", "hand_between_legs"], "she sits down and starts slow"),
    (["masturbation", "fingering", "spread_legs"], "two fingers in, hips already rolling"),
    (["masturbation", "spread_legs", "legs_up"], "flat on her back, knees wide"),
    (["spread_pussy", "spread_legs", "fingering"], "she holds herself open for the lens"),
    (["masturbation", "fingering", "arched_back"], "back arching, fingers soaked"),
    (["nipple_stimulation", "breast_hold", "masturbation"], "one hand on her chest, one busy lower"),
    (["hand_between_thighs", "crossed_legs", "masturbation"], "thighs pressed, working herself"),
    (["masturbation", "kneeling", "hand_between_legs"], "she kneels up and rides her own hand"),
    (["fingering", "hand_between_legs", "looking_at_viewer"], "she keeps her eyes on the camera"),
    (["masturbation", "squatting", "spread_legs"], "she squats low and opens herself wide"),
    (["hand_between_legs", "covering_crotch", "masturbation"], "she covers up for a second, then not"),
    (["fingering", "legs_up", "arched_back"], "legs up, wrist deep, no more acting"),
    (["masturbation", "lying", "legs_up"], "she rolls onto her back and keeps going"),
    (["fingering", "sitting_on_chair", "spread_legs"], "knees over the arms of the chair")]
CLIMAX = [
    (["orgasm", "masturbation", "spread_legs"], "orgasm hits and her legs shake"),
    (["orgasm", "fingering", "arched_back"], "orgasm: back bowed up, fingers still inside"),
    (["orgasm", "spread_legs", "legs_up"], "second wave, and she rides it out")]
AFTER = [
    (["afterglow", "lying", "looking_at_viewer"], "afterglow: flat out, chest heaving"),
    (["afterglow", "covered_nipples", "closed_eyes"], "afterglow: knees up, hand still between them"),
    (["afterglow", "lying", "hair_flip"], "afterglow: she rolls onto her side, wet hand through her hair")]
STYLE = {
    "floor": dict(pose="sitting", extra=["spread_legs", "knees_up"], cap="floor setup"),
    "wall": dict(pose="standing", extra=["against_wall", "leg_up"], cap="wall setup"),
    "chair": dict(pose="sitting", extra=["sitting_on_chair", "crossed_legs"], cap="chair setup"),
    "desk": dict(pose="sitting", extra=["sitting_on_desk", "spread_legs"], cap="desk setup"),
    "mirror": dict(pose="standing", extra=["looking_back", "leg_up"], cap="mirror setup"),
    "locker": dict(pose="standing", extra=["leaning_forward", "stretching"], cap="locker setup"),
}
LENS = {
    "doc": "photo_(medium)",
    "intimate": "depth_of_field",
    "pov": "pov",
    "detail": "from_side",
    "above": "from_above",
    "swedish": "from_behind",
}

# code, 3 bo: dong phuc Kuoh (cat gioi tinh) + do dac trung nhan vat + do goi duc, ending, lens
ACTS = [
    ("CHAR_013", ["KUOH_MICRO", "NUN_SEXY", "LINGERIE_LACE"], "floor", "doc"),
    ("CHAR_014", ["KUOH_SLUT_BLAZER", "EXORCIST_SEXY", "FISHNET_PASTIES"], "wall", "intimate"),
    ("CHAR_015", ["KUOH_WET", "ANGEL_SEXY", "BUNNY"], "chair", "pov"),
    ("CHAR_017", ["KUOH_TIGHT", "COUNCIL_SEXY", "LATEX_BONDAGE"], "desk", "detail"),
    ("CHAR_029", ["KUOH_UPSKIRT", "KENDO_SEXY", "GARTER_DRESS"], "mirror", "above"),
    ("CHAR_030", ["KUOH_MICRO", "KENDO_SEXY", "SLINGSHOT_SWIM"], "locker", "swedish"),
    ("CHAR_031", ["KUOH_BACKLESS", "MIKO_SEXY", "NURSE_SEXY"], "floor", "intimate"),
    ("CHAR_052", ["KUOH_SLUT_BLAZER", "KIMONO_SEXY", "SWIM_SEXY"], "wall", "doc"),
    ("CHAR_053", ["KUOH_WET", "MAID_SEXY", "BUNNY"], "chair", "above"),
    ("CHAR_054", ["KUOH_TIGHT", "LIBRARIAN_SEXY", "COMP_SEXY"], "desk", "pov"),
    ("CHAR_055", ["KUOH_UPSKIRT", "JERSEY_SEXY", "APRON_ONLY"], "mirror", "detail"),
    ("CHAR_056", ["KUOH_BACKLESS", "CHEER_SEXY", "GYM_SEXY"], "locker", "swedish"),
]
PER_BLOCK = 22
NUDE_N = 10
PREP_N = 5
MAST_N = 20
FRAME_N = len(FRAME_A)


ROSTER_JSON = {c["code"]: c for c in json.loads(ROSTER.read_text(encoding="utf-8"))["characters"]}


def plan_paths():
    out = {}
    for p in sorted(PLANS.glob("act*_kuoh_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["characters"][0]["code"]] = (p, d)
    return out


def build(act, path, plan):
    code, blocks, end_key, lens_key = act
    ch = plan["characters"][0]
    if code in ROSTER_JSON:          # identity is roster-owned, the plan copy goes stale
        ch["identity_json"] = ROSTER_JSON[code]["identity_json"]
        ch["identity_line"] = ROSTER_JSON[code].get("identity_line", ch.get("identity_line", ""))
    who = ch["name"]
    act_no = plan["act"]["act_no"]
    rng = random.Random(act_no * 977)
    st, lens = STYLE[end_key], LENS[lens_key]
    angles_pool = [lens] + ANGLE_A
    used, shots = set(), []

    def add(phase, outfit, action, expr, cam, caption, pose=None, motion=None):
        refs = wear(outfit)
        body = [r for r in refs if r.rpartition(":")[0] in story_logic.BODY_STATE_IN_OUTFIT]
        shots.append(dict(n=len(shots) + 1, phase=phase, participants=[code],
                          outfit=[r for r in refs if r not in body], body_state=body,
                          action=[T(a) for a in action],
                          expression=[T(e) for e in expr],
                          pose=[T(pose or pose_for(action, st["pose"]))],
                          motion=[T(m) for m in (motion or [])],
                          camera=TL(*cam), cast=[],
                          caption="%s: %s" % (who, caption),
                          beat="%s - %s" % (phase, caption)))

    def stage(a_pool, e_pool, n, start=0, poses=None):
        want = list(poses or [None] * n)
        combos = pool(rng, a_pool, e_pool, FRAME_A)
        out = []
        while combos and len(out) < n:
            a, e, f = combos.pop()
            if not pose_ok(a, want[len(out)]) or not look_ok((a, e)):
                continue
            key = "|".join((a, e, f))
            if key in used:
                continue
            used.add(key)
            out.append((a, e, f))
        if len(out) < n:      # pool het: noi ro chu khong am tham ha chuan pose
            raise SystemExit("pool het cho %d shot pose %s (%d/%d) - noi rong pool"
                             % (n, sorted(set(want)), len(out), n))
        angles = shuffle(rng, angles_pool)
        return [(a, e, [f, angles[(start + i) % len(angles)]]) for i, (a, e, f) in enumerate(out)]

    pP = stage(PREP_A, E_SOFT, PREP_N)
    for k, (a, e, c) in enumerate(pP):
        add("chuan bi", F[blocks[0]]["dressed"], [a], [e], c,
            PREP_CAP[k].format(f0=blocks[0].lower().replace("_", " ")),
            pose="standing", motion=["floating_hair"])

    for bi, fam in enumerate(blocks):
        phase = "set%d_%s" % (bi + 1, fam.lower())
        cues = F[fam]["cues"]
        bra = "no_bra" not in F[fam]["dressed"]
        panties = "no_panties" not in F[fam]["dressed"]
        caps = BRA_CAP if bra else NOBRA_CAP
        if not panties:
            caps = {**caps, **NOPAN_CAP}
        cD = stage(actions_for(fam, DRES_A), E_SET, 8, start=bi * 5, poses=POSE_ARC[:8])
        cA = stage(actions_for(fam, UND_A), E_SET, 4, start=bi * 5 + 1, poses=POSE_ARC[8:12])
        cB = stage(actions_for(fam, UND_B), E_SET, 3, start=bi * 5 + 2, poses=POSE_ARC[12:15])
        cC = stage(actions_for(fam, UND_C), E_SET, 3, start=bi * 5 + 3, poses=POSE_ARC[15:18])
        cE = stage(actions_for(fam, NUD_A), E_HOT, 4, start=bi * 5 + 4, poses=POSE_ARC[18:])
        for k, outfit in enumerate(ladder(fam), 1):
            if k <= 8:
                a, e, c = cD[k - 1]
                cap = "%s -- %s" % (cues[0], SET_CAP[k - 1])
            else:
                if k <= 12:
                    a, e, c = cA[k - 9]
                elif k <= 15:
                    a, e, c = cB[k - 13]
                elif k <= 18:
                    a, e, c = cC[k - 16]
                else:
                    a, e, c = cE[k - 19]
                cap = "%s -- %s" % (cues[2] if k == PER_BLOCK else cues[1],
                                    caps.get(k - 9, UND_CAP[k - 9]))
            pose = POSE_ARC[k - 1]
            motion = ["floating_hair"] if pose == "standing" else []
            add(phase, outfit, [a], [e], c, cap, pose=pose, motion=motion)

    nude_out = ["completely_nude", "nude", "bottomless", "no_bra", "no_panties", "pussy", "thighs",
                "navel"]
    for j, (a, e, c) in enumerate(stage(NUD_A, E_HOT, NUDE_N, start=5, poses=NUDE_ARC)):
        add("nude", nude_out + [NUDE_EX[j]], [a], [e], c, NUDE_CAP[j], pose=NUDE_ARC[j])

    pM = pool(rng, E_HOT, FRAME_A)
    angles = shuffle(rng, angles_pool)
    def rotate(pairs):        # van doi thu tu theo act de 12 act khong giong nhau
        return [pairs[(act_no + i) % len(pairs)] for i in range(len(pairs))]
    mast = ([(MAST_BASE[i], p) for i, p in MAST_KNEE] +        # squat -> kneel: thu tu co dinh
            [(MAST_BASE[i], p) for i, p in rotate(MAST_SIT)] +
            [(MAST_BASE[i], p) for i, p in rotate(MAST_LIE)] +
            [(e, "lying") for e in CLIMAX + AFTER])
    assert len(mast) == MAST_N, len(mast)
    for k, ((actions, cap), pose) in enumerate(mast):
        look = any(a.startswith("looking") for a in actions)
        e, f = take(pM, 1, used, key=lambda x: ",".join(actions) + "|" + x[0] + "|" + x[1],
                    ok=lambda x: not (look and x[0] == "closed_eyes"))[0]
        c = [f, angles[k % len(angles)]]
        mo = ["trembling", "heavy_breathing"] if MAST_N - 8 <= k < MAST_N - 5 else \
            (["heavy_breathing"] if k >= MAST_N - 5 else ["sweat"])
        extra = st["extra"] if pose == st["pose"] else []
        add("thu_dam", nude_out + ["wet_pussy"] + extra, actions, [e], c,
            "%s (%s)" % (cap, st["cap"]), pose=pose,
            motion=(["floating_hair"] if pose == "standing" else []) + mo)

    plan["act"] = dict(act_no=act_no,
                       title="Act %d - Photoshoot: %s - %s (%s) -> nude (%d) -> thu dam (%s, %d)"
                             % (act_no, who, " + ".join(blocks), lens_key, NUDE_N, end_key, MAST_N),
                       outline="3 bo: %s (moi bo %d shot: 8 mac + 14 coi dan tung lop, noi y noi ro "
                               "bra/panties o moi buoc coi). Bo 1 luon la dong phuc Kuoh cat gioi tinh, "
                               "bo 2 la do dac trung nhan vat, bo 3 do goi duc. Nude %d shot, ket bang "
                               "thu dam kieu %s (%d shot)."
                               % (" + ".join(blocks), PER_BLOCK, NUDE_N, end_key, MAST_N),
                       revision=plan["act"].get("revision", 1), status="planned")
    plan["shots"] = shots
    ch["outfit_json"] = dict(ch["outfit_json"],
                             **{fam.lower(): wear(F[fam]["dressed"]) for fam in blocks},
                             nude=TL("completely_nude"))
    return plan


ORDER = wardrobe.STANCE_ORDER   # cung bang voi seed_plan dung khi seed

def check_plan(plan):
    """2 bat bien cua bo 12 act: (1) trong 1 phase tu the chi di xuong theo thang
    dung -> quy -> ngoi -> nam, (2) moi tag do deu co tag mau di kem."""
    bad = []
    phase, last = None, -1
    for sh in plan["shots"]:
        names = [x.split(":")[0] for x in sh["pose"]]
        stance = max(ORDER.get(n, -1) for n in names)
        if sh["phase"] != phase:          # phase moi = bo/cut moi, thang tu the bat dau lai
            phase, last = sh["phase"], -1
        if stance < last:
            bad.append("shot %d %s: tu the lui %s -> %s" % (sh["n"], sh["phase"], last, stance))
        last = max(last, stance)
    if bad:
        raise SystemExit("plan hong:\n  " + "\n  ".join(bad[:20]))

def main():
    if "--allow-legacy-random" not in sys.argv:
        raise SystemExit("Unsafe legacy generator: action/expression are randomly combined with fixed captions. "
                         "Use etl/build_story_plan.py (beats -> shots), or explicitly pass "
                         "--allow-legacy-random for historical reproduction; review resulting plans.")
    sys.argv.remove("--allow-legacy-random")
    for code, *rest in ACTS:
        path, plan = PATHS[code]
        new = build((code, *rest), path, plan)
        check_plan(new)
        path.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
        print("%s %s shots=%d" % (path.name, code, len(new["shots"])))
    worn = {x.split(":")[0] for sh in new["shots"] for x in sh["outfit"]}
    picked = {n for n in worn if wardrobe.colour_of(n)[0]}
    cued = sorted({n for n in worn if n.endswith("_clothing")})
    undecided = sorted(n for n in worn - picked if TABLE.get(IDS.get(n, 0), {}).get("base") == n)
    print("mau do: %d mon dung mau cu the | cue chung: %s | chua chon mau: %s"
          % (len(picked), cued, undecided or "khong"))


PATHS = plan_paths()
if __name__ == "__main__":
    main()
