"""Read canonical shot specs; never fall back to the removed legacy column."""
from __future__ import annotations

import json
import sqlite3
from typing import Any


def latest_shot_spec(con: sqlite3.Connection, shot_id: int) -> dict[str, Any]:
    row = con.execute(
        "SELECT spec_json FROM shot_spec_revision"
        " WHERE shot_id=? ORDER BY revision DESC LIMIT 1",
        (shot_id,),
    ).fetchone()
    if row is None:
        return {}
    value = json.loads(row[0])
    return value if isinstance(value, dict) else {}


def shot_specs_for_act(con: sqlite3.Connection, act_id: int) -> list[tuple[int, int, dict]]:
    """Return ``(shot_id, shot_no, spec)`` for every shot in an act."""
    rows = con.execute(
        "SELECT id, shot_no FROM shot WHERE act_id=? ORDER BY shot_no", (act_id,)
    ).fetchall()
    return [(int(sid), int(no), latest_shot_spec(con, int(sid))) for sid, no in rows]
