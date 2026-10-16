# -*- coding: utf-8 -*-
"""Soat prompt cua mot act truoc khi render: file vs db, cu phap Anima, tag thieu/thua,
xung dot, so nguoi, do dai, trung lap, negative file, va cac van de da ghi trong shot_state.

Usage:
  python etl/check_prompts.py [--act N] [--examples K]
  Thu tu: seed_plan -> qa_shots --apply -> check_prompts

Exit 1 khi co ERROR. Read-only: khong sua prompt, khong ghi db.
"""
import argparse, collections, glob, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAX_TOKENS = 80
NEG_REQUIRED = ("worst quality", "low quality", "blurry")

def tag_text(name):
    name = name.strip()
    return name if name.startswith("score_") else name.replace("_", " ")

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--act", type=int)
    ap.add_argument("--examples", type=int, default=6, help="so vi du in ra moi loai loi")
    args = ap.parse_args(argv)

    con = build.connect(build.DB_PATH)
    edges = collections.defaultdict(list)
    for f, t in con.execute("SELECT from_tag_id, to_tag_id FROM tag_relation WHERE relation='implies'"):
        edges[f].append(t)
    compat = {frozenset((a, b)) for a, b in con.execute(
        "SELECT from_tag_id, to_tag_id FROM tag_relation WHERE relation='compatible'")}
    conflicts = collections.defaultdict(set)
    for a, b, note in con.execute("SELECT from_tag_id, to_tag_id, note FROM tag_relation"
                                  " WHERE relation='conflicts'"):
        # "not to be confused" hoac cap nay cung co quan he compatible -> chi la nhac nho
        sev = "WARN" if (note and "confused" in note) or frozenset((a, b)) in compat else "ERROR"
        conflicts[a].add((b, sev))
        conflicts[b].add((a, sev))

    def closure(tid):
        seen, stack = set(), [tid]
        while stack:
            for m in edges.get(stack.pop(), ()):
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        return seen

    plans = {}
    for f in glob.glob("data/plans/*.json"):
        d = json.load(open(f, encoding="utf-8-sig")) or {}
        no = (d.get("act") or {}).get("act_no")
        if no and d.get("shots"):
            plans[no] = d

    acts = con.execute("SELECT id, act_no FROM act%s ORDER BY act_no"
                       % (" WHERE act_no=%d" % args.act if args.act else "")).fetchall()
    total = collections.Counter()
    for aid, act_no in acts:
        rows = con.execute("SELECT id, shot_no, shot_spec_json FROM shot WHERE act_id=?"
                           " ORDER BY shot_no", (aid,)).fetchall()
        errs, warns, seen_at = [], [], collections.defaultdict(list)
        plan = plans.get(act_no)
        lines = []
        if not plan:
            warns.append((0, "", "khong co file plan local -> khong doi chieu duoc prompt file"))
        else:
            pf = pathlib.Path(plan["prompt_file"])
            if not pf.exists():
                errs.append((0, "", "thieu prompt file %s" % pf))
            else:
                lines = [b.strip() for b in pf.read_text(encoding="utf-8").split("\n\n") if b.strip()]
                if len(lines) != len(rows):
                    errs.append((0, "", "prompt file %d dong != db %d shot" % (len(lines), len(rows))))
            neg = pf.with_name(pf.stem + ".neg.txt")
            if not neg.exists() or not neg.read_text(encoding="utf-8").strip():
                errs.append((0, "", "thieu/rong negative file %s" % neg))
            else:
                body = neg.read_text(encoding="utf-8").lower()
                miss = [t for t in NEG_REQUIRED if t not in body]
                if miss:
                    warns.append((0, "", "negative thieu %s" % ", ".join(miss)))

        sig_seq = []
        for i, (shot_id, shot_no, spec_json) in enumerate(rows):
            spec = json.loads(spec_json)
            phase = spec.get("phase", "")
            text = spec.get("prompt", "")
            if i < len(lines) and lines[i] != text:
                errs.append((shot_no, phase, "prompt trong file khac shot_spec_json (drift)"))
            caption = spec.get("caption") or ""
            tag_zone = text.split(caption)[0] if caption and caption in text else text
            tag_zone = tag_zone.rstrip().rstrip(",").strip()   # bo dau phay cuoi cua phan tag
            toks = [t.strip() for t in tag_zone.split(",")]   # caption/NL la cau, khong phai tag
            words = set(toks)
            for t in toks:
                if not t:
                    errs.append((shot_no, phase, "co dau phay rong lien tiep"))
                    continue
                if "_" in t and not t.startswith("score_"):
                    errs.append((shot_no, phase, "tag con underscore: %s" % t))
                if t != t.lower() and not t.startswith("@"):
                    warns.append((shot_no, phase, "tag viet hoa: %s" % t))
                if "  " in t:
                    warns.append((shot_no, phase, "khoang trang doi: %s" % t))
            refs = [(x["name"], x["tagId"]) for g in
                    ("identity", "outfit", "action", "expression", "pose", "motion", "camera", "cast")
                    for x in spec.get(g) or []]
            refs += [(x["name"], x["tagId"]) for tx in spec.get("participants") or []
                     for x in tx.get("expression") or []]
            inside = {tid for name, tid in refs if tag_text(name) in words}   # tag co mat trong prompt
            all_ids = {tid for _name, tid in refs}
            pruned = set()                                   # seed bo tag bi tag khac imply
            for tid in all_ids:
                pruned |= closure(tid) & (all_ids - {tid})
            for name, tid in refs:
                if tag_text(name) not in words and tid not in pruned:
                    errs.append((shot_no, phase, "tag thieu trong prompt: %s" % name))
            for tid in inside:
                red = closure(tid) & (inside - {tid})
                if red:
                    names = {r[0]: r[1] for r in con.execute(
                        "SELECT id, canonical_name FROM tag WHERE id IN (%s)"
                        % ",".join(str(x) for x in red))}
                    errs.append((shot_no, phase, "tag bi imply boi tag khac: %s"
                                 % ", ".join(sorted(names.values()))))
                    break
            ids = inside
            for tok, n in collections.Counter(toks).items():
                if n > 1:
                    warns.append((shot_no, phase, "tag lap %d lan trong prompt: %s" % (n, tok)))
            for tid in ids:
                for other, sev in conflicts.get(tid, ()):
                    if other in ids and tid < other:
                        names = {r[0]: r[1] for r in con.execute(
                            "SELECT id, canonical_name FROM tag WHERE id IN (%d,%d)" % (tid, other))}
                        msg = "xung dot: %s" % " vs ".join(names.values())
                        (errs if sev == "ERROR" else warns).append((shot_no, phase, msg))
            codes = [c.get("code") for c in spec.get("participants") or []]
            gender = {c["code"]: c.get("gender", "girl") for c in (plan or {}).get("characters") or []}
            girls = sum(1 for c in codes if gender.get(c, "girl") == "girl")
            boys = len(codes) - girls
            want = {"%dgirl" % girls if girls == 1 else "%dgirls" % girls}
            if girls > 1 and boys == 0:
                want.add("yuri")
            if boys == 1:
                want.add("1boy")
            elif boys > 1:
                want.update({"multiple boys", "%dboys" % boys})
            if girls == 0:
                want = {"%dboys" % boys} if boys else set()
            if want and not (want & words):
                warns.append((shot_no, phase, "thieu dong so nguoi (%s)" % "/".join(sorted(want))))
            if not spec.get("action"):
                warns.append((shot_no, phase, "ACTION_UNRESOLVED"))
            if not spec.get("expression"):
                warns.append((shot_no, phase, "EXPRESSION_UNRESOLVED"))
            if not spec.get("pose"):
                warns.append((shot_no, phase, "POSE_UNRESOLVED"))
            if len(toks) > MAX_TOKENS:
                warns.append((shot_no, phase, "prompt dai %d token (>%d)" % (len(toks), MAX_TOKENS)))
            if text in seen_at:
                warns.append((shot_no, phase, "prompt trung shot %s" % seen_at[text][0]))
            seen_at[text].append(shot_no)
            sig_seq.append(spec.get("signature") or
                           ",".join(x["name"] for x in (spec.get("action") or [])))
            if len(sig_seq) >= 4 and len(set(sig_seq[-4:])) == 1:
                warns.append((shot_no, phase, "action lap 4 shot lien tiep"))

        for shot_no, axis, tid, sev, src in con.execute(
                "SELECT s.shot_no, st.axis, st.value_tag_id, st.severity, st.source FROM shot_state st"
                " JOIN shot s ON s.id=st.shot_id WHERE s.act_id=?"
                " AND st.source IN ('qa:v1', 'qa:llm:v1')", (aid,)):
            if src.endswith("llm:v1"):      # soat cua LLM = y kien tham khao, phai kiem chung -> WARN
                warns.append((shot_no, "", "%s sev %.1f" % (axis, sev)))
                continue
            name = con.execute("SELECT canonical_name FROM tag WHERE id=?", (tid,)).fetchone()
            row = (shot_no, "", "%s (%s, sev %.1f)" % (axis, name[0] if name else tid, sev))
            (errs if axis == "noi_dung_chan" else warns).append(row)

        total["err"] += len(errs)
        total["warn"] += len(warns)
        total["act"] += 1
        print("act %02d  %3d shot  %d error  %d warn" % (act_no, len(rows), len(errs), len(warns)))
        for tag, bucket in (("ERROR", errs), ("WARN", warns)):
            for shot_no, phase, msg in bucket[:args.examples]:
                print("  %-5s shot %-4s %-16s %s" % (tag, shot_no, phase[:16], msg))
            if len(bucket) > args.examples:
                print("  %-5s ... con %d %s" % (tag, len(bucket) - args.examples, tag))
    print("\n%d act, %d error, %d warn" % (total["act"], total["err"], total["warn"]))
    con.close()
    return 1 if total["err"] else 0

if __name__ == "__main__":
    sys.exit(main())
