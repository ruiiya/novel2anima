# novel2anima P0P1 upgrade
"""Infer experimental continuity state (rules v0.4) into shot_state / act_continuity.

v0.3 adds decay: a state that is not refreshed by the current shot loses severity and is
removed when it reaches zero (sweat dries faster than a bite mark). Rules remain a
hypothesis; see skills/novel2anima-shot-pipeline/references/continuity-state.md

Default is REPORT-ONLY: it prints what would be written. Pass --apply to write.
"""
import argparse, json, pathlib, sqlite3, sys

from novel2anima.paths import DB_PATH
from novel2anima.continuity.rules import *
from novel2anima.continuity.rules import RULES_VERSION

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--apply", action="store_true",
                    help="write shot_state/act_continuity (default: report only)")
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys=ON")
    if args.apply:  # older DBs may predate the observation tables
        con.executescript((pathlib.Path(__file__).resolve().parents[3]
                           / "sql" / "migrations" / "004_observation_publication.sql"
                           ).read_text(encoding="utf-8"))
    cur = con.cursor()

    def tid(name):
        r = cur.execute("SELECT id FROM tag WHERE canonical_name=?", (name,)).fetchone()
        if not r:
            print("missing tag: %s" % name, file=sys.stderr)
            sys.exit(1)
        return r[0]

    ladder_ids = {ax: [(lvl, tid(v), pred) for lvl, v, pred in steps] for ax, steps in LADDERS.items()}
    stage_ids = {lvl: (tid(v) if v else None) for lvl, v, _ in OUTFIT_STAGE}

    SRC = "inferred:" + RULES_VERSION
    acts = cur.execute("SELECT id, act_no FROM act ORDER BY act_no").fetchall()
    rows, removals = 0, 0
    for act_id, act_no in acts:
        shots = cur.execute("SELECT shot_no, shot_spec_json FROM shot WHERE act_id=? ORDER BY shot_no",
                            (act_id,)).fetchall()
        # Experimental counters are act-scoped, not character-scoped: disable for duo
        # rather than silently applying inferred state to both participants.
        if any(len(json.loads(spec_json).get("participants") or []) != 1
               for _no, spec_json in shots):
            print("skip inferred act continuity %s: multi-character state must be per participant" % act_no)
            continue
        if args.apply:  # only rows owned by this pipeline; manual shot_state/act_continuity stay intact
            cur.execute("DELETE FROM shot_observation WHERE source LIKE 'inferred:%'"
                        " AND shot_id IN (SELECT id FROM shot WHERE act_id=?)", (act_id,))
            cur.execute("DELETE FROM act_observation WHERE source LIKE 'inferred:%' AND act_id=?", (act_id,))
        counts = {k: 0 for k in ("genital", "fingers", "strong", "ejac", "sweat", "saliva", "kiss",
                                 "bite", "scratch", "tremble", "toy", "rope", "ownership",
                                 "semen", "pregnancy", "lactation", "impact", "spank", "whip", "pierced")}
        flags = {"blush": 0, "bare": 0, "motion": 0, "after": 0, "shoulder": 0}
        live, stage, opening, first_bg = {}, 0, set(), ""

        def write(shot_no, axis, vtid, sev, since, cause, source):
            if not args.apply:
                return
            cur.execute("INSERT OR REPLACE INTO shot_observation(shot_id, axis, value_tag_id, severity, since_shot_no,"
                        " cause_shot_no, source) VALUES((SELECT id FROM shot WHERE act_id=? AND shot_no=?),"
                        "?,?,?,?,?,?)", (act_id, shot_no, axis, vtid, sev, since, cause, source))

        for shot_no, spec_json in shots:
            spec = json.loads(spec_json)
            names = set()
            for g in ("outfit", "body_state", "props", "action", "expression", "pose", "motion", "camera"):
                names |= {t["name"] for t in spec.get(g, [])}
            caption = (spec.get("caption", "") + " " + spec.get("beat", "")).lower()
            if shot_no == shots[0][0]:
                opening = set(names)
                first_bg = spec.get("background") or ""
            for key, watch in (("genital", GENITAL), ("fingers", FINGERS), ("strong", STRONG), ("ejac", EJAC),
                               ("sweat", SWEAT), ("saliva", SALIVA), ("kiss", KISS), ("bite", BITE),
                               ("scratch", SCRATCH), ("tremble", TREMBLE), ("toy", TOY),
                               ("rope", ROPE), ("ownership", OWNERSHIP), ("semen", SEMEN),
                               ("pregnancy", BELLY), ("lactation", LACTATION), ("impact", IMPACT),
                               ("spank", SPANK), ("whip", WHIP), ("pierced", PIERCED)):
                if names & watch:
                    counts[key] += 1
            if names & {"blush"}:
                flags["blush"] += 1
            if names & {"nipples", "topless", "completely_nude"}:
                flags["bare"] += 1
            if names & {"messy_hair"}:
                flags["motion"] += 1
            if names & AFTER:
                flags["after"] += 1
            if "shoulder" in caption or "vai" in caption:
                flags["shoulder"] = 1

            for axis, steps in ladder_ids.items():
                level, value = 0, None
                for lvl, vtid, pred in steps:
                    if pred(counts, flags) and lvl > level:
                        level, value = lvl, vtid
                watch, decay = REFRESH[axis]
                refreshed = bool(names & watch)
                if value is None:
                    if axis in live:                       # no longer supported by the beat
                        live[axis][4] -= decay
                    continue
                if axis not in live:
                    live[axis] = [value, level, shot_no, shot_no, severity_of(level)]
                elif level > live[axis][1]:
                    live[axis] = [value, level, live[axis][2], shot_no,
                                  max(live[axis][4], severity_of(level))]
                elif refreshed:
                    live[axis][4] = max(live[axis][4], severity_of(level))
                else:
                    live[axis][4] -= decay

            for lvl, _name, trig in OUTFIT_STAGE:
                if lvl > stage and names & set(trig):
                    stage = lvl
            if "outfit:stage" not in live:
                live["outfit:stage"] = [stage_ids[stage], stage, shot_no, shot_no, 0.5]
            elif live["outfit:stage"][1] != stage:
                live["outfit:stage"] = [stage_ids[stage], stage, live["outfit:stage"][2], shot_no, 0.5]

            if stage < 3 and counts["sweat"] >= 1:
                if "outfit:soaked" not in live:
                    live["outfit:soaked"] = [tid("wet_clothes"), 1, shot_no, shot_no, 0.5]
            elif "outfit:soaked" in live:
                _, _, since, _, sev = live.pop("outfit:soaked")
                write(shot_no, "outfit:soaked", None, 0.0, since, shot_no, SRC + ":removed")
                removals += 1

            for axis in sorted(live):
                vtid, lvl, since, cause, sev = live[axis]
                if axis.startswith("outfit:"):
                    write(shot_no, axis, vtid, sev, since, cause, SRC)
                    rows += 1
                    continue
                if sev <= 1e-9:      # float drift: 0.6 - 0.12*5 is not exactly 0
                    write(shot_no, axis, None, 0.0, since, shot_no, SRC + ":decayed")
                    del live[axis]
                    removals += 1
                    continue
                write(shot_no, axis, vtid, round(sev, 3), since, cause, SRC)
                rows += 1

        props = sorted(opening & {"choker", "rope", "crotch_rope", "shackles", "handcuffs", "chain_leash",
                                  "leash", "blindfold", "slave_tattoo", "body_writing", "pregnancy_mark"})
        body = sorted((opening & BELLY) | (opening & {"nipples"}))
        fluids = sorted((opening & SEMEN) | (opening & {"saliva", "sweat", "pussy_juice", "female_ejaculation"}))
        for axis, note in (("fluid", "opening frame already shows: " + ", ".join(fluids) if fluids
                            else "act starts clean: no fluids"),
                           ("mark", "opening frame already carries: " + ", ".join(props) if props
                            else "act starts clean: no marks"),
                           ("outfit", "opening frame: " + ", ".join(sorted(set(props) | set(body))) if props or body
                            else "act starts fully dressed"),
                           ("environment", "opening set: " + first_bg if first_bg
                            else "no background recorded in opening shot")):
            if args.apply:
                cur.execute("INSERT OR REPLACE INTO act_observation(act_id, axis, initial_tag_id, notes, source)"
                            " VALUES(?,?,NULL,?,?)", (act_id, axis, note, SRC))
    if args.apply:
        con.commit()
    print("%s (rules %s): shot_observation rows: %d | removals (decay/end of state): %d | acts: %d"
          % ("applied" if args.apply else "report-only, pass --apply to write", RULES_VERSION,
             rows, removals, len(acts)))
    con.close()

if __name__ == "__main__":
    main()
