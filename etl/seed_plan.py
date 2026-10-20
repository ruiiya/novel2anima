# novel2anima P0P1 upgrade
"""Seed a plan JSON into the runtime tables and emit the prompt file.

Usage:
  python etl/seed_plan.py data/plans/act02_yuri_raiden_yae.json
  python etl/seed_plan.py data/plans/foo.json --dry-run
  python etl/seed_plan.py data/plans/foo.json --strict

The whole act is validated before any write. Prompt files are written with a
temporary file + atomic replace; SQLite writes run in one transaction. Existing
shot/render history is still protected by story_db.upsert_shot/prune_missing_shots.
"""
import argparse
import json
import os
import pathlib
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import wardrobe
import story_db, story_logic

GROUPS = ("outfit", "body_state", "action", "expression", "pose", "motion", "camera", "cast", "props")
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
    for ref in refs or []:
        name, tid = parse_ref(ref)
        row = TAG_CACHE.get(name)
        if row is None:
            row = TAG_CACHE[name] = cur.execute(
                "SELECT id, post_count FROM tag WHERE canonical_name=?", (name,)).fetchone()
        if row is None:
            unknown.append((shot_no, group, ref))
            continue
        if tid is not None and row[0] != tid:
            mismatched.append((shot_no, group, ref, row[0]))
        out.append((name, row[0]))
    return out

def as_refs(items):
    return [{"name": n, "tagId": t} for n, t in items]

