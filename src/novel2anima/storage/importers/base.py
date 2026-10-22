"""Shared primitives for the PR-03 external import infrastructure.

The importer deliberately separates *reading* a source file from *parsing* it:

* the ledger runner hashes every file once while streaming;
* a parser calls :meth:`SourceFile.read_bytes`, which re-checks that hash before
  returning bytes, so a file changed between inventory and parse is blocked;
* no parser uses the process working directory.  All paths are resolved against
  the explicit source root stored on :class:`SourceFile`.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

STATUS_IMPORTED = "imported"
STATUS_DUPLICATE = "duplicate"
STATUS_BLOCKED = "blocked"
STATUS_SKIPPED = "skipped_by_policy"
VALID_STATUSES = {
    STATUS_IMPORTED,
    STATUS_DUPLICATE,
    STATUS_BLOCKED,
    STATUS_SKIPPED,
}

CLASS_PLAN = "plan"
CLASS_PROMPT = "prompt"
CLASS_REVIEW = "review"
CLASS_WARDROBE = "wardrobe"
CLASS_ROSTER = "roster"
CLASS_CATALOG = "catalog"
CLASS_ASSET = "asset"
CLASS_SOURCE = "source_controlled"
CLASS_WORKSPACE = "legacy_workspace"
CLASS_REPORT = "legacy_report"
CLASS_LLM_SCAFFOLD = "llm_scaffold"
CLASS_DATABASE = "canonical_database"
CLASS_GENERATED = "generated_artifact"
CLASS_UNKNOWN = "unknown"


class ParseError(ValueError):
    """A stable, user-facing parser error (never an unhandled crash)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def bounded_json(value: Any, limit: int = 8000) -> Any:
    """Keep evidence useful without allowing a pathological row to bloat the DB."""
    encoded = canonical_json(value)
    if len(encoded.encode("utf-8")) <= limit:
        return value
    return {
        "truncated": True,
        "sha256": sha256_bytes(encoded.encode("utf-8")),
        "bytes": len(encoded.encode("utf-8")),
    }


@dataclass
class SourceFile:
    root: Path
    relative_path: str
    sha256: str
    size_bytes: int
    _data: bytes | None = field(default=None, repr=False)
    _read_attempted: bool = field(default=False, repr=False)

    @property
    def path(self) -> Path:
        return self.root / self.relative_path

    @property
    def was_read(self) -> bool:
        return self._data is not None

    def read_bytes(self) -> bytes:
        if self._data is None:
            try:
                data = self.path.read_bytes()
            except OSError as exc:
                raise ParseError("source_read_failed", f"{self.relative_path}: {exc}") from exc
            actual = sha256_bytes(data)
            if actual != self.sha256:
                raise ParseError(
                    "source_changed_during_import",
                    f"{self.relative_path}: expected {self.sha256}, got {actual}",
                )
            self._data = data
        self._read_attempted = True
        return self._data

    def read_text(self) -> str:
        try:
            return self.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseError(
                "source_not_utf8",
                f"{self.relative_path}: {exc}",
            ) from exc

    def read_json(self) -> Any:
        try:
            return json.loads(self.read_text())
        except json.JSONDecodeError as exc:
            raise ParseError(
                "source_invalid_json",
                f"{self.relative_path}: {exc}",
            ) from exc


@dataclass
class Outcome:
    status: str
    target_table: str | None = None
    target_pk: int | None = None
    exception: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    verified_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid import status: {self.status}")


def imported(
    *,
    target_table: str | None = None,
    target_pk: int | None = None,
    details: dict[str, Any] | None = None,
    exception: str | None = None,
) -> Outcome:
    return Outcome(
        status=STATUS_IMPORTED,
        target_table=target_table,
        target_pk=target_pk,
        exception=exception,
        details=details or {},
    )


def duplicate(
    *,
    target_table: str | None = None,
    target_pk: int | None = None,
    details: dict[str, Any] | None = None,
    exception: str | None = None,
) -> Outcome:
    return Outcome(
        status=STATUS_DUPLICATE,
        target_table=target_table,
        target_pk=target_pk,
        exception=exception,
        details=details or {},
    )


def blocked(
    reason: str,
    *,
    details: dict[str, Any] | None = None,
    target_table: str | None = None,
    target_pk: int | None = None,
) -> Outcome:
    return Outcome(
        status=STATUS_BLOCKED,
        target_table=target_table,
        target_pk=target_pk,
        exception=reason,
        details=details or {},
    )


def skipped(
    reason: str,
    *,
    details: dict[str, Any] | None = None,
    target_table: str | None = None,
    target_pk: int | None = None,
) -> Outcome:
    return Outcome(
        status=STATUS_SKIPPED,
        target_table=target_table,
        target_pk=target_pk,
        exception=reason,
        details=details or {},
    )


class FileParser(Protocol):
    classification: str
    parser_version: str

    def parse(self, source: SourceFile, connection: sqlite3.Connection) -> Outcome:
        ...


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ParseError("invalid_object", f"{label} must be a JSON object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ParseError("invalid_list", f"{label} must be a JSON array")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ParseError("invalid_text", f"{label} must be a non-empty string")
    return value.strip()


def require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParseError("invalid_integer", f"{label} must be an integer")
    return value


def queue_reconciliation(
    connection: sqlite3.Connection,
    *,
    gap_key: str,
    domain: str,
    rule_code: str,
    evidence: dict[str, Any],
    severity: str = "warning",
    project_id: int | None = None,
    act_id: int | None = None,
    shot_id: int | None = None,
    character_id: int | None = None,
    entity_table: str | None = None,
    entity_id: int | None = None,
) -> bool:
    """Insert a stable open gap; return True only for a new row.

    Gaps are intentionally not treated as import failures.  They are evidence
    that a human or a later PR must decide the missing content.
    """
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO reconciliation_item(
          gap_key, domain, severity, project_id, act_id, shot_id, character_id,
          entity_table, entity_id, rule_code, evidence_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gap_key,
            domain,
            severity,
            project_id,
            act_id,
            shot_id,
            character_id,
            entity_table,
            entity_id,
            rule_code,
            canonical_json(evidence),
        ),
    )
    return bool(cursor.rowcount)


def prompt_block_hash(positive_tags: str, negative_prompt: str, natural_prompt: str | None) -> str:
    return sha256_json(
        {
            "positive_tags": positive_tags,
            "negative_prompt": negative_prompt,
            "natural_prompt": natural_prompt,
        }
    )


def split_prompt_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
