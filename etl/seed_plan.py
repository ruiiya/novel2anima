"""Seed a plan JSON into the runtime tables and emit the prompt file.

Usage: python etl/seed_plan.py data/plans/act02_yuri_raiden_yae.json
Idempotent per (project title, character code, act_no, revision, shot_no).
Validates every "name:id" against `tag`; refuses to invent catalog IDs.
Multi-character: plan["characters"][] + shot["participants"][] + optional
shot["expressions"]{code:[refs]}. shot.character_id holds the primary participant
(schema has one FK column) - the full cast goes into shot_spec_json.participants
and is reported as SCHEMA_GAP.
"""
import argparse, json, sqlite3, sys, pathlib
from datetime import datetime, timezone

GROUPS = ("outfit", "action", "expression", "pose", "motion", "camera")

def parse_ref(ref):
    # split on the LAST colon: canonical names may contain colons (e.g. honkai:_star_rail)
    name, _, tid = ref.rpartition(":")
    if not name:
        return ref, None
    return name, (int(tid) if tid.isdigit() else None)

def tagged(cur, shot_no, group, refs, unknown, mismatched):
    out = []
    for ref in refs:
        name, tid = parse_ref(ref)
        row = cur.execute("SELECT id, post_count FROM tag WHERE canonical_name=?", (name,)).fetchone()
        if row is None:
            unknown.append((shot_no, group, ref))
            continue
        if tid is not None and row[0] != tid:
            mismatched.append((shot_no, group, ref, row[0]))
            continue
        out.append((name, row[0]))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--db", default="db/novel_anima.db")
    args = ap.parse_args()

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
        for group, refs in (("identity_tag", ch["identity_json"].get("identity_tags", [])),
                            ("attribute", ch["identity_json"].get("attributes", []))):
            tagged(cur, ch["code"], group, refs, unknown, mismatched)
    parsed = []
    for shot in plan["shots"]:
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

    refs_total = sum(len(p[g]) for _, p in parsed for g in GROUPS) + \
        sum(len(t) for _, p in parsed for t in p.get("expressions", {}).values())
    print("tag refs resolved:", refs_total)
    if unknown:
        print("UNKNOWN TAGS (not in db):")
        for u in unknown:
            print("  shot %s %s %s" % u)
    if mismatched:
        print("ID MISMATCH:")
        for m in mismatched:
            print("  shot %s %s %s -> db id %s" % m)
    if unknown or mismatched:
        print("aborting: fix the plan first", file=sys.stderr)
        return 1

    pj = plan["project"]
    cur.execute("SELECT id FROM project WHERE title=?", (pj["title"],))
    r = cur.fetchone()
    if r:
        pid = r[0]
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
        payload = (json.dumps(ch["identity_json"], ensure_ascii=False), json.dumps(ch["outfit_json"], ensure_ascii=False))
        if r:
            char_ids[ch["code"]] = r[0]
            cur.execute("UPDATE character_profile SET identity_json=?, outfit_json=? WHERE id=?", payload + (r[0],))
        else:
            cur.execute("INSERT INTO character_profile(project_id, code, identity_json, outfit_json) VALUES(?,?,?,?)",
                        (pid, ch["code"], payload[0], payload[1]))
            char_ids[ch["code"]] = cur.lastrowid
    ident_lines = {ch["code"]: ch.get("identity_line", "") for ch in chars}
    if len(chars) == 1 and not ident_lines[chars[0]["code"]]:
        ident_lines[chars[0]["code"]] = plan.get("identity_line", "")

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

        drop = {"1girl", "solo"} if len(p["participants"]) > 1 else set()
        ident_tokens = []
        for c in p["participants"]:
            for tok in ident_lines.get(c, "").split(","):
                tok = tok.strip()
                if tok and tok not in drop and tok not in ident_tokens:
                    ident_tokens.append(tok)
        parts = [plan["quality_line"]]
        if len(p["participants"]) > 1:
            parts.append("2girls, yuri")
        parts += [", ".join(ident_tokens)]
        pooled = [t for g in ("outfit", "action", "expression", "pose", "motion", "camera") for t in p[g]]
        present = {tid for _, tid in pooled if tid}
        redundant = set()
        for _, tid in pooled:
            if tid:
                redundant |= (implied_by(tid) & present)
        redundant.discard(None)
        pruned = [n for n, tid in pooled if tid in redundant]
        pruned_total += len(pruned)

        def clean(group):
            return ", ".join(dict.fromkeys(n for n, tid in p[group] if tid not in redundant))

        action_names = {n for n, _ in p["action"]}
        outfit_tokens = [n for n, tid in p["outfit"]
                         if n not in ident_tokens and n not in action_names and tid not in redundant]
        parts += [", ".join(dict.fromkeys(outfit_tokens)),
                  clean("action"),
                  clean("expression"),
                  clean("pose"),
                  clean("motion"),
                  clean("camera"),
                  p["caption"]]
        prompt = ", ".join(x for x in parts if x)

        signature = "%s|%s|%s" % (
            ",".join(n for n, _ in p["action"]),
            ",".join(dict.fromkeys(n for n, _ in p["expression"])),
            ",".join(n for n, _ in p["camera"]))

        spec = {
            "phase": p["phase"],
            "participants": [{"code": c, "role": "participant",
                              "expression": [{"name": n, "tagId": t} for n, t in p.get("expressions", {}).get(c, p["expression"])]}
                             for c in p["participants"]],
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

    con.commit()
    print("project id=%s act id=%s shots=%d characters=%s" % (pid, aid, len(lines), char_ids))
    print("prompt file: %s (%d prompts)" % (out, len(lines)))
    print("pose concept resolved: %d/%d" % (pose_hits, len(parsed)))
    print("implied-redundant tags pruned from prompts: %d" % pruned_total)
    if multi:
        print("SCHEMA_GAP: multi-character shots keep the whole cast in shot_spec_json.participants")
    con.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
