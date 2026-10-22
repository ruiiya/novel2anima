"""PR-01 migration runner tests."""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.storage.migrations import (  # noqa: E402
    MigrationError,
    apply_migrations,
    discover_migrations,
    split_statements,
)

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


def create_base_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()


def write_migrations(directory: Path, files: dict[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")


class MigrationRunnerTests(unittest.TestCase):
    def test_apply_005_006_on_base_schema_and_rerun(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "staging.db"
            create_base_db(db)
            migrations = root / "migrations"
            migrations.mkdir()
            shutil.copy2(ROOT / "sql/migrations/005_db_first.sql", migrations / "005_db_first.sql")
            shutil.copy2(ROOT / "sql/migrations/006_normalization.sql", migrations / "006_normalization.sql")

            first = apply_migrations(db, migrations, backup_path=root / "pre.db")
            self.assertEqual(first["status"], "ok")
            self.assertEqual(len(first["applied"]), 2)
            self.assertEqual(len(first["pending"]), 0)
            self.assertEqual(len(first["pending_before"]), 2)
            self.assertTrue(Path(first["backup"]).is_file())
            self.assertTrue(first["checks"]["integrity_ok"])
            self.assertTrue(first["checks"]["foreign_key_ok"])

            connection = sqlite3.connect(db)
            try:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                self.assertTrue(
                    {
                        "n2a_schema_migration",
                        "asset_blob",
                        "outfit_revision",
                        "shot_participant",
                        "shot_interaction",
                        "shot_prompt_revision",
                        "qa_run",
                        "qa_issue",
                    }.issubset(tables)
                )
                versions = [
                    row[0]
                    for row in connection.execute("SELECT version FROM n2a_schema_migration ORDER BY version")
                ]
                self.assertEqual(versions, ["005_db_first", "006_normalization"])
            finally:
                connection.close()

            second = apply_migrations(db, migrations)
            self.assertEqual(second["status"], "ok")
            self.assertEqual(len(second["applied"]), 0)
            self.assertEqual(len(second["skipped"]), 2)
            self.assertEqual(len(second["pending"]), 0)

    def test_checksum_drift_aborts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "staging.db"
            create_base_db(db)
            migrations = root / "migrations"
            migrations.mkdir()
            shutil.copy2(ROOT / "sql/migrations/005_db_first.sql", migrations / "005_db_first.sql")
            apply_migrations(db, migrations, backup_path=root / "pre.db")

            with (migrations / "005_db_first.sql").open("a", encoding="utf-8") as handle:
                handle.write("\n-- changed after apply\n")
            with self.assertRaises(MigrationError) as caught:
                apply_migrations(db, migrations)
            self.assertIn("checksum drift", str(caught.exception))

    def test_failed_migration_rolls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "staging.db"
            sqlite3.connect(db).close()
            migrations = root / "migrations"
            write_migrations(
                migrations,
                {
                    "001_create.sql": "CREATE TABLE alpha(id INTEGER PRIMARY KEY);\n",
                    "002_broken.sql": (
                        "CREATE TABLE beta(id INTEGER PRIMARY KEY);\n"
                        "INSERT INTO missing_table(id) VALUES (1);\n"
                    ),
                },
            )
            with self.assertRaises(MigrationError):
                apply_migrations(db, migrations, backup_path=root / "pre.db")

            connection = sqlite3.connect(db)
            try:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                versions = [
                    row[0]
                    for row in connection.execute("SELECT version FROM n2a_schema_migration ORDER BY version")
                ]
            finally:
                connection.close()
            self.assertIn("alpha", tables)
            self.assertNotIn("beta", tables)
            self.assertEqual(versions, ["001_create"])

    def test_foreign_keys_are_enforced_and_roll_back(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "staging.db"
            sqlite3.connect(db).close()
            migrations = root / "migrations"
            write_migrations(
                migrations,
                {
                    "001_fk.sql": (
                        "CREATE TABLE parent(id INTEGER PRIMARY KEY);\n"
                        "CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL "
                        "REFERENCES parent(id));\n"
                        "INSERT INTO child(id, parent_id) VALUES (1, 999);\n"
                    )
                },
            )
            with self.assertRaises(MigrationError):
                apply_migrations(db, migrations, backup_path=root / "pre.db")

            connection = sqlite3.connect(db)
            try:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                versions = list(connection.execute("SELECT version FROM n2a_schema_migration"))
            finally:
                connection.close()
            self.assertNotIn("parent", tables)
            self.assertNotIn("child", tables)
            self.assertEqual(versions, [])

    def test_live_database_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            live = root / "db/novel_anima.db"
            live.parent.mkdir(parents=True)
            sqlite3.connect(live).close()
            migrations = root / "migrations"
            write_migrations(migrations, {"001_test.sql": "CREATE TABLE t(id INTEGER);\n"})
            with self.assertRaises(MigrationError) as caught:
                apply_migrations(live, migrations)
            self.assertIn("refusing", str(caught.exception))

    def test_split_statements_keeps_trigger_body(self):
        sql = (
            "CREATE TABLE t(id INTEGER);\n"
            "CREATE TRIGGER trg AFTER INSERT ON t BEGIN\n"
            "  UPDATE t SET id=id WHERE id=NEW.id;\n"
            "END;\n"
        )
        statements = split_statements(sql)
        self.assertEqual(len(statements), 2)
        self.assertIn("CREATE TRIGGER", statements[1])
        self.assertTrue(statements[1].rstrip().endswith("END;"))

    def test_reconciliation_queue_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "staging.db"
            create_base_db(db)
            migrations = root / "migrations"
            migrations.mkdir()
            for name in ("005_db_first.sql", "006_normalization.sql", "007_reconciliation_queue.sql"):
                shutil.copy2(ROOT / "sql/migrations" / name, migrations / name)

            report = apply_migrations(db, migrations, backup_path=root / "pre.db")
            self.assertEqual(report["status"], "ok")
            self.assertEqual(len(report["applied"]), 3)

            connection = sqlite3.connect(db)
            try:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(reconciliation_item)")
                }
                self.assertTrue(
                    {
                        "gap_key",
                        "domain",
                        "severity",
                        "project_id",
                        "shot_id",
                        "character_id",
                        "rule_code",
                        "evidence_json",
                        "status",
                    }.issubset(columns)
                )
                connection.execute(
                    "INSERT INTO reconciliation_item(gap_key,domain,rule_code) "
                    "VALUES ('test:gap','other','test_rule')"
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO reconciliation_item(gap_key,domain,rule_code) "
                        "VALUES ('test:gap','other','test_rule')"
                    )
            finally:
                connection.close()

    def test_real_migrations_discover_and_parse(self):
        discovered = discover_migrations(ROOT / "sql/migrations")
        versions = [item.version for item in discovered]
        self.assertEqual(
            versions,
            [
                "002_shot_state",
                "003_shot_finding",
                "004_observation_publication",
                "005_db_first",
                "006_normalization",
                "007_reconciliation_queue",
                "008_import_ledger",
            ],
        )
        for item in discovered:
            self.assertGreater(len(split_statements(item.sql)), 0)


if __name__ == "__main__":
    unittest.main()
