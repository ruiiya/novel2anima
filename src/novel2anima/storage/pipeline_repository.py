"""DB provenance for V4.1 pipeline runs and immutable step attempts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Mapping

RUN_STATUSES = (
    "QUEUED", "RUNNING", "WAITING_APPROVAL", "BLOCKED_CONFIG",
    "BLOCKED_DEPENDENCY", "FAILED", "COMPLETED", "CANCELLED",
)
STEP_STATUSES = (
    "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED_CONFIG",
    "BLOCKED_DEPENDENCY", "NEEDS_REVIEW", "SKIPPED_CONDITION", "CANCELLED",
)
TERMINAL_RUN = {"BLOCKED_CONFIG", "BLOCKED_DEPENDENCY", "FAILED", "COMPLETED", "CANCELLED"}
TERMINAL_STEP = {
    "SUCCEEDED", "FAILED", "BLOCKED_CONFIG", "BLOCKED_DEPENDENCY",
    "NEEDS_REVIEW", "SKIPPED_CONDITION", "CANCELLED",
}


class PipelineRepositoryError(RuntimeError):
    """Invalid run/step transition or malformed row."""


class IdempotencyConflict(PipelineRepositoryError):
    """The same client run key was reused with a different payload."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def execution_key(run_id: int, step_code: str, attempt_no: int, fingerprint: str) -> str:
    return _sha({
        "pipeline_run_id": int(run_id),
        "step_code": step_code,
        "attempt_no": int(attempt_no),
        "input_fingerprint": fingerprint,
    })


