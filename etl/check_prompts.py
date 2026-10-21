# novel2anima P0P1 upgrade
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
import build, story_db, story_logic

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAX_TOKENS = 80
NEG_REQUIRED = ("worst quality", "low quality", "blurry")

def tag_text(name):
    name = name.strip()
    return name if name.startswith("score_") else name.replace("_", " ")

def prompt_body(text, caption):
    """Phan tag cua prompt, bo caption + role clause phia sau caption."""
    if caption and caption in text:
        return text.split(caption, 1)[0].rstrip(" ,")
    return text.rstrip(" ,")

def caption_prompt_issues(caption, words, codes, gender):
    """Caption says something the tag zone/cast cannot show."""
    out = []
    if re.search(r'\bopen (?:blouse|shirt)\b', caption, re.I):
        if not ({'open clothes', 'open shirt', 'open blouse', 'unbuttoned'} & words):
            out.append('CAPTION_OPEN_CLOTHES_UNBOUND: caption says open blouse/shirt')
    if re.search(r'\b(?:crowd|onlookers)\b', caption, re.I) and \
            not ({'crowd', 'onlookers'} & words):
        out.append('CAPTION_CROWD_UNBOUND: caption mentions a crowd')
    if len(codes) > 1:
        others = codes[1:]
        if re.search(r'\b(?:a|another|the) (?:woman|girl)\b', caption, re.I) and \
                all(gender.get(c, 'girl') != 'girl' for c in others):
            out.append('CAPTION_CAST_GENDER: caption says woman but secondary cast is male')
        if re.search(r'\b(?:a|another|the) (?:man|boy)\b', caption, re.I) and \
                all(gender.get(c, 'girl') == 'girl' for c in others):
            out.append('CAPTION_CAST_GENDER: caption says man but secondary cast is female')
    return out


def clause_map(text, caption):
    """Role clauses after the caption: {'Name': 'token, token, ...'}."""
    body = text.split(caption, 1)[1] if caption and caption in text else text
    out = {}
    for entry in body.split(";"):
        if ":" not in entry:
            continue
        name, _, tokens = entry.partition(":")
        name = name.strip().rstrip(".").strip()
        if name and len(name.split()) <= 3:   # role clause names, not sentences
            out.setdefault(name, tokens.strip())
    return out


def _template_for(action):
    """Same template lookup as seed_plan.directed_clause, QA side."""
    action = str(action or "").strip().lower()
    tpl = story_logic.DIRECTED_CLAUSE_TEMPLATES.get(action)
    if not tpl:
        grp = story_logic.ALIAS_INDEX.get(action)
        if grp is not None:
            for cand in story_logic.ALIAS_GROUPS[grp]:
                if cand in story_logic.DIRECTED_CLAUSE_TEMPLATES:
                    tpl = story_logic.DIRECTED_CLAUSE_TEMPLATES[cand]
                    break
    return tpl


