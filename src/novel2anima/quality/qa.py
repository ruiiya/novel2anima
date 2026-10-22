"""QA run history and targeted revision creation."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable, Mapping

from novel2anima.prompting.compiler import CompileError, load_prompt
from novel2anima.storage.domain_repository import DomainError, create_shot_spec_revision


class QAError(ValueError):
    """QA input would lose actor/target direction or violate run history."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_qa_run(
    con: sqlite3.Connection,
    *,
    act_id: int,
    run_key: str,
    evaluator_version: str,
    issues: Iterable[Mapping[str, Any]],
    pipeline_run_id: int | None = None,
) -> int:
    existing = con.execute(
        "SELECT id FROM qa_run WHERE run_key=?", (run_key,)
    ).fetchone()
    if existing is not None:
        return int(existing[0])
    cur = con.execute(
        "INSERT INTO qa_run(pipeline_run_id,act_id,run_key,evaluator_version,status)"
        " VALUES(?,?,?,?,'running')",
        (pipeline_run_id, act_id, run_key, evaluator_version),
    )
    qa_run_id = int(cur.lastrowid)
    try:
        shot_ids = {
            int(row[0])
            for row in con.execute("SELECT id FROM shot WHERE act_id=?", (act_id,))
        }
        for issue in issues:
            shot_id = int(issue["shot_id"])
            if shot_id not in shot_ids:
                raise QAError("QA issue shot is not in the act")
            rule_id = str(issue.get("rule_id") or "").strip()
            if not rule_id:
                raise QAError("QA issue needs rule_id")
            severity = float(issue.get("severity", 0.0))
            if not 0 <= severity <= 1:
                raise QAError("QA severity must be between 0 and 1")
            actor = issue.get("actor_character_id")
            target = issue.get("target_character_id")
            if actor is not None and target is not None and int(actor) == int(target):
                raise QAError("QA actor and target must differ")
            con.execute(
                "INSERT INTO qa_issue"
                "(qa_run_id,shot_id,rule_id,source,actor_character_id,"
                "target_character_id,severity,evidence_json,decision)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    qa_run_id,
                    shot_id,
                    rule_id,
                    str(issue.get("source") or "qa"),
                    int(actor) if actor is not None else None,
                    int(target) if target is not None else None,
                    severity,
                    _json(dict(issue.get("evidence") or {})),
                    str(issue.get("decision") or "open"),
                ),
            )
        con.execute(
            "UPDATE qa_run SET status='completed', finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (qa_run_id,),
        )
        con.commit()
    except Exception:
        con.execute(
            "UPDATE qa_run SET status='failed', finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (qa_run_id,),
        )
        con.commit()
        raise
    return qa_run_id


def qa_history(con: sqlite3.Connection, shot_id: int) -> list[dict[str, Any]]:
    rows = con.execute(
        "SELECT r.id,r.run_key,r.evaluator_version,r.status,"
        " i.id,i.rule_id,i.source,i.severity,i.decision,i.evidence_json"
        " FROM qa_run r JOIN qa_issue i ON i.qa_run_id=r.id"
        " WHERE i.shot_id=? ORDER BY r.id, i.id",
        (shot_id,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append({
            "run_id": int(row[0]),
            "run_key": row[1],
            "evaluator_version": row[2],
            "run_status": row[3],
            "issue_id": int(row[4]),
            "rule_id": row[5],
            "source": row[6],
            "severity": row[7],
            "decision": row[8],
            "evidence": json.loads(row[9] or "{}"),
        })
    return result


def apply_targeted_revision(
    con: sqlite3.Connection,
    *,
    prompt_revision_id: int,
    qa_issue_id: int,
    patch: Mapping[str, Any],
    reason: str,
) -> int:
    """Create a new draft ShotSpec; the old revision stays untouched."""
    if not reason.strip():
        raise QAError("targeted revision needs a reason")
    if not isinstance(patch, Mapping):
        raise QAError("targeted patch must be a JSON object")
    prompt = load_prompt(con, prompt_revision_id)
    spec = con.execute(
        "SELECT id,shot_id,revision,spec_json,source_document_revision_id"
        " FROM shot_spec_revision WHERE id=?",
        (prompt["shot_spec_revision_id"],),
    ).fetchone()
    if spec is None:
        raise CompileError("prompt source spec is missing")
    issue = con.execute(
        "SELECT shot_id FROM qa_issue WHERE id=?", (qa_issue_id,)
    ).fetchone()
    if issue is None or int(issue[0]) != prompt["shot_id"]:
        raise QAError("QA issue does not belong to the prompt shot")
    old_spec = json.loads(spec[3])
    new_spec = dict(old_spec)
    new_spec.update(dict(patch))
    participants = new_spec.get("participants")
    if not participants:
        raise QAError("targeted revision must keep explicit participants")
    for interaction in new_spec.get("interactions") or []:
        actor = interaction.get("actor_character_id")
        target = interaction.get("target_character_id")
        if actor is None or target is None or int(actor) == int(target):
            raise QAError("targeted interaction must keep explicit differing actor/target")
        if int(actor) not in participants or int(target) not in participants:
            raise QAError("targeted interaction actor/target must be participants")
    new_spec["targeted_revision"] = {
        "reason": reason,
        "from_revision": int(spec[2]),
        "qa_issue_id": int(qa_issue_id),
    }
    try:
        new_id = create_shot_spec_revision(
            con,
            prompt["shot_id"],
            new_spec,
            source_document_revision_id=spec[4],
            status="draft",
        )
    except DomainError as exc:
        raise QAError(str(exc)) from exc
    con.execute("UPDATE qa_issue SET decision='fixed' WHERE id=?", (qa_issue_id,))
    con.commit()
    return new_id
