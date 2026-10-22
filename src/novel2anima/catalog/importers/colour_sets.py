# -*- coding: utf-8 -*-
"""Bien kien thuc mau do thanh du lieu trong catalog (khong doi schema).

Usage: python etl/import_colour_sets.py [--apply] [--min-post 20]

Voi moi mon do (tag do) co bien the mau trong catalog:
  * visual_concept code WC_<do>, kind='other'  = bang mau cua mon do do
  * concept_tag.usage='primary'      -> tag do goc (vd thighhighs)
  * concept_tag.usage='alternative'  -> tung bien the mau that (black_thighhighs...)
  * priority 1 = mau dang dung, lay tu chinh cac act da seed (shot_spec_json);
    cac mau con lai xep theo post_count. Do khong co bien the mau trong catalog thi
    lay cue <mau>_clothing tu data/wardrobe/colour_cue.json (bo mau chuan bi cho phase 1).

Nho vay seed_plan/wardrobe doc mau tu DB, khong con bang mau hard-code trong code.
"""
import argparse, collections, json, os, pathlib, re, sys, time

from novel2anima.catalog import build_service as build
from novel2anima.paths import WARDROBE_DIR

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CUE_FILE = str(WARDROBE_DIR / "colour_cue.json")
CHOICE_FILE = str(WARDROBE_DIR / "colour_choice.json")   # bo mau chuan bi cho phase 1 (nguoi chon)
COLOURS = ("white", "black", "blue", "red", "pink", "grey", "gray", "brown", "silver",
           "blonde", "purple", "green", "yellow", "orange", "tan")

def colour_of(name):
    for c in COLOURS:
        if name.startswith(c + "_"):
            return c, name[len(c) + 1:]
    return None, None