def interaction_prompt_issues(spec, text, names):
    """Prompt must not contradict the certified interaction direction.

    Reads `spec['interaction']` (written by seed_plan from the validated
    `sequence`), never caption wording alone:
      * ERROR INTERACTION_PROMPT_DIRECTION_MISMATCH - the declared TARGET's
        role clause claims the primary action and names the actor while the
        actor has no role clause at all (the classic reversed-prompt shape).
      * WARN  INTERACTION_PROMPT_DIRECTION_SOFT - target claims it though an
        actor clause exists without it (legacy ambiguous ownership rows).
      * WARN  missing directed seed clause for actions that have a template.
    """
    out = []
    ia = spec.get("interaction") or {}
    if not isinstance(ia, dict):
        return out
    actor, target, action = ia.get("actor"), ia.get("target"), str(ia.get("action") or "")
    if not (actor and target and action) or actor == target:
        return out
    actor_name, target_name = names.get(actor), names.get(target)
    if not actor_name or not target_name or actor_name == target_name:
        return out
    token = re.escape(action.replace("_", " "))
    clauses = clause_map(text, spec.get("caption") or "")
    target_tokens = clauses.get(target_name, "")
    claims_reversal = bool(target_tokens
                           and re.search(r'\b%s\b' % token, target_tokens, re.I)
                           and "interacting with " + actor_name in target_tokens)
    if claims_reversal:
        if actor_name not in clauses:
            out.append("INTERACTION_PROMPT_DIRECTION_MISMATCH: prompt shows %s "
                       "performing %s but sequence actor is %s (no %s clause)"
                       % (target_name, action, actor_name, actor_name))
        elif not re.search(r'\b%s\b' % token, clauses.get(actor_name, ""), re.I):
            out.append("warn:INTERACTION_PROMPT_DIRECTION_SOFT: %s clause claims "
                       "%s; sequence actor is %s" %
                       (target_name, action, actor_name))
    tpl = _template_for(action)
    if tpl:
        expected = "%s %s." % (actor_name, tpl.format(t=target_name))
        if expected not in text:
            out.append("warn:prompt thieu cau interaction co huong (%s)" % expected)
    return out

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--act", type=int)
    ap.add_argument("--project")
    ap.add_argument("--revision", type=int)
    ap.add_argument("--db", default=build.DB_PATH)
    ap.add_argument("--plan-dir", default="data/plans")
    ap.add_argument("--examples", type=int, default=6, help="so vi du in ra moi loai loi")
    args = ap.parse_args(argv)

    con = build.connect(args.db)
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
    for f in glob.glob(str(pathlib.Path(args.plan_dir) / "*.json")):
        d = json.load(open(f, encoding="utf-8-sig")) or {}
        no = (d.get("act") or {}).get("act_no")
        if no and d.get("shots"):
            plans[(d["project"]["title"], no, (d.get("act") or {}).get("revision", 1))] = d
    if args.project or args.act is not None:
        plans = {k: v for k, v in plans.items()
                 if (not args.project or k[0] == args.project)
                 and (args.act is None or k[1] == args.act)}

    acts = con.execute("SELECT a.id,a.act_no,p.title,a.revision FROM act a "
                       "JOIN project p ON p.id=a.project_id WHERE "
                       "(? IS NULL OR a.act_no=?) AND (? IS NULL OR p.title=?) "
                       "AND (? IS NULL OR a.revision=?) ORDER BY p.title,a.act_no,a.revision",
                       (args.act,args.act,args.project,args.project,args.revision,args.revision)).fetchall()
    if args.act is not None and len(acts) != 1:
        raise SystemExit("act ambiguous/not found; specify --project and --revision")
    total = collections.Counter()
    for aid, act_no, project_title, revision in acts:
        rows = con.execute("SELECT id, shot_no, shot_spec_json FROM shot WHERE act_id=?"
                           " ORDER BY shot_no", (aid,)).fetchall()
        errs, warns, seen_at = [], [], collections.defaultdict(list)
        plan = plans.get((project_title, act_no, revision))
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

        sequence_issues = story_logic.validate_specs(
            [(n, json.loads(spec)) for _sid, n, spec in rows],
            phase_contract=(plan or {}).get("act", {}).get("phase_contract"))
        for issue in sequence_issues:
            item = (issue.shot, "story", "%s: %s" % (issue.code, issue.detail))
            (errs if issue.level == "ERROR" else warns).append(item)
        sig_seq = []
        for i, (shot_id, shot_no, spec_json) in enumerate(rows):
            spec = json.loads(spec_json)
            phase = spec.get("phase", "")
            text = spec.get("prompt", "")
            if plan:
                shot_plan = next((x for x in plan.get("shots") or []
                                  if x.get("n") == shot_no), {})
                expected_bg = story_logic.scene_line(shot_plan, plan)
                if expected_bg and spec.get("background") != expected_bg:
                    errs.append((shot_no, phase, "SCENE_METADATA_PARITY: background %r != plan %r"
                                 % (spec.get("background"), expected_bg)))
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
            for msg in caption_prompt_issues(caption, words, codes, gender):
                warns.append((shot_no, phase, msg))
            if plan:
                names = {c.get("code"): c.get("name", c.get("code"))
                         for c in (plan.get("characters") or [])}
                for msg in interaction_prompt_issues(spec, text, names):
                    if msg.startswith("warn:"):
                        warns.append((shot_no, phase, msg[5:]))
                    else:
                        errs.append((shot_no, phase, msg))
            if not spec.get("action") and spec.get("purpose") not in story_logic.NO_ACTION_OK:
                errs.append((shot_no, phase, "ACTION_UNRESOLVED"))
            if not spec.get("expression"):
                warns.append((shot_no, phase, "EXPRESSION_UNRESOLVED"))
            if not spec.get("pose"):
                warns.append((shot_no, phase, "POSE_UNRESOLVED"))
            if len(toks) > MAX_TOKENS:
                warns.append((shot_no, phase, "prompt dai %d token (>%d)" % (len(toks), MAX_TOKENS)))
            body = prompt_body(text, caption)
            if body in seen_at:
                warns.append((shot_no, phase, "prompt trung tag-zone shot %s" % seen_at[body][0]))
            seen_at[body].append(shot_no)
            sig_seq.append(spec.get("signature") or
                           ",".join(x["name"] for x in (spec.get("action") or [])))
            if len(sig_seq) >= 4 and len(set(sig_seq[-4:])) == 1:
                warns.append((shot_no, phase, "action lap 4 shot lien tiep"))

        for shot_no, axis, tid, sev, src in con.execute(
                "SELECT s.shot_no, f.rule_id, f.value_tag_id, f.severity, f.source FROM shot_finding f"
                " JOIN shot s ON s.id=f.shot_id WHERE s.act_id=?"
                " AND f.source IN ('qa:v1', 'qa:llm:v1')", (aid,)):
            if src.endswith("llm:v1"):
                # High-confidence reviewer findings require resolution before rendering.
                (errs if sev >= 0.85 else warns).append(
                    (shot_no, "", "%s sev %.1f" % (axis, sev)))
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
    for issue in story_logic.validate_batch_plans(plans):
        total["warn"] += 1
        print("WARN batch %-24s %s" % (issue.code, issue.detail))
    print("\n%d act, %d error, %d warn" % (total["act"], total["err"], total["warn"]))
    con.close()
    return 1 if total["err"] else 0

if __name__ == "__main__":
    sys.exit(main())
