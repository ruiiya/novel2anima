"""Explicit LLM prompt approval and idempotent stage invocation."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sqlite3
from typing import Any, Callable, Mapping

from novel2anima.llm.contracts import (
    STAGES,
    ContractError,
    StageBlocked,
    load_schema,
    validate,
    validate_output,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _template_sha(
    stage: str, system_text: str, task_text: str, examples_text: str, input_schema: str, output_schema: str
) -> str:
    return _sha(_json({
        "stage": stage,
        "system": system_text,
        "task": task_text,
        "examples": examples_text,
        "input_schema": json.loads(input_schema or "{}"),
        "output_schema": json.loads(output_schema or "{}"),
    }))


def _template_row(row: sqlite3.Row | tuple | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    keys = (
        "id", "stage", "revision", "system_text", "task_text", "examples_text",
        "input_schema_json", "output_schema_json", "content_sha256", "status",
        "created_at",
    )
    return dict(zip(keys, row))


def create_draft(
    con: sqlite3.Connection,
    stage: str,
    system_text: str,
    task_text: str,
    *,
    examples_text: str = "",
    input_schema_json: str = "{}",
    output_schema_json: str | None = None,
) -> int:
    """Create a draft template. Drafts are never invokable until approved."""
    if stage not in STAGES:
        raise ContractError(f"unknown LLM stage: {stage}")
    if output_schema_json is None:
        output_schema_json = _json(load_schema(stage))
    try:
        parsed_output = json.loads(output_schema_json)
        parsed_input = json.loads(input_schema_json or "{}")
    except json.JSONDecodeError as exc:
        raise ContractError("schema JSON is invalid") from exc
    if not isinstance(parsed_output, dict) or not isinstance(parsed_input, dict):
        raise ContractError("schemas must be JSON objects")
    schema = load_schema(stage)
    if parsed_output.get("properties", {}).get("stage", {}).get("const") != stage:
        raise ContractError("output schema does not match stage")

    revision = int(con.execute(
        "SELECT coalesce(max(revision),0)+1 FROM llm_prompt_template WHERE stage=?",
        (stage,),
    ).fetchone()[0])
    content_sha = _template_sha(
        stage, system_text, task_text, examples_text, input_schema_json, output_schema_json
    )
    cur = con.execute(
        "INSERT INTO llm_prompt_template"
        "(stage,revision,system_text,task_text,examples_text,input_schema_json,"
        "output_schema_json,content_sha256,status)"
        " VALUES(?,?,?,?,?,?,?,?,'draft')",
        (
            stage,
            revision,
            system_text,
            task_text,
            examples_text,
            input_schema_json,
            output_schema_json,
            content_sha,
        ),
    )
    return int(cur.lastrowid)


def get_template(con: sqlite3.Connection, template_id: int) -> dict[str, Any]:
    row = _template_row(con.execute(
        "SELECT id,stage,revision,system_text,task_text,examples_text,input_schema_json,"
        "output_schema_json,content_sha256,status,created_at"
        " FROM llm_prompt_template WHERE id=?",
        (template_id,),
    ).fetchone())
    if row is None:
        raise ContractError(f"unknown prompt template: {template_id}")
    return row


def active_template(con: sqlite3.Connection, stage: str) -> dict[str, Any] | None:
    if stage not in STAGES:
        raise ContractError(f"unknown LLM stage: {stage}")
    return _template_row(con.execute(
        "SELECT id,stage,revision,system_text,task_text,examples_text,input_schema_json,"
        "output_schema_json,content_sha256,status,created_at"
        " FROM llm_prompt_template WHERE stage=? AND status='active'"
        " ORDER BY revision DESC LIMIT 1",
        (stage,),
    ).fetchone())


def approve(con: sqlite3.Connection, template_id: int) -> dict[str, Any]:
    """Explicit approval: retire the old active template and activate this draft."""
    template = get_template(con, template_id)
    if template["status"] == "active":
        return template
    if template["status"] != "draft":
        raise ContractError("only a draft can be approved")
    if not template["system_text"].strip() or not template["task_text"].strip():
        raise StageBlocked("prompt template has empty system/task instructions")
    try:
        output_schema = json.loads(template["output_schema_json"])
    except json.JSONDecodeError as exc:
        raise ContractError("output schema is invalid") from exc
    if not output_schema:
        raise StageBlocked("prompt template has no output schema")
    if output_schema.get("properties", {}).get("stage", {}).get("const") != template["stage"]:
        raise ContractError("output schema does not match stage")
    con.execute(
        "UPDATE llm_prompt_template SET status='retired'"
        " WHERE stage=? AND status='active' AND id<>?",
        (template["stage"], template_id),
    )
    con.execute(
        "UPDATE llm_prompt_template SET status='active' WHERE id=?",
        (template_id,),
    )
    con.commit()
    return get_template(con, template_id)


def retire(con: sqlite3.Connection, template_id: int) -> None:
    template = get_template(con, template_id)
    if template["status"] == "retired":
        return
    con.execute("UPDATE llm_prompt_template SET status='retired' WHERE id=?", (template_id,))
    con.commit()


def _existing_run(con: sqlite3.Connection, execution_key: str) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT id,status,output_json,validation_json,error_text"
        " FROM llm_run WHERE execution_key=?",
        (execution_key,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row[0]),
        "status": row[1],
        "output": json.loads(row[2]) if row[2] else None,
        "validation": json.loads(row[3] or "{}"),
        "error": row[4],
    }


@dataclasses.dataclass(frozen=True)
class RunResult:
    run_id: int
    status: str
    output: dict[str, Any] | None
    replayed: bool = False


def invoke_stage(
    con: sqlite3.Connection,
    stage: str,
    *,
    project_id: int,
    request: Mapping[str, Any],
    executor: Callable[[dict[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    model_provider: str = "stub",
    model_name: str = "stub",
    pipeline_run_id: int | None = None,
    act_id: int | None = None,
    shot_id: int | None = None,
    execution_key: str | None = None,
) -> RunResult:
    """Invoke an approved stage; the same execution key never calls twice."""
    if stage not in STAGES:
        raise ContractError(f"unknown LLM stage: {stage}")
    template = active_template(con, stage)
    if template is None or not template["system_text"].strip() or not template["task_text"].strip():
        raise StageBlocked(f"stage {stage} has no approved prompt template")
    if not isinstance(request, Mapping):
        raise ContractError("LLM request must be a JSON object")
    try:
        input_schema = json.loads(template["input_schema_json"] or "{}")
        output_schema = json.loads(template["output_schema_json"] or "{}")
    except json.JSONDecodeError as exc:
        raise ContractError("active template schema is invalid") from exc
    if not output_schema:
        raise StageBlocked(f"stage {stage} has no approved output schema")
    validate(dict(request), input_schema)

    key = execution_key or _sha(_json({
        "stage": stage,
        "project_id": project_id,
        "request": request,
        "template": template["content_sha256"],
    }))
    existing = _existing_run(con, key)
    if existing is not None:
        return RunResult(
            run_id=existing["id"],
            status=existing["status"],
            output=existing["output"],
            replayed=True,
        )

    cur = con.execute(
        "INSERT INTO llm_run"
        "(pipeline_run_id,project_id,act_id,shot_id,template_id,execution_key,"
        "model_provider,model_name,request_json,validation_json,status)"
        " VALUES(?,?,?,?,?,?,?,?,?,'{}','running')",
        (
            pipeline_run_id,
            project_id,
            act_id,
            shot_id,
            template["id"],
            key,
            model_provider,
            model_name,
            _json(dict(request)),
        ),
    )
    run_id = int(cur.lastrowid)
    con.commit()
    try:
        output = executor(template, request)
    except Exception as exc:
        con.execute(
            "UPDATE llm_run SET status='failed', error_text=?, completed_at=CURRENT_TIMESTAMP"
            " WHERE id=?",
            (str(exc), run_id),
        )
        con.commit()
        raise

    try:
        validated = validate_output(stage, output)
    except ContractError as exc:
        con.execute(
            "UPDATE llm_run SET status='invalid', error_text=?, validation_json=?,"
            " completed_at=CURRENT_TIMESTAMP WHERE id=?",
            (str(exc), _json({"ok": False, "error": str(exc)}), run_id),
        )
        con.commit()
        raise

    con.execute(
        "UPDATE llm_run SET status='succeeded', response_json=?, output_json=?,"
        " validation_json=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
        (_json(dict(output)), _json(validated), _json({"ok": True}), run_id),
    )
    con.commit()
    return RunResult(run_id=run_id, status="succeeded", output=validated)
