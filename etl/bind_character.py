# novel2anima P0P1 upgrade
"""Bind a blind-mode placeholder slot to a catalog character_profile row.

Usage:
  python etl/bind_character.py --plan data/plans/blind.json --slot LEAD \
      --character ba_asuna_blue_archive
  python etl/bind_character.py --list asuna
  python etl/bind_character.py ... --project-id 1 --out data/plans/bound.json --dry-run

The slot code is replaced by the DB code in characters[] and in every per-character
map (participants, character_actions/poses/gaze/targets, reactions, sequence
actor/target). Identity/outfit come from character_profile; the placeholder
appearance anchors are discarded. Nothing is written unless the plan still
validates.
"""
import argparse
import json
import os
import pathlib
import re
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import story_logic

PER_CHAR_MAPS = ("character_actions", "character_poses", "character_gaze",
                 "character_targets", "expressions", "reactions")


def humanize(tag):
    base = re.sub(r"\([^)]*\)", "", str(tag).replace("_", " "))
    base = re.sub(r":\s*\d+$", "", base).strip()
    return " ".join(w.capitalize() for w in base.split()) or str(tag)


def profile_to_character(row, slot):
    code = row["code"]
    identity = json.loads(row["identity_json"] or "{}")
    outfit = json.loads(row["outfit_json"] or "{}")
    tags = [str(t) for t in identity.get("identity_tags") or []]
    attrs = [str(a) for a in identity.get("attributes") or []]
    line = list(dict.fromkeys(tags + attrs))
    if identity.get("adult") is True and "adult" not in line:
        line.append("adult")
    attr_set = {a.replace("_", " ") for a in attrs}
    gender = slot.get("gender", "girl")
    if "1boy" in attr_set or "1male" in attr_set:
        gender = "boy"
    elif "1girl" in attr_set or "1female" in attr_set:
        gender = "girl"
    name = humanize(tags[0]) if tags else humanize(code)
    return {
        "code": code,
        "name": name,
        "gender": gender,
        "adult": bool(identity.get("adult") is True or slot.get("adult") is True),
        "identity_line": ", ".join(line),
        "identity_json": identity,
        "outfit_json": outfit,
    }


def rename_slot(plan, old, new):
    chars = plan.get("characters") or ([plan["character"]] if plan.get("character") else [])
    for shot in plan.get("shots") or []:
        parts = shot.get("participants")
        if isinstance(parts, list):
            shot["participants"] = [new if c == old else c for c in parts]
        for key in PER_CHAR_MAPS:
            m = shot.get(key)
            if isinstance(m, dict):
                shot[key] = {(new if k == old else k): (new if v == old else v)
                             for k, v in m.items()}
        seq = shot.get("sequence")
        if isinstance(seq, dict):
            for k in ("actor", "target"):
                if seq.get(k) == old:
                    seq[k] = new


def bind(plan, slot_code, row, force=False):
    """Return (plan, warnings). Raises ValueError on unusable input."""
    chars = plan.get("characters") or []
    slot = next((c for c in chars if c.get("code") == slot_code), None)
    if slot is None:
        raise ValueError("slot %r not in characters[] (have: %s)"
                         % (slot_code, ", ".join(c.get("code", "?") for c in chars)))
    warnings = []
    if slot.get("role") != "placeholder" or slot.get("identity_json", {}).get("identity_tags"):
        if not force:
            raise ValueError("slot %r is not a placeholder; pass --force to overwrite" % slot_code)
        warnings.append("overwrote non-placeholder slot %s" % slot_code)
    new_code = row["code"]
    if new_code != slot_code and any(c.get("code") == new_code for c in chars):
        raise ValueError("character %r already bound in this plan" % new_code)
    bound = profile_to_character(row, slot)
    chars[chars.index(slot)] = bound
    rename_slot(plan, slot_code, new_code)
    if plan.get("blind_mode") and all(c.get("role") != "placeholder" for c in chars):
        plan["blind_mode"] = False
        warnings.append("blind_mode=false: no placeholder slots remain")
    return plan, warnings


def select_row(cur, code, project_id=None):
    rows = cur.execute(
        "SELECT id, project_id, code, identity_json, outfit_json FROM character_profile"
        " WHERE code=? ORDER BY id DESC", (code,)).fetchall()
    if not rows:
        raise ValueError("no character_profile with code %r" % code)
    if project_id is not None:
        rows = [r for r in rows if r[1] == project_id]
        if not rows:
            raise ValueError("code %r not in project %s" % (code, project_id))
    cols = ("id", "project_id", "code", "identity_json", "outfit_json")
    rows = [dict(zip(cols, r)) for r in rows]
    if len(rows) > 1:
        raise ValueError("code %r is ambiguous across projects %s; pass --project-id"
                         % (code, sorted({r["project_id"] for r in rows})))
    return rows[0]


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
    ap.add_argument("--plan", help="blind-mode plan JSON")
    ap.add_argument("--slot", help="placeholder code, e.g. LEAD")
    ap.add_argument("--character", help="character_profile.code from the DB")
    ap.add_argument("--db", default="db/novel_anima.db")
    ap.add_argument("--project-id", type=int)
    ap.add_argument("--out", help="write here instead of overwriting --plan")
    ap.add_argument("--list", nargs="?", const="", metavar="QUERY",
                    help="list character_profile codes; optional substring filter")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()
    try:
        if args.list is not None:
            q = "%%%s%%" % args.list
            rows = cur.execute(
                "SELECT project_id, code, identity_json FROM character_profile"
                " WHERE code LIKE ? ORDER BY project_id, code", (q,)).fetchall()
            for pid, code, ident in rows:
                tags = (json.loads(ident or "{}").get("identity_tags") or [""])
                print("%s\t%s\t%s" % (pid, code, humanize(tags[0]) if tags else ""))
            print("%d row(s)" % len(rows), file=sys.stderr)
            return 0
        missing = [f for f in ("plan", "slot", "character") if not getattr(args, f)]
        if missing:
            ap.error("required: --%s" % ", --".join(missing))
        row = select_row(cur, args.character, args.project_id)
    except ValueError as exc:
        print("bind error: %s" % exc, file=sys.stderr)
        return 2
    finally:
        con.close()

    src = pathlib.Path(args.plan)
    plan = json.loads(src.read_text(encoding="utf-8-sig"))
    try:
        plan, warnings = bind(plan, args.slot, row, force=args.force)
    except ValueError as exc:
        print("bind error: %s" % exc, file=sys.stderr)
        return 1
    for w in warnings:
        print("WARN %s" % w, file=sys.stderr)
    issues = story_logic.validate_plan(plan) if plan.get("shots") else []
    for issue in issues:
        if issue.level == "ERROR":
            print("ERROR shot %s %s: %s" % (issue.shot, issue.code, issue.detail), file=sys.stderr)
    errors = [i for i in issues if i.level == "ERROR"]
    if errors and not args.force:
        print("aborting: bound plan has %d ERROR(s); --force to write anyway" % len(errors),
              file=sys.stderr)
        return 1

    text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.dry_run:
        print("dry-run: %s %s -> %s (%d shots, no write)"
              % (args.slot, args.plan, row["code"], len(plan.get("shots") or [])))
        return 0
    dest = pathlib.Path(args.out) if args.out else src
    atomic_write(dest, text)
    print("bound %s -> %s (project %s) in %s" % (args.slot, row["code"], row["project_id"], dest))
    if plan.get("blind_mode") is False:
        print("blind_mode=false: all slots bound")
    return 0


if __name__ == "__main__":
    sys.exit(main())