def _row(row: sqlite3.Row | tuple | None, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(zip(keys, row))


def get_run(con: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT r.id,r.project_id,r.act_id,r.run_key,r.status,r.input_json,"
        "r.result_json,r.created_at,r.finished_at,"
        "e.workflow_code,e.workflow_version,e.workflow_definition_sha256,"
        "e.request_sha256,e.runtime_mode,e.trigger_source"
        " FROM pipeline_run r LEFT JOIN pipeline_run_execution e"
        " ON e.pipeline_run_id=r.id WHERE r.id=?",
        (int(run_id),),
    ).fetchone()
    keys = (
        "id", "project_id", "act_id", "run_key", "status", "input_json",
        "result_json", "created_at", "finished_at", "workflow_code",
        "workflow_version", "workflow_definition_sha256", "request_sha256",
        "runtime_mode", "trigger_source",
    )
    result = _row(row, keys)
    if result and result["input_json"]:
        result["input"] = json.loads(result["input_json"])
    return result


def get_run_by_key(con: sqlite3.Connection, run_key: str) -> dict[str, Any] | None:
    row = con.execute("SELECT id FROM pipeline_run WHERE run_key=?", (run_key,)).fetchone()
    return None if row is None else get_run(con, int(row[0]))


def create_run(
    con: sqlite3.Connection,
    *,
    project_id: int,
    run_key: str,
    request: Mapping[str, Any],
    workflow: Mapping[str, Any],
    runtime_mode: str,
    trigger_source: str = "USER",
    act_id: int | None = None,
) -> tuple[int, bool]:
    """Create one logical run, or return the existing exact request.

    Returns ``(run_id, created)``.  A reused key with a different request hash is
    an ``IDEMPOTENCY_CONFLICT``; no hidden second run is written.
    """
    if not str(run_key).strip():
        raise PipelineRepositoryError("client_run_key must not be empty")
    if runtime_mode not in {"LEGACY", "MIGRATING", "V4_ACTIVE"}:
        raise PipelineRepositoryError(f"invalid runtime_mode: {runtime_mode}")
    if trigger_source not in {"USER", "API", "SCHEDULED", "ADMIN"}:
        raise PipelineRepositoryError(f"invalid trigger_source: {trigger_source}")
    request_sha = _sha(dict(request))
    existing = get_run_by_key(con, run_key)
    if existing is not None:
        same_workflow = (
            existing["workflow_code"] == workflow["workflow_code"]
            and existing["workflow_version"] == workflow["workflow_version"]
            and existing["workflow_definition_sha256"] == workflow["sha256"]
        )
        same_request = existing["request_sha256"] == request_sha
        legacy_same_request = (
            existing["workflow_code"] is None
            and _sha(existing.get("input", {})) == request_sha
        )
        if (same_workflow and same_request) or legacy_same_request:
            return int(existing["id"]), False
        raise IdempotencyConflict(
            f"IDEMPOTENCY_CONFLICT: run_key {run_key!r} was reused with a different payload"
        )

    cur = con.execute(
        "INSERT INTO pipeline_run(project_id,act_id,run_key,status,input_json)"
        " VALUES(?,?,?,'QUEUED',?)",
        (int(project_id), act_id, str(run_key), _json(dict(request))),
    )
    run_id = int(cur.lastrowid)
    con.execute(
        "INSERT INTO pipeline_run_execution"
        "(pipeline_run_id,workflow_code,workflow_version,workflow_definition_sha256,"
        "request_sha256,runtime_mode,trigger_source)"
        " VALUES(?,?,?,?,?,?,?)",
        (
            run_id,
            workflow["workflow_code"],
            workflow["workflow_version"],
            workflow["sha256"],
            request_sha,
            runtime_mode,
            trigger_source,
        ),
    )
    return run_id, True


def set_run_status(
    con: sqlite3.Connection,
    run_id: int,
    status: str,
    *,
    result: Mapping[str, Any] | None = None,
) -> None:
    if status not in RUN_STATUSES:
        raise PipelineRepositoryError(f"invalid run status: {status}")
    finished = "CURRENT_TIMESTAMP" if status in TERMINAL_RUN else "NULL"
    con.execute(
        f"UPDATE pipeline_run SET status=?,result_json=?,finished_at={finished} WHERE id=?",
        (status, None if result is None else _json(dict(result)), int(run_id)),
    )
    con.commit()


def _next_attempt(con: sqlite3.Connection, run_id: int, step_code: str) -> int:
    row = con.execute(
        "SELECT coalesce(max(attempt_no),0)+1 FROM pipeline_step_run"
        " WHERE pipeline_run_id=? AND step_code=?",
        (int(run_id), step_code),
    ).fetchone()
    return int(row[0])


def start_step(
    con: sqlite3.Connection,
    *,
    run_id: int,
    step_code: str,
    workflow_version: str,
    input_fingerprint: str,
    dependency_snapshot: list[Any] | None = None,
    attempt_no: int | None = None,
    retry_of_step_run_id: int | None = None,
    execution_key: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> tuple[int, int]:
    """Insert a RUNNING attempt and return ``(step_run_id, attempt_no)``."""
    attempt = int(attempt_no or _next_attempt(con, run_id, step_code))
    key = execution_key or _sha({
        "pipeline_run_id": int(run_id),
        "step_code": step_code,
        "attempt_no": attempt,
        "input_fingerprint": input_fingerprint,
    })
    cur = con.execute(
        "INSERT INTO pipeline_step_run"
        "(pipeline_run_id,step_code,workflow_version,attempt_no,execution_key,"
        "input_fingerprint,dependency_snapshot_json,status,retry_of_step_run_id,"
        "started_at,details_json)"
        " VALUES(?,?,?,?,?,?,?,'RUNNING',?,CURRENT_TIMESTAMP,?)",
        (
            int(run_id), step_code, workflow_version, attempt, key,
            input_fingerprint, _json(dependency_snapshot or []),
            retry_of_step_run_id, _json(dict(details or {})),
        ),
    )
    return int(cur.lastrowid), attempt


def finish_step(
    con: sqlite3.Connection,
    step_run_id: int,
    status: str,
    *,
    output_revision_refs: Any = None,
    error_code: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    if status not in STEP_STATUSES or status in {"QUEUED", "RUNNING"}:
        raise PipelineRepositoryError(f"invalid terminal step status: {status}")
    refs = None if output_revision_refs is None else _json(list(output_revision_refs))
    if status == "SUCCEEDED" and refs is None:
        raise PipelineRepositoryError("SUCCEEDED step needs output_revision_refs")
    con.execute(
        "UPDATE pipeline_step_run SET status=?,output_revision_refs_json=?,"
        "error_code=?,details_json=coalesce(?,details_json),finished_at=CURRENT_TIMESTAMP WHERE id=?",
        (
            status,
            refs,
            error_code,
            None if details is None else _json(dict(details)),
            int(step_run_id),
        ),
    )


def record_step(
    con: sqlite3.Connection,
    *,
    run_id: int,
    step_code: str,
    workflow_version: str,
    input_fingerprint: str,
    status: str,
    output_revision_refs: Any = None,
    error_code: str | None = None,
    details: Mapping[str, Any] | None = None,
    dependency_snapshot: list[Any] | None = None,
    attempt_no: int = 1,
    execution_key: str | None = None,
) -> int:
    """Insert a terminal step row (used for conditional skips)."""
    if status not in TERMINAL_STEP:
        raise PipelineRepositoryError(f"terminal step status expected: {status}")
    key = execution_key or _sha({
        "pipeline_run_id": int(run_id),
        "step_code": step_code,
        "attempt_no": int(attempt_no),
        "input_fingerprint": input_fingerprint,
        "status": status,
    })
    refs = None if output_revision_refs is None else _json(list(output_revision_refs))
    cur = con.execute(
        "INSERT INTO pipeline_step_run"
        "(pipeline_run_id,step_code,workflow_version,attempt_no,execution_key,"
        "input_fingerprint,dependency_snapshot_json,output_revision_refs_json,status,"
        "error_code,started_at,finished_at,details_json)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,?)",
        (
            int(run_id), step_code, workflow_version, int(attempt_no), key,
            input_fingerprint, _json(dependency_snapshot or []), refs, status,
            error_code, _json(dict(details or {})),
        ),
    )
    return int(cur.lastrowid)


def find_reusable_step(
    con: sqlite3.Connection,
    run_id: int,
    step_code: str,
    input_fingerprint: str,
) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT id,status,output_revision_refs_json,attempt_no,details_json"
        " FROM pipeline_step_run WHERE pipeline_run_id=? AND step_code=?"
        " AND input_fingerprint=? AND status IN ('SUCCEEDED','SKIPPED_CONDITION')"
        " ORDER BY attempt_no DESC LIMIT 1",
        (int(run_id), step_code, input_fingerprint),
    ).fetchone()
    if row is None:
        return None
    result = _row(row, ("id", "status", "output_revision_refs_json", "attempt_no", "details_json"))
    return result


def latest_step(
    con: sqlite3.Connection, run_id: int, step_code: str
) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT id,status,attempt_no,input_fingerprint,error_code,output_revision_refs_json"
        " FROM pipeline_step_run WHERE pipeline_run_id=? AND step_code=?"
        " ORDER BY attempt_no DESC LIMIT 1",
        (int(run_id), step_code),
    ).fetchone()
    return _row(row, (
        "id", "status", "attempt_no", "input_fingerprint", "error_code",
        "output_revision_refs_json",
    ))


def steps_for_run(con: sqlite3.Connection, run_id: int) -> list[dict[str, Any]]:
    rows = con.execute(
        "SELECT id,step_code,attempt_no,status,input_fingerprint,error_code,"
        "output_revision_refs_json,started_at,finished_at"
        " FROM pipeline_step_run WHERE pipeline_run_id=? ORDER BY id",
        (int(run_id),),
    ).fetchall()
    keys = (
        "id", "step_code", "attempt_no", "status", "input_fingerprint",
        "error_code", "output_revision_refs_json", "started_at", "finished_at",
    )
    return [_row(row, keys) for row in rows]


def copy_step(
    con: sqlite3.Connection,
    *,
    source_run_id: int,
    target_run_id: int,
    step_code: str,
    workflow_version: str,
) -> bool:
    """Copy the terminal result of an unchanged step into a rerun.

    A new immutable attempt row is created; the source row is never mutated.
    """
    source = con.execute(
        "SELECT status,input_fingerprint,dependency_snapshot_json,"
        "output_revision_refs_json,error_code,details_json,attempt_no"
        " FROM pipeline_step_run WHERE pipeline_run_id=? AND step_code=?"
        " AND status IN ('SUCCEEDED','SKIPPED_CONDITION') ORDER BY attempt_no DESC LIMIT 1",
        (int(source_run_id), step_code),
    ).fetchone()
    if source is None:
        return False
    if latest_step(con, target_run_id, step_code) is not None:
        return True
    details = json.loads(source[5] or "{}")
    details["reused_from_run_id"] = int(source_run_id)
    details["reused_attempt_no"] = int(source[6])
    key = _sha({
        "pipeline_run_id": int(target_run_id),
        "step_code": step_code,
        "attempt_no": 1,
        "source_step_run_id": int(source_run_id),
        "reused": True,
    })
    con.execute(
        "INSERT INTO pipeline_step_run"
        "(pipeline_run_id,step_code,workflow_version,attempt_no,execution_key,"
        "input_fingerprint,dependency_snapshot_json,output_revision_refs_json,status,"
        "error_code,started_at,finished_at,details_json)"
        " VALUES(?,?,?,1,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,?)",
        (
            int(target_run_id), step_code, workflow_version, key, source[1],
            source[2], source[3], source[0], source[4], _json(details),
        ),
    )
    return True


def create_catalog_job(
    con: sqlite3.Connection,
    *,
    job_key: str,
    job_code: str,
    actor: str,
    approved_by: str,
    payload: Mapping[str, Any] | None = None,
) -> tuple[int, bool]:
    if not job_key.strip() or not job_code.strip() or not actor.strip() or not approved_by.strip():
        raise PipelineRepositoryError("catalog job requires key, code, actor and approver")
    existing = con.execute("SELECT id FROM catalog_job WHERE job_key=?", (job_key,)).fetchone()
    if existing is not None:
        return int(existing[0]), False
    cur = con.execute(
        "INSERT INTO catalog_job(job_key,job_code,actor,approved_by,status,payload_json)"
        " VALUES(?,?,?,?, 'RUNNING', ?)",
        (job_key, job_code, actor, approved_by, _json(dict(payload or {}))),
    )
    return int(cur.lastrowid), True


def finish_catalog_job(
    con: sqlite3.Connection,
    job_id: int,
    status: str,
    *,
    result: Mapping[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if status not in {"SUCCEEDED", "FAILED", "BLOCKED"}:
        raise PipelineRepositoryError(f"invalid catalog job status: {status}")
    con.execute(
        "UPDATE catalog_job SET status=?,result_json=?,error_text=?,"
        "finished_at=CURRENT_TIMESTAMP WHERE id=?",
        (status, None if result is None else _json(dict(result)), error, int(job_id)),
    )
