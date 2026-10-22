#!/usr/bin/env python3
"""CLI wrapper for the PR-03 external import ledger."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.storage.import_ledger import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
