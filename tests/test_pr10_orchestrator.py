"""O10-01..12: implemented V4.1 execution control on a migrated SQLite copy."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.catalog.admin import CatalogPermissionError, run_catalog_job  # noqa: E402
from novel2anima.llm import registry as prompt_registry  # noqa: E402
from novel2anima.llm.contracts import StageBlocked  # noqa: E402
from novel2anima.llm.stage_executor import LLMStageExecutor, active_template_sha256  # noqa: E402
from novel2anima.pipeline import dependency_graph, orchestrator, policies, registry  # noqa: E402
from novel2anima.pipeline.step_runner import StepRunner  # noqa: E402
from novel2anima.storage import pipeline_repository as repo  # noqa: E402
from novel2anima.storage.migrations import apply_migrations  # noqa: E402

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


def _output(stage: str) -> dict:
    base = {
        "schema_version": "v4-1",
        "stage": stage,
        "status": "proposed",
        "decisions": {},
        "uncertainties": [],
        "evidence_refs": [],
    }
    extras = {
        "01_brief": {"brief": {}},
        "02_story": {"story": {}},
        "03_character": {"characters": [{"code": "a", "name": "A"}]},
        "04_wardrobe": {"items": [{"slot": "top", "garment_type": "shirt"}]},
        "05_act_beats": {"acts": [{"act_no": 1, "beats": [{}]}]},
        "06_shot_direction": {
            "shot_id": 1,
            "participants": [1, 2],
            "interactions": [{
                "actor_character_id": 1,
                "target_character_id": 2,
                "action_code": "headpat",
            }],
            "outfit_bindings": [],
            "camera": {},
        },
        "07_catalog_selection": {"tag_ids": [1]},
        "08_natural_prompt": {"natural_prompt": "a prompt", "negative_prompt": "bad"},
        "09_semantic_review": {"issues": []},
        "10_visual_qc": {"issues": []},
        "11_targeted_revision": {"revision": {"reason": "fix", "axes": ["pose"]}},
    }
    base.update(extras[stage])
    return base


class Provider:
    def __init__(self, *, fail_stage: str | None = None, fail_once: bool = False,
                 injected: dict | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail_stage = fail_stage
        self.fail_once = fail_once
        self.injected = injected
        self.failures = 0

    def __call__(self, template: dict, request: dict) -> dict:
        stage = template["stage"]
        self.calls.append((stage, dict(request)))
        if self.fail_stage == stage and (not self.fail_once or self.failures == 0):
            self.failures += 1
            raise RuntimeError("provider failure")
        output = _output(stage)
        if self.injected is not None:
            output.update(self.injected)
        return output

    def stage_calls(self, stage: str) -> int:
        return sum(1 for item, _ in self.calls if item == stage)


def handlers(counter: dict | None = None):
    counter = counter if counter is not None else {}

    def note(name):
        counter[name] = counter.get(name, 0) + 1

    def retrieve(payload):
        note("retrieve_catalog")
        return {"revision_ids": ["catalog:1"]}

    def compile_prompt(payload):
        note("compile_prompt")
        return {"revision_ids": ["prompt:1"]}

    def render(payload):
        note("render")
        return {"revision_ids": ["generation:1"]}

    return {
        "retrieve_catalog": retrieve,
        "compile_prompt": compile_prompt,
        "render": render,
    }, counter


def make_db(case: unittest.TestCase, *, approve_all: bool = True) -> sqlite3.Connection:
    tmp = tempfile.TemporaryDirectory(prefix="n2a-pr10-")
    case.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    db = root / "staging.db"
    con = sqlite3.connect(db)
    con.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
    con.commit()
    con.close()
    migrations = root / "migrations"
    migrations.mkdir()
    for path in sorted((ROOT / "sql/migrations").glob("*.sql")):
        shutil.copy2(path, migrations / path.name)
    assert apply_migrations(db, migrations, backup_path=root / "pre.db")["status"] == "ok"
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("INSERT INTO project(id,title) VALUES(1,'PR10 test')")
    policies.set_runtime_mode(con, "V4_ACTIVE")
    policies.set_strict_execution_control(con, True)
    if approve_all:
        for stage in prompt_registry.STAGES:
            template_id = prompt_registry.create_draft(con, stage, "system", "task")
            prompt_registry.approve(con, template_id)
    con.commit()
    case.addCleanup(con.close)
    return con


def start(con, provider, handler_map, key="run-1", payload=None, **kwargs):
    return orchestrator.start_story(
        con,
        project_id=1,
        input_revision_id=1,
        client_run_key=key,
        request_payload=payload or {"shots": [{"shot_id": 1}]},
        provider=provider,
        handlers=handler_map,
        **kwargs,
    )


class OrchestratorTests(unittest.TestCase):
    def test_o10_01_same_key_same_payload_one_run(self):
        con = make_db(self)
        provider = Provider()
        handler_map, _ = handlers()
        first = start(con, provider, handler_map)
        calls = len(provider.calls)
        second = start(con, provider, handler_map)
        self.assertEqual(first, second)
        self.assertEqual(con.execute("SELECT count(*) FROM pipeline_run").fetchone()[0], 1)
        self.assertGreater(calls, 0)
        self.assertEqual(len(provider.calls), calls)
        self.assertEqual(con.execute("SELECT status FROM pipeline_run WHERE id=?", (first,)).fetchone()[0], "COMPLETED")

    def test_o10_02_same_key_different_payload_conflicts(self):
        con = make_db(self)
        provider = Provider()
        handler_map, _ = handlers()
        start(con, provider, handler_map)
        with self.assertRaises(repo.IdempotencyConflict):
            start(con, provider, handler_map, payload={"shots": [{"shot_id": 2}]})
        self.assertEqual(con.execute("SELECT count(*) FROM pipeline_run").fetchone()[0], 1)

    def test_o10_03_llm_shell_is_rejected_without_subprocess_or_catalog_job(self):
        con = make_db(self)
        provider = Provider(injected={"run_command": "etl/build.py"})
        handler_map, _ = handlers()
        with mock.patch("subprocess.run") as subprocess_run, mock.patch("os.system") as os_system:
            run_id = start(con, provider, handler_map)
            self.assertFalse(subprocess_run.called)
            self.assertFalse(os_system.called)
        self.assertEqual(con.execute("SELECT status FROM pipeline_run WHERE id=?", (run_id,)).fetchone()[0], "FAILED")
        row = con.execute("SELECT status,error_code FROM pipeline_step_run WHERE pipeline_run_id=? ORDER BY id", (run_id,)).fetchone()
        self.assertEqual((row[0], row[1]), ("FAILED", "INVALID_PROPOSAL"))
        self.assertEqual(con.execute("SELECT count(*) FROM catalog_job").fetchone()[0], 0)

    def test_o10_04_missing_approved_stage_blocks_with_zero_calls(self):
        con = make_db(self, approve_all=False)
        provider = Provider()
        with self.assertRaises(StageBlocked):
            LLMStageExecutor(con, provider).execute(
                "06_shot_direction", project_id=1, request={"shot_id": 1}, execution_key="k"
            )
        self.assertEqual(provider.calls, [])
        run_id = start(con, provider, handlers()[0])
        self.assertEqual(con.execute("SELECT status FROM pipeline_run WHERE id=?", (run_id,)).fetchone()[0], "BLOCKED_CONFIG")
        self.assertEqual(provider.calls, [])
        self.assertEqual(con.execute("SELECT count(*) FROM llm_run").fetchone()[0], 0)

    def test_o10_05_partial_failure_resume_does_not_rerun_committed_steps(self):
        con = make_db(self)
        provider = Provider(fail_stage="06_shot_direction", fail_once=True)
        handler_map, _ = handlers()
        run_id = start(con, provider, handler_map, max_attempts=1)
        self.assertEqual(con.execute("SELECT status FROM pipeline_run WHERE id=?", (run_id,)).fetchone()[0], "FAILED")
        before = {stage: provider.stage_calls(stage) for stage in prompt_registry.STAGES}
        run_id = orchestrator.resume_run(con, run_id, provider=provider, handlers=handler_map)
        self.assertEqual(con.execute("SELECT status FROM pipeline_run WHERE id=?", (run_id,)).fetchone()[0], "COMPLETED")
        for stage in ("01_brief", "02_story", "03_character", "04_wardrobe", "05_act_beats"):
            self.assertEqual(provider.stage_calls(stage), before[stage])
        attempts = {
            row[0]: row[1]
            for row in con.execute(
                "SELECT step_code,max(attempt_no) FROM pipeline_step_run"
                " WHERE pipeline_run_id=? AND step_code IN ('06_shot_direction','01_brief')"
                " GROUP BY step_code", (run_id,)
            )
        }
        self.assertEqual(attempts["01_brief"], 1)
        self.assertEqual(attempts["06_shot_direction"], 2)

    def test_o10_06_action_edit_only_invalidates_downstream(self):
        result = dependency_graph.shot_action_invalidation(15)
        self.assertFalse(result["catalog_rebuild"])
        self.assertEqual(result["subject"]["shot_id"], 15)
        self.assertIn("06_shot_direction", result["steps"])
        self.assertIn("compile_prompt", result["steps"])
        self.assertIn("10_visual_qc", result["steps"])
        self.assertNotIn("01_brief", result["steps"])
        self.assertNotIn("05_act_beats", result["steps"])

    def test_o10_07_outfit_edit_invalidates_bound_targets_only(self):
        result = dependency_graph.outfit_invalidation(7, [15, 16])
        self.assertFalse(result["catalog_rebuild"])
        self.assertEqual(result["bound_shot_ids"], [15, 16])
        self.assertIn("04_wardrobe", result["steps"])
        self.assertIn("compile_prompt", result["steps"])
        self.assertNotIn("03_character", result["steps"])

    def test_o10_08_duo_actor_target_preserved_through_all_stages(self):
        con = make_db(self)
        provider = Provider()
        handler_map, _ = handlers()
        payload = {
            "shots": [{
                "shot_id": 15,
                "interactions": [{
                    "actor_character_id": 2,
                    "target_character_id": 1,
                    "action_code": "headpat",
                }],
            }],
        }
        run_id = start(con, provider, handler_map, payload=payload)
        self.assertEqual(con.execute("SELECT status FROM pipeline_run WHERE id=?", (run_id,)).fetchone()[0], "COMPLETED")
        for stage, request in provider.calls:
            if stage in {"06_shot_direction", "09_semantic_review"}:
                self.assertEqual(
                    request["shots"][0]["interactions"][0],
                    {"actor_character_id": 2, "target_character_id": 1, "action_code": "headpat"},
                )

    def test_o10_09_replay_same_execution_key_is_idempotent(self):
        con = make_db(self)
        provider = Provider()
        executor = LLMStageExecutor(con, provider)
        first = executor.execute(
            "01_brief", project_id=1, request={"brief": "x"}, execution_key="same-key"
        )
        second = executor.execute(
            "01_brief", project_id=1, request={"brief": "x"}, execution_key="same-key"
        )
        self.assertEqual(first.run_id, second.run_id)
        self.assertTrue(second.replayed)
        self.assertEqual(provider.stage_calls("01_brief"), 1)
        self.assertEqual(con.execute("SELECT count(*) FROM llm_run").fetchone()[0], 1)

    def test_o10_09b_process_reset_reuses_committed_llm_output(self):
        con = make_db(self)
        provider = Provider()
        workflow = registry.get_workflow()
        payload = {"input_revision_id": 1, "shots": []}
        run_id, _ = repo.create_run(
            con, project_id=1, run_key="crash-run", request=payload,
            workflow=workflow, runtime_mode="V4_ACTIVE",
        )
        con.commit()
        template_sha = active_template_sha256(con, "01_brief")
        fingerprint = policies.fingerprint(
            registry.WORKFLOW_VERSION, "01_brief", payload,
            template_sha256=template_sha,
        )
        step_id, attempt = repo.start_step(
            con, run_id=run_id, step_code="01_brief",
            workflow_version=registry.WORKFLOW_VERSION,
            input_fingerprint=fingerprint,
        )
        con.commit()
        key = repo.execution_key(run_id, "01_brief", attempt, fingerprint)
        result = LLMStageExecutor(con, provider).execute(
            "01_brief", project_id=1, request=payload,
            execution_key=key, pipeline_run_id=run_id,
        )
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(
            con.execute("SELECT status FROM pipeline_step_run WHERE id=?", (step_id,)).fetchone()[0],
            "RUNNING",
        )
        handler_map, _ = handlers()
        orchestrator.resume_run(con, run_id, provider=provider, handlers=handler_map)
        self.assertEqual(
            con.execute("SELECT status FROM pipeline_run WHERE id=?", (run_id,)).fetchone()[0],
            "COMPLETED",
        )
        self.assertEqual(provider.stage_calls("01_brief"), 1)
        self.assertEqual(
            con.execute(
                "SELECT status FROM pipeline_step_run WHERE pipeline_run_id=? AND step_code='01_brief'"
                " ORDER BY attempt_no", (run_id,)
            ).fetchone()[0],
            "SUCCEEDED",
        )

    def test_o10_10_catalog_admin_is_separate_and_approved(self):
        con = make_db(self)
        calls = []
        result = run_catalog_job(
            con, job_code="verify_catalog", job_key="catalog-1",
            actor="operator", approved_by="owner",
            handler=lambda connection, payload: calls.append(payload) or {"ok": True},
        )
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(calls, [{}])
        provider = Provider()
        handler_map, _ = handlers()
        start(con, provider, handler_map)
        self.assertEqual(con.execute("SELECT count(*) FROM catalog_job").fetchone()[0], 1)
        with self.assertRaises(CatalogPermissionError):
            run_catalog_job(
                con, job_code="verify_catalog", job_key="catalog-2",
                actor="llm", approved_by="owner",
            )

    def test_o10_11_custom_step_shell_and_python_are_rejected(self):
        con = make_db(self)
        with self.assertRaises(registry.RegistryError):
            StepRunner(con).execute(
                run_id=1, project_id=1, workflow_version=registry.WORKFLOW_VERSION,
                step_code="run_shell", payload={}, dependency_snapshot=[],
            )
        with self.assertRaises(policies.InvalidProposal):
            policies.reject_execution_intent({"command": "python etl/build.py"})
        with mock.patch("subprocess.run") as subprocess_run:
            with self.assertRaises(policies.InvalidProposal):
                start(con, Provider(), handlers()[0], payload={"command": "python etl/build.py"})
            self.assertFalse(subprocess_run.called)
        self.assertEqual(con.execute("SELECT count(*) FROM pipeline_run").fetchone()[0], 0)

    def test_o10_12_step_attempt_fk_and_terminal_uniqueness(self):
        con = make_db(self)
        workflow = registry.get_workflow()
        run_id, _ = repo.create_run(
            con, project_id=1, run_key="retry-run", request={"x": 1},
            workflow=workflow, runtime_mode="V4_ACTIVE",
        )
        con.commit()
        first, _ = repo.start_step(
            con, run_id=run_id, step_code="01_brief",
            workflow_version=registry.WORKFLOW_VERSION, input_fingerprint="a" * 64,
        )
        repo.finish_step(con, first, "FAILED", error_code="SERVICE_ERROR")
        con.commit()
        second, _ = repo.start_step(
            con, run_id=run_id, step_code="01_brief",
            workflow_version=registry.WORKFLOW_VERSION, input_fingerprint="a" * 64,
            retry_of_step_run_id=first,
        )
        repo.finish_step(con, second, "SUCCEEDED", output_revision_refs=["llm_run:1"])
        con.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            repo.start_step(
                con, run_id=run_id, step_code="01_brief",
                workflow_version=registry.WORKFLOW_VERSION, input_fingerprint="a" * 64,
                attempt_no=1,
            )
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE pipeline_step_run SET status='FAILED' WHERE id=?", (second,))
        other, _ = repo.create_run(
            con, project_id=1, run_key="other-run", request={"x": 2},
            workflow=workflow, runtime_mode="V4_ACTIVE",
        )
        con.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            repo.start_step(
                con, run_id=other, step_code="01_brief",
                workflow_version=registry.WORKFLOW_VERSION, input_fingerprint="a" * 64,
                retry_of_step_run_id=first,
            )
        self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_rerun_from_reuses_unaffected_steps(self):
        con = make_db(self)
        provider = Provider()
        handler_map, _ = handlers()
        parent = start(con, provider, handler_map)
        child = orchestrator.rerun_from(
            con, parent, "06_shot_direction", "action correction", "run-2",
            provider=provider, handlers=handler_map,
        )
        self.assertEqual(con.execute("SELECT status FROM pipeline_run WHERE id=?", (child,)).fetchone()[0], "COMPLETED")
        reused = {
            row[0]: json.loads(row[1]).get("reused_from_run_id")
            for row in con.execute(
                "SELECT step_code,details_json FROM pipeline_step_run WHERE pipeline_run_id=?", (child,)
            )
        }
        for code in ("01_brief", "02_story", "03_character", "04_wardrobe", "05_act_beats"):
            self.assertEqual(reused[code], parent)
        self.assertIsNone(reused["06_shot_direction"])
        self.assertEqual(con.execute("SELECT count(*) FROM catalog_job").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