def atomic_write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--db", default="db/novel_anima.db")
    ap.add_argument("--dry-run", action="store_true", help="validate and compile, write nothing")
    ap.add_argument("--strict", action="store_true", help="also block warnings")
    ap.add_argument("--fix-pose", dest="fix_pose", action="store_true", default=False,
                    help="legacy read-only pose diagnostic; never rewrites actions")
    ap.add_argument("--no-fix-pose", dest="fix_pose", action="store_false")
    args = ap.parse_args()

    plan = json.loads(pathlib.Path(args.plan).read_text(encoding="utf-8-sig"))
    if not isinstance(plan.get("shots"), list) or not plan.get("act"):
        print("not a story plan: %s" % args.plan, file=sys.stderr)
        return 2
    issues = story_logic.validate_plan(plan)
    for issue in issues:
        if issue.level == "ERROR":
            print("STORY_ERROR shot %s %s: %s" % (issue.shot, issue.code, issue.detail), file=sys.stderr)
    if any(i.level == "ERROR" for i in issues):
        print("aborting before write: %d P0 issue(s)" % sum(i.level == "ERROR" for i in issues),
              file=sys.stderr)
        return 1
    if args.strict and any(i.level == "WARN" for i in issues):
        for issue in issues:
            if issue.level == "WARN":
                print("STRICT_WARN shot %s %s: %s" % (issue.shot, issue.code, issue.detail),
                      file=sys.stderr)
        return 1
    if issues:
        print("story plan: %d warning(s); run etl/plan_actions.py for suggestions" %
              sum(i.level == "WARN" for i in issues))

    chars = plan.get("characters") or [plan["character"]]
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    cur = con.cursor()

    edges = {}
    for f, t in cur.execute("SELECT from_tag_id, to_tag_id FROM tag_relation WHERE relation='implies'"):
        edges.setdefault(f, []).append(t)
    closure_cache = {}

    def implied_by(tid):
        if tid in closure_cache:
            return closure_cache[tid]
        seen, stack = set(), [tid]
        while stack:
            for m in edges.get(stack.pop(), ()):
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        closure_cache[tid] = seen
        return seen

    unknown, mismatched = [], []
    for ch in chars:
        ident = ch.get("identity_json") or {}
        outfit = ch.get("outfit_json") or {}
        for group, refs in (("identity_tag", ident.get("identity_tags", [])),
                            ("attribute", ident.get("attributes", [])),
                            *[("outfit:" + k, v) for k, v in outfit.items() if isinstance(v, list)]):
            tagged(cur, ch["code"], group, refs, unknown, mismatched)

    parsed = []
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
        p["character_actions"] = {code: tagged(cur, shot["n"], "action:" + code, refs, unknown, mismatched)
                                  for code, refs in (shot.get("character_actions") or {}).items()}
        p["character_poses"] = {code: tagged(cur, shot["n"], "pose:" + code, refs, unknown, mismatched)
                                for code, refs in (shot.get("character_poses") or {}).items()}
        p["character_gaze"] = shot.get("character_gaze") or {}
        p["character_targets"] = shot.get("character_targets") or {}
        p["action"] = list(dict.fromkeys(p["action"] + [v for refs in p["character_actions"].values() for v in refs]))
        p["pose"] = list(dict.fromkeys(p["pose"] + [v for refs in p["character_poses"].values() for v in refs]))
        p["phase"] = shot.get("phase", "")
        p["caption"] = shot["caption"]
        p["beat"] = shot.get("beat", "")
        parsed.append((shot, p))

    def id_of(name):
        row = cur.execute("SELECT id FROM tag WHERE canonical_name=?", (name,)).fetchone()
        return row[0] if row else None

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
    pose_fix = wardrobe.lock_poses(parsed, id_of) if args.fix_pose else []
    print("khoa mau: +mau cho %d/%d shot | chua chon mau: %s | thang tu the: %s"
          % (coloured, len(parsed), sorted(undecided) or "du",
             ("keo %d shot" % len(pose_fix)) if args.fix_pose else "tat (--fix-pose de bat)"))
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
    char_name = {ch["code"]: ch.get("name", ch["code"]) for ch in chars}
    attr_names = {ch["code"]: [parse_ref(r)[0] for r in (ch.get("identity_json") or {}).get("attributes", [])]
                  for ch in chars}

    def identity_line(ch):
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
        name = name.strip()
        return name if name.startswith("score_") else name.replace("_", " ")

    def join_tags(names):
        return ", ".join(tag_text(n) for n in names if n)

    def cast_line(codes, explicit_counts=False):
        girls = sum(1 for c in codes if gender.get(c, "girl") == "girl")
        boys = len(codes) - girls
        if explicit_counts:
            return "%dgirl%s" % (girls, "s" if girls > 1 else "")
        if boys == 0:
            return "%dgirls, yuri" % girls
        if girls == 0:
            return "%dboys" % boys
        if girls > 1:
            return "%dgirls, %dboys" % (girls, boys)
        if girls == 1 and boys >= 3:
            return "1girl, multiple boys"
        if boys == 1:
            return "1girl, 1boy"
        return "1girl, %dboys" % boys

    def scene_for(shot):
        scene = shot.get("scene") or plan.get("scene") or {}
        if not isinstance(scene, dict):
            scene = {}
        render = shot.get("render_style") or plan.get("render_style") or {}
        if not isinstance(render, dict):
            render = {}
        style_bg = (plan.get("style_json") or {}).get("background")
        line = (render.get("background_style") or shot.get("background_line")
                or scene.get("background_line") or plan.get("background_line")
                or style_bg or "plain background")
        out = dict(scene)
        out.setdefault("location", scene.get("location") or style_bg or line)
        out.setdefault("tags", [x.strip() for x in re.split(r"[,;]", line) if x.strip()])
        return out, line

    built = []
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
        body_tokens = [n for n, tid in p["body_state"]
                       if n not in ident_tokens and n not in action_names and tid not in redundant]

        def nl_block():
            who = char_name.get(p["participants"][0], p["participants"][0])
            attrs = [tag_text(n) for n in attr_names.get(p["participants"][0], [])][:4]
            state_names = [n for n, _ in p["outfit"]] + [n for n, _ in p["body_state"]] + [n for n, _ in p["cast"]]
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

        scene, background_line = scene_for(shot)
        parts += [clean("cast"),
                  take(outfit_tokens),
                  take(body_tokens),
                  clean("props"),
                  clean("action"),
                  clean("expression"),
                  clean("pose"),
                  clean("motion"),
                  clean("camera"),
                  background_line.replace("_", " "),
                  p["caption"]]
        prompt = ", ".join(x for x in parts if x)

        role_clauses = []
        for c in p["participants"]:
            scoped = [n.replace("_", " ") for n, _ in p["character_actions"].get(c, [])]
            scoped += [n.replace("_", " ") for n, _ in p["character_poses"].get(c, [])]
            gaze = p["character_gaze"].get(c)
            if gaze:
                scoped.append("looking toward " + str(gaze))
            target = p["character_targets"].get(c)
            if target:
                scoped.append("interacting with " + str(target))
            if scoped:
                role_clauses.append("%s: %s" % (char_name.get(c, c), ", ".join(scoped)))
        if role_clauses:
            prompt += ". " + "; ".join(role_clauses)
        if plan.get("nl"):
            prompt += ". " + " ".join(nl_block())

        signature = "%s|%s|%s" % (
            ",".join(n for n, _ in p["action"]),
            ",".join(dict.fromkeys(n for n, _ in p["expression"])),
            ",".join(n for n, _ in p["pose"]) + "|" + str(shot.get("sequence", {}).get("eventId", "")))

        spec = {
            "phase": p["phase"],
            "participants": [{"code": c, "role": "participant",
                               "expression": as_refs(p.get("expressions", {}).get(c, p["expression"])),
                               "action": as_refs(p["character_actions"].get(c, [])),
                               "pose": as_refs(p["character_poses"].get(c, [])),
                               "gazeTarget": p["character_gaze"].get(c),
                               "target": p["character_targets"].get(c)}
                              for c in p["participants"]],
            "cast": as_refs(p["cast"]),
            "outfit": as_refs(p["outfit"]),
            "body_state": as_refs(p["body_state"]),
            "props": as_refs(p["props"]),
            "action": as_refs(p["action"]),
            "expression": as_refs(p["expression"]),
            "pose": as_refs(p["pose"]),
            "motion": as_refs(p["motion"]),
            "camera": as_refs(p["camera"]),
            "background": background_line,
            "scene": scene,
            "render_style": {"background_style": background_line},
            "caption": p["caption"],
            "beat": p["beat"],
            "purpose": (shot.get("sequence") or {}).get("purpose", shot.get("purpose", "")),
            "sequence": shot.get("sequence") or {},
            "character_actions": {c: as_refs(refs) for c, refs in p["character_actions"].items()},
            "character_poses": {c: as_refs(refs) for c, refs in p["character_poses"].items()},
            "signature": signature,
            "prompt": prompt,
            "flags": flags,
            "contentProfile": str(pj.get("content_profile", "nsfw")).upper(),
        }
        built.append({"shot": shot, "p": p, "pose_cid": pose_cid, "spec": spec, "prompt": prompt})

    blocked_ids = {r[0] for r in cur.execute("SELECT tag_id FROM tag_content_label WHERE scope='blocked'")}
    phase_contract = (plan.get("act") or {}).get("phase_contract")
    semantic = story_logic.validate_specs(
        [(item["shot"]["n"], item["spec"]) for item in built],
        phase_contract=phase_contract, blocked_ids=blocked_ids)
    semantic_errors = [i for i in semantic if i.level == "ERROR"]
    for issue in semantic:
        print("%s shot %s %s: %s" % (issue.level, issue.shot, issue.code, issue.detail),
              file=(sys.stderr if issue.level == "ERROR" else sys.stdout))
    if semantic_errors:
        print("aborting before write: %d semantic P0 issue(s)" % len(semantic_errors), file=sys.stderr)
        return 1
    if args.strict and semantic:
        print("strict: semantic warnings block seed; rerun without --strict", file=sys.stderr)
        return 1

    if args.dry_run:
        print("dry-run: project=%r act_no=%s revision=%s shots=%d (no writes)"
              % (pj["title"], plan["act"]["act_no"], plan["act"].get("revision", 1), len(built)))
        con.close()
        return 0

    con.isolation_level = None
    try:
        con.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT id FROM project WHERE title=?", (pj["title"],))
        r = cur.fetchone()
        if r:
            pid = r[0]
            if plan.get("shots"):
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

        if "shots" not in plan:
            con.commit()
            print("project id=%s characters=%s" % (pid, char_ids))
            print("roster mode: %d character_profile rows upserted, no shots written" % len(chars))
            return 0

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

        multi = False
        for item in built:
            shot, p, spec = item["shot"], item["p"], item["spec"]
            multi = multi or len(p["participants"]) > 1
            story_db.upsert_shot(cur, aid, shot["n"], char_ids[p["participants"][0]],
                                 item["pose_cid"], spec["signature"], spec, "nsfw")
            lines.append(item["prompt"])

        story_db.prune_missing_shots(cur, aid, [item["shot"]["n"] for item in built])
        out = pathlib.Path(plan["prompt_file"])
        atomic_write(out, "\n\n".join(lines) + "\n")
        negative = plan.get("negative_line", DEFAULT_NEGATIVE)
        atomic_write(out.with_name(out.stem + ".neg.txt"), negative + "\n")
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()

    print("project id=%s act id=%s shots=%d characters=%s" % (pid, aid, len(lines), char_ids))
    print("prompt file: %s (%d prompts)" % (out, len(lines)))
    print("negative file: %s" % out.with_name(out.stem + ".neg.txt"))
    print("pose concept resolved: %d/%d" % (pose_hits, len(parsed)))
    print("implied-redundant tags pruned from prompts: %d" % pruned_total)
    if multi:
        print("SCHEMA_GAP: multi-character shots keep the whole cast in shot_spec_json.participants")
    return 0

if __name__ == "__main__":
    sys.exit(main())
