"""Render persistence: approved prompt -> BLOB -> generation provenance."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sqlite3
from typing import Any, Mapping

from novel2anima.prompting.compiler import CompileError, load_prompt
from novel2anima.storage.assets import AssetError, get_asset, put_asset


class RenderError(ValueError):
    """A render cannot be persisted without its complete input pin."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclasses.dataclass(frozen=True)
class RenderResult:
    generation_id: int
    asset_id: int
    sha256: str


def create_render(
    con: sqlite3.Connection,
    *,
    shot_id: int,
    model_profile_id: int,
    prompt_revision_id: int,
    image: bytes,
    mime_type: str = "image/png",
    seed: int,
    model_settings: Mapping[str, Any],
    pipeline_run_id: int | None = None,
) -> RenderResult:
    prompt = load_prompt(con, prompt_revision_id)
    if prompt["status"] != "approved":
        raise RenderError("render requires an approved prompt revision")
    if prompt["shot_id"] != shot_id:
        raise RenderError("prompt revision belongs to another shot")
    if seed is None:
        raise RenderError("render requires an explicit seed")
    if not isinstance(model_settings, Mapping):
        raise RenderError("model_settings must be a JSON object")
    if prompt["outfit_snapshot_sha256"] is None:
        raise RenderError("prompt has no pinned outfit snapshot")

    asset_id = put_asset(
        con,
        image,
        mime_type,
        original_name=f"shot-{shot_id}-gen.png",
        metadata={"seed": seed, "prompt_revision_id": prompt_revision_id},
    )
    body, sha = get_asset(con, asset_id)
    if hashlib.sha256(body).hexdigest() != sha:
        raise RenderError("asset SHA mismatch")
    full_prompt = f"{prompt['positive_tags']}\nNegative: {prompt['negative_prompt']}"
    cur = con.execute(
        "INSERT INTO generation"
        "(shot_id,model_profile_id,prompt,seed,image_path,image_sha256,evaluation_json,decision)"
        " VALUES(?,?,?,?,NULL,?,'{}','pending')",
        (shot_id, model_profile_id, full_prompt, seed, sha),
    )
    generation_id = int(cur.lastrowid)
    con.execute(
        "INSERT INTO generation_asset(generation_id,role,asset_id) VALUES(?,'render',?)",
        (generation_id, asset_id),
    )
    settings = dict(model_settings)
    settings["seed"] = seed
    settings["prompt_revision_id"] = prompt_revision_id
    settings["asset_sha256"] = sha
    con.execute(
        "INSERT INTO generation_provenance"
        "(generation_id,shot_prompt_revision_id,pipeline_run_id,model_settings_json,"
        "outfit_snapshot_sha256) VALUES(?,?,?,?,?)",
        (
            generation_id,
            prompt_revision_id,
            pipeline_run_id,
            _json(settings),
            prompt["outfit_snapshot_sha256"],
        ),
    )
    con.commit()
    return RenderResult(generation_id=generation_id, asset_id=asset_id, sha256=sha)


def get_render(con: sqlite3.Connection, generation_id: int) -> dict[str, Any]:
    row = con.execute(
        "SELECT g.id,g.shot_id,g.seed,g.image_sha256,a.id,a.sha256,a.mime_type"
        " FROM generation g"
        " JOIN generation_asset ga ON ga.generation_id=g.id AND ga.role='render'"
        " JOIN asset_blob a ON a.id=ga.asset_id"
        " WHERE g.id=?",
        (generation_id,),
    ).fetchone()
    if row is None:
        raise RenderError(f"unknown render generation: {generation_id}")
    body, sha = get_asset(con, int(row[4]))
    if sha != row[5] or sha != row[3]:
        raise RenderError("render asset SHA does not match generation")
    return {
        "generation_id": int(row[0]),
        "shot_id": int(row[1]),
        "seed": row[2],
        "image_sha256": row[3],
        "asset_id": int(row[4]),
        "asset_sha256": sha,
        "mime_type": row[6],
        "bytes": body,
    }


def replay_render(con: sqlite3.Connection, generation_id: int) -> dict[str, Any]:
    """DB-only replay; no image path or prompt file is read."""
    render = get_render(con, generation_id)
    row = con.execute(
        "SELECT shot_prompt_revision_id,model_settings_json,outfit_snapshot_sha256"
        " FROM generation_provenance WHERE generation_id=?",
        (generation_id,),
    ).fetchone()
    if row is None:
        raise RenderError("render has no provenance")
    prompt = load_prompt(con, int(row[0]))
    settings = json.loads(row[1])
    render["prompt_revision_id"] = int(row[0])
    render["model_settings"] = settings
    render["outfit_snapshot_sha256"] = row[2]
    render["prompt_content_sha256"] = prompt["content_sha256"]
    return render
