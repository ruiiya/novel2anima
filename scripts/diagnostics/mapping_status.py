#!/usr/bin/env python3
"""Compare the V4 121-row master mapping with the real checkout and SQLite DB.

Read-only. Produces a per-row CSV and a summary JSON. A missing row is not
automatically a failure: PR-00 records the baseline so later PRs can move or
archive each path deliberately.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

TARGET_KEYS = ("category", "legacy_path_or_table", "canonical_target", "operation", "priority")
MANUAL_MARKERS = (
    "embedded in code",
    "render and reference image files",
    "temporary downloads",
    "runtime logs",
)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def db_snapshot(path: Path) -> tuple[dict[str, int], dict]:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {}
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            counts[name] = connection.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
        integrity = [row[0] for row in connection.execute("PRAGMA quick_check").fetchmany(21)]
        fk = [list(row) for row in connection.execute("PRAGMA foreign_key_check").fetchmany(21)]
        check = {
            "quick_check": integrity,
            "quick_check_ok": integrity == ["ok"],
            "foreign_key_violations_first_20": fk,
            "foreign_key_ok": not fk,
            "table_count": len(names),
        }
        return counts, check
    finally:
        connection.close()


def _clean_token(token: str) -> str:
    token = token.strip().strip("`").strip()
    token = re.sub(r"\s+zero-byte placeholders?$", "", token, flags=re.IGNORECASE)
    return token


def _split_external(value: str) -> tuple[list[str], list[str]]:
    """Return (path patterns, manual notes)."""
    patterns: list[str] = []
    manual: list[str] = []
    text = value.strip()
    lowered = text.lower()
    if any(marker in lowered for marker in MANUAL_MARKERS):
        return [], [text]
    base_dir = ""
    for raw in text.split(";"):
        token = _clean_token(raw)
        if not token:
            continue
        if token.lower() in {"keep in git source control"}:
            continue
        if " and " in token:
            left, right = token.split(" and ", 1)
            left = _clean_token(left)
            right = _clean_token(right)
            if left:
                patterns.append(left)
                base_dir = str(Path(left).parent) if "/" in left else base_dir
            if right:
                if "/" not in right and base_dir:
                    patterns.append(f"{base_dir}/{right}")
                else:
                    patterns.append(right)
            continue
        if " " in token and "/" not in token:
            manual.append(token)
            continue
        patterns.append(token)
        if "/" in token and not any(char in token for char in "*?["):
            base_dir = str(Path(token).parent)
    return patterns, manual


def _match_pattern(root: Path, pattern: str, base_dir: str = "") -> list[str]:
    pattern = pattern.strip().strip("`")
    if not pattern:
        return []
    if any(char in pattern for char in "*?["):
        return sorted(path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file())
    candidate = root / pattern
    if candidate.is_file():
        return [pattern]
    if base_dir:
        candidate = root / base_dir / pattern
        if candidate.is_file():
            return [candidate.relative_to(root).as_posix()]
    return []


def evaluate_source(root: Path, legacy_path: str, canonical_target: str) -> dict:
    legacy = root / legacy_path
    target = root / canonical_target
    if legacy.exists():
        status = "matched"
        detail = "legacy path present"
    elif target.exists():
        status = "moved"
        detail = "legacy path absent but canonical target present"
    else:
        status = "missing"
        detail = "neither legacy path nor canonical target present"
    return {
        "status": status,
        "detail": detail,
        "matched_count": 1 if status == "matched" else 0,
        "expected_count": "",
        "db_count": "",
        "db_expected_count": "",
    }


def evaluate_table(db_counts: dict[str, int], legacy_table: str, expected: int | None, canonical_target: str) -> dict:
    targets = [part.strip() for part in canonical_target.split(",") if part.strip()]
    present = [name for name in targets if name in db_counts]
    if legacy_table not in db_counts:
        return {
            "status": "missing",
            "detail": f"legacy table absent; canonical targets present={present}",
            "matched_count": 0,
            "expected_count": expected if expected is not None else "",
            "db_count": "",
            "db_expected_count": "",
        }
    count = db_counts[legacy_table]
    if expected is not None and count != expected:
        status = "count_mismatch"
        detail = f"row count differs from V4 snapshot; canonical targets present={present}"
    else:
        status = "matched"
        detail = f"legacy table present; canonical targets present={present}"
    return {
        "status": status,
        "detail": detail,
        "matched_count": 1,
        "expected_count": expected if expected is not None else "",
        "db_count": count,
        "db_expected_count": expected if expected is not None else "",
    }


def evaluate_external(root: Path, value: str) -> dict:
    patterns, manual = _split_external(value)
    matched: list[str] = []
    missing: list[str] = []
    base_dir = ""
    for pattern in patterns:
        hits = _match_pattern(root, pattern, base_dir)
        if hits:
            matched.extend(hits)
            if "/" in pattern and not any(char in pattern for char in "*?["):
                base_dir = str(Path(pattern).parent)
        else:
            missing.append(pattern)
    matched = sorted(set(matched))
    if manual and not patterns:
        status = "manual"
        detail = "not a concrete path; classify during import design: " + "; ".join(manual)
    elif manual:
        status = "partial" if missing else "matched"
        detail = f"manual notes={manual}; missing={missing}"
    elif patterns and not missing:
        status = "matched"
        detail = f"all patterns matched ({len(matched)} files)"
    elif matched:
        status = "partial"
        detail = f"missing patterns={missing}"
    else:
        status = "missing"
        detail = f"no matches for {missing}"
    return {
        "status": status,
        "detail": detail,
        "matched_count": len(matched),
        "expected_count": "",
        "db_count": "",
        "db_expected_count": "",
    }


def build_mapping_status(root: Path, db_path: Path, mapping_path: Path, legacy_path: Path) -> dict:
    root = root.resolve(strict=True)
    rows = read_csv(mapping_path)
    legacy_rows = read_csv(legacy_path)
    expected_counts = {
        row["old_table"].strip(): int(row["rows_in_2026_10_22_snapshot"])
        for row in legacy_rows
        if row.get("old_table", "").strip() and row.get("rows_in_2026_10_22_snapshot", "").strip().isdigit()
    }
    db_counts, db_check = db_snapshot(db_path)

    results: list[dict] = []
    for row in rows:
        category = row["category"].strip()
        legacy_key = row["legacy_path_or_table"].strip()
        target = row["canonical_target"].strip()
        if category == "SOURCE_FILE":
            result = evaluate_source(root, legacy_key, target)
        elif category == "LEGACY_DB_TABLE":
            result = evaluate_table(db_counts, legacy_key, expected_counts.get(legacy_key), target)
        elif category == "EXTERNAL_RUNTIME":
            result = evaluate_external(root, legacy_key)
        else:
            result = {
                "status": "unknown_category",
                "detail": category,
                "matched_count": 0,
                "expected_count": "",
                "db_count": "",
                "db_expected_count": "",
            }
        results.append(
            {
                "category": category,
                "legacy_path_or_table": legacy_key,
                "canonical_target": target,
                "operation": row["operation"].strip(),
                "priority": row["priority"].strip(),
                **result,
            }
        )

    summary: dict[str, dict] = {}
    for row in results:
        bucket = summary.setdefault(
            row["category"],
            {"rows": 0, "status": {}},
        )
        bucket["rows"] += 1
        bucket["status"][row["status"]] = bucket["status"].get(row["status"], 0) + 1

    missing = [
        {
            "category": row["category"],
            "legacy": row["legacy_path_or_table"],
            "target": row["canonical_target"],
            "status": row["status"],
            "detail": row["detail"],
        }
        for row in results
        if row["status"] not in {"matched", "moved"}
    ]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "database": str(db_path.resolve()),
        "mapping_rows": len(rows),
        "expected_mapping_rows": 121,
        "coverage_ok": len(rows) == 121,
        "by_category": summary,
        "exception_rows": missing,
        "db_check": db_check,
        "db_counts": db_counts,
        "note": "PR-00 baseline only. Exception rows are reviewed and resolved by later PRs.",
        "results": results,
    }


def write_csv(path: Path, results: list[dict]) -> None:
    fields = [
        "category",
        "legacy_path_or_table",
        "canonical_target",
        "operation",
        "priority",
        "status",
        "detail",
        "matched_count",
        "expected_count",
        "db_count",
        "db_expected_count",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--db", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--legacy", required=True)
    parser.add_argument("--output", required=True, help="Per-row CSV")
    parser.add_argument("--summary", required=True, help="Summary JSON")
    args = parser.parse_args(argv)

    result = build_mapping_status(
        Path(args.root),
        Path(args.db),
        Path(args.mapping),
        Path(args.legacy),
    )
    write_csv(Path(args.output).resolve(), result["results"])
    Path(args.summary).resolve().parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for category, bucket in result["by_category"].items():
        print(category, bucket["rows"], bucket["status"])
    print("Exceptions:", len(result["exception_rows"]), "rows=", result["mapping_rows"])
    return 0 if result["coverage_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
