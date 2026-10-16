"""Seed a plan JSON into the runtime tables and emit the prompt file.

Usage: python etl/seed_plan.py data/plans/act02_yuri_raiden_yae.json
Idempotent per (project title, character code, act_no, revision, shot_no).
Validates every "name:id" against `tag`; refuses to invent catalog IDs.
Multi-character: plan["characters"][] + shot["participants"][] + optional
shot["expressions"]{code:[refs]}. shot.character_id holds the primary participant
(schema has one FK column) - the full cast goes into shot_spec_json.participants
and is reported as SCHEMA_GAP.
"""
import argparse, json, re, sqlite3, sys, pathlib
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wardrobe   # quy tac chung: khoa mau do + thang tu the (xem etl/wardrobe.py)

GROUPS = ("outfit", "action", "expression", "pose", "motion", "camera", "cast")

DEFAULT_NEGATIVE = ("worst quality, low quality, score_1, score_2, score_3, artist name, "
                    "blurry, jpeg artifacts, chromatic aberration")

def parse_ref(ref):
    # split on the LAST colon: canonical names may contain colons (e.g. honkai:_star_rail)
    name, _, tid = ref.rpartition(":")
    if not name:
        return ref, None
    return name, (int(tid) if tid.isdigit() else None)

TAG_CACHE = {}   # ten -> (id, post_count): mot plan tra lai cung vai nghin tag

