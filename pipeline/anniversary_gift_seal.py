"""Seal the 122-shot storyboard after prompt QA, then export the story prompts."""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "database/src")
from n2m_db import connect, export_story_prompts  # noqa: E402
from n2m_storyboard import seal_storyboard  # noqa: E402

ROOT = pathlib.Path("exports/anniversary_gift")
STATE = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
PROMPTS = json.loads((ROOT / "prompts.json").read_text(encoding="utf-8"))

bindings = {key: {"shot_id": info["shot_id"], "prompt_id": info["prompt_id"]}
            for key, info in PROMPTS.items()}
sequence_qa = {
    "verdict": "PASS",
    "evidence": (
        "122 shots / 40 beats / 40 events; every Event VISUALIZED; one suite and one couple; "
        "continuity chain checked; 119 prompts pass the Anima format validator; 3 scenery "
        "prompts carry a documented subject-count exception; no tattoo; HUSBAND_C off-frame."
    ),
}
con = connect(pathlib.Path("database/data/novel2anima.db"))
seal = seal_storyboard(con, STATE["storyboard_id"], {"bindings": bindings, "sequence_qa": sequence_qa})
print("sealed:", STATE["storyboard_id"], "bindings:", len(seal["bindings"]))
out = pathlib.Path("exports/anniversary_gift/export")
result = export_story_prompts(con, STATE["story_id"], out_dir=out)
print(json.dumps(result, ensure_ascii=False, indent=2))
