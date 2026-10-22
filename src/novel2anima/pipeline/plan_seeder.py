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
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

from novel2anima.paths import DB_PATH
from novel2anima.wardrobe import rules as wardrobe
from novel2anima.storage import story_repository as story_db
from novel2anima.story import logic as story_logic

GROUPS = ("outfit", "body_state", "action", "expression", "pose", "motion", "camera", "cast", "props")
DEFAULT_NEGATIVE = ("worst quality, low quality, score_1, score_2, score_3, artist name, "
                    "blurry, jpeg artifacts, chromatic aberration, text, watermark, "
                    "bad hands, extra fingers")

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

def _token_key(name):
    return str(name).strip().replace("_", " ")

def split_identities(participants, ident_lines, drop):
    # Main character giu identity o dau prompt; nhan vat phu di theo clause rieng.
    main = participants[0] if participants else ""
    main_tokens, seen = [], set()
    for tok in ident_lines.get(main, "").split(","):
        tok = tok.strip()
        key = _token_key(tok)
        if tok and key not in drop and key not in seen:
            main_tokens.append(tok)
            seen.add(key)
    scoped = {}
    # "adult" belongs to every participant, not only the lead. Keeping it in
    # each scoped identity makes multi-character prompts explicit even when the
    # main character's identity already contains the same tag.
    scoped_always = {"adult"}
    for code in participants[1:]:
        toks = []
        for tok in ident_lines.get(code, "").split(","):
            tok = tok.strip()
            key = _token_key(tok)
            if tok and key not in drop and (key in scoped_always or key not in seen) \
                    and key not in {_token_key(x) for x in toks}:
                toks.append(tok)
        if toks:
            scoped[code] = toks
    return main_tokens, scoped

def take_unique(names, emitted):
    out = []
    for name in names:
        key = _token_key(name)
        if key and key not in emitted:
            out.append(name)
            emitted.add(key)
    return out

def publish_files(files):
    """Publish (path, text) pairs after the DB commit, all-or-nothing.

    Each file is replaced atomically. If a later replace fails, earlier files are
    restored from their previous bytes so the published set never keeps a partial
    update from this run.
    """
    prior = {path: (path.read_bytes() if path.exists() else None) for path, _ in files}
    done = []
    try:
        for path, text in files:
            atomic_write(path, text)
            done.append(path)
    except BaseException:
        for path in done:
            old = prior[path]
            if old is None:
                try:
                    path.unlink()
                except OSError:
                    pass
            else:
                atomic_write(path, old.decode("utf-8"))
        raise

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

def blocked_by(issues, strict=False):
    """ERROR always blocks; WARN blocks only under --strict (P1-09 CI gate)."""
    errors = [i for i in issues if i.level == "ERROR"]
    if errors:
        return errors
    return [i for i in issues if i.level == "WARN"] if strict else []


def append_sentence(text, part):
    """Join a sentence after a caption without producing '..' gaps."""
    text, part = str(text or "").rstrip(), str(part or "").strip()
    if not part:
        return text
    return text + (" " if text.endswith((".", "!?", "?")) else ". ") + part


def directed_clause(char_name, actor, target, primary):
    """Render the one-direction sentence from a CERTIFIED sequence.

    Templates are configuration data (story_logic.DIRECTED_CLAUSE_TEMPLATES);
    actor/target names come from the plan, never guessed from gender, tag
    order or caption pronouns. Unknown action -> empty string: no clause, and
    the prompt may not claim a direction the metadata does not certify.
    """
    primary = str(primary or "").strip().lower()
    tpl = story_logic.DIRECTED_CLAUSE_TEMPLATES.get(primary)
    if not tpl:
        grp = story_logic.ALIAS_INDEX.get(primary)
        if grp is not None:
            for cand in story_logic.ALIAS_GROUPS[grp]:
                if cand in story_logic.DIRECTED_CLAUSE_TEMPLATES:
                    tpl = story_logic.DIRECTED_CLAUSE_TEMPLATES[cand]
                    break
    if not tpl:
        return ""
    return "%s %s." % (char_name.get(actor, str(actor)),
                       tpl.format(t=char_name.get(target, str(target))))

