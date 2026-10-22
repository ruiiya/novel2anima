"""Deterministic prompt compilation from canonical database rows only."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Mapping

COMPILER_VERSION = "v4-1"
DEFAULT_NEGATIVE = "worst quality, low quality, blurry"
ROLE_ORDER = {
    "identity": 0,
    "outfit": 1,
    "interaction": 2,
    "action": 3,
    "expression": 4,
    "pose": 5,
    "camera": 6,
    "background": 7,
    "style": 8,
    "other": 9,
}


class CompileError(ValueError):
    """The canonical rows do not contain enough explicit information to compile."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _approved_spec(con: sqlite3.Connection, shot_id: int) -> sqlite3.Row:
    row = con.execute(
        "SELECT id,shot_id,revision,spec_json,spec_sha256,status FROM shot_spec_revision"
        " WHERE shot_id=? AND status='approved' ORDER BY revision DESC LIMIT 1",
        (shot_id,),
    ).fetchone()
    if row is None:
        raise CompileError(f"shot {shot_id} has no approved shot_spec_revision")
    return row


def _tag(con: sqlite3.Connection, name: str) -> sqlite3.Row:
    row = con.execute(
        "SELECT id,canonical_name,danbooru_category FROM tag WHERE canonical_name=?",
        (name,),
    ).fetchone()
    if row is None:
        raise CompileError(f"catalog tag does not exist: {name}")
    return row


