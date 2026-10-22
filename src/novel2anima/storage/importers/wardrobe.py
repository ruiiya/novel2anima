"""Legacy wardrobe colour-setting importer (PR-03).

The two colour JSON files are legacy setting inputs, not prompt truth.  They
are stored as draft ``n2a_setting_revision`` rows and are never activated here.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .base import (
    SourceFile,
    ParseError,
    blocked,
    canonical_json,
    duplicate,
    imported,
    require_object,
    sha256_json,
)


class WardrobeParser:
    classification = "wardrobe"
    parser_version = "wardrobe/1"

    def parse(self, source: SourceFile, connection: sqlite3.Connection):
        data = require_object(source.read_json(), "wardrobe root")
        if not data:
            return blocked("wardrobe_empty")
        for key, value in data.items():
            if not isinstance(key, str) or not key.strip():
                raise ParseError("wardrobe_invalid_key", "keys must be non-empty strings")
            if not isinstance(value, str) or not value.strip():
                raise ParseError(
                    "wardrobe_invalid_value",
                    f"{key}: values must be non-empty strings",
                )

        stem = Path(source.relative_path).stem
        if stem not in {"colour_choice", "colour_cue"}:
            return blocked(
                "wardrobe_setting_unknown",
                details={"stem": stem},
            )
        setting_key = f"wardrobe.{stem}"
        value_json = canonical_json(data)
        value_sha = sha256_json(data)
        existing = connection.execute(
            "SELECT id, revision, content_sha256 FROM n2a_setting_revision "
            "WHERE scope = 'global' AND setting_key = ? ORDER BY revision",
            (setting_key,),
        ).fetchall()
        for row in existing:
            if row["content_sha256"] == value_sha:
                return duplicate(
                    target_table="n2a_setting_revision",
                    target_pk=row["id"],
                    details={
                        "setting_key": setting_key,
                        "revision": row["revision"],
                        "entries": len(data),
                    },
                )
        revision = max((row["revision"] for row in existing), default=0) + 1
        cursor = connection.execute(
            "INSERT INTO n2a_setting_revision("
            "scope, setting_key, revision, value_json, content_sha256, status"
            ") VALUES ('global', ?, ?, ?, ?, 'draft')",
            (setting_key, revision, value_json, value_sha),
        )
        return imported(
            target_table="n2a_setting_revision",
            target_pk=cursor.lastrowid,
            details={
                "setting_key": setting_key,
                "revision": revision,
                "entries": len(data),
            },
        )