def chosen_from_acts(con):
    """mau dang dung cho tung mon do = cap (do goc, bien the mau) xuat hien nhieu nhat trong cac act"""
    tally = collections.Counter()
    for (spec,) in con.execute("SELECT shot_spec_json FROM shot"):
        try:
            outfit = json.loads(spec).get("outfit") or []
        except ValueError:
            continue
        worn = [x["name"] for x in outfit]
        bases = {b for _c, b in (colour_of(n) for n in worn) if b}
        for n in worn:
            c, base = colour_of(n)
            if c and base and base in bases:
                tally[(base, n)] += 1
    return tally

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--min-post", type=int, default=20)
    args = ap.parse_args(argv)

    con = build.connect(build.DB_PATH)
    con.isolation_level = None
    con.execute("PRAGMA journal_mode=WAL")
    ep = time.time()

    ids = {r[0]: r[1] for r in con.execute("SELECT canonical_name, id FROM tag")}
    pcs = {r[0]: r[1] for r in con.execute("SELECT canonical_name, post_count FROM tag")}

    # "mon do" = tag co tag_role='outfit' (hoac do da chuan bi cue trong colour_cue.json).
    # role='outfit' mot minh khong du: navel/thighs cung bi gan outfit, nen bien the
    # mau cung phai co role='outfit' (white_thighs/blue_navel khong co -> khong phai do mac).
    role_outfit = {r[0] for r in con.execute("SELECT t.canonical_name FROM tag_role r"
                                             " JOIN tag t ON t.id=r.tag_id WHERE r.role='outfit'")}
    cue_raw = json.loads(pathlib.Path(CUE_FILE).read_text(encoding="utf-8")) \
        if os.path.exists(CUE_FILE) else {}
    cue = {k: v for k, v in cue_raw.items() if k in ids and ("%s_clothing" % v) in ids}
    choice_raw = json.loads(pathlib.Path(CHOICE_FILE).read_text(encoding="utf-8")) \
        if os.path.exists(CHOICE_FILE) else {}
    choice = {k: v for k, v in choice_raw.items()
              if k in ids and ("%s_%s" % (v, k)) in ids}
    garments = role_outfit | set(cue)

    variants = {}                       # base -> [(colour, variant_tag, post_count)]
    for name, pc in pcs.items():
        c, base = colour_of(name)
        if c and base in ids and base in garments and name in role_outfit and pc >= args.min_post:
            variants.setdefault(base, []).append((c, name, pc))
    # mau da chuan bi (data/wardrobe/colour_choice.json) duoc tin: bien the khong co role='outfit'
    # van duoc dung lam lua chon phase 1
    for base, c in choice.items():
        if base in garments:
            v = "%s_%s" % (c, base)
            if v in ids and v not in [x[1] for x in variants.get(base, [])]:
                variants.setdefault(base, []).append((c, v, pcs.get(v, 0)))
    for base in variants:
        variants[base].sort(key=lambda x: -x[2])

    # mau dang dung: bo mau chuan bi (phase 1) thang mau suy ra tu cac act
    chosen = {k: "%s_%s" % (v, k) for k, v in choice.items()}   # do -> ten bien the mau da chuan bi
    for (base, variant), n in chosen_from_acts(con).most_common():
        chosen.setdefault(base, variant)          # mau suy ra tu act (neu chua chuan bi)


    print("mon do co bien the mau trong catalog: %d | do co cue chuan bi: %d | da chon mau tu act: %d"
          % (len(variants), len(cue), len(chosen)))
    unknown = sorted(b for b in set(cue) - set(chosen) if b not in variants)
    if unknown:
        print("cue su dung cho do khong co bien the mau: %s" % unknown)
    if not args.apply:
        print("dry-run: them --apply de ghi vao db")
        con.close()
        return

    con.execute("BEGIN")
    keep = sorted({"WC_%s" % b for b in set(variants) | set(cue)})
    ph = ",".join("?" * len(keep))
    stale = ("code LIKE ? AND code NOT IN (%s)" % ph,)
    gone = con.execute("SELECT count(*) FROM visual_concept WHERE " + stale[0],
                       ("WC%",) + tuple(keep)).fetchone()[0]
    con.execute("DELETE FROM visual_concept WHERE " + stale[0], ("WC%",) + tuple(keep))
    made = set_ct = 0
    for base in sorted(set(variants) | set(cue)):
        code = "WC_%s" % base
        opts = [v for _c, v, _pc in variants.get(base, [])]
        desc = "mau do co trong catalog: %s" % ", ".join(opts[:12]) if opts else "khong co bien the mau that"
        meta = {"garment": base, "tag_id": ids[base], "chosen": chosen.get(base),
                "cue": ("%s_clothing" % cue[base]) if base in cue else None,
                "colours": [c for c, _v, _pc in variants.get(base, [])]}
        row = con.execute("SELECT id FROM visual_concept WHERE code=?", (code,)).fetchone()
        if row:
            cid = row[0]
            con.execute("UPDATE visual_concept SET name=?, description=?, metadata_json=?, kind='other' WHERE id=?",
                        (base, desc, json.dumps(meta, ensure_ascii=False), cid))
            con.execute("DELETE FROM concept_tag WHERE concept_id=?", (cid,))
        else:
            cur = con.execute("INSERT INTO visual_concept(code, kind, name, description, search_terms,"
                              " content_scope, review_status, metadata_json)"
                              " VALUES(?,?,?,?,?,?,?,?)",
                              (code, "other", base, desc, "%s colour mau %s" % (base, " ".join(opts[:12])),
                               "neutral", "draft", json.dumps(meta, ensure_ascii=False)))
            cid = cur.lastrowid
            made += 1
        con.execute("INSERT INTO concept_tag(concept_id, tag_id, usage, priority) VALUES(?,?,?,?)",
                    (cid, ids[base], "primary", 1))
        pick = chosen.get(base)
        for i, (_c, v, _pc) in enumerate(variants.get(base, [])):
            con.execute("INSERT INTO concept_tag(concept_id, tag_id, usage, priority) VALUES(?,?,?,?)",
                        (cid, ids[v], "alternative", 1 if v == pick else 100 + i))
            set_ct += 1
        if base in cue:
            con.execute("INSERT INTO concept_tag(concept_id, tag_id, usage, priority) VALUES(?,?,?,?)",
                        (cid, ids["%s_clothing" % cue[base]], "alternative", 2))
            set_ct += 1
    con.execute("INSERT INTO visual_concept_fts(visual_concept_fts) VALUES('rebuild')")
    con.commit()
    print("concept moi: %d | xoa %d concept khong con la do mac | concept_tag: %d | %.1fs"
          % (made, gone, set_ct, time.time() - ep))
    print("visual_concept %d | concept_tag %d | fts %d"
          % (con.execute("SELECT count(*) FROM visual_concept").fetchone()[0],
             con.execute("SELECT count(*) FROM concept_tag").fetchone()[0],
             con.execute("SELECT count(*) FROM visual_concept_fts").fetchone()[0]))
    con.close()

if __name__ == "__main__":
    main()
