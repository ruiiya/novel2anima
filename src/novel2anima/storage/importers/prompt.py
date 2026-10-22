"""Legacy prompt TXT importer (PR-03).

Prompt exports are untrusted historical output.  The parser requires:

* a positive TXT split into one block per shot using blank lines;
* a matching ``*.neg.txt`` file;
* an exact shot count for the act;
* a plan document whose ``prompt_file`` field resolves the file to an explicit
  project/act (or a byte-equivalent slice of such a plan prompt).

The importer writes ``shot_prompt_revision`` rows only after every block has
been validated.  If anything is missing, the whole file is blocked and the
per-file savepoint is rolled back.  No prompt is assigned by filename guessing.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from .base import (
    SourceFile,
    ParseError,
    blocked,
    duplicate,
    imported,
    prompt_block_hash,
    sha256_text,
    skipped,
    split_prompt_blocks,
)

HYBRID_ORDER = ["STYLE", "IDENTITY", "OUTFIT", "SCENE & ACTION", "CINEMATOGRAPHY"]
HYBRID_LABELS = set(HYBRID_ORDER)
LABEL_RE = re.compile(r"^(STYLE|IDENTITY|OUTFIT|SCENE & ACTION|CINEMATOGRAPHY):\s*(.*)$")


def _candidate_prompt_paths(relative_path: str) -> set[str]:
    """Plan files may use 'prompts/x.txt' while the workspace stores x under 765/."""
    candidates = {relative_path}
    name = Path(relative_path).name
    if relative_path.startswith("765/prompts/"):
        candidates.add(f"prompts/{name}")
    if relative_path.endswith(".hybrid.txt"):
        base = relative_path[: -len(".hybrid.txt")]
        candidates.add(base + ".txt")
        if relative_path.startswith("765/prompts/"):
            candidates.add(f"prompts/{name[: -len('.hybrid.txt')]}.txt")
    elif relative_path.endswith(".txt"):
        base = relative_path[:-4]
        candidates.add(base + ".hybrid.txt")
        if relative_path.startswith("765/prompts/"):
            candidates.add(f"prompts/{name[:-4]}.hybrid.txt")
    return candidates


def _prompt_plan_map(connection: sqlite3.Connection) -> dict[str, set[tuple[int, int]]]:
    mapping: dict[str, set[tuple[int, int]]] = defaultdict(set)
    rows = connection.execute(
        "SELECT project_id, act_id, body_json FROM project_document_revision "
        "WHERE kind = 'legacy_plan' AND act_id IS NOT NULL"
    ).fetchall()
    for row in rows:
        try:
            body = json.loads(row["body_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        prompt_file = body.get("prompt_file") if isinstance(body, dict) else None
        if isinstance(prompt_file, str) and prompt_file.strip():
            mapping[prompt_file.strip()].add((row["project_id"], row["act_id"]))
    return mapping


def _plan_acts_for(
    source: SourceFile, connection: sqlite3.Connection
) -> tuple[set[tuple[int, int]], list[str]]:
    mapping = _prompt_plan_map(connection)
    acts: set[tuple[int, int]] = set()
    matched: list[str] = []
    for candidate in sorted(_candidate_prompt_paths(source.relative_path)):
        if candidate in mapping:
            matched.append(candidate)
            acts.update(mapping[candidate])
    return acts, matched


def _resolve_existing_prompt_path(root: Path, relative_path: str) -> str | None:
    candidates = [relative_path]
    if relative_path.startswith("prompts/"):
        candidates.append("765/" + relative_path)
    for candidate in candidates:
        if (root / candidate).is_file():
            return candidate
    return None


def _canonical_prompt_candidates(
    root: Path, connection: sqlite3.Connection
) -> list[str]:
    candidates: set[str] = set()
    for mapped in _prompt_plan_map(connection):
        if mapped.endswith(".neg.txt") or mapped.endswith(".negative.txt"):
            continue
        variants = {mapped}
        if mapped.endswith(".txt"):
            variants.add(mapped[:-4] + ".hybrid.txt")
        for variant in variants:
            actual = _resolve_existing_prompt_path(root, variant)
            if actual:
                candidates.add(actual)
    return sorted(candidates)


def _find_duplicate_slice(
    source: SourceFile,
    blocks: list[str],
    connection: sqlite3.Connection,
):
    matches: list[dict] = []
    for candidate in _canonical_prompt_candidates(source.root, connection):
        if candidate == source.relative_path:
            continue
        try:
            text = (source.root / candidate).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        candidate_blocks = split_prompt_blocks(text)
        if not candidate_blocks or len(blocks) > len(candidate_blocks):
            continue
        for offset in range(0, len(candidate_blocks) - len(blocks) + 1):
            if candidate_blocks[offset : offset + len(blocks)] == blocks:
                matches.append(
                    {
                        "path": candidate,
                        "offset": offset,
                        "blocks": len(blocks),
                        "canonical_blocks": len(candidate_blocks),
                    }
                )
                break
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ParseError(
            "prompt_duplicate_slice_ambiguous",
            f"{source.relative_path}: matches {len(matches)} canonical prompt files",
        )
    return None


def _parse_block(block: str) -> tuple[str, str | None]:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        raise ParseError("prompt_empty_block", "prompt block is empty")
    if not lines[0].startswith("STYLE:"):
        # Plain legacy positive prompt: preserve the complete block exactly.
        return block.strip(), None

    fields: dict[str, str] = {}
    order: list[str] = []
    for line in lines:
        match = LABEL_RE.match(line)
        if not match:
            raise ParseError("prompt_hybrid_invalid_line", f"unexpected line: {line[:80]}")
        label, value = match.group(1), match.group(2).strip()
        if label in fields:
            raise ParseError("prompt_hybrid_duplicate_field", f"duplicate field: {label}")
        if not value:
            raise ParseError("prompt_hybrid_empty_field", f"empty field: {label}")
        fields[label] = value
        order.append(label)
    if order != HYBRID_ORDER:
        raise ParseError(
            "prompt_hybrid_order_invalid",
            f"expected {HYBRID_ORDER}, got {order}",
        )
    positive = ", ".join(
        fields[label] for label in ("STYLE", "IDENTITY", "OUTFIT", "CINEMATOGRAPHY")
    )
    return positive, fields["SCENE & ACTION"]


def _negative_path(relative_path: str) -> str:
    if not relative_path.endswith(".txt"):
        raise ParseError("prompt_negative_pair_invalid", relative_path)
    return relative_path[:-4] + ".neg.txt"


class PromptParser:
    classification = "prompt"
    parser_version = "prompt/1"

    def parse(self, source: SourceFile, connection: sqlite3.Connection):
        relative = source.relative_path
        name = Path(relative).name.lower()
        if name.endswith(".neg.txt") or name.endswith(".negative.txt"):
            return skipped(
                "negative_prompt_auxiliary",
                details={"role": "negative_prompt", "paired_by": "positive_prompt_parser"},
            )
        if "test" in Path(relative).stem.lower():
            return skipped(
                "prompt_test_artifact",
                details={"reason": "test/limited prompt exports are not production inputs"},
            )

        blocks = split_prompt_blocks(source.read_text())
        if not blocks:
            return blocked("prompt_empty_file")
        if len(blocks) == 1 and any(label in blocks[0] for label in HYBRID_LABELS):
            # A hybrid file without blank-line separators cannot be safely split.
            if len(blocks[0].splitlines()) > len(HYBRID_ORDER) * 2:
                return blocked(
                    "prompt_block_separator_missing",
                    details={"lines": len(blocks[0].splitlines())},
                )

        acts, matched_plan_paths = _plan_acts_for(source, connection)
        if not acts:
            slice_match = _find_duplicate_slice(source, blocks, connection)
            if slice_match:
                return duplicate(
                    details={
                        "reason": "byte-equivalent slice of an explicitly mapped prompt",
                        **slice_match,
                    }
                )
            return blocked(
                "prompt_plan_mapping_missing",
                details={
                    "blocks": len(blocks),
                    "candidates": sorted(_candidate_prompt_paths(relative)),
                },
            )
        if len(acts) > 1:
            return blocked(
                "prompt_plan_mapping_ambiguous",
                details={
                    "matches": [
                        {"project_id": project_id, "act_id": act_id}
                        for project_id, act_id in sorted(acts)
                    ],
                    "matched_plan_paths": matched_plan_paths,
                },
            )
        project_id, act_id = next(iter(acts))

        shots = connection.execute(
            "SELECT id, shot_no FROM shot WHERE act_id = ? ORDER BY shot_no", (act_id,)
        ).fetchall()
        expected_numbers = list(range(1, len(blocks) + 1))
        if [row["shot_no"] for row in shots] != expected_numbers:
            return blocked(
                "prompt_shot_set_mismatch",
                details={
                    "project_id": project_id,
                    "act_id": act_id,
                    "prompt_blocks": len(blocks),
                    "database_shots": len(shots),
                },
            )

        negative_rel = _negative_path(relative)
        negative_file = source.root / negative_rel
        if not negative_file.is_file():
            return blocked(
                "prompt_negative_missing",
                details={"negative_path": negative_rel, "project_id": project_id, "act_id": act_id},
            )
        try:
            negative_prompt = negative_file.read_text(encoding="utf-8-sig").strip()
        except (OSError, UnicodeDecodeError) as exc:
            return blocked(
                "prompt_negative_unreadable",
                details={"negative_path": negative_rel, "error": str(exc)},
            )
        if not negative_prompt:
            return blocked(
                "prompt_negative_empty",
                details={"negative_path": negative_rel},
            )
        negative_sha = sha256_text(negative_prompt)

        specs: dict[int, sqlite3.Row] = {}
        for shot in shots:
            spec = connection.execute(
                "SELECT id, spec_sha256 FROM shot_spec_revision "
                "WHERE shot_id = ? ORDER BY revision DESC, id DESC LIMIT 1",
                (shot["id"],),
            ).fetchone()
            if spec is None:
                return blocked(
                    "prompt_shot_spec_missing",
                    details={"project_id": project_id, "act_id": act_id, "shot_id": shot["id"]},
                )
            specs[shot["id"]] = spec

        parsed_blocks: list[tuple[str, str | None]] = []
        for index, block in enumerate(blocks):
            try:
                parsed_blocks.append(_parse_block(block))
            except ParseError as exc:
                return blocked(
                    exc.code,
                    details={"block": index + 1, "message": exc.message},
                )

        insert_rows: list[dict] = []
        duplicate_rows: list[dict] = []
        for index, (shot, (positive, natural)) in enumerate(zip(shots, parsed_blocks), start=1):
            content_sha = prompt_block_hash(positive, negative_prompt, natural)
            existing = connection.execute(
                "SELECT id, revision FROM shot_prompt_revision "
                "WHERE shot_id = ? AND content_sha256 = ? ORDER BY revision LIMIT 1",
                (shot["id"], content_sha),
            ).fetchone()
            if existing:
                duplicate_rows.append(
                    {"shot_id": shot["id"], "shot_no": index, "prompt_id": existing["id"]}
                )
                continue
            latest = connection.execute(
                "SELECT COALESCE(MAX(revision), 0) AS revision "
                "FROM shot_prompt_revision WHERE shot_id = ?",
                (shot["id"],),
            ).fetchone()
            insert_rows.append(
                {
                    "shot_id": shot["id"],
                    "shot_no": index,
                    "revision": latest["revision"] + 1,
                    "positive_tags": positive,
                    "negative_prompt": negative_prompt,
                    "natural_prompt": natural,
                    "content_sha256": content_sha,
                    "spec": specs[shot["id"]],
                }
            )

        target_ids: list[int] = []
        for row in insert_rows:
            cursor = connection.execute(
                "INSERT INTO shot_prompt_revision("
                "shot_id, revision, positive_tags, negative_prompt, natural_prompt, "
                "source_shot_spec_sha256, compiler_version, status, content_sha256"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)",
                (
                    row["shot_id"],
                    row["revision"],
                    row["positive_tags"],
                    row["negative_prompt"],
                    row["natural_prompt"],
                    row["spec"]["spec_sha256"],
                    "legacy-prompt-import/1",
                    row["content_sha256"],
                ),
            )
            prompt_id = cursor.lastrowid
            target_ids.append(prompt_id)
            connection.execute(
                "INSERT INTO shot_prompt_spec(shot_prompt_revision_id, shot_spec_revision_id) "
                "VALUES (?, ?)",
                (prompt_id, row["spec"]["id"]),
            )

        all_target_ids = target_ids or [row["prompt_id"] for row in duplicate_rows]
        details = {
            "project_id": project_id,
            "act_id": act_id,
            "matched_plan_paths": matched_plan_paths,
            "prompt_blocks": len(blocks),
            "inserted": len(target_ids),
            "duplicates": len(duplicate_rows),
            "negative_path": negative_rel,
            "negative_sha256": negative_sha,
            "first_target_id": all_target_ids[0] if all_target_ids else None,
            "last_target_id": all_target_ids[-1] if all_target_ids else None,
        }
        if target_ids:
            return imported(
                target_table="shot_prompt_revision",
                target_pk=target_ids[0],
                details=details,
            )
        return duplicate(
            target_table="shot_prompt_revision",
            target_pk=duplicate_rows[0]["prompt_id"] if duplicate_rows else None,
            details=details,
        )
