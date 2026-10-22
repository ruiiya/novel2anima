#!/usr/bin/env python3
"""Run one explicitly approved catalog maintenance job (outside story runs)."""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.catalog.admin import run_catalog_job  # noqa: E402
from novel2anima.pipeline import registry  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, type=pathlib.Path)
    parser.add_argument("--job", required=True, choices=registry.CATALOG_JOB_CODES)
    parser.add_argument("--job-key", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args(argv)
    payload = json.loads(args.payload)
    if not isinstance(payload, dict):
        parser.error("--payload must be a JSON object")
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    try:
        result = run_catalog_job(
            con,
            job_code=args.job,
            job_key=args.job_key,
            actor=args.actor,
            approved_by=args.approved_by,
            payload=payload,
        )
    finally:
        con.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