def tagged(cur, shot_no, group, refs, unknown, mismatched):
    out = []
    for ref in refs:
        name, tid = parse_ref(ref)
        row = TAG_CACHE.get(name)
        if row is None:
            row = TAG_CACHE[name] = cur.execute(
                "SELECT id, post_count FROM tag WHERE canonical_name=?", (name,)).fetchone()
        if row is None:
            unknown.append((shot_no, group, ref))
            continue
        if tid is not None and row[0] != tid:
            mismatched.append((shot_no, group, ref, row[0]))   # id cu -> ten la chuan, lay id theo ten
        out.append((name, row[0]))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--db", default="db/novel_anima.db")
    ap.add_argument("--fix-pose", dest="fix_pose", action="store_true", default=True,
                    help="keo tu the lui thang ve tu the shot truoc (mac dinh bat)")
    ap.add_argument("--no-fix-pose", dest="fix_pose", action="store_false",
                    help="giu nguyen tu the tac gia viet, chi bao cao lech thang")
    args = ap.parse_args()
    fix_pose = args.fix_pose

    plan = json.loads(pathlib.Path(args.plan).read_text(encoding="utf-8-sig"))
    chars = plan.get("characters") or [plan["character"]]
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    edges = {}
    for f, t in cur.execute("SELECT from_tag_id, to_tag_id FROM tag_relation WHERE relation='implies'"):
        edges.setdefault(f, []).append(t)
    closure_cache = {}

    def implied_by(tid):
        """ids this tid transitively implies (what may be dropped when tid is present)"""
        if tid in closure_cache:
            return closure_cache[tid]
        seen, stack = set(), [tid]
        while stack:
            n = stack.pop()
            for m in edges.get(n, []):
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        closure_cache[tid] = seen
        return seen

    unknown, mismatched = [], []
    for ch in chars:   # character identity refs go into the prompt too - validate them
        ident = ch.get("identity_json") or {}   # gang/extra participants may only carry code+name
        outfit = ch.get("outfit_json") or {}
        for group, refs in (("identity_tag", ident.get("identity_tags", [])),
                            ("attribute", ident.get("attributes", [])),
                            *[("outfit:" + k, v) for k, v in outfit.items()]):
            tagged(cur, ch["code"], group, refs, unknown, mismatched)
    parsed = []   # a characters-only roster has no shots: skip prompt parsing
    for shot in plan.get("shots", []):
        p = {}
        for g in GROUPS:
            if g == "expression":
                continue
            p[g] = tagged(cur, shot["n"], g, shot.get(g, []), unknown, mismatched)
        per_char = shot.get("expressions")
        if per_char:
            p["expressions"] = {code: tagged(cur, shot["n"], "expression:" + code, refs, unknown, mismatched)
                                for code, refs in per_char.items()}
            p["expression"] = [t for code in [c["code"] for c in chars] for t in p["expressions"].get(code, [])]
        else:
            p["expression"] = tagged(cur, shot["n"], "expression", shot.get("expression", []), unknown, mismatched)
        p["participants"] = shot.get("participants") or [chars[0]["code"]]
        p["phase"] = shot.get("phase", "")
        p["caption"] = shot["caption"]
        p["beat"] = shot.get("beat", "")
        parsed.append((shot, p))

    # ---- quy tac chung: moi tag do phai co mau, tu the khong duoc lui thang trong phase
    def id_of(name):
        row = cur.execute("SELECT id FROM tag WHERE canonical_name=?", (name,)).fetchone()
        return row[0] if row else None

    # bang mau doc tu catalog (visual_concept WC_* + concept_tag) - xem etl/import_colour_sets.py
    table = wardrobe.colour_table(cur)
    coloured, undecided = 0, set()
    for shot, p in parsed:
        new = wardrobe.under_fix(wardrobe.colorize(p["outfit"], table), table)
        if new != p["outfit"]:
            coloured += 1
            p["outfit"] = new
        for name, tid in p["outfit"]:
            e = table.get(tid)
            if e and tid == e["base_id"] and not e["chosen"] and not e["cue"]:
                undecided.add(name)
    pose_fix = wardrobe.lock_poses(parsed, id_of) if fix_pose else []
    print("khoa mau: +mau cho %d/%d shot | chua chon mau: %s | thang tu the: %s"
          % (coloured, len(parsed), sorted(undecided) or "du",
             ("keo %d shot" % len(pose_fix)) if fix_pose else "tat (--fix-pose de bat)"))
    for n, phase, old, new in pose_fix[:12]:
        print("  shot %s (%s): %s -> %s" % (n, phase, old, new))
    if len(pose_fix) > 12:
        print("  ... con %d shot" % (len(pose_fix) - 12))

    refs_total = sum(len(p[g]) for _, p in parsed for g in GROUPS) + \
        sum(len(t) for _, p in parsed for t in p.get("expressions", {}).values())
    print("tag refs resolved:", refs_total)
    if unknown:
        print("UNKNOWN TAGS (not in db):")
        for u in unknown:
            print("  shot %s %s %s" % u)
    if mismatched:
        print("id cu trong plan -> lay theo ten: %d ref (vi du %s)" % (len(mismatched), mismatched[0]))
    if unknown:
        print("aborting: fix the plan first", file=sys.stderr)
        return 1

    pj = plan["project"]
    cur.execute("SELECT id FROM project WHERE title=?", (pj["title"],))
    r = cur.fetchone()
    if r:
        pid = r[0]
        if plan.get("shots"):   # a roster-only file (no shots) never rewrites the project row
            cur.execute("UPDATE project SET idea=?, content_profile=?, style_json=? WHERE id=?",
                        (pj["idea"], pj["content_profile"], json.dumps(pj["style_json"], ensure_ascii=False), pid))
    else:
        cur.execute("INSERT INTO project(title, idea, content_profile, style_json, created_at) VALUES(?,?,?,?,?)",
                    (pj["title"], pj["idea"], pj["content_profile"],
                     json.dumps(pj["style_json"], ensure_ascii=False),
                     datetime.now(timezone.utc).isoformat(timespec="seconds")))
        pid = cur.lastrowid

    char_ids = {}
    for ch in chars:
        cur.execute("SELECT id FROM character_profile WHERE project_id=? AND code=?", (pid, ch["code"]))
        r = cur.fetchone()
        payload = (json.dumps(ch.get("identity_json") or {}, ensure_ascii=False),
                   json.dumps(ch.get("outfit_json") or {}, ensure_ascii=False))
        if r:
            char_ids[ch["code"]] = r[0]
            cur.execute("UPDATE character_profile SET identity_json=?, outfit_json=? WHERE id=?", payload + (r[0],))
        else:
            cur.execute("INSERT INTO character_profile(project_id, code, identity_json, outfit_json) VALUES(?,?,?,?)",
                        (pid, ch["code"], payload[0], payload[1]))
            char_ids[ch["code"]] = cur.lastrowid
    if "shots" not in plan:   # characters-only roster: no act/shot/prompt to build
        con.commit()
        print("project id=%s characters=%s" % (pid, char_ids))
        print("roster mode: %d character_profile rows upserted, no shots written" % len(chars))
        con.close()
        return 0

    char_name = {ch["code"]: ch.get("name", ch["code"]) for ch in chars}
    attr_names = {ch["code"]: [parse_ref(r)[0] for r in (ch.get("identity_json") or {}).get("attributes", [])]
                  for ch in chars}
    def identity_line(ch):
        """identity_line, nhung character/copyright tags tu identity_json luon co mat
        (chen ngay sau 1girl/1boy de giu danbooru count line o dau)."""
        line = ch.get("identity_line", "")
        ident = ch.get("identity_json") or {}
        extra = [parse_ref(r)[0] for r in ident.get("identity_tags", [])] + \
                [parse_ref(r)[0] for r in ident.get("attributes", [])]
        norm = lambda t: t.strip().replace("_", " ")
        have = {norm(t) for t in line.split(",")}
        add = [t for t in extra if norm(t) not in have]
        if not add:
            return line
        parts = [t.strip() for t in line.split(",") if t.strip()]
        return ", ".join(parts[:2] + add + parts[2:])

    ident_lines = {ch["code"]: identity_line(ch) for ch in chars}
    if len(chars) == 1 and not ident_lines[chars[0]["code"]]:
        ident_lines[chars[0]["code"]] = plan.get("identity_line", "")
    gender = {ch["code"]: ch.get("gender", "girl") for ch in chars}

    def tag_text(name):
        """Anima tag syntax: lowercase, spaces instead of underscores; score_* keeps its underscore."""
        name = name.strip()
        return name if name.startswith("score_") else name.replace("_", " ")

    def join_tags(names):
        return ", ".join(tag_text(n) for n in names if n)

    def cast_line(codes, explicit_counts=False):
        """danbooru count line for a multi-participant shot; 1girl/1boy live in identity_line."""
        girls = sum(1 for c in codes if gender.get(c, "girl") == "girl")
        boys = len(codes) - girls
        if explicit_counts:                   # the plan carries its own boy count (4boys/5boys/...)
            return "%dgirl%s" % (girls, "s" if girls > 1 else "")
        if boys == 0:
            return "%dgirls, yuri" % girls
        if girls == 0:
            return "%dboys" % boys
        if girls > 1:
            return "%dgirls, %dboys" % (girls, boys)
        if girls == 1 and boys >= 3:
            return "1girl, multiple boys"      # Anima tag syntax: spaces, not underscores
        if boys == 1:
            return "1girl, 1boy"
        return "1girl, %dboys" % boys

    ac = plan["act"]
    cur.execute("SELECT id FROM act WHERE project_id=? AND act_no=? AND revision=?",
                (pid, ac["act_no"], ac.get("revision", 1)))
    r = cur.fetchone()
    if r:
        aid = r[0]
        cur.execute("UPDATE act SET title=?, outline=?, status=? WHERE id=?",
                    (ac["title"], ac["outline"], ac["status"], aid))
    else:
        cur.execute("INSERT INTO act(project_id, act_no, title, outline, revision, status) VALUES(?,?,?,?,?,?)",
                    (pid, ac["act_no"], ac["title"], ac["outline"], ac.get("revision", 1), ac["status"]))
        aid = cur.lastrowid

    cur.execute("DELETE FROM shot WHERE act_id=?", (aid,))   # re-seed replaces this act's shot rows

    multi = any(len(p["participants"]) > 1 for _, p in parsed)
    lines, pose_hits, pruned_total = [], 0, 0
    for shot, p in parsed:
        pose_cid = None
        if p["pose"]:
            row = cur.execute("SELECT c.id FROM visual_concept c JOIN concept_tag ct ON ct.concept_id=c.id "
                              "WHERE ct.tag_id=? AND c.kind='pose' LIMIT 1", (p["pose"][0][1],)).fetchone()
            pose_cid = row[0] if row else None
        pose_hits += 1 if pose_cid else 0

        flags = ["CURATION_GAP: no action/expression concepts in visual_concept"]
        if not p["action"]:
            flags.append("ACTION_UNRESOLVED")
        if not p["expression"]:
            flags.append("EXPRESSION_UNRESOLVED")
        if pose_cid is None:
            flags.append("POSE_CONCEPT_GAP")
        if len(p["participants"]) > 1:
            flags.append("SCHEMA_GAP: shot.character_id holds one FK; %d participants live in shot_spec_json"
                         % len(p["participants"]))

        drop = {"1girl", "1boy", "solo"} if len(p["participants"]) > 1 else set()
        ident_tokens = []
        for c in p["participants"]:
            for tok in ident_lines.get(c, "").split(","):
                tok = tok.strip()
                if tok and tok not in drop and tok not in ident_tokens:
                    ident_tokens.append(tok)
        parts = [plan["quality_line"], plan.get("safety_tag", "safe")]
        if len(p["participants"]) > 1:
            parts.append(cast_line(p["participants"], bool(p["cast"])))
        parts += [join_tags(ident_tokens)]
        if plan.get("artist_line"):
            parts.append(plan["artist_line"])
        pooled = [t for g in GROUPS for t in p[g]]
        present = {tid for _, tid in pooled if tid}
        redundant = set()
        for _, tid in pooled:
            if tid:
                redundant |= (implied_by(tid) & present)
        redundant.discard(None)
        pruned = [n for n, tid in pooled if tid in redundant]
        pruned_total += len(pruned)

        emitted = set(ident_tokens)

        def take(names):
            out = [n for n in dict.fromkeys(names) if n not in emitted]
            emitted.update(out)
            return join_tags(out)

        def clean(group):
            return take(n for n, tid in p[group] if tid not in redundant)

        action_names = {n for n, _ in p["action"]}
        outfit_tokens = [n for n, tid in p["outfit"]
                         if n not in ident_tokens and n not in action_names and tid not in redundant]
        def nl_block():
            """Two natural-language sentences; the model is trained on tags + captions + mixes."""
            who = char_name.get(p["participants"][0], p["participants"][0])
            attrs = [tag_text(n) for n in attr_names.get(p["participants"][0], [])][:4]
            state_names = [n for n, _ in p["outfit"]] + [n for n, _ in p["cast"]]
            state = [tag_text(n) for n in dict.fromkeys(state_names)
                     if re.search(r"piercing|chain|gag|pregnan|belly|welts|bruise|mark", n)][:3]
            men = len(p["participants"]) - 1
            first = "An anime-style illustration of %s" % who
            if attrs:
                first += " with " + ", ".join(attrs)
            if state:
                first += ", " + ", ".join(state)
            if men > 0:
                first += ", with %d men" % men
            first += "."
            second = "The scene focuses on %s with %s, framed as %s." % (
                join_tags([n for n, _ in p["action"]]) or "the pose",
                join_tags([n for n, _ in p["expression"]]) or "a neutral face",
                join_tags([n for n, _ in p["camera"]]) or "a full shot")
            return [first, second]

        parts += [clean("cast"),
                  take(outfit_tokens),
                  clean("action"),
                  clean("expression"),
                  clean("pose"),
                  clean("motion"),
                  clean("camera"),
                  plan.get("background_line", "white background, simple background"),
                  p["caption"]]
        prompt = ", ".join(x for x in parts if x)
        if plan.get("nl"):
            prompt += ". " + " ".join(nl_block())

        signature = "%s|%s|%s" % (
            ",".join(n for n, _ in p["action"]),
            ",".join(dict.fromkeys(n for n, _ in p["expression"])),
            ",".join(n for n, _ in p["camera"]))

        spec = {
            "phase": p["phase"],
            "participants": [{"code": c, "role": "participant",
                              "expression": [{"name": n, "tagId": t} for n, t in p.get("expressions", {}).get(c, p["expression"])]}
                             for c in p["participants"]],
            "cast": [{"name": n, "tagId": t} for n, t in p["cast"]],
            "outfit": [{"name": n, "tagId": t} for n, t in p["outfit"]],
            "action": [{"name": n, "tagId": t} for n, t in p["action"]],
            "expression": [{"name": n, "tagId": t} for n, t in p["expression"]],
            "pose": [{"name": n, "tagId": t} for n, t in p["pose"]],
            "motion": [{"name": n, "tagId": t} for n, t in p["motion"]],
            "camera": [{"name": n, "tagId": t} for n, t in p["camera"]],
            "background": "white",
            "caption": p["caption"],
            "beat": p["beat"],
            "prompt": prompt,
            "flags": flags,
            "contentProfile": "NSFW",
        }

        cur.execute(
            "INSERT INTO shot(act_id, shot_no, character_id, action_concept_id, expression_concept_id,"
            " pose_concept_id, camera_concept_id, signature, shot_spec_json, content_mode, status, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, shot["n"], char_ids[p["participants"][0]], None, None, pose_cid, None, signature,
             json.dumps(spec, ensure_ascii=False), "nsfw", "planned",
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
        lines.append(prompt)

    out = pathlib.Path(plan["prompt_file"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    negative = plan.get("negative_line", DEFAULT_NEGATIVE)
    neg_out = out.with_name(out.stem + ".neg.txt")
    neg_out.write_text(negative + "\n", encoding="utf-8", newline="\n")

    con.commit()
    print("project id=%s act id=%s shots=%d characters=%s" % (pid, aid, len(lines), char_ids))
    print("prompt file: %s (%d prompts)" % (out, len(lines)))
    print("negative file: %s" % neg_out)
    print("pose concept resolved: %d/%d" % (pose_hits, len(parsed)))
    print("implied-redundant tags pruned from prompts: %d" % pruned_total)
    if multi:
        print("SCHEMA_GAP: multi-character shots keep the whole cast in shot_spec_json.participants")
    con.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())

