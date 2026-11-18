import json, pathlib, sys
sys.path.insert(0, "database/src")
from n2m_db import connect
from n2m_storyboard import save_storyboard

ROOT = pathlib.Path("exports/anniversary_gift")
state = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
board = json.loads((ROOT / "storyboard.draft.json").read_text(encoding="utf-8"))
board["approval"] = {
    "status": "APPROVED",
    "approved_by": "user",
    "approved_at": "2026-11-17T00:00:00Z",
    "evidence": "User said ok to the 122-shot storyboard draft.",
}
con = connect(pathlib.Path("database/data/novel2anima.db"))
bid, rev = save_storyboard(con, state["story_id"], board, expected_revision=0)
state["storyboard_id"] = bid
state["storyboard_revision"] = rev
(ROOT / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
print("storyboard:", bid, "revision:", rev)
