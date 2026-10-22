"""PR-06: eleven LLM stage contracts, approval gate and idempotent runs."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.llm.contracts import (  # noqa: E402
    STAGES,
    ContractError,
    StageBlocked,
    load_schema,
    validate_output,
)
from novel2anima.llm.registry import (  # noqa: E402
    active_template,
    approve,
    create_draft,
    invoke_stage,
    retire,
)
from novel2anima.storage.migrations import apply_migrations  # noqa: E402

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


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
    ):
        shutil.copy2(ROOT / "sql/migrations" / name, migrations / name)
    report = apply_migrations(db, migrations, backup_path=root / "pre.db")
    assert report["status"] == "ok", report
    return db


def valid_output(stage: str) -> dict:
    payload = {
        "schema_version": "v4-1",
        "stage": stage,
        "status": "proposed",
        "decisions": {},
        "uncertainties": [],
        "evidence_refs": [],
    }
    extra = {
        "01_brief": {"brief": {"idea": "test"}},
        "02_story": {"story": {"title": "test"}},
        "03_character": {"characters": [{"code": "A", "name": "Alpha"}]},
        "04_wardrobe": {"items": [{"item_code": "top", "slot": "upper", "garment_type": "shirt"}]},
        "05_act_beats": {"acts": [{"act_no": 1, "beats": [{"kind": "setup"}]}]},
        "06_shot_direction": {
            "shot_id": 1,
            "participants": [1],
            "interactions": [],
            "outfit_bindings": [],
            "camera": {},
        },
        "07_catalog_selection": {"tag_ids": [1]},
        "08_natural_prompt": {"natural_prompt": "a test scene", "negative_prompt": ""},
        "09_semantic_review": {"issues": []},
        "10_visual_qc": {"issues": []},
        "11_targeted_revision": {"revision": {"reason": "fix hair", "axes": ["hair"]}},
    }[stage]
    payload.update(extra)
    return payload


class LlmContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = create_db(Path(self.temp.name))
        self.con = sqlite3.connect(self.db)
        self.con.execute("PRAGMA foreign_keys=ON")
        self.con.execute("INSERT INTO project(id,title) VALUES(1,'P1')")
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def test_schemas_cover_all_stages_and_their_own_stage(self):
        self.assertEqual(len(STAGES), 11)
        for stage in STAGES:
            self.assertEqual(load_schema(stage)["properties"]["stage"]["const"], stage)

    def test_all_eleven_stages_require_approval_and_validate_output(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                draft = create_draft(self.con, stage, "system", "task")
                with self.assertRaises(StageBlocked):
                    invoke_stage(
                        self.con, stage, project_id=1, request={},
                        executor=lambda template, request: valid_output(stage),
                    )
                approved = approve(self.con, draft)
                self.assertEqual(approved["status"], "active")
                result = invoke_stage(
                    self.con, stage, project_id=1, request={},
                    executor=lambda template, request: valid_output(stage),
                )
                self.assertEqual(result.status, "succeeded")
                self.assertEqual(result.output["stage"], stage)
                validate_output(stage, result.output)

    def test_retry_same_execution_key_does_not_call_twice(self):
        draft = create_draft(self.con, "01_brief", "system", "task")
        approve(self.con, draft)
        calls = []

        def executor(template, request):
            calls.append(1)
            return valid_output("01_brief")

        first = invoke_stage(
            self.con, "01_brief", project_id=1, request={"x": 1}, executor=executor,
        )
        second = invoke_stage(
            self.con, "01_brief", project_id=1, request={"x": 1}, executor=executor,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(first.run_id, second.run_id)
        self.assertTrue(second.replayed)
        count = self.con.execute("SELECT count(*) FROM llm_run").fetchone()[0]
        self.assertEqual(count, 1)

    def test_empty_or_unapproved_template_blocks_invocation(self):
        empty = create_draft(self.con, "02_story", "", "")
        with self.assertRaises(StageBlocked):
            approve(self.con, empty)
        unapproved = create_draft(self.con, "02_story", "system", "task")
        with self.assertRaises(StageBlocked):
            invoke_stage(
                self.con, "02_story", project_id=1, request={},
                executor=lambda template, request: valid_output("02_story"),
            )
        approve(self.con, unapproved)
        self.assertIsNotNone(active_template(self.con, "02_story"))
        retire(self.con, unapproved)
        self.assertIsNone(active_template(self.con, "02_story"))

    def test_invalid_output_is_not_written_as_a_canonical_result(self):
        draft = create_draft(self.con, "08_natural_prompt", "system", "task")
        approve(self.con, draft)
        with self.assertRaises(ContractError):
            invoke_stage(
                self.con, "08_natural_prompt", project_id=1, request={},
                executor=lambda template, request: {"schema_version": "v4-1"},
            )
        row = self.con.execute("SELECT status,output_json FROM llm_run").fetchone()
        self.assertEqual(row, ("invalid", None))

    def test_template_changes_are_audited_and_events_are_immutable(self):
        draft = create_draft(self.con, "03_character", "system", "task")
        approve(self.con, draft)
        rows = self.con.execute(
            "SELECT action FROM llm_prompt_template_event ORDER BY id"
        ).fetchall()
        self.assertEqual([row[0] for row in rows], ["draft", "active"])
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("UPDATE llm_prompt_template_event SET action='retired'")


if __name__ == "__main__":
    unittest.main()
