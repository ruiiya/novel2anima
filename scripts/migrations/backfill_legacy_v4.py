#!/usr/bin/env python3
"""CLI wrapper for the PR-02 deterministic relational backfill."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.storage.repositories.legacy_backfill import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
