"""Execute exactly one registered step. No dynamic dispatch, shell or eval."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from novel2anima.llm.contracts import ContractError, StageBlocked
from novel2anima.llm.stage_executor import (
    LLMStageExecutor,
    Provider,
    active_template_sha256,
)
from novel2anima.pipeline import policies, registry
from novel2anima.storage import pipeline_repository as repo

Handler = Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class StepOutcome:
    step_run_id: int
    attempt_no: int
    status: str
    output_revision_refs: list[str]
    error_code: str | None = None
    error: str | None = None


class StepRunner:
    def __init__(
        self,
        con: sqlite3.Connection,
        *,
        provider: Provider | None = None,
        handlers: Mapping[str, Handler] | None = None,
    ) -> None:
        self.con = con
        self.executor = None if provider is None else LLMStageExecutor(con, provider)
        self.handlers = dict(handlers or {})

    def execute(
        self,
        *,
        run_id: int,
        project_id: int,
        workflow_version: str,
        step_code: str,
        payload: Mapping[str, Any],
        dependency_snapshot: list[Any],
        attempt_no: int | None = None,
        retry_of_step_run_id: int | None = None,
        act_id: int | None = None,
        shot_id: int | None = None,
    ) -> StepOutcome:
        spec = registry.step_spec(step_code)
        template_sha = (
            active_template_sha256(self.con, step_code)
            if spec.kind == "LLM" else None
        )
        fingerprint = policies.fingerprint(
            workflow_version, step_code, dict(payload), template_sha256=template_sha
        )
        step_run_id, attempt = repo.start_step(
            self.con,
            run_id=run_id,
            step_code=step_code,
            workflow_version=workflow_version,
            input_fingerprint=fingerprint,
            dependency_snapshot=dependency_snapshot,
            attempt_no=attempt_no,
            retry_of_step_run_id=retry_of_step_run_id,
            details={"kind": spec.kind, "template_sha256": template_sha},
        )
        self.con.commit()

        try:
            if spec.kind == "LLM":
                if self.executor is None:
                    raise StageBlocked("no LLM provider configured")
                execution_key = repo.execution_key(run_id, step_code, attempt, fingerprint)
                result = self.executor.execute(
                    step_code,
                    project_id=project_id,
                    request=payload,
                    execution_key=execution_key,
                    pipeline_run_id=run_id,
                    act_id=act_id,
                    shot_id=shot_id,
                )
                if result.status != "succeeded" or result.output is None:
                    raise RuntimeError(f"LLM stage ended with status {result.status!r}")
                refs = [f"llm_run:{result.run_id}"]
            else:
                handler = self.handlers.get(step_code)
                if handler is None:
                    raise StageBlocked(f"step {step_code} has no registered service handler")
                output = handler(payload)
                policies.reject_execution_intent(output, "output")
                refs = _revision_refs(output)
        except (StageBlocked, policies.ExecutionControlDisabled) as exc:
            repo.finish_step(
                self.con, step_run_id, "BLOCKED_CONFIG",
                error_code="BLOCKED_CONFIG", details={"error": str(exc)},
            )
            self.con.commit()
            return StepOutcome(step_run_id, attempt, "BLOCKED_CONFIG", [], "BLOCKED_CONFIG", str(exc))
        except policies.InvalidProposal as exc:
            repo.finish_step(
                self.con, step_run_id, "FAILED",
                error_code="INVALID_PROPOSAL", details={"error": str(exc)},
            )
            self.con.commit()
            return StepOutcome(step_run_id, attempt, "FAILED", [], "INVALID_PROPOSAL", str(exc))
        except ContractError as exc:
            repo.finish_step(
                self.con, step_run_id, "FAILED",
                error_code="CONTRACT_ERROR", details={"error": str(exc)},
            )
            self.con.commit()
            return StepOutcome(step_run_id, attempt, "FAILED", [], "CONTRACT_ERROR", str(exc))
        except Exception as exc:  # noqa: BLE001 - retained as a failed attempt, never swallowed
            repo.finish_step(
                self.con, step_run_id, "FAILED",
                error_code="SERVICE_ERROR", details={"error": type(exc).__name__},
            )
            self.con.commit()
            return StepOutcome(step_run_id, attempt, "FAILED", [], "SERVICE_ERROR", str(exc))

        repo.finish_step(
            self.con, step_run_id, "SUCCEEDED",
            output_revision_refs=refs,
            details={"kind": spec.kind, "template_sha256": template_sha},
        )
        self.con.commit()
        return StepOutcome(step_run_id, attempt, "SUCCEEDED", refs)


def _revision_refs(output: Any) -> list[str]:
    if output is None:
        return []
    if isinstance(output, (list, tuple)):
        return [str(value) for value in output]
    if isinstance(output, Mapping):
        raw = output.get("revision_ids") or output.get("refs") or []
        if isinstance(raw, (str, int)):
            return [str(raw)]
        return [str(value) for value in raw]
    return [str(output)]
