"""Tests for the staging verification diagnostic."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


verify = load_module("n2a_verify_staging", "scripts/diagnostics/verify_staging.py")


class VerifyStagingTests(unittest.TestCase):
    def test_baseline_unchanged_new_tables_and_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "staging.db"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
            connection.executemany("INSERT INTO t(id) VALUES (?)", [(1,), (2,)])
            connection.commit()
            connection.close()

            baseline = root / "baseline.json"
            baseline.write_text(json.dumps({"table_counts": {"t": 2}}), encoding="utf-8")

            clean = verify.build_report(db, baseline)
            self.assertEqual(clean["status"], "ok")
            self.assertEqual(clean["new_tables"], [])
            self.assertTrue(clean["legacy_counts_unchanged"])

            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE added(id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO added(id) VALUES (1)")
            connection.commit()
            connection.close()
            with_new = verify.build_report(db, baseline)
            self.assertEqual(with_new["status"], "ok")
            self.assertEqual(with_new["new_tables"], [{"name": "added", "rows": 1}])

            connection = sqlite3.connect(db)
            connection.execute("INSERT INTO t(id) VALUES (3)")
            connection.commit()
            connection.close()
            drifted = verify.build_report(db, baseline)
            self.assertEqual(drifted["status"], "failed")
            self.assertEqual(drifted["baseline_tables_changed"]["t"], {"before": 2, "after": 3})

            allowed = verify.build_report(db, baseline, ["t"])
            self.assertEqual(allowed["status"], "ok")
            self.assertEqual(
                allowed["baseline_tables_allowed_changed"],
                {"t": {"before": 2, "after": 3}},
            )
            self.assertEqual(allowed["baseline_tables_unexpected_changed"], {})


if __name__ == "__main__":
    unittest.main()
