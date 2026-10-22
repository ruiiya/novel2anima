"""PR-03 external import ledger and parser tests."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.storage.import_ledger import (  # noqa: E402
    ImportLedgerError,
    run_import,
    verify_ledger,
)
from novel2anima.storage.migrations import apply_migrations  # noqa: E402

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"
MIGRATIONS = ("005_db_first.sql", "006_normalization.sql", "007_reconciliation_queue.sql", "008_import_ledger.sql")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def create_v4_db(root: Path) -> Path:
    db = root / "staging.db"
    connection = sqlite3.connect(db)
    try:
        connection.executescript(BASE_SCHEMA.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()
    migrations = root / "migrations"
    migrations.mkdir()
    for name in MIGRATIONS:
        shutil.copy2(ROOT / "sql/migrations" / name, migrations / name)
    report = apply_migrations(db, migrations, backup_path=root / "pre_test.db")
    assert report["status"] == "ok", report
    return db


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


class ImportLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = create_v4_db(self.root)
        self.source = self.root / "source"
        self.source.mkdir()
        self._seed_db()
        self._write_sources()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _seed_db(self) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            connection.execute(
                "INSERT INTO project(id,title,idea,content_profile,style_json) "
                "VALUES (1,'Fixture Project','test','mixed','{}')"
            )
            connection.execute(
                "INSERT INTO act(id,project_id,act_no,title,outline,revision,status) "
                "VALUES (1,1,1,'Act One','',1,'planned')"
            )
            alpha_identity = {"identity_tags": ["alpha"]}
            alpha_outfit = {"default": ["dress:101"]}
            beta_identity = {"identity_tags": ["beta"]}
            beta_outfit = {"default": []}
            connection.executemany(
                "INSERT INTO character_profile(id,project_id,code) VALUES (?,?,?)",
                [(1, 1, "ALPHA_CHAR"), (2, 1, "BETA_CHAR")],
            )
            for cid, identity, outfit in (
                (1, alpha_identity, alpha_outfit),
                (2, beta_identity, beta_outfit),
            ):
                body = canonical(identity)
                connection.execute(
                    "INSERT INTO character_identity_revision"
                    "(character_id,revision,identity_json,sha256,status)"
                    " VALUES(?,1,?,?,'approved')",
                    (cid, body, sha(body)),
                )
                body = canonical(outfit)
                connection.execute(
                    "INSERT INTO outfit_revision"
                    "(character_id,revision,spec_json,spec_sha256,status)"
                    " VALUES(?,1,?,?,'approved')",
                    (cid, body, sha(body)),
                )
            for shot_no in (1, 2, 3):
                spec_json = canonical({"shot": shot_no, "action": ["test"]})
                spec_sha = sha(spec_json)
                cursor = connection.execute(
                    "INSERT INTO shot(act_id,shot_no,character_id,shot_spec_json,status) "
                    "VALUES (1,?,1,?,'planned')",
                    (shot_no, spec_json),
                )
                connection.execute(
                    "INSERT INTO shot_spec_revision(shot_id,revision,spec_json,spec_sha256,status) "
                    "VALUES (?,1,?,?,'draft')",
                    (cursor.lastrowid, spec_json, spec_sha),
                )
            connection.commit()
        finally:
            connection.close()

    def _write_sources(self) -> None:
        plan = {
            "project": {"title": "Fixture Project"},
            "act": {"title": "Act One", "act_no": 1, "revision": 1},
            "characters": [{"code": "ALPHA_CHAR"}],
            "shots": [{"n": 1}, {"n": 2}, {"n": 3}],
            "prompt_file": "prompts/fixture.txt",
        }
        write(self.source / "data/plans/plan-fixture.json", canonical(plan))
        write(
            self.source / "data/plans/blocked.json",
            canonical(
                {
                    "project": {"title": "Missing Project"},
                    "act": {"title": "Missing Act", "act_no": 1},
                    "shots": [],
                }
            ),
        )
        write(
            self.source / "prompts/fixture.txt",
            "tag_alpha, red_dress\n\ntag_beta, blue_dress\n\ntag_gamma, green_dress\n",
        )
        write(self.source / "prompts/fixture.neg.txt", "bad quality\n")
        write(
            self.source / "data/reviews/review_1.json",
            canonical(
                {
                    "act": 1,
                    "act_id": 1,
                    "project": 1,
                    "findings": [
                        {
                            "shot": 2,
                            "axis": "mau_thuan",
                            "severity": 0.5,
                            "why": "fixture finding",
                        },
                        {
                            "shot": 2,
                            "axis": "mau_thuan",
                            "severity": 0.8,
                            "why": "second fixture finding for the same axis",
                        },
                    ],
                }
            ),
        )
        write(
            self.source / "data/wardrobe/colour_choice.json",
            canonical({"dress": "black", "shirt": "white"}),
        )
        write(
            self.source / "data/characters/roster.json",
            canonical(
                [
                    {
                        "code": "ALPHA_CHAR",
                        "identity_json": {"identity_tags": ["alpha"]},
                        "outfit_json": {"default": ["dress:101"]},
                    },
                    {
                        "code": "BETA_CHAR",
                        "identity_json": {"identity_tags": ["beta"]},
                        "outfit_json": {"default": ["coat:202"]},
                    },
                ]
            ),
        )
        catalog_bytes = b"tag\n"
        catalog_sha = sha(catalog_bytes)
        write(self.source / "data/sources/test_family/data.csv", catalog_bytes)
        write(
            self.source / "data/sources/manifest.json",
            canonical(
                {
                    "test_family": {
                        "revision": "rev1",
                        "files": {
                            "data.csv": {
                                "bytes": len(catalog_bytes),
                                "sha256": catalog_sha,
                                "url": "https://example.invalid/test_family/data.csv",
                            }
                        },
                    }
                }
            ),
        )
        write(self.source / "data/sources/report.txt", "generated report\n")
        write(self.source / "assets/ref.png", b"\x89PNG\r\n\x1a\nfixture")
        write(self.source / "llm/prompts/01_brief/system.txt", b"")
        write(self.source / "src/example.py", "print('source')\n")
        write(self.source / "765/notes.md", "# workspace notes\n")
        write(self.source / "db/import_report.json", "{}\n")
        write(self.source / "db/novel_anima.db", b"canonical database placeholder")

    def _count(self, table: str) -> int:
        connection = sqlite3.connect(self.db)
        try:
            return connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        finally:
            connection.close()

    def test_import_is_classified_idempotent_and_verifiable(self) -> None:
        report = run_import(self.db, self.source, batch_key="fixture-1")
        self.assertEqual(report["status"], "ok", report)
        self.assertTrue(report["checks"]["quick_check_ok"])
        self.assertTrue(report["checks"]["foreign_key_ok"])
        self.assertEqual(report["counts"]["by_status"]["imported"], 5)
        self.assertEqual(report["counts"]["by_status"]["blocked"], 2)
        self.assertGreaterEqual(report["counts"]["by_status"]["skipped_by_policy"], 7)
        self.assertEqual(report["counts"]["by_status"]["duplicate"], 1)
        self.assertEqual(
            [item["relative_path"] for item in report["policy_skipped_files"]],
            ["db/novel_anima.db"],
        )

        self.assertEqual(self._count("project_document_revision"), 1)
        self.assertEqual(self._count("shot_prompt_revision"), 3)
        self.assertEqual(self._count("shot_prompt_spec"), 3)
        self.assertEqual(self._count("qa_run"), 1)
        self.assertEqual(self._count("qa_issue"), 1)
        self.assertEqual(self._count("qa_run_source"), 1)
        self.assertEqual(self._count("n2a_setting_revision"), 1)
        self.assertEqual(self._count("source_snapshot"), 1)
        self.assertEqual(self._count("reconciliation_item"), 1)
        self.assertEqual(self._count("asset_blob"), 0)
        self.assertEqual(self._count("import_batch"), 1)
        ledger_rows = self._count("import_file_ledger")
        self.assertGreaterEqual(ledger_rows, 14)

        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            rows = {
                row["source_relative_path"]: row
                for row in connection.execute("SELECT * FROM import_file_ledger")
            }
            self.assertEqual(rows["data/plans/plan-fixture.json"]["status"], "imported")
            self.assertEqual(rows["data/plans/blocked.json"]["status"], "blocked")
            self.assertEqual(rows["prompts/fixture.txt"]["status"], "imported")
            self.assertEqual(rows["prompts/fixture.neg.txt"]["status"], "skipped_by_policy")
            self.assertEqual(rows["data/reviews/review_1.json"]["status"], "imported")
            self.assertEqual(rows["data/wardrobe/colour_choice.json"]["status"], "imported")
            self.assertEqual(rows["data/characters/roster.json"]["status"], "blocked")
            self.assertEqual(rows["data/sources/manifest.json"]["status"], "imported")
            self.assertEqual(rows["data/sources/test_family/data.csv"]["status"], "duplicate")
            self.assertEqual(rows["data/sources/report.txt"]["status"], "skipped_by_policy")
            self.assertEqual(rows["assets/ref.png"]["status"], "skipped_by_policy")
            self.assertEqual(rows["src/example.py"]["status"], "skipped_by_policy")
            self.assertEqual(rows["db/import_report.json"]["status"], "skipped_by_policy")
            for row in rows.values():
                if row["status"] == "imported":
                    self.assertIsNotNone(row["imported_at"], row["source_relative_path"])
                else:
                    self.assertIsNone(row["imported_at"], row["source_relative_path"])
            raw = connection.execute("SELECT raw_json FROM qa_run_source").fetchone()[0]
            self.assertIn("fixture finding", raw)
            issue = connection.execute(
                "SELECT severity, evidence_json FROM qa_issue"
            ).fetchone()
            self.assertEqual(issue["severity"], 0.8)
            self.assertEqual(json.loads(issue["evidence_json"])["finding_count"], 2)
            prompt = connection.execute(
                "SELECT positive_tags, negative_prompt, natural_prompt, status FROM shot_prompt_revision "
                "ORDER BY shot_id LIMIT 1"
            ).fetchone()
            self.assertIn("tag_alpha", prompt["positive_tags"])
            self.assertEqual(prompt["negative_prompt"], "bad quality")
            self.assertIsNone(prompt["natural_prompt"])
            self.assertEqual(prompt["status"], "draft")
            queue = connection.execute(
                "SELECT rule_code, domain, character_id FROM reconciliation_item"
            ).fetchone()
            self.assertEqual(queue["rule_code"], "roster_outfit_mismatch")
            self.assertEqual(queue["domain"], "outfit")
            self.assertEqual(queue["character_id"], 2)
        finally:
            connection.close()

        verification = verify_ledger(self.db, self.source)
        self.assertEqual(verification["status"], "ok", verification)
        self.assertEqual(verification["checks"]["ledger_rows"], ledger_rows)

        before = {
            table: self._count(table)
            for table in (
                "project_document_revision",
                "shot_prompt_revision",
                "shot_prompt_spec",
                "qa_run",
                "qa_issue",
                "qa_run_source",
                "n2a_setting_revision",
                "source_snapshot",
                "reconciliation_item",
                "asset_blob",
                "import_file_ledger",
            )
        }
        rerun = run_import(self.db, self.source, batch_key="fixture-2")
        self.assertEqual(rerun["status"], "ok", rerun)
        self.assertEqual(rerun["counts"]["by_status"].get("imported", 0), 0, rerun)
        self.assertEqual(self._count("import_batch"), 2)
        self.assertEqual(self._count("import_file_ledger"), ledger_rows)
        for table, value in before.items():
            self.assertEqual(self._count(table), value, table)
        self.assertEqual(verify_ledger(self.db, self.source)["status"], "ok")

    def test_prompt_duplicate_slice_is_recorded(self) -> None:
        write(self.source / "prompts/fixture-act01.txt", "tag_alpha, red_dress\n")
        report = run_import(self.db, self.source, batch_key="fixture-slice")
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(self._count("shot_prompt_revision"), 3)
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT status, details_json FROM import_file_ledger "
                "WHERE source_relative_path='prompts/fixture-act01.txt'"
            ).fetchone()
            self.assertEqual(row["status"], "duplicate")
            details = json.loads(row["details_json"])
            self.assertEqual(details["path"], "prompts/fixture.txt")
            self.assertEqual(details["offset"], 0)
            self.assertEqual(details["blocks"], 1)
        finally:
            connection.close()

    def test_dry_run_rolls_back_all_writes(self) -> None:
        report = run_import(self.db, self.source, dry_run=True, batch_key="fixture-dry")
        self.assertEqual(report["status"], "dry_run", report)
        self.assertGreater(report["counts"]["by_status"]["imported"], 0)
        self.assertEqual(self._count("project_document_revision"), 0)
        self.assertEqual(self._count("shot_prompt_revision"), 0)
        self.assertEqual(self._count("qa_run"), 0)
        self.assertEqual(self._count("import_batch"), 0)
        self.assertEqual(self._count("import_file_ledger"), 0)

    def test_live_database_is_refused_without_explicit_opt_in(self) -> None:
        live = self.root / "db" / "novel_anima.db"
        live.parent.mkdir()
        live.write_bytes(b"")
        with self.assertRaises(ImportLedgerError):
            run_import(live, self.source)

    def test_prompt_count_mismatch_blocks_the_whole_prompt_file(self) -> None:
        write(self.source / "prompts/fixture.txt", "tag_alpha, red_dress\n\ntag_beta, blue_dress\n")
        report = run_import(self.db, self.source, batch_key="fixture-bad-prompt")
        self.assertEqual(report["status"], "ok", report)
        self.assertGreater(report["counts"]["by_status"]["blocked"], 0)
        self.assertEqual(self._count("shot_prompt_revision"), 0)
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT status, exception FROM import_file_ledger "
                "WHERE source_relative_path='prompts/fixture.txt'"
            ).fetchone()
            self.assertEqual(row["status"], "blocked")
            self.assertIn("prompt_shot_set_mismatch", row["exception"])
        finally:
            connection.close()

    def test_catalog_checksum_mismatch_is_staged_without_snapshot(self) -> None:
        manifest_path = self.source / "data/sources/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["test_family"]["files"]["data.csv"]["sha256"] = "0" * 64
        write(manifest_path, canonical(manifest))
        report = run_import(self.db, self.source, batch_key="fixture-bad-catalog")
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(self._count("source_snapshot"), 0)
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT status, exception FROM import_file_ledger "
                "WHERE source_relative_path='data/sources/manifest.json'"
            ).fetchone()
            self.assertEqual(row["status"], "blocked")
            self.assertIn("catalog_manifest_invalid", row["exception"])
            cache = connection.execute(
                "SELECT status FROM import_file_ledger "
                "WHERE source_relative_path='data/sources/test_family/data.csv'"
            ).fetchone()
            self.assertEqual(cache["status"], "blocked")
        finally:
            connection.close()

    def test_explicit_source_root_does_not_use_process_cwd(self) -> None:
        other = self.root / "elsewhere"
        other.mkdir()
        previous = Path.cwd()
        os.chdir(other)
        try:
            report = run_import(self.db, self.source, batch_key="fixture-cwd")
        finally:
            os.chdir(previous)
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(report["source_root"], str(self.source.resolve()))


if __name__ == "__main__":
    unittest.main()