def _spec_tag_rows(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tags = spec.get("tags") or []
    if isinstance(tags, dict):
        for role, values in tags.items():
            for value in values:
                if isinstance(value, str):
                    rows.append({"name": value, "role": role})
                else:
                    rows.append({**value, "role": value.get("role", role)})
    elif isinstance(tags, list):
        for value in tags:
            if isinstance(value, str):
                rows.append({"name": value, "role": "other"})
            elif isinstance(value, Mapping):
                rows.append(dict(value))
    for role, key in (
        ("identity", "identity_tags"),
        ("outfit", "outfit_tags"),
        ("action", "action_tags"),
        ("expression", "expression_tags"),
        ("pose", "pose_tags"),
        ("camera", "camera_tags"),
        ("background", "background_tags"),
        ("style", "style_tags"),
    ):
        values = spec.get(key) or []
        if isinstance(values, Mapping):
            for character_id, names in values.items():
                for name in names:
                    rows.append({"name": name, "role": role, "character_id": character_id})
        else:
            for value in values:
                if isinstance(value, str):
                    rows.append({"name": value, "role": role})
                else:
                    rows.append({**value, "role": value.get("role", role)})
    return rows


def _resolve_spec_tags(con: sqlite3.Connection, spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for item in _spec_tag_rows(spec):
        name = item.get("name") or item.get("canonical_name")
        if not name:
            if item.get("tag_id") is None:
                raise CompileError("spec tag needs name or tag_id")
            row = con.execute(
                "SELECT id,canonical_name,danbooru_category FROM tag WHERE id=?",
                (int(item["tag_id"]),),
            ).fetchone()
            if row is None:
                raise CompileError(f"catalog tag id does not exist: {item['tag_id']}")
        else:
            row = _tag(con, str(name))
        role = str(item.get("role") or "other")
        if role not in ROLE_ORDER:
            raise CompileError(f"unknown prompt tag role: {role}")
        resolved.append({
            "tag_id": int(row[0]),
            "canonical_name": str(row[1]),
            "category": row[2],
            "role": role,
            "character_id": int(item["character_id"]) if item.get("character_id") else None,
            "target_character_id": (
                int(item["target_character_id"]) if item.get("target_character_id") else None
            ),
            "weight": float(item.get("weight", 1.0)),
        })
    return resolved


def compile_shot(con: sqlite3.Connection, shot_id: int) -> int:
    """Compile a new draft prompt revision from approved canonical rows.

    The function never reads prompt files or the working directory. It refuses
    to infer a tag, participant, outfit or action that is absent from the DB.
    """
    shot = con.execute(
        "SELECT id,act_id,shot_no FROM shot WHERE id=?", (shot_id,)
    ).fetchone()
    if shot is None:
        raise CompileError(f"unknown shot: {shot_id}")
    spec = _approved_spec(con, shot_id)
    spec_json = json.loads(spec[3])
    if not isinstance(spec_json, dict):
        raise CompileError("shot spec must be a JSON object")

    participants = con.execute(
        "SELECT character_id,slot_no FROM shot_participant WHERE shot_id=? ORDER BY slot_no",
        (shot_id,),
    ).fetchall()
    if not participants:
        raise CompileError("shot has no explicit participants")
    participant_ids = {int(row[0]) for row in participants}

    resolved = _resolve_spec_tags(con, spec_json)

    interactions = con.execute(
        "SELECT actor_character_id,target_character_id,action_code FROM shot_interaction"
        " WHERE shot_id=? ORDER BY sort_order,id",
        (shot_id,),
    ).fetchall()
    for actor, target, action_code in interactions:
        actor, target = int(actor), int(target)
        if actor not in participant_ids or target not in participant_ids:
            raise CompileError("interaction actor/target is not a participant of this shot")
        if actor == target:
            raise CompileError("interaction actor and target must differ")
        tag = _tag(con, action_code)
        resolved.append({
            "tag_id": int(tag[0]),
            "canonical_name": str(tag[1]),
            "category": tag[2],
            "role": "interaction",
            "character_id": actor,
            "target_character_id": target,
            "weight": 1.0,
        })

    for value in spec_json.get("actions") or []:
        if isinstance(value, str):
            resolved.append({
                "tag_id": int(_tag(con, value)[0]),
                "canonical_name": value,
                "category": None,
                "role": "action",
                "character_id": None,
                "target_character_id": None,
                "weight": 1.0,
            })

    bindings = con.execute(
        "SELECT b.character_id,b.outfit_revision_id,r.spec_sha256,r.spec_json"
        " FROM shot_outfit_binding b JOIN outfit_revision r ON r.id=b.outfit_revision_id"
        " WHERE b.shot_id=? ORDER BY b.character_id",
        (shot_id,),
    ).fetchall()
    binding_rows: list[tuple[int, int, str]] = []
    for character_id, outfit_revision_id, spec_sha, outfit_spec in bindings:
        if int(character_id) not in participant_ids:
            raise CompileError("outfit binding character is not a participant")
        binding_rows.append((int(character_id), int(outfit_revision_id), str(spec_sha)))
        outfit = json.loads(outfit_spec or "{}")
        for item in _spec_tag_rows(outfit):
            name = item.get("name")
            if not name:
                continue
            tag = _tag(con, str(name))
            resolved.append({
                "tag_id": int(tag[0]),
                "canonical_name": str(tag[1]),
                "category": tag[2],
                "role": "outfit",
                "character_id": int(character_id),
                "target_character_id": None,
                "weight": float(item.get("weight", 1.0)),
            })

    if not resolved:
        raise CompileError("shot spec has no explicit positive tags")

    deduped: dict[tuple[int, str, int | None, int | None], dict[str, Any]] = {}
    for item in resolved:
        key = (item["tag_id"], item["role"], item["character_id"], item["target_character_id"])
        if key not in deduped:
            deduped[key] = item
        else:
            deduped[key]["weight"] = max(deduped[key]["weight"], item["weight"])
    ordered = sorted(
        deduped.values(),
        key=lambda item: (
            ROLE_ORDER[item["role"]],
            item["character_id"] or 0,
            item["target_character_id"] or 0,
            item["canonical_name"],
        ),
    )
    positive = ", ".join(
        f"({item['canonical_name']}:{item['weight']:g})" if item["weight"] != 1.0
        else item["canonical_name"]
        for item in ordered
    )
    negative = str(spec_json.get("negative_prompt") or DEFAULT_NEGATIVE)
    natural = spec_json.get("natural_prompt")
    natural_prompt = str(natural) if natural is not None else None
    content_sha = _sha(_json({
        "positive": positive,
        "negative": negative,
        "natural": natural_prompt,
        "source_shot_spec_sha256": spec[4],
        "compiler_version": COMPILER_VERSION,
    }))
    revision = int(con.execute(
        "SELECT coalesce(max(revision),0)+1 FROM shot_prompt_revision WHERE shot_id=?",
        (shot_id,),
    ).fetchone()[0])
    cur = con.execute(
        "INSERT INTO shot_prompt_revision"
        "(shot_id,revision,positive_tags,negative_prompt,natural_prompt,"
        "source_shot_spec_sha256,compiler_version,status,content_sha256)"
        " VALUES(?,?,?,?,?,?,?,'draft',?)",
        (
            shot_id,
            revision,
            positive,
            negative,
            natural_prompt,
            spec[4],
            COMPILER_VERSION,
            content_sha,
        ),
    )
    prompt_id = int(cur.lastrowid)

    con.executemany(
        "INSERT INTO shot_prompt_tag"
        "(shot_prompt_revision_id,seq,tag_id,character_id,target_character_id,token_role,weight)"
        " VALUES(?,?,?,?,?,?,?)",
        [
            (
                prompt_id,
                index + 1,
                item["tag_id"],
                item["character_id"],
                item["target_character_id"],
                item["role"],
                item["weight"],
            )
            for index, item in enumerate(ordered)
        ],
    )
    catalog_sha = _sha(_json([
        {"id": item["tag_id"], "name": item["canonical_name"], "category": item["category"]}
        for item in ordered
    ]))
    outfit_sha = _sha(_json(binding_rows))
    con.execute(
        "INSERT INTO shot_prompt_spec"
        "(shot_prompt_revision_id,shot_spec_revision_id,catalog_snapshot_sha256,"
        "outfit_snapshot_sha256) VALUES(?,?,?,?)",
        (prompt_id, int(spec[0]), catalog_sha, outfit_sha),
    )
    con.executemany(
        "INSERT INTO shot_prompt_outfit_input"
        "(shot_prompt_revision_id,character_id,outfit_revision_id) VALUES(?,?,?)",
        [(prompt_id, character_id, outfit_id) for character_id, outfit_id, _ in binding_rows],
    )
    return prompt_id


def load_prompt(con: sqlite3.Connection, prompt_id: int) -> dict[str, Any]:
    row = con.execute(
        "SELECT id,shot_id,revision,positive_tags,negative_prompt,natural_prompt,"
        "source_shot_spec_sha256,compiler_version,status,content_sha256"
        " FROM shot_prompt_revision WHERE id=?",
        (prompt_id,),
    ).fetchone()
    if row is None:
        raise CompileError(f"unknown prompt revision: {prompt_id}")
    tags = con.execute(
        "SELECT seq,tag_id,character_id,target_character_id,token_role,weight"
        " FROM shot_prompt_tag WHERE shot_prompt_revision_id=? ORDER BY seq",
        (prompt_id,),
    ).fetchall()
    spec = con.execute(
        "SELECT shot_spec_revision_id,catalog_snapshot_sha256,outfit_snapshot_sha256"
        " FROM shot_prompt_spec WHERE shot_prompt_revision_id=?",
        (prompt_id,),
    ).fetchone()
    outfits = con.execute(
        "SELECT character_id,outfit_revision_id FROM shot_prompt_outfit_input"
        " WHERE shot_prompt_revision_id=? ORDER BY character_id",
        (prompt_id,),
    ).fetchall()
    return {
        "id": int(row[0]),
        "shot_id": int(row[1]),
        "revision": int(row[2]),
        "positive_tags": row[3],
        "negative_prompt": row[4],
        "natural_prompt": row[5],
        "source_shot_spec_sha256": row[6],
        "compiler_version": row[7],
        "status": row[8],
        "content_sha256": row[9],
        "tags": [tuple(tag) for tag in tags],
        "shot_spec_revision_id": int(spec[0]) if spec else None,
        "catalog_snapshot_sha256": spec[1] if spec else None,
        "outfit_snapshot_sha256": spec[2] if spec else None,
        "outfits": [tuple(item) for item in outfits],
    }


def approve_prompt(con: sqlite3.Connection, prompt_id: int) -> dict[str, Any]:
    prompt = load_prompt(con, prompt_id)
    if prompt["status"] == "active":
        return prompt
    if prompt["status"] != "draft":
        raise CompileError("only a draft prompt can be approved")
    con.execute("UPDATE shot_prompt_revision SET status='approved' WHERE id=?", (prompt_id,))
    con.commit()
    return load_prompt(con, prompt_id)


def replay_prompt(con: sqlite3.Connection, prompt_id: int) -> dict[str, Any]:
    """Return a stored prompt and verify that its pinned input still exists."""
    prompt = load_prompt(con, prompt_id)
    spec = con.execute(
        "SELECT spec_sha256 FROM shot_spec_revision WHERE id=?",
        (prompt["shot_spec_revision_id"],),
    ).fetchone()
    if spec is None or spec[0] != prompt["source_shot_spec_sha256"]:
        raise CompileError("pinned shot spec revision is missing or changed")
    for character_id, outfit_revision_id in prompt["outfits"]:
        row = con.execute(
            "SELECT spec_sha256 FROM outfit_revision WHERE id=?", (outfit_revision_id,)
        ).fetchone()
        if row is None:
            raise CompileError("pinned outfit revision is missing")
    return prompt
