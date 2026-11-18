"""Remove interactions from off-frame events so the seal's actor/target check stays truthful.

The knock/phone/door events are performed by HUSBAND_C or PARTNER_B outside the frame.
The shot visualizes the reaction, so it has participants but no actor->target interaction.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "database/src")
from n2m_db import connect  # noqa: E402
from n2m_workflow import save_continuity, save_shot  # noqa: E402

ROOT = pathlib.Path("exports/anniversary_gift")
STATE = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
SHOTS = json.loads((ROOT / "shots.json").read_text(encoding="utf-8"))
OFF_FRAME = {"P1.B07", "P4.B03", "P4.B05", "P5.B07"}

con = connect(pathlib.Path("database/data/novel2anima.db"))
changed = 0
for key, info in list(SHOTS.items()):
    if info["beat_key"] not in OFF_FRAME:
        continue
    old_id = info["shot_id"]
    row = con.execute("SELECT shot_spec_json FROM shots WHERE id=?", (old_id,)).fetchone()
    spec = json.loads(row["shot_spec_json"])
    spec["interactions"] = []
    spec["continuity_revision_note"] = "off-frame event: reaction coverage without interaction"
    new_id, new_rev = save_shot(con, con.execute(
        "SELECT beat_id FROM shots WHERE id=?", (old_id,)).fetchone()["beat_id"],
        key, spec, info["event_id"])
    if new_id != old_id:
        snaps = []
        for r in con.execute("""SELECT s.role_key,c.before_json,c.delta_json,c.after_json
                                FROM continuity_snapshots c LEFT JOIN story_roles s ON s.id=c.story_role_id
                                WHERE c.shot_id=?""", (old_id,)):
            snaps.append({"role_key": r["role_key"], "before": json.loads(r["before_json"]),
                          "delta": json.loads(r["delta_json"]), "after": json.loads(r["after_json"])})
        save_continuity(con, new_id, {"snapshots": snaps})
        SHOTS[key]["shot_id"] = new_id
        SHOTS[key]["shot_rev"] = new_rev
        changed += 1
        print(key, old_id, "->", new_id, "rev", new_rev)

(ROOT / "shots.json").write_text(json.dumps(SHOTS, ensure_ascii=False, indent=1), encoding="utf-8")
print("changed:", changed)
