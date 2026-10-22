"""Legacy plan / act-spec JSON importer (PR-03).

Plans are preserved as immutable document revisions in
``project_document_revision``.  The importer never creates projects or acts:
the title and act number in the JSON must match an existing DB row.  A missing
or ambiguous match is a staged ``blocked`` error and is not repaired by
guessing.
"""
from __future__ import annotations

import sqlite3

from .base import (
    SourceFile,
    ParseError,
    blocked,
    canonical_json,
    duplicate,
    imported,
    require_int,
    require_list,
    require_object,
    require_text,
    sha256_json,
)


class PlanParser:
    classification = "plan"
    parser_version = "plan/1"

    def parse(self, source: SourceFile, connection: sqlite3.Connection):
        data = source.read_json()
        if not isinstance(data, dict):
            raise ParseError("plan_invalid_shape", "plan root must be a JSON object")

        is_act_spec = source.relative_path.startswith("act_specs/")
        kind = "act_spec" if is_act_spec else "legacy_plan"
        project = require_object(data.get("project"), "project")
        act = require_object(data.get("act"), "act")
        title = require_text(project.get("title"), "project.title")
        act_title = require_text(act.get("title"), "act.title")
        act_no = require_int(act.get("act_no"), "act.act_no")
        if act_no <= 0:
            raise ParseError("plan_invalid_act_no", "act.act_no must be positive")

        projects = connection.execute(
            "SELECT id FROM project WHERE title = ? ORDER BY id", (title,)
        ).fetchall()
        if not projects:
            return blocked(
                "plan_project_not_found",
                details={"title": title, "act_title": act_title, "act_no": act_no},
            )
        if len(projects) > 1:
            return blocked(
                "plan_project_ambiguous",
                details={"title": title, "project_ids": [row["id"] for row in projects]},
            )
        project_id = projects[0]["id"]

        act_revision = act.get("revision")
        if isinstance(act_revision, bool) or not isinstance(act_revision, int):
            act_revision = None
        if act_revision is None:
            acts = connection.execute(
                "SELECT id, revision FROM act "
                "WHERE project_id = ? AND title = ? AND act_no = ? "
                "ORDER BY revision DESC, id DESC",
                (project_id, act_title, act_no),
            ).fetchall()
        else:
            acts = connection.execute(
                "SELECT id, revision FROM act "
                "WHERE project_id = ? AND title = ? AND act_no = ? AND revision = ? "
                "ORDER BY id DESC",
                (project_id, act_title, act_no, act_revision),
            ).fetchall()
        if not acts:
            return blocked(
                "plan_act_not_found",
                details={
                    "project_id": project_id,
                    "title": title,
                    "act_title": act_title,
                    "act_no": act_no,
                    "act_revision": act_revision,
                },
            )
        if len(acts) > 1:
            return blocked(
                "plan_act_ambiguous",
                details={
                    "project_id": project_id,
                    "title": title,
                    "act_title": act_title,
                    "act_no": act_no,
                    "act_ids": [row["id"] for row in acts],
                },
            )
        act_id = acts[0]["id"]

        shots = data.get("shots")
        shot_count = 0
        if shots is not None:
            shots = require_list(shots, "shots")
            shot_count = len(shots)
            numbers: list[int] = []
            for index, shot in enumerate(shots):
                if not isinstance(shot, dict):
                    raise ParseError("plan_invalid_shot", f"shots[{index}] must be an object")
                number = shot.get("n")
                if isinstance(number, bool) or not isinstance(number, int):
                    raise ParseError(
                        "plan_invalid_shot_number",
                        f"shots[{index}].n must be an integer",
                    )
                numbers.append(number)
            expected = list(range(1, shot_count + 1))
            if sorted(numbers) != expected:
                return blocked(
                    "plan_shot_numbers_invalid",
                    details={"project_id": project_id, "act_id": act_id, "numbers": numbers[:20]},
                )
            db_numbers = [
                row["shot_no"]
                for row in connection.execute(
                    "SELECT shot_no FROM shot WHERE act_id = ? ORDER BY shot_no", (act_id,)
                )
            ]
            if db_numbers != expected:
                return blocked(
                    "plan_shot_set_mismatch",
                    details={
                        "project_id": project_id,
                        "act_id": act_id,
                        "plan_shots": shot_count,
                        "database_shots": len(db_numbers),
                    },
                )

        body_json = canonical_json(data)
        body_sha = sha256_json(data)
        scope_key = f"legacy:{source.relative_path}"
        existing = connection.execute(
            "SELECT id, revision, body_sha256 FROM project_document_revision "
            "WHERE project_id = ? AND act_id = ? AND scope_key = ? AND kind = ? "
            "ORDER BY revision",
            (project_id, act_id, scope_key, kind),
        ).fetchall()
        for row in existing:
            if row["body_sha256"] == body_sha:
                return duplicate(
                    target_table="project_document_revision",
                    target_pk=row["id"],
                    details={
                        "project_id": project_id,
                        "act_id": act_id,
                        "kind": kind,
                        "revision": row["revision"],
                        "shot_count": shot_count,
                        "beat_count": len(data.get("beats") or []),
                    },
                )

        revision = max((row["revision"] for row in existing), default=0) + 1
        provenance = {
            "source_path": source.relative_path,
            "source_sha256": source.sha256,
            "source_bytes": source.size_bytes,
            "parser_version": self.parser_version,
            "prompt_file": data.get("prompt_file"),
        }
        cursor = connection.execute(
            "INSERT INTO project_document_revision("
            "project_id, act_id, scope_key, kind, revision, schema_version, "
            "body_json, body_sha256, lifecycle, provenance_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
            (
                project_id,
                act_id,
                scope_key,
                kind,
                revision,
                "legacy-plan/1" if not is_act_spec else "legacy-act-spec/1",
                body_json,
                body_sha,
                canonical_json(provenance),
            ),
        )
        return imported(
            target_table="project_document_revision",
            target_pk=cursor.lastrowid,
            details={
                "project_id": project_id,
                "act_id": act_id,
                "kind": kind,
                "revision": revision,
                "shot_count": shot_count,
                "beat_count": len(data.get("beats") or []),
                "body_sha256": body_sha,
            },
        )
