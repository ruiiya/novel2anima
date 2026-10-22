"""Deny-by-default LLM stage boundary used by the pipeline dispatcher.

The provider receives only a validated JSON request and the approved template.
It has no shell, filesystem, SQL or tool-registry callback.  When the template
is missing/disabled the provider is not called at all.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Callable, Mapping

from novel2anima.llm.contracts import STAGES, ContractError, StageBlocked
from novel2anima.llm.registry import RunResult, active_template, invoke_stage
from novel2anima.pipeline import policies

Provider = Callable[[dict[str, Any], Mapping[str, Any]], Mapping[str, Any]]


class StageExecutionBlocked(StageBlocked):
    """Configuration/approval is missing before any provider call."""


def active_template_sha256(con: sqlite3.Connection, stage: str) -> str | None:
    template = active_template(con, stage)
    return None if template is None else str(template["content_sha256"])


class LLMStageExecutor:
    def __init__(
        self,
        con: sqlite3.Connection,
        provider: Provider,
        *,
        model_provider: str = "stub",
        model_name: str = "stub",
    ) -> None:
        if not callable(provider):
            raise TypeError("provider must be callable")
        self.con = con
        self.provider = provider
        self.model_provider = model_provider
        self.model_name = model_name

    def execute(
        self,
        stage: str,
        *,
        project_id: int,
        request: Mapping[str, Any],
        execution_key: str,
        pipeline_run_id: int | None = None,
        act_id: int | None = None,
        shot_id: int | None = None,
    ) -> RunResult:
        if stage not in STAGES:
            raise ContractError(f"unknown LLM stage: {stage}")
        template = active_template(self.con, stage)
        if template is None:
            raise StageExecutionBlocked(f"stage {stage} has no approved prompt template")
        if not template["system_text"].strip() or not template["task_text"].strip():
            raise StageExecutionBlocked(f"stage {stage} has empty approved instructions")
        policies.reject_execution_intent(dict(request), "request")

        def guarded(template_row: dict[str, Any], payload: Mapping[str, Any]) -> Mapping[str, Any]:
            output = self.provider(template_row, payload)
            policies.reject_execution_intent(output, "output")
            return output

        return invoke_stage(
            self.con,
            stage,
            project_id=int(project_id),
            request=request,
            executor=guarded,
            model_provider=self.model_provider,
            model_name=self.model_name,
            pipeline_run_id=None if pipeline_run_id is None else int(pipeline_run_id),
            act_id=act_id,
            shot_id=shot_id,
            execution_key=execution_key,
        )
