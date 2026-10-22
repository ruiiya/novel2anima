"""The eleven versioned LLM stage contracts.

The repository deliberately uses a small JSON-Schema subset instead of adding a
runtime dependency. Every output has a stage constant and envelope so a result
from one stage cannot be accepted by another.
"""
from __future__ import annotations

import json
import pathlib
from typing import Any, Mapping

from novel2anima.paths import ROOT

SCHEMA_VERSION = "v4-1"
SCHEMA_DIR = ROOT / "llm" / "schemas"

STAGES = (
    "01_brief",
    "02_story",
    "03_character",
    "04_wardrobe",
    "05_act_beats",
    "06_shot_direction",
    "07_catalog_selection",
    "08_natural_prompt",
    "09_semantic_review",
    "10_visual_qc",
    "11_targeted_revision",
)


class ContractError(ValueError):
    """Invalid request/output or an unavailable stage contract."""


class StageBlocked(RuntimeError):
    """The stage has no explicitly approved, non-empty prompt template."""


def schema_path(stage: str) -> pathlib.Path:
    if stage not in STAGES:
        raise ContractError(f"unknown LLM stage: {stage}")
    return SCHEMA_DIR / f"{stage}.schema.json"


def load_schema(stage: str) -> dict[str, Any]:
    path = schema_path(stage)
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError(f"missing schema for {stage}: {path}") from exc
    if not isinstance(schema, dict):
        raise ContractError(f"schema must be an object: {path}")
    return schema


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ContractError(f"unsupported schema type: {expected}")


def validate(payload: Any, schema: Mapping[str, Any], path: str = "$") -> None:
    """Validate the JSON-Schema subset used by the eleven contracts."""
    if "const" in schema and payload != schema["const"]:
        raise ContractError(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and payload not in schema["enum"]:
        raise ContractError(f"{path}: expected one of {schema['enum']!r}")
    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(payload, item) for item in types):
            raise ContractError(f"{path}: expected {expected}, got {type(payload).__name__}")
    if isinstance(payload, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in payload:
                raise ContractError(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, value in payload.items():
            if key in properties:
                validate(value, properties[key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                raise ContractError(f"{path}: unexpected property {key!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate(value, schema["additionalProperties"], f"{path}.{key}")
    if isinstance(payload, list):
        if "minItems" in schema and len(payload) < schema["minItems"]:
            raise ContractError(f"{path}: needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(payload) > schema["maxItems"]:
            raise ContractError(f"{path}: allows at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen = {json.dumps(item, sort_keys=True) for item in payload}
            if len(seen) != len(payload):
                raise ContractError(f"{path}: items must be unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(payload):
                validate(item, schema["items"], f"{path}[{index}]")
    if isinstance(payload, str):
        if "minLength" in schema and len(payload) < schema["minLength"]:
            raise ContractError(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(payload) > schema["maxLength"]:
            raise ContractError(f"{path}: longer than {schema['maxLength']}")
    if isinstance(payload, (int, float)) and not isinstance(payload, bool):
        if "minimum" in schema and payload < schema["minimum"]:
            raise ContractError(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and payload > schema["maximum"]:
            raise ContractError(f"{path}: above maximum {schema['maximum']}")


def validate_output(stage: str, output: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(output, Mapping):
        raise ContractError("LLM output must be a JSON object")
    schema = load_schema(stage)
    validate(dict(output), schema)
    return dict(output)
