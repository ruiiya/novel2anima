"""Content-addressed asset storage with byte-hash verification."""
from __future__ import annotations

import hashlib
import sqlite3
from typing import Any, Mapping

import json


class AssetError(ValueError):
    """Asset bytes do not match their declared hash or metadata."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def put_asset(
    con: sqlite3.Connection,
    data: bytes,
    mime_type: str,
    *,
    original_name: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> int:
    if not isinstance(data, (bytes, bytearray)):
        raise AssetError("asset data must be bytes")
    if not mime_type:
        raise AssetError("asset mime_type is required")
    body = bytes(data)
    sha = hashlib.sha256(body).hexdigest()
    existing = con.execute(
        "SELECT id,byte_length,sha256 FROM asset_blob WHERE sha256=?", (sha,)
    ).fetchone()
    if existing is not None:
        if int(existing[1]) != len(body) or existing[2] != sha:
            raise AssetError("existing asset row does not match bytes")
        return int(existing[0])
    cur = con.execute(
        "INSERT INTO asset_blob(sha256,mime_type,original_name,byte_length,body,metadata_json)"
        " VALUES(?,?,?,?,?,?)",
        (sha, mime_type, original_name, len(body), sqlite3.Binary(body), _json(dict(metadata or {}))),
    )
    return int(cur.lastrowid)


def get_asset(con: sqlite3.Connection, asset_id: int) -> tuple[bytes, str]:
    row = con.execute(
        "SELECT body,sha256 FROM asset_blob WHERE id=?", (asset_id,)
    ).fetchone()
    if row is None:
        raise AssetError(f"unknown asset: {asset_id}")
    body = bytes(row[0])
    actual = hashlib.sha256(body).hexdigest()
    if actual != row[1]:
        raise AssetError("stored asset SHA-256 does not match bytes")
    return body, row[1]


def verify_asset(con: sqlite3.Connection, asset_id: int) -> str:
    body, sha = get_asset(con, asset_id)
    row = con.execute(
        "SELECT byte_length FROM asset_blob WHERE id=?", (asset_id,)
    ).fetchone()
    if row is None or int(row[0]) != len(body):
        raise AssetError("asset byte_length does not match body")
    return sha