MIGRATIONS = pathlib.Path(__file__).resolve().parents[3] / "sql" / "migrations"

def ensure_runtime_tables(con):
    """Create observation/publication tables on older DBs (idempotent DDL)."""
    con.executescript((MIGRATIONS / "004_observation_publication.sql").read_text(encoding="utf-8"))

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def record_publication(cur, act_id, revision, files):
    """Write the publication outbox row as pending before touching the filesystem."""
    prompt_path, prompt_text = files[0]
    neg_path, neg_text = files[1] if len(files) > 1 else (None, "")
    cur.execute(
        "INSERT INTO act_publication(act_id, revision, prompt_path, prompt_sha256,"
        " negative_path, negative_sha256, pending, updated_at) VALUES(?,?,?,?,?,?,1,?)"
        " ON CONFLICT(act_id, revision) DO UPDATE SET prompt_path=excluded.prompt_path,"
        " prompt_sha256=excluded.prompt_sha256, negative_path=excluded.negative_path,"
        " negative_sha256=excluded.negative_sha256, pending=1, updated_at=excluded.updated_at",
        (act_id, revision, str(prompt_path), hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
         str(neg_path) if neg_path else None,
         hashlib.sha256(neg_text.encode("utf-8")).hexdigest() if neg_path else None, _now()))

