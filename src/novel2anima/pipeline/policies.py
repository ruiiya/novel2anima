"""Execution policy: runtime mode, input hygiene, fingerprints and skips."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any, Mapping

from . import registry


class ExecutionControlDisabled(RuntimeError):
    """The story dispatcher is not enabled by the DB runtime flags."""


class InvalidProposal(ValueError):
    """Request/output tries to execute code, shell or an unregistered command."""


class PolicyError(RuntimeError):
    """Invalid runtime setting or step policy."""


_FORBIDDEN_KEYS = {
    "command", "run_command", "shell", "shell_command", "script", "python",
    "python_code", "sql", "subprocess", "create_etl", "etl", "eval", "exec",
}
_FORBIDDEN_TEXT = tuple(re.compile(pattern) for pattern in (
    r"(^|[\\/])etl[\\/]",
    r"\bsubprocess\b",
    r"\bos\.system\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bshell\s*=\s*True\b",
    r"\bpython\s+-c\b",
    r"\b(?:build|import_tags|import_wiki_pages|import_colour_sets|prune_tags|cleanup_db)\.py\b",
))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def reject_execution_intent(value: Any, path: str = "$") -> None:
    """Reject keys or strings that attempt to smuggle executable work."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).strip().lower() in _FORBIDDEN_KEYS:
                raise InvalidProposal(f"{path}: forbidden execution key {key!r}")
            reject_execution_intent(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_execution_intent(item, f"{path}[{index}]")
    elif isinstance(value, str):
        for pattern in _FORBIDDEN_TEXT:
            if pattern.search(value):
                raise InvalidProposal(f"{path}: forbidden execution text")


def setting(con: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = con.execute("SELECT value FROM runtime_setting WHERE key=?", (key,)).fetchone()
    return default if row is None else str(row[0])


def runtime_mode(con: sqlite3.Connection) -> str:
    value = setting(con, "runtime_mode", "LEGACY") or "LEGACY"
    if value not in registry.RUNTIME_MODES:
        raise PolicyError(f"invalid runtime_mode: {value}")
    return value


def strict_enabled(con: sqlite3.Connection) -> bool:
    return (setting(con, "strict_execution_control", "off") or "off").lower() in {"on", "1", "true"}


def set_runtime_mode(con: sqlite3.Connection, mode: str) -> None:
    if mode not in registry.RUNTIME_MODES:
        raise PolicyError(f"invalid runtime_mode: {mode}")
    con.execute(
        "INSERT INTO runtime_setting(key,value) VALUES('runtime_mode',?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (mode,),
    )
    con.commit()


def set_strict_execution_control(con: sqlite3.Connection, enabled: bool) -> None:
    con.execute(
        "INSERT INTO runtime_setting(key,value) VALUES('strict_execution_control',?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        ("on" if enabled else "off",),
    )
    con.commit()


def require_story_enabled(con: sqlite3.Connection, mode: str | None = None) -> str:
    actual = mode or runtime_mode(con)
    if actual != "V4_ACTIVE":
        raise ExecutionControlDisabled(
            f"story orchestrator requires V4_ACTIVE (runtime_mode={actual})"
        )
    if not strict_enabled(con):
        raise ExecutionControlDisabled("strict_execution_control is OFF")
    return actual


def fingerprint(
    workflow_version: str,
    step_code: str,
    payload: Mapping[str, Any],
    *,
    template_sha256: str | None = None,
    policy_version: str = "v4.1",
) -> str:
    registry.step_spec(step_code)
    return _sha({
        "workflow_version": workflow_version,
        "step_code": step_code,
        "input": payload,
        "template_sha256": template_sha256,
        "policy_version": policy_version,
    })


def skip_reason(step_code: str, context: Mapping[str, Any]) -> str | None:
    if step_code == "07_catalog_selection" and not context.get("selection_needed", False):
        return "selection_not_requested"
    if step_code == "08_natural_prompt" and not context.get("natural_prompt", False):
        return "natural_prompt_not_requested"
    if step_code == "10_visual_qc" and not context.get("image_available", False):
        return "no_rendered_image"
    if step_code == "11_targeted_revision":
        if not context.get("image_available", False):
            return "no_rendered_image"
        if not context.get("targeted_revision", False):
            return "no_revision_requested"
    return None
