"""PR-02 deterministic backfill tests."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel2anima.storage.migrations import apply_migrations  # noqa: E402
from novel2anima.storage.repositories.legacy_backfill import (  # noqa: E402
    BackfillError,
    run_backfill,
)

BASE_SCHEMA = ROOT / "docs/v4/sql/reference/current_schema_20261022.sql"


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
    for name in ("005_db_first.sql", "006_normalization.sql", "007_reconciliation_queue.sql"):
        shutil.copy2(ROOT / "sql/migrations" / name, migrations / name)
    report = apply_migrations(db, migrations, backup_path=root / "pre_backfill.db")
    assert report["status"] == "ok", report
    return db


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def insert_fixture(db: Path) -> None:
    connection = sqlite3.connect(db)
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.execute(
            "INSERT INTO project(id,title,idea,content_profile,style_json,created_at) "
            "VALUES (1,'Project One','Idea one','nsfw',?, '2026-01-01T00:00:00Z')",
            (dumps({"style": "anime"}),),
        )
        connection.execute(
            "INSERT INTO project(id,title,idea,content_profile,style_json,created_at) "
            "VALUES (2,'Project Two','Idea two','sfw','{}','2026-01-01T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO character_profile(id,project_id,code,identity_json,outfit_json) "
            "VALUES (1,1,'ALPHA',?,?)",
            (
                dumps({"identity_tags": [{"name": "alpha", "tagId": 1}]}),
                dumps(
                    {
                        "default": ["dress:101"],
                        "nude": ["completely_nude:102"],
                        "source": "assumed",
                        "variants": {"torn": ["torn_dress:103"]},
                    }
                ),
            ),
        )
        connection.execute(
            "INSERT INTO character_profile(id,project_id,code,identity_json,outfit_json) "
            "VALUES (2,1,'BETA',?,?)",
            (
                dumps({"identity_tags": [{"name": "beta", "tagId": 2}]}),
                dumps({"default": ["suit:201"]}),
            ),
        )
        connection.execute(
            "INSERT INTO character_profile(id,project_id,code,identity_json,outfit_json) "
            "VALUES (3,2,'GAMMA','{}','{}')"
        )
        connection.execute(
            "INSERT INTO act(id,project_id,act_no,title,outline,revision,status) "
            "VALUES (1,1,1,'Act One','',1,'planned')"
        )

        solo = {
            "participants": [{"code": "ALPHA", "role": "participant"}],
            "outfit": [{"name": "dress", "tagId": 101}],
        }
        duo_explicit = {
            "participants": [
                {"code": "ALPHA", "role": "participant"},
                {"code": "BETA", "role": "participant"},
            ],
            "sequence": {
                "purpose": "interaction",
                "actor": "BETA",
                "target": "ALPHA",
                "primaryAction": "hand_on_hip",
            },
            "outfit": [{"name": "dress", "tagId": 101}],
        }
        duo_missing = {
            "participants": [
                {"code": "ALPHA", "role": "participant"},
                {"code": "BETA", "role": "participant"},
            ]
        }
        cross_project = {
            "participants": [{"code": "GAMMA", "role": "participant"}],
        }
        rows = [
            (1, 1, 1, 1, dumps(solo)),
            (2, 1, 2, 1, dumps(duo_explicit)),
            (3, 1, 3, 1, dumps(duo_missing)),
            (4, 1, 4, 3, dumps(cross_project)),
        ]
        connection.executemany(
            "INSERT INTO shot(id,act_id,shot_no,character_id,shot_spec_json,status) "
            "VALUES (?,?,?,?,?,'planned')",
            rows,
        )
        connection.commit()
    finally:
        connection.close()


class BackfillTests(unittest.TestCase):
    def test_backfill_relational_rows_and_gap_queue(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = create_v4_db(root)
            insert_fixture(db)

            report = run_backfill(db)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["counts"]["project_documents"]["inserted"], 2)
            self.assertEqual(report["counts"]["identities"]["inserted"], 3)
            self.assertEqual(report["counts"]["outfits"]["revisions_inserted"], 4)
            self.assertEqual(report["counts"]["outfits"]["items_inserted"], 4)
            self.assertEqual(report["counts"]["shot_specs"]["inserted"], 4)
            self.assertEqual(report["counts"]["participants"]["inserted"], 5)
            self.assertEqual(report["counts"]["interactions"]["inserted"], 1)
            self.assertEqual(report["counts"]["outfit_bindings"]["inserted"], 2)
            self.assertGreaterEqual(report["reconciliation"]["inserted"], 5)

            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            try:
                shots = {
                    row["id"]: row
                    for row in connection.execute(
                        "SELECT id, shot_no FROM shot ORDER BY id"
                    )
                }
                self.assertEqual(shots[1]["shot_no"], 1)

                # IDs are preserved and participants are explicit.
                participants = connection.execute(
                    "SELECT shot_id, character_id, slot_no, scene_role "
                    "FROM shot_participant ORDER BY shot_id, slot_no"
                ).fetchall()
                self.assertEqual(
                    [(row["shot_id"], row["character_id"], row["slot_no"]) for row in participants],
                    [(1, 1, 1), (2, 1, 1), (2, 2, 2), (3, 1, 1), (3, 2, 2)],
                )
                self.assertTrue(all(row["scene_role"] == "subject" for row in participants))

                # Direction comes only from the explicit sequence.
                interaction = connection.execute(
                    "SELECT shot_id, actor_character_id, target_character_id, action_code, instruction "
                    "FROM shot_interaction"
                ).fetchall()
                self.assertEqual(len(interaction), 1)
                self.assertEqual(
                    (
                        interaction[0]["shot_id"],
                        interaction[0]["actor_character_id"],
                        interaction[0]["target_character_id"],
                        interaction[0]["action_code"],
                        interaction[0]["instruction"],
                    ),
                    (2, 2, 1, "hand_on_hip", "legacy:sequence"),
                )

                # No row may be created for the duo shot without explicit
                # actor/target, and the omission is queued.
                missing = connection.execute(
                    "SELECT count(*) FROM shot_interaction WHERE shot_id=3"
                ).fetchone()[0]
                self.assertEqual(missing, 0)
                queue = {
                    row["rule_code"]: row["count"]
                    for row in connection.execute(
                        "SELECT rule_code, count(*) AS count FROM reconciliation_item GROUP BY rule_code"
                    )
                }
                self.assertEqual(queue.get("interaction_actor_target_missing"), 1)
                self.assertNotIn("participant_duplicate_character", queue)

                # Exact outfit matches bind; unmapped and absent outfits are
                # queued rather than guessed.
                bindings = connection.execute(
                    "SELECT shot_id, character_id, outfit_revision_id "
                    "FROM shot_outfit_binding ORDER BY shot_id, character_id"
                ).fetchall()
                self.assertEqual(
                    [(row["shot_id"], row["character_id"]) for row in bindings],
                    [(1, 1), (2, 1)],
                )
                self.assertIn("outfit_binding_unmatched", queue)
                self.assertIn("outfit_binding_missing", queue)

                # Cross-project character and unknown participant code are
                # blocked, not silently mapped to project 1.
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM shot_participant WHERE shot_id=4"
                    ).fetchone()[0],
                    0,
                )
                self.assertIn("participant_shot_character_cross_project", queue)
                self.assertIn("participant_unknown_code", queue)

                # Legacy IDs in JSON payloads survive in the new revisions.
                identity = connection.execute(
                    "SELECT identity_json FROM character_identity_revision WHERE character_id=1"
                ).fetchone()[0]
                self.assertIn('"tagId":1', identity)
                outfit_items = connection.execute(
                    "SELECT item_code, details_json FROM outfit_item "
                    "WHERE outfit_revision_id IN (SELECT id FROM outfit_revision WHERE character_id=1) "
                    "ORDER BY item_code"
                ).fetchall()
                self.assertEqual([row["item_code"] for row in outfit_items], ["completely_nude", "dress", "torn_dress"])
            finally:
                connection.close()

            # Rerun is idempotent.
            second = run_backfill(db)
            self.assertEqual(second["counts"]["participants"]["inserted"], 0)
            self.assertEqual(second["counts"]["shot_specs"]["inserted"], 0)
            self.assertEqual(second["counts"]["interactions"]["inserted"], 0)
            self.assertEqual(second["reconciliation"]["inserted"], 0)
            self.assertGreater(second["reconciliation"]["existing"], 0)

    def test_dry_run_rolls_back_all_additive_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = create_v4_db(root)
            insert_fixture(db)

            report = run_backfill(db, dry_run=True)
            self.assertEqual(report["status"], "dry_run")
            self.assertEqual(report["counts"]["participants"]["inserted"], 5)

            connection = sqlite3.connect(db)
            try:
                for table in (
                    "project_document_revision",
                    "character_identity_revision",
                    "outfit_revision",
                    "outfit_item",
                    "shot_spec_revision",
                    "shot_participant",
                    "shot_interaction",
                    "shot_outfit_binding",
                    "reconciliation_item",
                ):
                    self.assertEqual(
                        connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0],
                        0,
                        table,
                    )
            finally:
                connection.close()

    def test_project_subset_filters_every_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = create_v4_db(root)
            insert_fixture(db)

            report = run_backfill(db, project_ids=[1])
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["source_counts"]["projects"], 1)
            self.assertEqual(report["counts"]["project_documents"]["inserted"], 1)
            self.assertEqual(report["counts"]["identities"]["inserted"], 2)
            self.assertEqual(report["counts"]["shot_specs"]["inserted"], 4)

            connection = sqlite3.connect(db)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM project_document_revision WHERE project_id=2"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM character_identity_revision WHERE character_id=3"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM shot_spec_revision WHERE shot_id=4"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_incomplete_outfit_revision_is_not_used_for_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = create_v4_db(root)
            insert_fixture(db)

            connection = sqlite3.connect(db)
            try:
                connection.execute(
                    "UPDATE character_profile SET outfit_json=? WHERE id=2",
                    (dumps({"default": ["suit:201", "free_text"]}),),
                )
                connection.execute(
                    "INSERT INTO shot(id,act_id,shot_no,character_id,shot_spec_json,status) "
                    "VALUES (5,1,5,2,?,'planned')",
                    (
                        dumps(
                            {
                                "participants": [{"code": "BETA", "role": "participant"}],
                                "outfit": [{"name": "suit", "tagId": 201}],
                            }
                        ),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            run_backfill(db)
            connection = sqlite3.connect(db)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM shot_outfit_binding WHERE shot_id=5 AND character_id=2"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM reconciliation_item "
                        "WHERE shot_id=5 AND rule_code='outfit_binding_unmatched'"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_null_primary_is_queued_but_explicit_participant_is_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = create_v4_db(root)
            insert_fixture(db)

            connection = sqlite3.connect(db)
            try:
                connection.execute("UPDATE shot SET character_id=NULL WHERE id=1")
                connection.commit()
            finally:
                connection.close()

            run_backfill(db)
            connection = sqlite3.connect(db)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM shot_participant WHERE shot_id=1 AND character_id=1"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM reconciliation_item "
                        "WHERE shot_id=1 AND rule_code='participant_shot_character_missing'"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_invalid_json_is_queued_without_partial_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = create_v4_db(root)
            insert_fixture(db)

            connection = sqlite3.connect(db)
            try:
                connection.execute(
                    "UPDATE character_profile SET identity_json='[]' WHERE id=1"
                )
                connection.execute(
                    "UPDATE shot SET shot_spec_json='[1,2]' WHERE id=1"
                )
                connection.commit()
            finally:
                connection.close()

            report = run_backfill(db)
            self.assertEqual(report["counts"]["identities"]["invalid"], 1)
            self.assertEqual(report["counts"]["shot_specs"]["invalid"], 1)
            connection = sqlite3.connect(db)
            try:
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM character_identity_revision WHERE character_id=1"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT count(*) FROM shot_spec_revision WHERE shot_id=1"
                    ).fetchone()[0],
                    0,
                )
                rules = {
                    row[0]
                    for row in connection.execute("SELECT rule_code FROM reconciliation_item")
                }
                self.assertIn("identity_not_object", rules)
                self.assertIn("shot_spec_not_object", rules)
            finally:
                connection.close()

    def test_live_database_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            live = root / "db/novel_anima.db"
            live.parent.mkdir(parents=True)
            sqlite3.connect(live).close()
            with self.assertRaises(BackfillError):
                run_backfill(live)


if __name__ == "__main__":
    unittest.main()
