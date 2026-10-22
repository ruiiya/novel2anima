"""Legacy LLM review JSON importer (PR-03).

Each review file is preserved verbatim in ``qa_run_source`` and projected into
an immutable ``qa_run`` with one ``qa_issue`` per shot/axis.  Repeated findings
for the same shot/axis are retained together in ``evidence_json``.  The
review's ``act_id`` (or an explicit ``_idNN`` in the filename) is required;
finding shot numbers must resolve inside that act.  A review is never attached
to a project by guessing from the first act with the same act number.
"""
from __future__ import annotations

import re
import sqlite3

from .base import (
    SourceFile,
    ParseError,
    blocked,
    canonical_json,
    duplicate,
    imported,
    require_list,
    require_object,
    require_text,
    utc_now,
)

ID_RE = re.compile(r"_id(\d+)(?:_|$)", re.IGNORECASE)


class ReviewParser:
    classification = "review"
    parser_version = "review/1"

    def parse(self, source: SourceFile, connection: sqlite3.Connection):
        data = source.read_json()
        if not isinstance(data, dict):
            raise ParseError("review_invalid_shape", "review root must be a JSON object")

        raw_act_id = data.get("act_id")
        if isinstance(raw_act_id, bool) or not isinstance(raw_act_id, int):
            match = ID_RE.search(source.relative_path)
            raw_act_id = int(match.group(1)) if match else None
        if raw_act_id is None:
            return blocked(
                "review_act_id_missing",
                details={"path": source.relative_path},
            )

        act = connection.execute(
            "SELECT id, project_id FROM act WHERE id = ?", (raw_act_id,)
        ).fetchone()
        if act is None:
            return blocked(
                "review_act_not_found",
                details={"act_id": raw_act_id},
            )
        raw_project = data.get("project")
        if isinstance(raw_project, int) and not isinstance(raw_project, bool):
            if raw_project != act["project_id"]:
                return blocked(
                    "review_project_mismatch",
                    details={
                        "act_id": raw_act_id,
                        "act_project_id": act["project_id"],
                        "review_project": raw_project,
                    },
                )

        findings = require_list(data.get("findings", []), "findings")
        validated: list[tuple[dict, int]] = []
        for index, finding in enumerate(findings):
            item = require_object(finding, f"findings[{index}]")
            shot_no = item.get("shot")
            if isinstance(shot_no, bool) or not isinstance(shot_no, int) or shot_no <= 0:
                return blocked(
                    "review_shot_invalid",
                    details={"finding_index": index, "shot": shot_no},
                )
            require_text(item.get("axis"), f"findings[{index}].axis")
            severity = item.get("severity")
            if isinstance(severity, bool) or not isinstance(severity, (int, float)):
                return blocked(
                    "review_severity_invalid",
                    details={"finding_index": index, "shot": shot_no, "severity": severity},
                )
            severity = float(severity)
            if not 0 <= severity <= 1:
                return blocked(
                    "review_severity_invalid",
                    details={"finding_index": index, "shot": shot_no, "severity": severity},
                )
            why = item.get("why", "")
            if not isinstance(why, str):
                return blocked(
                    "review_why_invalid",
                    details={"finding_index": index, "shot": shot_no},
                )
            shot = connection.execute(
                "SELECT id FROM shot WHERE act_id = ? AND shot_no = ?",
                (act["id"], shot_no),
            ).fetchone()
            if shot is None:
                return blocked(
                    "review_shot_not_found",
                    details={
                        "act_id": act["id"],
                        "finding_index": index,
                        "shot": shot_no,
                    },
                )
            # Keep the original finding object untouched in evidence_json.
            validated.append((item, shot["id"]))

        run_key = f"legacy-review:{source.sha256}"
        existing = connection.execute(
            "SELECT id FROM qa_run WHERE run_key = ?", (run_key,)
        ).fetchone()
        if existing:
            return duplicate(
                target_table="qa_run",
                target_pk=existing["id"],
                details={
                    "act_id": act["id"],
                    "findings": len(findings),
                    "issues": 0,
                    "run_key": run_key,
                },
            )

        now = utc_now()
        cursor = connection.execute(
            "INSERT INTO qa_run("
            "act_id, run_key, evaluator_version, status, started_at, finished_at"
            ") VALUES (?, ?, 'legacy-review/1', 'completed', ?, ?)",
            (act["id"], run_key, now, now),
        )
        qa_run_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO qa_run_source("
            "qa_run_id, source_relative_path, source_sha256, parser_version, raw_json"
            ") VALUES (?, ?, ?, ?, ?)",
            (
                qa_run_id,
                source.relative_path,
                source.sha256,
                self.parser_version,
                canonical_json(data),
            ),
        )

        # qa_issue is unique per (run, shot, rule, source).  Legacy reviews may
        # repeat an axis for one shot; keep every raw finding in evidence_json
        # and project one normalized issue per shot/axis with the maximum
        # severity.  The untouched review remains in qa_run_source.
        grouped: dict[tuple[int, str], dict] = {}
        for index, (finding, shot_id) in enumerate(validated):
            axis = str(finding["axis"]).strip()
            key = (shot_id, axis)
            bucket = grouped.setdefault(
                key,
                {"shot_id": shot_id, "axis": axis, "severity": 0.0, "findings": []},
            )
            bucket["severity"] = max(bucket["severity"], float(finding["severity"]))
            bucket["findings"].append({"finding_index": index, "finding": finding})

        for (shot_id, axis), bucket in grouped.items():
            evidence = {
                "source_path": source.relative_path,
                "source_sha256": source.sha256,
                "finding_count": len(bucket["findings"]),
                "findings": bucket["findings"],
            }
            connection.execute(
                "INSERT INTO qa_issue("
                "qa_run_id, shot_id, rule_id, source, severity, evidence_json, decision"
                ") VALUES (?, ?, ?, 'legacy-llm-review', ?, ?, 'open')",
                (
                    qa_run_id,
                    shot_id,
                    f"legacy:{axis}"[:200],
                    bucket["severity"],
                    canonical_json(evidence),
                ),
            )

        return imported(
            target_table="qa_run",
            target_pk=qa_run_id,
            details={
                "act_id": act["id"],
                "findings": len(findings),
                "issues": len(grouped),
                "run_key": run_key,
            },
        )
