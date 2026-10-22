"""DB-first story/wardrobe/continuity writers for PR-05.

Every function takes an open SQLite connection whose caller enabled foreign keys.
The SQL schema remains the final guard; these helpers add explicit contracts and
stable revision/JSON hashing so callers cannot bypass them by accident.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Iterable, Mapping

MAX_PARTICIPANTS = 8


class DomainError(ValueError):
    """Raised when a domain invariant is violated before a write."""


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _next_revision(con: sqlite3.Connection, table: str, key: str, key_id: int) -> int:
    row = con.execute(
        f"SELECT coalesce(max(revision), 0) + 1 FROM {table} WHERE {key}=?", (key_id,)
    ).fetchone()
    return int(row[0])


def create_identity_revision(
    con: sqlite3.Connection,
    character_id: int,
    identity: Mapping[str, Any],
    *,
    status: str = "draft",
    reference_asset_id: int | None = None,
) -> int:
    if not isinstance(identity, Mapping):
        raise DomainError("identity must be a JSON object")
    body = _json(dict(identity))
    revision = _next_revision(con, "character_identity_revision", "character_id", character_id)
    cur = con.execute(
        "INSERT INTO character_identity_revision"
        "(character_id,revision,identity_json,reference_asset_id,sha256,status)"
        " VALUES(?,?,?,?,?,?)",
        (character_id, revision, body, reference_asset_id, _sha(body), "draft"),
    )
    revision_id = int(cur.lastrowid)
    if status != "draft":
        con.execute(
            "UPDATE character_identity_revision SET status=? WHERE id=?", (status, revision_id)
        )
    return revision_id


def create_outfit_revision(
    con: sqlite3.Connection,
    character_id: int,
    spec: Mapping[str, Any],
    items: Iterable[Mapping[str, Any]],
    *,
    status: str = "draft",
    anchor_asset_id: int | None = None,
) -> int:
    """Create an outfit revision and its immutable item construction.

    Each item must carry item_code, slot and garment_type. Slots are not free
    text at write time: an empty slot is rejected rather than guessed.
    """
    if not isinstance(spec, Mapping):
        raise DomainError("outfit spec must be a JSON object")
    rows = list(items)
    if not rows:
        raise DomainError("outfit revision needs at least one item")
    seen: set[str] = set()
    for item in rows:
        for field in ("item_code", "slot", "garment_type"):
            if not str(item.get(field) or "").strip():
                raise DomainError(f"outfit item missing {field}")
        code = str(item["item_code"])
        if code in seen:
            raise DomainError(f"duplicate outfit item_code: {code}")
        seen.add(code)

    body = _json(dict(spec))
    revision = _next_revision(con, "outfit_revision", "character_id", character_id)
    cur = con.execute(
        "INSERT INTO outfit_revision"
        "(character_id,revision,spec_json,anchor_asset_id,status,spec_sha256)"
        " VALUES(?,?,?,?,?,?)",
        (character_id, revision, body, anchor_asset_id, "draft", _sha(body)),
    )
    revision_id = int(cur.lastrowid)
    con.executemany(
        "INSERT INTO outfit_item"
        "(outfit_revision_id,item_code,slot,garment_type,silhouette,cut,material,"
        "base_color,pattern,details_json,exact_anchor_asset_id)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                revision_id,
                item["item_code"],
                item["slot"],
                item["garment_type"],
                item.get("silhouette", ""),
                item.get("cut", ""),
                item.get("material", ""),
                item.get("base_color", ""),
                item.get("pattern", ""),
                _json(dict(item.get("details") or {})),
                item.get("exact_anchor_asset_id"),
            )
            for item in rows
        ],
    )
    if status != "draft":
        con.execute("UPDATE outfit_revision SET status=? WHERE id=?", (status, revision_id))
    return revision_id


def add_participant(
    con: sqlite3.Connection,
    shot_id: int,
    character_id: int,
    *,
    slot_no: int = 1,
    scene_role: str = "subject",
) -> None:
    con.execute(
        "INSERT INTO shot_participant(shot_id,character_id,slot_no,scene_role)"
        " VALUES(?,?,?,?)",
        (shot_id, character_id, slot_no, scene_role),
    )


def add_interaction(
    con: sqlite3.Connection,
    shot_id: int,
    actor_character_id: int,
    target_character_id: int | None,
    action_code: str,
    *,
    body_target: str | None = None,
    instruction: str = "",
    sort_order: int = 1,
) -> int:
    """Record a directed interaction; never infer missing actor/target."""
    if not action_code or not str(action_code).strip():
        raise DomainError("directed interaction needs action_code")
    if target_character_id is None:
        raise DomainError("directed interaction needs explicit target_character_id")
    if actor_character_id == target_character_id:
        raise DomainError("actor and target must differ")
    participants = {
        row[0]
        for row in con.execute(
            "SELECT character_id FROM shot_participant WHERE shot_id=?", (shot_id,)
        )
    }
    if actor_character_id not in participants or target_character_id not in participants:
        raise DomainError("actor and target must be participants of this shot")
    cur = con.execute(
        "INSERT INTO shot_interaction"
        "(shot_id,actor_character_id,target_character_id,action_code,body_target,"
        "instruction,sort_order) VALUES(?,?,?,?,?,?,?)",
        (
            shot_id,
            actor_character_id,
            target_character_id,
            str(action_code).strip(),
            body_target,
            instruction,
            sort_order,
        ),
    )
    return int(cur.lastrowid)


def create_shot_spec_revision(
    con: sqlite3.Connection,
    shot_id: int,
    spec: Mapping[str, Any],
    *,
    source_document_revision_id: int | None = None,
    status: str = "draft",
) -> int:
    if not isinstance(spec, Mapping):
        raise DomainError("shot spec must be a JSON object")
    participants = spec.get("participants")
    if not isinstance(participants, list) or not participants:
        raise DomainError("shot spec needs explicit participants")
    if len(participants) > MAX_PARTICIPANTS:
        raise DomainError("shot supports at most eight explicit participants")
    body = _json(dict(spec))
    revision = _next_revision(con, "shot_spec_revision", "shot_id", shot_id)
    cur = con.execute(
        "INSERT INTO shot_spec_revision"
        "(shot_id,revision,source_document_revision_id,spec_json,spec_sha256,status)"
        " VALUES(?,?,?,?,?,?)",
        (shot_id, revision, source_document_revision_id, body, _sha(body), "draft"),
    )
    revision_id = int(cur.lastrowid)
    if status != "draft":
        con.execute("UPDATE shot_spec_revision SET status=? WHERE id=?", (status, revision_id))
    return revision_id


def bind_outfit(
    con: sqlite3.Connection,
    shot_id: int,
    character_id: int,
    outfit_revision_id: int,
) -> None:
    con.execute(
        "INSERT INTO shot_outfit_binding(shot_id,character_id,outfit_revision_id)"
        " VALUES(?,?,?) ON CONFLICT(shot_id,character_id) DO UPDATE SET"
        " outfit_revision_id=excluded.outfit_revision_id",
        (shot_id, character_id, outfit_revision_id),
    )


def add_continuity_assertion(
    con: sqlite3.Connection,
    shot_id: int,
    character_id: int,
    axis: str,
    *,
    source: str,
    value_tag_id: int | None = None,
    evidence: Mapping[str, Any] | None = None,
    confidence: float = 1.0,
    state: str = "proposed",
) -> int:
    if source not in {"user", "llm", "inference", "qa", "system"}:
        raise DomainError("invalid continuity source")
    if not axis.strip():
        raise DomainError("continuity axis is required")
    if not 0 <= confidence <= 1:
        raise DomainError("continuity confidence must be between 0 and 1")
    cur = con.execute(
        "INSERT INTO continuity_assertion"
        "(shot_id,character_id,axis,value_tag_id,source,evidence_json,confidence,state)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (
            shot_id,
            character_id,
            axis.strip(),
            value_tag_id,
            source,
            _json(dict(evidence or {})),
            confidence,
            state,
        ),
    )
    return int(cur.lastrowid)


def effective_continuity(con: sqlite3.Connection, shot_id: int) -> dict[tuple[int, str], dict[str, Any]]:
    """Approved user claims outrank approved inferred/LLM claims, never overwrite them."""
    rows = con.execute(
        "SELECT character_id,axis,value_tag_id,source,state,confidence,evidence_json"
        " FROM continuity_assertion WHERE shot_id=? AND state='approved'"
        " ORDER BY CASE source WHEN 'user' THEN 0 WHEN 'qa' THEN 1 ELSE 2 END, id DESC",
        (shot_id,),
    ).fetchall()
    result: dict[tuple[int, str], dict[str, Any]] = {}
    for character_id, axis, value_tag_id, source, state, confidence, evidence in rows:
        key = (int(character_id), str(axis))
        if key not in result:
            result[key] = {
                "value_tag_id": value_tag_id,
                "source": source,
                "state": state,
                "confidence": confidence,
                "evidence": json.loads(evidence or "{}"),
            }
    return result
