# -*- coding: utf-8 -*-
"""Nap outfit_json cho character_profile con thieu (roster Blue Archive tu blue_archive.md).

Nguon du lieu (chi tag that trong catalog):
  1. costume trong identity tag: `asuna_(bunny)_(blue_archive)` -> COSTUME['bunny'] = playboy_bunny
  2. do mac co role 'outfit' nhung khong phai identity/background (hat, headwear, goggles...)
  3. nhan vat base khong co costume -> school_uniform, danh dau "assumed" de phase 1 sua
Khong bia tag: tu nao khong map duoc thi ghi vao report.

Usage: python etl/add_ba_outfits.py [--apply] [--code ba_]
"""
import argparse, collections, json, pathlib, re, sqlite3, sys

from novel2anima.catalog import build_service as build
from novel2anima.paths import CHARACTERS_DIR, DB_PATH

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = CHARACTERS_DIR / "ba_outfits.json"
COSTUME = {"swimsuit": "swimsuit", "dress": "dress", "bunny": "playboy_bunny",
           "track": "track_uniform", "maid": "maid", "school_uniform": "school_uniform",
           "pajamas": "pajamas", "cheer_squad": "cheerleader",
           "kindergarten_uniform": "kindergarten_uniform", "bodysuit": "bodysuit",
           "new_year": "kimono", "band": "band_uniform", "idol": "idol_clothes",
           "halloween": "halloween_costume", "hot_spring": "yukata", "robot": "mecha"}
HEAD = ("hat", "headwear", "beret", "cap", "visor", "goggles", "sunglasses", "glasses",
        "helmet", "hood", "eyewear")
SKIP_WORDS = {"small", "young", "first_year", "armed", "camp", "cycling", "guide"}

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--export", action="store_true", help="xuat roster (identity+outfit) ra json")
    ap.add_argument("--code", default="ba_")
    args = ap.parse_args(argv)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    roles = collections.defaultdict(set)
    for tid, r in con.execute("SELECT tag_id, role FROM tag_role"):
        roles[tid].add(r)
    by_name = {r["canonical_name"]: (r["id"], r["post_count"]) for r in
               con.execute("SELECT id, canonical_name, post_count FROM tag")}

    def is_outfit(name):
        t = by_name.get(name)
        return bool(t) and "outfit" in roles[t[0]] and not ({"identity", "background"} & roles[t[0]])

    ba_tags = [r["canonical_name"] for r in con.execute(
        "SELECT canonical_name FROM tag WHERE canonical_name LIKE '%(blue\\_archive)' ESCAPE '\\'")]
    variants_by_base = collections.defaultdict(list)
    for name in ba_tags:
        for i, ch in enumerate(name):
            if name.startswith("_(blue_archive)"):
                break
        m2 = re.match(r"^(.+?)_\(([a-z0-9_]+)\)_\(blue_archive\)$", name)
        if m2:
            variants_by_base[m2.group(1) + "_(blue_archive)"].append(name)

    rows = con.execute("SELECT id, code, identity_json, outfit_json FROM character_profile"
                       " WHERE code LIKE ? ORDER BY code", (args.code + "%",)).fetchall()
    report = {"filled": 0, "assumed": 0, "empty": [], "unmapped_word": [], "items": {}}
    plan = []
    for r in rows:
        cur = json.loads(r["outfit_json"] or "{}")
        if cur:
            continue
        ident = json.loads(r["identity_json"] or "{}")
        tags = ident.get("identity_tags") or []
        first = tags[0] if tags else ""
        m = re.match(r"^(.+?)_\(([a-z0-9_]+)\)_\(blue_archive\)$", first)
        word = m.group(2) if m else None
        anchor = COSTUME.get(word) if word else None
        if anchor and anchor not in by_name:
            anchor = None
        names = list(dict.fromkeys((ident.get("core_tags") or []) + (ident.get("attributes") or [])))
        extra = [n for n in names if is_outfit(n) and any(h in n for h in HEAD)]
        extra = sorted(dict.fromkeys(extra), key=lambda n: -by_name[n][1])[:1]   # 1 mon tren dau
        default = [anchor] if anchor else []
        default += [n for n in extra if n != anchor]
        assumed = None
        if not anchor:
            default = ["school_uniform"] + default
            assumed = "school_uniform"          # nhan vat base: mac dinh dong phuc, phase 1 xac nhan
        base_tag = (m.group(1) + "_(blue_archive)") if m else first
        variants = [v for v in sorted(variants_by_base.get(base_tag, ())) if v != first]
        outfit = {"default": ["%s:%d" % (n, by_name[n][0]) for n in default],
                  "nude": ["completely_nude:%d" % by_name["completely_nude"][0]],
                  "source": ("costume:" + word) if anchor else "assumed_school_uniform"}
        if assumed:
            outfit["assumed"] = assumed
        if variants:
            outfit["variants"] = variants[:8]
        if word and not anchor and word not in SKIP_WORDS:
            report["unmapped_word"].append("%s (%s)" % (word, r["code"]))
        if not default:
            report["empty"].append(r["code"])
        report["filled"] += 1
        report["assumed"] += 1 if assumed else 0
        plan.append((r["id"], r["code"], outfit))
        report["items"][r["code"]] = [n for n in default]

    print("profile thieu outfit: %d | nap: %d (assumed=%d) | rong: %d | word chua map: %d"
          % (len(rows), report["filled"], report["assumed"], len(report["empty"]),
             len(report["unmapped_word"])))
    if not plan:                       # chay lai: giu report cu, chi bao trang thai
        print("tat ca profile da co outfit (khong co gi de nap)")
    for k, v in list(report["items"].items())[:10]:
        print("  %-34s %s" % (k, ", ".join(v)))
    if report["unmapped_word"]:
        print("  word chua map:", ", ".join(report["unmapped_word"][:12]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    st = {"profiles": len(rows), "with_outfit": 0, "assumed": 0, "empty": [],
          "items": {}, "unmapped_word": report["unmapped_word"]}
    for r in con.execute("SELECT code, outfit_json FROM character_profile WHERE code LIKE ?"
                         " ORDER BY code", (args.code + "%",)):
        o = json.loads(r["outfit_json"] or "{}")
        st["with_outfit"] += 1 if o else 0
        st["assumed"] += 1 if o.get("assumed") else 0
        if not o:
            st["empty"].append(r["code"])
        st["items"][r["code"]] = [x.split(":")[0] for x in o.get("default") or []]
    OUT.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("report:", OUT)
    if not args.apply:
        print("dry-run: them --apply de ghi character_profile.outfit_json")
        return 0
    with con:
        for pid, code, outfit in plan:
            con.execute("UPDATE character_profile SET outfit_json=? WHERE id=?",
                        (json.dumps(outfit, ensure_ascii=False), pid))
    print("da ghi %d profile" % len(plan))
    if args.export:
        out = OUT.with_name("ba_roster.json")
        data = []
        for r in con.execute("SELECT code, identity_json, outfit_json FROM character_profile"
                             " WHERE code LIKE ? ORDER BY code", (args.code + "%",)):
            ident = json.loads(r["identity_json"] or "{}")
            data.append({"code": r["code"], "name": ident.get("name"),
                         "identity_json": ident, "outfit_json": json.loads(r["outfit_json"] or "{}")})
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        print("roster:", out, "(%d nhan vat)" % len(data))
    return 0

if __name__ == "__main__":
    sys.exit(main())
