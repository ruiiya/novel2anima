"""PR-07: DB-only prompt compile, render pinning, QA history and revisions."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.prompting.compiler import (  # noqa: E402
    approve_prompt,
    compile_shot,
    load_prompt,
    replay_prompt,
)
from novel2anima.quality.qa import (  # noqa: E402
    apply_targeted_revision,
    qa_history,
    record_qa_run,
)
from novel2anima.render.service import create_render, get_render, replay_render  # noqa: E402
from novel2anima.storage.assets import get_asset, put_asset  # noqa: E402
from novel2anima.storage.domain_repository import (  # noqa: E402
    add_interaction,
    add_participant,
    bind_outfit,
    create_outfit_revision,
    create_shot_spec_revision,
)
from novel2anima.storage.migrations import apply_migrations  # noqa: E402

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_db(root: Path) -> Path:
    db = root / "staging.db"
    con = sqlite3.connect(db)
    con.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
    con.commit()
    con.close()
    migrations = root / "migrations"
    migrations.mkdir()
    for name in (
        "005_db_first.sql",
        "006_normalization.sql",
        "007_reconciliation_queue.sql",
        "009_llm_registry.sql",
        "010_prompt_pinning.sql",
    ):
        shutil.copy2(ROOT / "sql/migrations" / name, migrations / name)
    report = apply_migrations(db, migrations, backup_path=root / "pre.db")
    assert report["status"] == "ok", report
    return db


def fixture(db: Path) -> None:
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        con.execute("INSERT INTO project(id,title) VALUES(1,'P1')")
        for character_id, code in ((1, "ALPHA"), (2, "BETA")):
            con.execute(
                "INSERT INTO character_profile(id,project_id,code,identity_json,outfit_json)"
                " VALUES(?,?,?,'{}','{}')",
                (character_id, 1, code),
            )
        con.execute(
            "INSERT INTO act(id,project_id,act_no,title,revision,status)"
            " VALUES(1,1,1,'Act',1,'planned')"
        )
        con.execute(
            "INSERT INTO shot(id,act_id,shot_no,character_id,shot_spec_json,status)"
            " VALUES(1,1,1,1,'{}','planned')"
        )
        tag_names = (
            "long_hair", "white_shirt", "black_shirt", "headpat", "standing",
            "bedroom", "smile",
        )
        con.executemany(
            "INSERT INTO tag(id,canonical_name,search_name) VALUES(?,?,?)",
            [(i + 1, name, name.replace("_", " ")) for i, name in enumerate(tag_names)],
        )
        con.execute(
            "INSERT INTO model_profile(id,code,model_name) VALUES(1,'anima','anima')"
        )
        con.commit()
    finally:
        con.close()


class CompileRenderQa(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = create_db(Path(self.temp.name))
        fixture(self.db)
        self.con = sqlite3.connect(self.db)
        self.con.execute("PRAGMA foreign_keys=ON")
        add_participant(self.con, 1, 1, slot_no=1)
        add_participant(self.con, 1, 2, slot_no=2)
        add_interaction(self.con, 1, 2, 1, "headpat", sort_order=1)
        first = create_outfit_revision(
            self.con,
            1,
            {"tags": ["white_shirt"]},
            [{"item_code": "top", "slot": "upper", "garment_type": "shirt"}],
            status="approved",
        )
        second = create_outfit_revision(
            self.con,
            2,
            {"tags": ["black_shirt"]},
            [{"item_code": "top", "slot": "upper", "garment_type": "shirt"}],
            status="approved",
        )
        bind_outfit(self.con, 1, 1, first)
        bind_outfit(self.con, 1, 2, second)
        create_shot_spec_revision(
            self.con,
            1,
            {
                "participants": [1, 2],
                "identity_tags": {"1": ["long_hair"], "2": ["long_hair"]},
                "action_tags": ["standing"],
                "background_tags": ["bedroom"],
                "negative_prompt": "bad",
            },
            status="approved",
        )
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def test_compile_is_db_only_and_preserves_direction(self):
        prompt_id = compile_shot(self.con, 1)
        prompt = load_prompt(self.con, prompt_id)
        self.assertIn("long_hair", prompt["positive_tags"])
        self.assertIn("white_shirt", prompt["positive_tags"])
        self.assertIn("headpat", prompt["positive_tags"])
        interaction = self.con.execute(
            "SELECT character_id,target_character_id,token_role FROM shot_prompt_tag"
            " WHERE shot_prompt_revision_id=? AND token_role='interaction'",
            (prompt_id,),
        ).fetchone()
        self.assertEqual(interaction, (2, 1, "interaction"))
        self.assertEqual(prompt["outfits"], [(1, 1), (2, 2)])
        self.assertEqual(len(prompt["catalog_snapshot_sha256"]), 64)
        self.assertEqual(replay_prompt(self.con, prompt_id)["content_sha256"], prompt["content_sha256"])

    def test_render_blob_sha_and_db_only_replay(self):
        prompt_id = compile_shot(self.con, 1)
        approve_prompt(self.con, prompt_id)
        image = b"\x89PNG\r\n\x1a\n" + b"render-bytes"
        result = create_render(
            self.con,
            shot_id=1,
            model_profile_id=1,
            prompt_revision_id=prompt_id,
            image=image,
            seed=42,
            model_settings={"sampler": "er_sde", "steps": 4},
        )
        self.assertEqual(result.sha256, hashlib.sha256(image).hexdigest())
        stored = get_render(self.con, result.generation_id)
        self.assertEqual(stored["bytes"], image)
        replay = replay_render(self.con, result.generation_id)
        self.assertEqual(replay["seed"], 42)
        self.assertEqual(replay["prompt_revision_id"], prompt_id)
        self.assertEqual(replay["outfit_snapshot_sha256"], load_prompt(self.con, prompt_id)["outfit_snapshot_sha256"])
        asset_id = put_asset(self.con, image, "image/png")
        self.assertEqual(asset_id, result.asset_id)
        self.assertEqual(get_asset(self.con, asset_id)[0], image)

    def test_qa_history_is_append_only_and_targeted_revision_keeps_old(self):
        prompt_id = compile_shot(self.con, 1)
        approve_prompt(self.con, prompt_id)
        run_id = record_qa_run(
            self.con,
            act_id=1,
            run_key="qa-1",
            evaluator_version="qa-v1",
            issues=[{
                "shot_id": 1, "rule_id": "expression.missing", "severity": 0.4,
                "actor_character_id": 2, "target_character_id": 1,
                "evidence": {"source": "review"},
            }],
        )
        again = record_qa_run(
            self.con, act_id=1, run_key="qa-1", evaluator_version="qa-v1", issues=[]
        )
        self.assertEqual(run_id, again)
        history = qa_history(self.con, 1)
        self.assertEqual(len(history), 1)
        issue_id = history[0]["issue_id"]
        old_spec = self.con.execute(
            "SELECT spec_json FROM shot_spec_revision WHERE id=?",
            (load_prompt(self.con, prompt_id)["shot_spec_revision_id"],),
        ).fetchone()[0]
        new_spec_id = apply_targeted_revision(
            self.con,
            prompt_revision_id=prompt_id,
            qa_issue_id=issue_id,
            patch={"expression_tags": ["smile"]},
            reason="add the missing expression",
        )
        new_spec = self.con.execute(
            "SELECT spec_json,status FROM shot_spec_revision WHERE id=?", (new_spec_id,)
        ).fetchone()
        self.assertEqual(new_spec[1], "draft")
        self.assertEqual(json.loads(new_spec[0])["participants"], [1, 2])
        self.assertEqual(json.loads(new_spec[0])["targeted_revision"]["qa_issue_id"], issue_id)
        self.assertEqual(
            self.con.execute(
                "SELECT spec_json FROM shot_spec_revision WHERE id=?",
                (load_prompt(self.con, prompt_id)["shot_spec_revision_id"],),
            ).fetchone()[0],
            old_spec,
        )

    def test_prompt_approval_blocks_tag_rewrite(self):
        prompt_id = compile_shot(self.con, 1)
        approve_prompt(self.con, prompt_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute(
                "INSERT INTO shot_prompt_tag"
                "(shot_prompt_revision_id,seq,tag_id,token_role,weight)"
                " VALUES(?,999,1,'identity',1.0)",
                (prompt_id,),
            )


if __name__ == "__main__":
    unittest.main()
