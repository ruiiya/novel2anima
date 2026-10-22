# novel2anima P0P1 upgrade
# -*- coding: utf-8 -*-
"""Xac dinh van de cua tung shot bang du lieu trong catalog (khong tu sua prompt).

Usage:
  python etl/qa_shots.py [--act N] [--apply]

ghi vao bang shot_finding (rule_id, axis, value_tag_id, severity, source)
de model/nguoi doc roi quyet dinh - day la phan "xac dinh van de" thay cho viec sua cung:
  * mau_thieu    - mon do chua co mau nao trong db (chua chuan bi cho phase 1)
  * mau_lech     - mon do co mau trong db nhung shot dung ban khong mau (prompt chua chuan hoa)
  * xung_dot     - 2 tag trong cung shot co quan he conflicts
  * tu_the_lech  - tu the lui thang (dung -> quy -> ngoi -> nam) so voi shot truoc
  * noi_dung_chan- tag bi danh dau blocked trong tag_content_label
"""
import argparse, collections, json, pathlib, sys

from novel2anima.paths import PLANS_DIR
from novel2anima.catalog import build_service as build
from novel2anima.wardrobe import rules as wardrobe
from novel2anima.storage import story_repository as story_db
from novel2anima.story import logic as story_logic

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SOURCE = "qa:v1"
SEV = {"mau_thieu": 0.4, "mau_lech": 0.5, "xung_dot": 0.6, "tu_the_lech": 0.5, "noi_dung_chan": 1.0}

def shot_refs(spec):
    out = {}
    for group in ("identity", "outfit", "body_state", "props", "cast",
                  "action", "expression", "pose", "motion", "camera"):
        for x in spec.get(group) or []:
            out.setdefault(group, []).append((x["name"], x["tagId"]))
    return out

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--act", type=int)
    ap.add_argument("--project")
    ap.add_argument("--revision", type=int)
    ap.add_argument("--db", default=build.DB_PATH)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    con = build.connect(args.db)
    con.isolation_level = None
    table = wardrobe.colour_table(con)
    conflicts = collections.defaultdict(set)
    for a, b, note in con.execute("SELECT from_tag_id, to_tag_id, note FROM tag_relation"
                                  " WHERE relation='conflicts'"):
        sev = SEV["xung_dot"] * 0.5 if note and "confused" in note else SEV["xung_dot"]
        conflicts[a].add((b, sev))          # note dang "not to be confused" -> chi la nhac nho
        conflicts[b].add((a, sev))
    blocked = {r[0] for r in con.execute("SELECT tag_id FROM tag_content_label WHERE scope='blocked'")}

    plans = {}
    for path in PLANS_DIR.glob("*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        ac = d.get("act") or {}
        if d.get("shots") and (d.get("project") or {}).get("title") and ac.get("act_no"):
            plans[((d["project"]["title"]), ac["act_no"], ac.get("revision", 1))] = d
    acts = con.execute("SELECT a.id, a.act_no, p.title, a.revision FROM act a JOIN project p ON p.id=a.project_id "
                       "WHERE (? IS NULL OR a.act_no=?) AND (? IS NULL OR p.title=?) "
                       "AND (? IS NULL OR a.revision=?) ORDER BY p.title, a.act_no",
                       (args.act, args.act, args.project, args.project, args.revision, args.revision)).fetchall()
    if args.act is not None and len(acts) != 1:
        raise SystemExit("act ambiguous/not found; specify --project and --revision")
    found = collections.Counter()
    rows = []
    for aid, act_no, project_title, revision in acts:
        plan = plans.get((project_title, act_no, revision))
        floor, cause, phase = -1, 0, None
        specs, shot_ids = [], {}
        for shot_id, shot_no, spec_json in con.execute(
                "SELECT id, shot_no, shot_spec_json FROM shot WHERE act_id=? ORDER BY shot_no", (aid,)):
            spec = json.loads(spec_json)
            specs.append((shot_no, spec))
            shot_ids[shot_no] = shot_id
            refs = shot_refs(spec)
            worn = refs.get("outfit", [])
            ids = {t for _n, t in worn}
            # mau
            for n, t in worn:
                e = table.get(t)
                if not e or t != e["base_id"] or wardrobe.colour_of(n)[0]:
                    continue                     # khong phai do goc -> da co mau trong ten
                axis = None
                if not e["chosen"] and not e["cue"]:
                    axis = "mau_thieu"           # phase 1 chua chuan bi bo mau cho mon nay
                elif e["cue"] and e["cue"][1] in ids:
                    pass                         # da co cue <mau>_clothing trong shot
                else:
                    axis = "mau_lech"            # db biet mau nhung prompt khong mang mau
                if axis:
                    rows.append((shot_id, axis, t, SEV[axis], shot_no, shot_no))
                    found[axis] += 1
            # xung dot
            for t in ids:
                for other, sev in conflicts.get(t, ()):
                    if other in ids and t < other:
                        rows.append((shot_id, "xung_dot", other, sev, shot_no, shot_no))
                        found["xung_dot"] += 1
            # noi dung bi chan
            for grp in refs.values():
                for _n, t in grp:
                    if t in blocked:
                        rows.append((shot_id, "noi_dung_chan", t, SEV["noi_dung_chan"], shot_no, shot_no))
                        found["noi_dung_chan"] += 1
            # The old monotone pose ladder is invalid for normal narratives.
            # Missing bridges are validated conservatively in story_logic/check_story,
            # without treating sitting -> standing as an intrinsically invalid pose.
        phase_contract = (plan or {}).get("act", {}).get("phase_contract")
        if not phase_contract:
            print("phase_contract missing for %s act %s: phase coverage NOT checked"
                  % (project_title, act_no))
            if args.apply and shot_ids:
                first = min(shot_ids)
                story_db.record_finding(con, shot_ids[first], "phase_contract_missing",
                                        SOURCE, 0.3, evidence={"reason": "no plan/phase_contract"})
        for issue in story_logic.validate_specs(
                specs, phase_contract=phase_contract, blocked_ids=blocked):
            sev = SEV["xung_dot"] if issue.level == "ERROR" else 0.4
            sid = shot_ids.get(issue.shot)
            if sid is None:
                continue
            rows.append((sid, "semantic:" + issue.code, None, sev, issue.shot, issue.shot))
            found["semantic"] += 1
    print("van de tim thay: %s" % dict(found or {"khong co": 0}))
    if rows:
        print("vi du:")
        for r in rows[:8]:
            name = con.execute("SELECT canonical_name FROM tag WHERE id=?", (r[2],)).fetchone()
            print("  shot_id=%s %-14s tag=%-24s sev=%s" % (r[0], r[1], name[0] if name else r[2], r[3]))
    if not args.apply:
        print("dry-run: them --apply de ghi vao shot_finding")
        con.close()
        return
    con.execute("BEGIN")
    for aid, _act_no, _title, _rev in acts:
        story_db.clear_findings_for_act(con, SOURCE, aid)
    for r in rows:
        sid, axis, tid, sev = r[:4]
        since, cause_ = (r[4], r[5]) if len(r) == 6 else (None, None)
        story_db.record_finding(con, sid, axis, SOURCE, sev,
                                axis=axis, value_tag_id=tid,
                                evidence={"since": since, "cause": cause_})
    con.commit()
    print("shot_finding: %d dong (source=%s)" % (len(rows), SOURCE))
    con.close()

if __name__ == "__main__":
    main()


