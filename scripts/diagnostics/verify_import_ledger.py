#!/usr/bin/env python3
"""Read-only verification of the PR-03 import file ledger against a source root."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.storage.import_ledger import verify_ledger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    try:
        report = verify_ledger(Path(args.db), Path(args.source_root))
    except Exception as exc:  # noqa: BLE001 - diagnostic must return a report
        report = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    if args.report:
        output = Path(args.report).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
