"""Operator-only catalog maintenance API.

This module is deliberately not imported by the story orchestrator.  A story
run can report ``CURATION_GAP``; it cannot start an import, prune or FTS rebuild.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable, Mapping

from novel2anima.pipeline import registry
from novel2anima.storage import pipeline_repository as repo

CatalogHandler = Callable[[sqlite3.Connection, Mapping[str, Any]], Mapping[str, Any]]

_FORBIDDEN_STORY_ACTORS = {"story", "pipeline", "llm", "agent"}


class CatalogPermissionError(PermissionError):
    """The caller is not an operator/catalog administrator."""


def _verify_catalog(con: sqlite3.Connection, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    quick = con.execute("PRAGMA quick_check").fetchone()[0]
    foreign_keys = con.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "quick_check": quick,
        "foreign_key_errors": len(foreign_keys),
        "tag_count": int(con.execute("SELECT count(*) FROM tag").fetchone()[0]),
    }


def _rebuild_fts(con: sqlite3.Connection, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    con.execute("INSERT INTO visual_concept_fts(visual_concept_fts) VALUES('rebuild')")
    return {"rebuilt": "visual_concept_fts"}


def _import_catalog(con: sqlite3.Connection, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    # Import is an explicit operator command.  It never runs in a story process.
    from novel2anima.catalog import build_service

    code = build_service.main(["load"])
    if code:
        raise RuntimeError(f"catalog import exited with {code}")
    return {"imported": True}


DEFAULT_HANDLERS: dict[str, CatalogHandler] = {
    "verify_catalog": _verify_catalog,
    "rebuild_fts": _rebuild_fts,
    "import_catalog": _import_catalog,
}


def run_catalog_job(
    con: sqlite3.Connection,
    *,
    job_code: str,
    job_key: str,
    actor: str,
    approved_by: str,
    payload: Mapping[str, Any] | None = None,
    handler: CatalogHandler | None = None,
) -> dict[str, Any]:
    registry.assert_catalog_job(job_code)
    if actor.strip().lower() in _FORBIDDEN_STORY_ACTORS:
        raise CatalogPermissionError("story/LLM principals cannot run catalog maintenance")
    if not approved_by.strip():
        raise CatalogPermissionError("catalog job requires an explicit operator approval")
    fn = handler or DEFAULT_HANDLERS.get(job_code)
    if fn is None:
        raise registry.RegistryError(f"no implementation for catalog job: {job_code}")
    job_id, created = repo.create_catalog_job(
        con,
        job_key=job_key,
        job_code=job_code,
        actor=actor,
        approved_by=approved_by,
        payload=payload,
    )
    con.commit()
    if not created:
        row = con.execute(
            "SELECT status,result_json,error_text FROM catalog_job WHERE id=?", (job_id,)
        ).fetchone()
        return {
            "job_id": job_id,
            "replayed": True,
            "status": row[0],
            "result": None if row[1] is None else json.loads(row[1]),
            "error": row[2],
        }
    try:
        result = fn(con, payload or {})
        repo.finish_catalog_job(con, job_id, "SUCCEEDED", result=result)
        con.commit()
        return {"job_id": job_id, "replayed": False, "status": "SUCCEEDED", "result": dict(result)}
    except Exception as exc:  # noqa: BLE001 - ledger records the failure
        con.rollback()
        repo.finish_catalog_job(con, job_id, "FAILED", error=str(exc))
        con.commit()
        raise
