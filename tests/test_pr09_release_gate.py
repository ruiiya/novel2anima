"""PR-09 release gate: E2E, backup/restore, rollback and signed ledger."""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/release"))
sys.path.insert(0, str(ROOT / "scripts/migrations"))

from release_gate import run_gate  # noqa: E402
from p8_drop_legacy_authority import rebuild as rebuild_authority  # noqa: E402
from novel2anima.storage.migrations import apply_migrations  # noqa: E402

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


def create_db(root: Path) -> Path:
    db = root / "staging.db"
    con = sqlite3.connect(db)
    con.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
    con.commit()
    con.close()
    migrations = root / "migrations"
    migrations.mkdir()
    for path in sorted((ROOT / "sql/migrations").glob("*.sql")):
        shutil.copy2(path, migrations / path.name)
    assert apply_migrations(db, migrations, backup_path=root / "pre.db")["status"] == "ok"
    return db


class ReleaseGate(unittest.TestCase):
    def test_gate_runs_e2e_restore_rollback_and_blocks_on_p8(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = create_db(Path(temp.name))
        report = run_gate(db)
        self.assertEqual(report["status"], "NOT_READY")
        self.assertIn("P8_LEGACY_DISPOSITION", report["blockers"])
        self.assertTrue(report["checks"]["migrations"]["ok"])
        self.assertTrue(report["checks"]["e2e"]["ok"])
        self.assertTrue(report["checks"]["e2e"]["qa_history"] >= 1)
        self.assertEqual(
            report["checks"]["e2e"]["body_sha"], report["checks"]["e2e"]["render_sha"]
        )
        self.assertTrue(report["checks"]["backup_restore"]["ok"])
        self.assertTrue(report["checks"]["rollback"]["ok"])
        self.assertTrue(report["checks"]["benchmark"]["ok"])
        ledger = report["signed_ledger"]
        self.assertEqual(len(ledger["signature"]), 64)
        self.assertEqual(ledger["status"], "NOT_READY")
        self.assertEqual(ledger["signature_type"], "sha256-content")

    def test_gate_is_ready_after_legacy_authority_removal(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = create_db(Path(temp.name))
        from p8_drop_generation_image_path import rebuild as rebuild_generation
        self.assertEqual(rebuild_generation(db)["status"], "ok")
        self.assertEqual(rebuild_authority(db)["status"], "ok")
        report = run_gate(db)
        self.assertEqual(report["status"], "READY", report["blockers"])
        self.assertFalse(report["blockers"])
        self.assertTrue(report["checks"]["disposition"]["ok"])
        self.assertEqual(report["signed_ledger"]["status"], "READY")

    def test_gate_refuses_live_without_approval(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = create_db(Path(temp.name))
        live = Path(temp.name) / "db" / "novel_anima.db"
        live.parent.mkdir()
        shutil.copy2(db, live)
        with self.assertRaises(RuntimeError):
            run_gate(live)


if __name__ == "__main__":
    unittest.main()
