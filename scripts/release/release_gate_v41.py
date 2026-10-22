#!/usr/bin/env python3
"""V4.1 PR-10/PR-11 repository + staging gate.

This gate proves the implemented registry/orchestrator, migration ledger, skill
contracts and the O10/S11 tests on a real SQLite copy.  It does not claim a real
Anima provider run, production cutover or human signoff.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.pipeline import registry  # noqa: E402
from novel2anima.storage.migrations import (  # noqa: E402
    applied_migrations,
    discover_migrations,
)

EXPECTED_TABLES = {
    "pipeline_run", "pipeline_run_execution", "pipeline_step_run",
    "catalog_job", "runtime_setting",
}
EXPECTED_TRIGGERS = {"trg_step_retry_same_run", "trg_step_terminal_immutable"}
SKILLS = (
    "novel2anima-catalog",
    "novel2anima-shot-pipeline",
    "novel2anima-natural-language-prompt",
)
FORBIDDEN_STORY_IMPORTS = {"subprocess", "catalog"}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _migration_check(con) -> dict:
    applied = applied_migrations(con)
    files = discover_migrations(ROOT / "sql/migrations")
    missing = [item.version for item in files if item.version not in applied]
    drift = [
        item.version for item in files
        if item.version in applied and applied[item.version] != item.sha256
    ]
    return {
        "ok": not missing and not drift and "013_execution_control" in applied,
        "applied": len(applied),
        "missing": missing,
        "drift": drift,
        "execution_control_sha256": applied.get("013_execution_control"),
    }


def _schema_check(con) -> dict:
    tables = {
        row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    triggers = {
        row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )
    }
    runtime = dict(con.execute("SELECT key,value FROM runtime_setting"))
    return {
        "ok": EXPECTED_TABLES <= tables and EXPECTED_TRIGGERS <= triggers,
        "missing_tables": sorted(EXPECTED_TABLES - tables),
        "missing_triggers": sorted(EXPECTED_TRIGGERS - triggers),
        "runtime_setting": runtime,
        "strict_default_off": runtime.get("strict_execution_control") == "off",
    }


def _code_check() -> dict:
    offenders: list[str] = []
    for path in (
        ROOT / "src/novel2anima/pipeline/orchestrator.py",
        ROOT / "src/novel2anima/pipeline/step_runner.py",
        ROOT / "src/novel2anima/pipeline/registry.py",
        ROOT / "src/novel2anima/pipeline/policies.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in FORBIDDEN_STORY_IMPORTS:
                    offenders.append(f"{path.name}:{name}")
    prompts = sorted((ROOT / "llm/prompts").rglob("*.txt"))
    prompt_bytes = sum(path.stat().st_size for path in prompts)
    skills_ok = all((ROOT / "skills" / name / "SKILL.md").is_file() for name in SKILLS)
    return {
        "ok": not offenders and len(prompts) == 33 and prompt_bytes == 0 and skills_ok,
        "forbidden_story_imports": offenders,
        "prompt_scaffolds": len(prompts),
        "prompt_scaffold_bytes": prompt_bytes,
        "skills_present": skills_ok,
    }


def _test_check() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest",
         "tests.test_pr10_orchestrator", "tests.test_pr11_skills"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    output = (proc.stdout + proc.stderr).strip().splitlines()
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "summary": output[-1] if output else "",
    }


def run_gate(db_path: pathlib.Path) -> dict:
    import sqlite3

    db_path = db_path.resolve()
    con = sqlite3.connect(db_path)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = con.execute("PRAGMA foreign_key_check").fetchall()
        report = {
            "schema_version": "v4.1-pr10-pr11-gate-1",
            "database": str(db_path),
            "workflow": {
                "code": registry.WORKFLOW_CODE,
                "version": registry.WORKFLOW_VERSION,
                "sha256": registry.workflow_sha256(),
                "steps": len(registry.STEPS),
            },
            "checks": {
                "migrations": _migration_check(con),
                "schema": _schema_check(con),
                "code": _code_check(),
                "integrity": {
                    "ok": integrity == "ok" and not foreign_keys,
                    "integrity_check": integrity,
                    "foreign_key_errors": len(foreign_keys),
                },
            },
        }
    finally:
        con.close()
    report["checks"]["tests"] = _test_check()
    blockers = [
        name for name, value in report["checks"].items()
        if not value.get("ok")
    ]
    report["status"] = "PASS" if not blockers else "FAIL"
    report["blockers"] = blockers
    report["not_run"] = [
        "external_LLM_provider",
        "real_Anima_render",
        "production_cutover_and_rollback_drill",
    ]
    report["production_signoff"] = False
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    body = _json({key: value for key, value in report.items() if key != "signature"})
    report["signature"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=pathlib.Path)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args(argv)
    report = run_gate(args.db)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "blockers": report["blockers"],
        "workflow_sha256": report["workflow"]["sha256"],
        "signature": report["signature"],
        "not_run": report["not_run"],
    }, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