def mark_published(cur, act_id, revision):
    cur.execute("UPDATE act_publication SET pending=0, updated_at=? WHERE act_id=? AND revision=?",
                (_now(), act_id, revision))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true", help="validate and compile, write nothing")
    ap.add_argument("--strict", action="store_true", help="also block warnings")
    ap.add_argument("--fix-pose", dest="fix_pose", action="store_true", default=False,
                    help="legacy read-only pose diagnostic; never rewrites actions")
    ap.add_argument("--no-fix-pose", dest="fix_pose", action="store_false")
    args = ap.parse_args()

    plan = json.loads(pathlib.Path(args.plan).read_text(encoding="utf-8-sig"))
    roster_only = bool(plan.get("characters")) and "shots" not in plan
    if not roster_only and (not isinstance(plan.get("shots"), list) or not plan.get("act")):
        print("not a story plan: %s" % args.plan, file=sys.stderr)
        return 2
    issues = story_logic.validate_plan(plan)
    for issue in issues:
        if issue.level == "ERROR":
            print("STORY_ERROR shot %s %s: %s" % (issue.shot, issue.code, issue.detail), file=sys.stderr)
    blocking = blocked_by(issues, args.strict)
    if blocking:
        for issue in blocking:
            print("%s shot %s %s: %s" % (issue.level, issue.shot, issue.code, issue.detail),
                  file=sys.stderr)
        print("aborting before write: %d %s issue(s)" % (len(blocking), "strict" if args.strict else "P0"),
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
        # The global prompt describes the lead character only. Secondary
        # characters keep their actions, poses and expressions in their scoped
        # role clauses; pooling them here would mix two postures and two people
        # into one body descriptor.
        lead = p["participants"][0] if p["participants"] else ""
        p["action"] = list(dict.fromkeys(
            p["action"] + [v for v in p["character_actions"].get(lead, [])]))
        p["pose"] = list(dict.fromkeys(
            p["pose"] + [v for v in p["character_poses"].get(lead, [])]))
        if per_char:
            p["expression"] = list(p["expressions"].get(lead, []))
        p["phase"] = shot.get("phase", "")
        p["caption"] = shot["caption"]
        p["beat"] = shot.get("beat", "")
        parsed.append((shot, p))

    def id_of(name):
        row = cur.execute("SELECT id FROM tag WHERE canonical_name=?", (name,)).fetchone()
        return row[0] if row else None

    table = wardrobe.colour_table(cur)
    coloured, undecided = 0, set()
    act_colours = (plan.get("act") or {}).get("colour_choice") or {}
    for shot, p in parsed:
        wanted = dict(act_colours)
        wanted.update(shot.get("colour_choice") or {})
        new = wardrobe.under_fix(wardrobe.colorize(p["outfit"], table, wanted=wanted),
                                 table, explicit=set(wanted))
        if new != p["outfit"]:
            coloured += 1
            p["outfit"] = new
        for name, tid in p["outfit"]:
            e = table.get(tid)
            if e and tid == e["base_id"]:
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
    if str(plan.get("project", {}).get("content_profile", "")).lower() in ("nsfw", "explicit"):
        for ch in chars:
            words = {w.strip().replace("_", " ").lower()
                     for w in ident_lines.get(ch["code"], "").split(",")}
            if "adult" not in words and "mature female" not in words:
                print("WARN ADULT_TAG_MISSING %s: them adult/mature_female vao identity"
                      % ch["code"], file=sys.stderr)

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
            return "%dgirls" % girls
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
        line = story_logic.scene_line(shot, plan)
        out = dict(scene)
        out.setdefault("location", scene.get("location")
                       or (plan.get("style_json") or {}).get("background") or "")
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
        ident_tokens, scoped_ident = split_identities(p["participants"], ident_lines, drop)
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

        ident_keys = {_token_key(n) for n in ident_tokens}
        emitted = set(ident_keys)

        def take(names):
            return join_tags(take_unique(dict.fromkeys(names), emitted))

        def clean(group):
            return take(n for n, tid in p[group] if tid not in redundant)

        action_names = {n for n, _ in p["action"]}
        outfit_tokens = [n for n, tid in p["outfit"]
                         if _token_key(n) not in ident_keys and n not in action_names and tid not in redundant]
        body_tokens = [n for n, tid in p["body_state"]
                       if _token_key(n) not in ident_keys and n not in action_names and tid not in redundant]

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
        background_tokens = [t.strip() for t in re.split(r"[,;]", background_line) if t.strip()]
        parts += [clean("cast"),
                  take(outfit_tokens),
                  take(body_tokens),
                  clean("props"),
                  clean("action"),
                  clean("expression"),
                  clean("pose"),
                  clean("motion"),
                  clean("camera"),
                  take(background_tokens),
                  p["caption"]]
        prompt = ", ".join(x for x in parts if x)

        role_clauses = []
        for c in p["participants"]:
            scoped = [n.replace("_", " ") for n in scoped_ident.get(c, [])]
            scoped += [n.replace("_", " ") for n, _ in p["character_actions"].get(c, [])]
            scoped += [n.replace("_", " ") for n, _ in p["character_poses"].get(c, [])]
            gaze = p["character_gaze"].get(c)
            if gaze:
                scoped.append("looking toward " + char_name.get(gaze, str(gaze)))
            target = p["character_targets"].get(c)
            if target:
                scoped.append("interacting with " + char_name.get(target, str(target)))
            scoped = list(dict.fromkeys(scoped))
            if scoped:
                role_clauses.append("%s: %s" % (char_name.get(c, c), ", ".join(scoped)))
        seq0 = shot.get("sequence") or {}
        a0, t0 = seq0.get("actor"), seq0.get("target")
        pr0 = str(seq0.get("primaryAction") or seq0.get("action") or "")
        interaction = {}
        if a0 and t0 and pr0 and a0 != t0:
            interaction = {"actor": a0, "target": t0, "action": pr0,
                           "purpose": seq0.get("purpose") or shot.get("purpose", ""),
                           "eventId": seq0.get("eventId") or ""}
            directed = directed_clause(char_name, a0, t0, pr0)
            if directed and directed not in prompt:
                prompt = append_sentence(prompt, directed)

        if role_clauses:
            prompt = append_sentence(prompt, "; ".join(role_clauses))
        if plan.get("nl"):
            prompt = append_sentence(prompt, " ".join(nl_block()))

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
            "exposure_level": shot.get("exposure_level", ""),
            "sequence": shot.get("sequence") or {},
            "interaction": interaction,
            "reactions": shot.get("reactions") or {},
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
    for issue in semantic:
        print("%s shot %s %s: %s" % (issue.level, issue.shot, issue.code, issue.detail),
              file=(sys.stderr if issue.level == "ERROR" else sys.stdout))
    if blocked_by(semantic, args.strict):
        print("aborting before write: semantic issues block seed%s" % (" under --strict" if args.strict else ""),
              file=sys.stderr)
        return 1

    if args.dry_run:
        if "shots" not in plan:
            print("dry-run roster: project=%r characters=%d (no writes)"
                  % (pj["title"], len(chars)))
        else:
            print("dry-run: project=%r act_no=%s revision=%s shots=%d (no writes)"
                  % (pj["title"], plan["act"]["act_no"], plan["act"].get("revision", 1), len(built)))
        con.close()
        return 0

    ensure_runtime_tables(con)
    con.isolation_level = None
    try:
        con.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT id FROM project WHERE title=?", (pj["title"],))
        r = cur.fetchone()
        if r:
            pid = r[0]
            if plan.get("shots"):
                has_act = cur.execute("SELECT 1 FROM act WHERE project_id=? LIMIT 1", (pid,)).fetchone()
                if has_act:
                    cur.execute("UPDATE project SET idea=?, content_profile=? WHERE id=?",
                                (pj["idea"], pj["content_profile"], pid))
                else:
                    cur.execute("UPDATE project SET idea=?, content_profile=?, style_json=? WHERE id=?",
                                (pj["idea"], pj["content_profile"],
                                 json.dumps(pj["style_json"], ensure_ascii=False), pid))
        else:
            cur.execute("INSERT INTO project(title, idea, content_profile, style_json, created_at) VALUES(?,?,?,?,?)",
                        (pj["title"], pj["idea"], pj["content_profile"],
                         json.dumps(pj["style_json"], ensure_ascii=False),
                         datetime.now(timezone.utc).isoformat(timespec="seconds")))
            pid = cur.lastrowid

        char_ids = {}
        for ch in chars:
            cur.execute("SELECT id, identity_json, outfit_json FROM character_profile"
                        " WHERE project_id=? AND code=?", (pid, ch["code"]))
            r = cur.fetchone()
            ident = ch.get("identity_json") or (json.loads(r[1]) if r and r[1] else {})
            outfit = ch.get("outfit_json") or (json.loads(r[2]) if r and r[2] else {})
            payload = (json.dumps(ident, ensure_ascii=False), json.dumps(outfit, ensure_ascii=False))
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

        content_mode = "sfw" if str(pj.get("content_profile", "")).lower() == "sfw" else "nsfw"
        multi = False
        for item in built:
            shot, p, spec = item["shot"], item["p"], item["spec"]
            multi = multi or len(p["participants"]) > 1
            story_db.upsert_shot(cur, aid, shot["n"], char_ids[p["participants"][0]],
                                 item["pose_cid"], spec["signature"], spec, content_mode)
            lines.append(item["prompt"])

        story_db.prune_missing_shots(cur, aid, [item["shot"]["n"] for item in built])
        con.commit()
        out = pathlib.Path(plan["prompt_file"])
        negative = plan.get("negative_line", DEFAULT_NEGATIVE)
        files = [
            (out, "\n\n".join(lines) + "\n"),
            (out.with_name(out.stem + ".neg.txt"), negative + "\n"),
        ]
        record_publication(cur, aid, ac.get("revision", 1), files)
        con.commit()
        try:
            publish_files(files)
        except OSError as exc:
            print("prompt publish failed after DB commit: %s; rerun this plan to reconcile" % exc,
                  file=sys.stderr)
            raise
        mark_published(cur, aid, ac.get("revision", 1))
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
