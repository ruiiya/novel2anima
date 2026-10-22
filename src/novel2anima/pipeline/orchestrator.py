"""Single-root story orchestration with DB step provenance.

Public API:
    start_story(...) -> run_id
    resume_run(run_id, ...) -> run_id
    rerun_from(run_id, step_code, reason, request_key, ...) -> run_id

Only registered steps can run.  Catalog maintenance is a separate admin API in
``novel2anima.catalog.admin`` and is never imported or dispatched here.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping

from novel2anima.llm.stage_executor import Provider, active_template_sha256
from novel2anima.pipeline import dependency_graph, policies, registry
from novel2anima.pipeline.step_runner import Handler, StepRunner
from novel2anima.storage import pipeline_repository as repo

_RETRYABLE = {"SERVICE_ERROR", "CONTRACT_ERROR"}


def _input_payload(input_revision_id: int, request_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(request_payload or {})
    payload["input_revision_id"] = int(input_revision_id)
    policies.reject_execution_intent(payload, "request")
    return payload


def start_story(
    con: sqlite3.Connection,
    *,
    project_id: int,
    input_revision_id: int,
    client_run_key: str,
    workflow_version: str = registry.WORKFLOW_VERSION,
    request_payload: Mapping[str, Any] | None = None,
    provider: Provider | None = None,
    handlers: Mapping[str, Handler] | None = None,
    context: Mapping[str, Any] | None = None,
    runtime_mode: str | None = None,
    trigger_source: str = "USER",
    act_id: int | None = None,
    max_attempts: int = 2,
) -> int:
    mode = policies.require_story_enabled(con, runtime_mode)
    workflow = registry.get_workflow(workflow_version)
    payload = _input_payload(input_revision_id, request_payload)
    run_id, created = repo.create_run(
        con,
        project_id=project_id,
        run_key=client_run_key,
        request=payload,
        workflow=workflow,
        runtime_mode=mode,
        trigger_source=trigger_source,
        act_id=act_id,
    )
    con.commit()
    if not created:
        run = repo.get_run(con, run_id)
        if run is not None and run["status"] == "COMPLETED":
            return run_id
    return _drive(
        con, run_id, provider=provider, handlers=handlers, context=context,
        max_attempts=max_attempts,
    )


def resume_run(
    con: sqlite3.Connection,
    run_id: int,
    *,
    provider: Provider | None = None,
    handlers: Mapping[str, Handler] | None = None,
    context: Mapping[str, Any] | None = None,
    max_attempts: int = 2,
) -> int:
    policies.require_story_enabled(con)
    return _drive(
        con, int(run_id), provider=provider, handlers=handlers, context=context,
        max_attempts=max_attempts,
    )


def rerun_from(
    con: sqlite3.Connection,
    run_id: int,
    step_code: str,
    reason: str,
    request_key: str,
    *,
    provider: Provider | None = None,
    handlers: Mapping[str, Handler] | None = None,
    context: Mapping[str, Any] | None = None,
    max_attempts: int = 2,
) -> int:
    policies.require_story_enabled(con)
    if not reason.strip():
        raise ValueError("rerun reason is required")
    policies.reject_execution_intent({"reason": reason}, "rerun")
    registry.step_spec(step_code)
    parent = repo.get_run(con, int(run_id))
    if parent is None:
        raise ValueError(f"pipeline run not found: {run_id}")
    affected = dependency_graph.affected_steps({step_code})
    workflow = registry.get_workflow(parent["workflow_version"])
    payload = dict(parent["input"])
    payload["_rerun_from"] = step_code
    payload["_rerun_reason"] = reason.strip()
    payload["_parent_run_id"] = int(run_id)
    new_run_id, created = repo.create_run(
        con,
        project_id=parent["project_id"],
        run_key=request_key,
        request=payload,
        workflow=workflow,
        runtime_mode=parent["runtime_mode"],
        trigger_source="USER",
        act_id=parent["act_id"],
    )
    if not created:
        return new_run_id
    missing: set[str] = set()
    for code in registry.STEP_CODES:
        if code not in affected:
            copied = repo.copy_step(
                con,
                source_run_id=int(run_id),
                target_run_id=new_run_id,
                step_code=code,
                workflow_version=workflow["workflow_version"],
            )
            if not copied:
                missing.add(code)
    con.commit()
    return _drive(
        con, new_run_id, provider=provider, handlers=handlers, context=context,
        max_attempts=max_attempts, only_steps=set(affected) | missing,
    )


def _drive(
    con: sqlite3.Connection,
    run_id: int,
    *,
    provider: Provider | None,
    handlers: Mapping[str, Handler] | None,
    context: Mapping[str, Any] | None,
    max_attempts: int,
    only_steps: set[str] | None = None,
) -> int:
    run = repo.get_run(con, run_id)
    if run is None:
        raise ValueError(f"pipeline run not found: {run_id}")
    if run["status"] in {"COMPLETED", "CANCELLED"}:
        return run_id
    version = run["workflow_version"]
    registry.get_workflow(version)
    request = dict(run["input"])
    ctx = dict(context or {})
    runner = StepRunner(con, provider=provider, handlers=handlers)
    repo.set_run_status(con, run_id, "RUNNING")

    for spec in registry.STEPS:
        if only_steps is not None and spec.code not in only_steps:
            continue
        template_sha = (
            active_template_sha256(con, spec.code)
            if spec.kind == "LLM" else None
        )
        fingerprint = policies.fingerprint(
            version, spec.code, request, template_sha256=template_sha
        )
        reusable = repo.find_reusable_step(con, run_id, spec.code, fingerprint)
        if reusable is not None:
            if reusable["status"] == "SUCCEEDED":
                continue
            # A prior conditional skip is reusable only while the condition is
            # still false.  A newly available image/target must execute.
            if policies.skip_reason(spec.code, ctx) is not None:
                continue

        dependency_states = []
        for dependency in spec.dependencies:
            latest = repo.latest_step(con, run_id, dependency)
            dependency_states.append({
                "step_code": dependency,
                "status": None if latest is None else latest["status"],
                "step_run_id": None if latest is None else latest["id"],
            })
        unfinished = [
            item for item in dependency_states
            if item["status"] not in {"SUCCEEDED", "SKIPPED_CONDITION"}
        ]
        if unfinished:
            repo.record_step(
                con,
                run_id=run_id,
                step_code=spec.code,
                workflow_version=version,
                input_fingerprint=fingerprint,
                status="BLOCKED_DEPENDENCY",
                error_code="BLOCKED_DEPENDENCY",
                dependency_snapshot=dependency_states,
                details={"unfinished": unfinished},
            )
            con.commit()
            _finish_run(con, run_id, "BLOCKED_DEPENDENCY", request)
            return run_id

        skip = policies.skip_reason(spec.code, ctx)
        if skip is not None:
            repo.record_step(
                con,
                run_id=run_id,
                step_code=spec.code,
                workflow_version=version,
                input_fingerprint=fingerprint,
                status="SKIPPED_CONDITION",
                error_code=skip,
                dependency_snapshot=dependency_states,
                details={"skip_reason": skip},
            )
            con.commit()
            continue

        latest = repo.latest_step(con, run_id, spec.code)
        if latest is not None and _recover_interrupted_llm_step(
            con, run_id, spec.code, latest, fingerprint
        ):
            continue
        retry_of = None
        if latest is not None:
            retry_of = int(latest["id"])
        outcome = runner.execute(
            run_id=run_id,
            project_id=int(run["project_id"]),
            workflow_version=version,
            step_code=spec.code,
            payload=request,
            dependency_snapshot=dependency_states,
            retry_of_step_run_id=retry_of,
            act_id=run["act_id"],
            shot_id=ctx.get("shot_id"),
        )
        retries = 0
        while outcome.status == "FAILED" and outcome.error_code in _RETRYABLE and retries + 1 < max_attempts:
            retries += 1
            outcome = runner.execute(
                run_id=run_id,
                project_id=int(run["project_id"]),
                workflow_version=version,
                step_code=spec.code,
                payload=request,
                dependency_snapshot=dependency_states,
                retry_of_step_run_id=outcome.step_run_id,
                act_id=run["act_id"],
                shot_id=ctx.get("shot_id"),
            )
        if outcome.status != "SUCCEEDED":
            _finish_run(con, run_id, outcome.status, request)
            return run_id

    _finish_run(con, run_id, "COMPLETED", request)
    return run_id


def _recover_interrupted_llm_step(
    con: sqlite3.Connection,
    run_id: int,
    step_code: str,
    latest: Mapping[str, Any],
    fingerprint: str,
) -> bool:
    """Complete a step whose llm_run committed before the process died.

    The provider output is already validated and persisted; replaying it is the
    only way to keep one logical run without a second model call or revision.
    """
    if latest.get("status") != "RUNNING":
        return False
    if latest.get("input_fingerprint") != fingerprint:
        return False
    key = repo.execution_key(
        run_id, step_code, int(latest["attempt_no"]), fingerprint
    )
    row = con.execute(
        "SELECT id,status FROM llm_run WHERE execution_key=?", (key,)
    ).fetchone()
    if row is None or row[1] != "succeeded":
        return False
    repo.finish_step(
        con,
        int(latest["id"]),
        "SUCCEEDED",
        output_revision_refs=[f"llm_run:{row[0]}"],
        details={"recovered_after_process_reset": True},
    )
    con.commit()
    return True


def _finish_run(
    con: sqlite3.Connection,
    run_id: int,
    status: str,
    request: Mapping[str, Any],
) -> None:
    steps = repo.steps_for_run(con, run_id)
    repo.set_run_status(
        con,
        run_id,
        status,
        result={
            "request": dict(request),
            "status": status,
            "steps": [
                {
                    "step_code": row["step_code"],
                    "attempt_no": row["attempt_no"],
                    "status": row["status"],
                    "output_revision_refs": (
                        None if row["output_revision_refs_json"] is None
                        else json.loads(row["output_revision_refs_json"])
                    ),
                }
                for row in steps
            ],
        },
    )
