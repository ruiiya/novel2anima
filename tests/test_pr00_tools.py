"""PR-00 tool tests: inventory, backup/restore and mapping status."""
from __future__ import annotations

import csv
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


inventory = load_module("n2a_inventory_runtime", "scripts/diagnostics/inventory_runtime.py")
backup = load_module("n2a_backup_db", "scripts/diagnostics/backup_db.py")
mapping = load_module("n2a_mapping_status", "scripts/diagnostics/mapping_status.py")


class InventoryTests(unittest.TestCase):
    def test_hash_categories_and_skips(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data/plans").mkdir(parents=True)
            (root / "prompts").mkdir()
            (root / "db/backup").mkdir(parents=True)
            (root / "docs/v4").mkdir(parents=True)
            (root / ".git").mkdir()
            (root / "__pycache__").mkdir()
            (root / "data/plans/a.json").write_text('{"a":1}', encoding="utf-8")
            (root / "prompts/a.txt").write_text("prompt", encoding="utf-8")
            (root / "db/test.db").write_bytes(b"not-a-real-db")
            (root / "db/backup/old.db").write_bytes(b"skip")
            (root / "docs/v4/README.md").write_text("v4", encoding="utf-8")
            (root / ".git/config").write_text("skip", encoding="utf-8")
            (root / "__pycache__/x.pyc").write_bytes(b"skip")

            result = inventory.build_inventory(root, sha256=True, include_git=False)
            paths = {item["relative_path"] for item in result["files"]}

            self.assertEqual(
                paths,
                {"data/plans/a.json", "prompts/a.txt", "db/test.db", "docs/v4/README.md"},
            )
            self.assertEqual(result["file_count"], 4)
            self.assertTrue(all(len(item["sha256"]) == 64 for item in result["files"]))
            self.assertEqual(result["summary"]["by_category"]["external_data"]["files"], 1)
            self.assertEqual(result["summary"]["by_category"]["legacy_prompt_export"]["files"], 1)
            self.assertIn("db/backup", {item["relative_path"] for item in result["skipped_directories"]})

            csv_path = root / "evidence" / "inventory.csv"
            inventory.write_csv(csv_path, result)
            with csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["sha256"], result["files"][0]["sha256"])


class BackupTests(unittest.TestCase):
    def test_backup_and_restore_with_wal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.db"
            writer = sqlite3.connect(source)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("CREATE TABLE item(id INTEGER PRIMARY KEY, name TEXT)")
            writer.executemany("INSERT INTO item(name) VALUES (?)", [("a",), ("b",), ("c",)])
            writer.commit()

            report_path = root / "backup-report.json"
            result = backup.backup_database(
                source,
                root / "db/backup",
                report_path,
                label="test",
                restore_check=True,
            )
            writer.close()

            self.assertEqual(result["status"], "ok")
            self.assertTrue(Path(result["backup"]["path"]).is_file())
            self.assertEqual(result["backup"]["table_counts"]["item"], 3)
            self.assertTrue(result["backup"]["integrity_ok"])
            self.assertTrue(result["backup"]["foreign_key_ok"])
            self.assertTrue(result["restore_check"]["ok"])
            self.assertEqual(result["source"]["sha256"], result["source"]["sha256"])
            written = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(written["status"], "ok")

            backup_conn = sqlite3.connect(result["backup"]["path"])
            try:
                self.assertEqual(backup_conn.execute("SELECT count(*) FROM item").fetchone()[0], 3)
            finally:
                backup_conn.close()

    def test_backup_rejects_same_source_and_target_type(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.db"
            sqlite3.connect(source).close()
            result = backup.backup_database(source, root / "backup", root / "report.json", label="x")
            self.assertEqual(result["status"], "ok")


class MappingTests(unittest.TestCase):
    def test_source_table_external_and_exceptions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data/plans").mkdir(parents=True)
            (root / "prompts").mkdir()
            (root / "etl").mkdir()
            (root / "docs/audits/2026-10-22").mkdir(parents=True)
            (root / "data/plans/a.json").write_text("{}", encoding="utf-8")
            (root / "prompts/a.txt").write_text("x", encoding="utf-8")
            (root / "etl/sources.json").write_text("{}", encoding="utf-8")
            (root / "docs/audits/2026-10-22/BUNDLE_README.md").write_text("bundle", encoding="utf-8")

            db_path = root / "test.db"
            connection = sqlite3.connect(db_path)
            connection.execute("CREATE TABLE tag(id INTEGER PRIMARY KEY)")
            connection.executemany("INSERT INTO tag(id) VALUES (?)", [(1,), (2,)])
            connection.execute("CREATE TABLE shot(id INTEGER PRIMARY KEY)")
            connection.executemany("INSERT INTO shot(id) VALUES (?)", [(1,), (2,)])
            connection.commit()
            connection.close()

            mapping_path = root / "mapping.csv"
            with mapping_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["category", "legacy_path_or_table", "canonical_target", "operation", "priority", "source", "read_write_rule", "validation", "notes"])
                writer.writerow(["SOURCE_FILE", "missing.md", "docs/audits/2026-10-22/BUNDLE_README.md", "ARCHIVE", "P4", "V1", "", "", ""])
                writer.writerow(["SOURCE_FILE", "data/plans/a.json", "data/plans/a.json", "KEEP", "P4", "V1", "", "", ""])
                writer.writerow(["LEGACY_DB_TABLE", "tag", "tag", "KEEP", "P4", "V3", "", "", ""])
                writer.writerow(["LEGACY_DB_TABLE", "shot", "shot", "KEEP", "P4", "V3", "", "", ""])
                writer.writerow(["EXTERNAL_RUNTIME", "data/plans/*.json", "project_document_revision", "IMPORT", "P1", "V2", "", "", ""])
                writer.writerow(["EXTERNAL_RUNTIME", "prompts/*.txt and *.neg.txt", "shot_prompt_revision", "IMPORT", "P1", "V2", "", "", ""])
                writer.writerow(["EXTERNAL_RUNTIME", "Render and reference image files", "asset_blob", "IMPORT", "P3", "V2", "", "", ""])

            legacy_path = root / "legacy.csv"
            with legacy_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["old_table", "rows_in_2026_10_22_snapshot", "strategy", "current_issue", "v3_target", "migration_rule", "phase"])
                writer.writerow(["tag", "2", "KEEP", "", "tag", "", "P4"])
                writer.writerow(["shot", "3", "KEEP", "", "shot", "", "P4"])

            result = mapping.build_mapping_status(root, db_path, mapping_path, legacy_path)
            statuses = {row["legacy_path_or_table"]: row["status"] for row in result["results"]}

            self.assertEqual(result["mapping_rows"], 7)
            self.assertFalse(result["coverage_ok"])
            self.assertEqual(statuses["missing.md"], "moved")
            self.assertEqual(statuses["data/plans/a.json"], "matched")
            self.assertEqual(statuses["tag"], "matched")
            self.assertEqual(statuses["shot"], "count_mismatch")
            self.assertEqual(statuses["data/plans/*.json"], "matched")
            self.assertEqual(statuses["prompts/*.txt and *.neg.txt"], "partial")
            self.assertEqual(statuses["Render and reference image files"], "manual")
            self.assertEqual(result["db_check"]["quick_check_ok"], True)
            self.assertEqual(result["db_counts"]["tag"], 2)

            csv_path = root / "mapping-status.csv"
            mapping.write_csv(csv_path, result["results"])
            with csv_path.open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 7)


if __name__ == "__main__":
    unittest.main()
