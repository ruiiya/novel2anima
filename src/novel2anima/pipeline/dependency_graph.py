"""Dependency-aware invalidation for story steps.

Only steps reachable from the edited step are invalidated.  Catalog ETL is not
part of this graph and is never scheduled here.
"""
from __future__ import annotations

from . import registry


def topological_order() -> list[str]:
    return list(registry.STEP_CODES)


def descendants(step_code: str) -> set[str]:
    registry.step_spec(step_code)
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for step in registry.STEPS:
            if step.code in found:
                continue
            if any(dep in found or dep == step_code for dep in step.dependencies):
                found.add(step.code)
                changed = True
    return found


def affected_steps(changed_steps: set[str] | tuple[str, ...]) -> list[str]:
    """Return changed steps plus every dependent step in DAG order."""
    changed = set(changed_steps)
    if not changed:
        return []
    for code in changed:
        registry.step_spec(code)
    affected = set(changed)
    for code in changed:
        affected |= descendants(code)
    return [code for code in topological_order() if code in affected]


def shot_action_invalidation(shot_id: int) -> dict:
    return _invalidation("shot_action", {"shot_id": int(shot_id)}, "06_shot_direction")


def outfit_invalidation(character_id: int, shot_ids: list[int]) -> dict:
    result = _invalidation("outfit_revision", {"character_id": int(character_id)}, "04_wardrobe")
    result["bound_shot_ids"] = [int(value) for value in shot_ids]
    return result


def _invalidation(kind: str, subject: dict, start: str) -> dict:
    steps = affected_steps({start})
    return {
        "kind": kind,
        "subject": subject,
        "steps": steps,
        "catalog_rebuild": False,
    }
