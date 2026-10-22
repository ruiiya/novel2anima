"""Static, versioned workflow registry for V4.1 story execution.

The registry is source code.  An LLM response, a request payload or a prompt
file can never add a step, a dependency or a shell command here.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

WORKFLOW_CODE = "story"
WORKFLOW_VERSION = "v4.1"
WORKFLOW_VERSION_UNKNOWN = "unknown-workflow-version"

STORY_TRIGGER_SOURCES = ("USER", "API", "SCHEDULED", "ADMIN")
RUNTIME_MODES = ("LEGACY", "MIGRATING", "V4_ACTIVE")

CATALOG_JOB_CODES = (
    "verify_catalog",
    "rebuild_fts",
    "import_catalog",
)


class RegistryError(ValueError):
    """Unknown workflow, step or operation."""


@dataclass(frozen=True)
class StepSpec:
    code: str
    kind: str
    dependencies: tuple[str, ...]
    conditional: bool = False


# The DAG is deliberately linear plus conditional tails.  Any change here is a
# workflow version change and changes workflow_sha256(), invalidating old runs.
_STEPS = (
    StepSpec("01_brief", "LLM", ()),
    StepSpec("02_story", "LLM", ("01_brief",)),
    StepSpec("03_character", "LLM", ("02_story",)),
    StepSpec("04_wardrobe", "LLM", ("03_character",)),
    StepSpec("05_act_beats", "LLM", ("04_wardrobe",)),
    StepSpec("06_shot_direction", "LLM", ("05_act_beats",)),
    StepSpec("retrieve_catalog", "PY", ("06_shot_direction",)),
    StepSpec("07_catalog_selection", "LLM", ("retrieve_catalog",), True),
    StepSpec("compile_prompt", "PY", ("07_catalog_selection", "retrieve_catalog")),
    StepSpec("08_natural_prompt", "LLM", ("compile_prompt",), True),
    StepSpec("09_semantic_review", "LLM", ("08_natural_prompt", "compile_prompt")),
    StepSpec("render", "PY", ("09_semantic_review",)),
    StepSpec("10_visual_qc", "LLM", ("render",), True),
    StepSpec("11_targeted_revision", "LLM", ("10_visual_qc", "09_semantic_review"), True),
)

STEPS = _STEPS
STEP_BY_CODE = {step.code: step for step in STEPS}
STEP_CODES = tuple(step.code for step in STEPS)
LLM_STEP_CODES = tuple(step.code for step in STEPS if step.kind == "LLM")
PY_STEP_CODES = tuple(step.code for step in STEPS if step.kind == "PY")

# Contract cut-down allowlist: story runs may only dispatch registry steps.
STORY_OPERATIONS = ("start_story", "resume_run", "rerun_from")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def workflow_definition(version: str = WORKFLOW_VERSION) -> dict[str, Any]:
    if version != WORKFLOW_VERSION:
        raise RegistryError(f"unknown workflow version: {version}")
    return {
        "workflow_code": WORKFLOW_CODE,
        "workflow_version": version,
        "steps": [
            {
                "code": step.code,
                "kind": step.kind,
                "dependencies": list(step.dependencies),
                "conditional": step.conditional,
            }
            for step in STEPS
        ],
    }


def workflow_sha256(version: str = WORKFLOW_VERSION) -> str:
    return hashlib.sha256(_canonical(workflow_definition(version)).encode("utf-8")).hexdigest()


def get_workflow(version: str = WORKFLOW_VERSION) -> dict[str, Any]:
    definition = workflow_definition(version)
    definition["sha256"] = workflow_sha256(version)
    return definition


def step_spec(step_code: str) -> StepSpec:
    try:
        return STEP_BY_CODE[step_code]
    except KeyError as exc:
        raise RegistryError(f"step is not registered: {step_code}") from exc


def is_llm_step(step_code: str) -> bool:
    return step_spec(step_code).kind == "LLM"


def assert_story_operation(operation: str) -> None:
    if operation not in STORY_OPERATIONS:
        raise RegistryError(f"operation is not allowed in a story run: {operation}")


def assert_catalog_job(job_code: str) -> None:
    if job_code not in CATALOG_JOB_CODES:
        raise RegistryError(f"catalog job is not registered: {job_code}")
