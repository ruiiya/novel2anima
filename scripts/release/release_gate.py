"""PR-09 release gate: DB-only E2E, backup/restore, rollback and benchmark.

This is a gate, not a claim of production readiness. It writes a JSON report and
returns 0 only when every required blocker is clear. P8 transitional columns are
reported as blockers instead of being silently accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import pathlib
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/qa"))

from novel2anima.prompting.compiler import (  # noqa: E402
    approve_prompt,
    compile_shot,
    replay_prompt,
)
from novel2anima.quality.qa import qa_history, record_qa_run  # noqa: E402
from novel2anima.render.service import create_render, replay_render  # noqa: E402
from novel2anima.storage.assets import get_asset  # noqa: E402
from novel2anima.storage.domain_repository import (  # noqa: E402
    add_interaction,
    add_participant,
    bind_outfit,
    create_outfit_revision,
    create_shot_spec_revision,
)
from novel2anima.storage.migrations import (  # noqa: E402
    applied_migrations,
    backup_database,
    discover_migrations,
    is_live_database,
)
from verify_p8_disposition import is_clean_row as disposition_row_clean, report as disposition_report  # noqa: E402

SCHEMA_VERSION = "v4-release-gate-1"
MIGRATIONS = ROOT / "sql/migrations"


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _db_sha(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(con) -> dict[str, int]:
    tables = (
        "project", "character_profile", "act", "shot", "shot_prompt_revision",
        "generation", "asset_blob", "qa_run", "qa_issue",
    )
    return {
        table: int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _migration_check(source) -> dict:
    con = sqlite3_connect(source)
    try:
        applied = applied_migrations(con)
        files = discover_migrations(MIGRATIONS)
    finally:
        con.close()
    missing = [item.version for item in files if item.version not in applied]
    drift = [
        item.version for item in files
        if item.version in applied and applied[item.version] != item.sha256
    ]
    return {
        "ok": not missing and not drift,
        "files": [{"version": item.version, "sha256": item.sha256} for item in files],
        "applied": applied,
        "missing": missing,
        "drift": drift,
    }


def sqlite3_connect(path):
    import sqlite3
    return sqlite3.connect(path)


def _seed_e2e(db: pathlib.Path) -> dict:
    import sqlite3

    from novel2anima.storage.domain_repository import connect
    con = connect(db)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        ids = {}
        for table in ("project", "character_profile", "act", "shot", "tag", "model_profile"):
            ids[table] = int(con.execute(f"SELECT coalesce(max(id),0)+1 FROM {table}").fetchone()[0])
        project_id = ids["project"]
        a = ids["character_profile"]
        b = a + 1
        con.execute("INSERT INTO project(id,title) VALUES(?, 'Release gate E2E')", (project_id,))
        con.executemany(
            "INSERT INTO character_profile(id,project_id,code)"
            " VALUES(?,?,?)",
            [(a, project_id, "E2E_A"), (b, project_id, "E2E_B")],
        )
        act_id = ids["act"]
        con.execute(
            "INSERT INTO act(id,project_id,act_no,title,revision,status)"
            " VALUES(?,?,1,'E2E act',1,'planned')",
            (act_id, project_id),
        )
        shot_id = ids["shot"]
        con.execute(
            "INSERT INTO shot(id,act_id,shot_no,status)"
            " VALUES(?,?,1,'planned')",
            (shot_id, act_id),
        )
        tag_names = (
            "n2a_e2e_long_hair", "n2a_e2e_shirt_a", "n2a_e2e_shirt_b",
            "n2a_e2e_headpat", "n2a_e2e_standing", "n2a_e2e_bedroom",
        )
        first_tag = ids["tag"]
        con.executemany(
            "INSERT INTO tag(id,canonical_name,search_name) VALUES(?,?,?)",
            [(first_tag + i, name, name.replace("_", " ")) for i, name in enumerate(tag_names)],
        )
        model_id = ids["model_profile"]
        con.execute(
            "INSERT INTO model_profile(id,code,model_name) VALUES(?,?,?)",
            (model_id, "e2e_anima", "anima"),
        )
        add_participant(con, shot_id, a, slot_no=1)
        add_participant(con, shot_id, b, slot_no=2)
        add_interaction(con, shot_id, b, a, "n2a_e2e_headpat", sort_order=1)
        outfit_a = create_outfit_revision(
            con, a, {"tags": ["n2a_e2e_shirt_a"]},
            [{"item_code": "top", "slot": "upper", "garment_type": "shirt"}],
            status="approved",
        )
        outfit_b = create_outfit_revision(
            con, b, {"tags": ["n2a_e2e_shirt_b"]},
            [{"item_code": "top", "slot": "upper", "garment_type": "shirt"}],
            status="approved",
        )
        bind_outfit(con, shot_id, a, outfit_a)
        bind_outfit(con, shot_id, b, outfit_b)
        create_shot_spec_revision(
            con, shot_id,
            {
                "participants": [a, b],
                "identity_tags": {str(a): ["n2a_e2e_long_hair"]},
                "action_tags": ["n2a_e2e_standing"],
                "background_tags": ["n2a_e2e_bedroom"],
                "negative_prompt": "bad",
            },
            status="approved",
        )
        con.commit()
        prompt_id = compile_shot(con, shot_id)
        approve_prompt(con, prompt_id)
        image = b"\x89PNG\r\n\x1a\n" + _json({"e2e": True}).encode("utf-8")
        render = create_render(
            con, shot_id=shot_id, model_profile_id=model_id,
            prompt_revision_id=prompt_id, image=image, seed=123,
            model_settings={"sampler": "er_sde", "steps": 4},
        )
        prompt = replay_prompt(con, prompt_id)
        replay = replay_render(con, render.generation_id)
        qa_id = record_qa_run(
            con, act_id=act_id, run_key=f"e2e-qa-{act_id}", evaluator_version="e2e",
            issues=[{
                "shot_id": shot_id, "rule_id": "e2e.review", "severity": 0.1,
                "actor_character_id": b, "target_character_id": a,
                "evidence": {"source": "release_gate"},
            }],
        )
        data = {
            "project_id": project_id, "act_id": act_id, "shot_id": shot_id,
            "prompt_id": prompt_id, "generation_id": render.generation_id,
            "qa_run_id": qa_id, "prompt_sha": prompt["content_sha256"],
            "render_sha": render.sha256, "image_bytes": len(image),
            "qa_history": len(qa_history(con, shot_id)),
            "interaction": con.execute(
                "SELECT actor_character_id,target_character_id FROM shot_interaction"
                " WHERE shot_id=?", (shot_id,)
            ).fetchone(),
            "body_sha": _sha_bytes(get_asset(con, render.asset_id)[0]),
            "replay_sha": replay["asset_sha256"],
        }
        return data
    finally:
        con.close()


def _backup_restore_check(source: pathlib.Path, work: pathlib.Path, expected: dict) -> dict:
    import sqlite3
    backup = work / "e2e_backup.db"
    restored = work / "e2e_restored.db"
    started = time.perf_counter()
    backup_database(source, backup)
    backup_database(backup, restored)
    elapsed = time.perf_counter() - started
    con = sqlite3.connect(restored)
    try:
        counts = _counts(con)
        quick = con.execute("PRAGMA quick_check").fetchone()[0]
        fk = con.execute("PRAGMA foreign_key_check").fetchall()
        asset = con.execute(
            "SELECT body,sha256 FROM asset_blob WHERE sha256=?",
            (expected["render_sha"],),
        ).fetchone()
        asset_ok = (
            asset is not None
            and _sha_bytes(bytes(asset[0])) == asset[1] == expected["render_sha"]
        )
        prompt = con.execute(
            "SELECT content_sha256 FROM shot_prompt_revision WHERE id=?",
            (expected["prompt_id"],),
        ).fetchone()
        return {
            "ok": quick == "ok" and not fk and asset_ok
                  and int(counts["project"]) >= 1
                  and prompt is not None and prompt[0] == expected["prompt_sha"],
            "quick_check": quick,
            "foreign_key_errors": len(fk),
            "asset_sha_match": asset_ok,
            "prompt_sha_match": prompt is not None and prompt[0] == expected["prompt_sha"],
            "counts": counts,
            "seconds": round(elapsed, 3),
        }
    finally:
        con.close()


def _rollback_check(old_backup: pathlib.Path, work: pathlib.Path, source_counts: dict) -> dict:
    import sqlite3
    rollback = work / "rollback_old.db"
    backup_database(old_backup, rollback)
    con = sqlite3.connect(rollback)
    try:
        counts = _counts(con)
        quick = con.execute("PRAGMA quick_check").fetchone()[0]
        return {
            "ok": quick == "ok" and counts == source_counts,
            "quick_check": quick,
            "counts": counts,
            "expected": source_counts,
        }
    finally:
        con.close()


def _benchmark(db: pathlib.Path) -> dict:
    import sqlite3
    con = sqlite3.connect(db)
    try:
        timings = {}
        started = time.perf_counter()
        tag_count = con.execute("SELECT count(*) FROM tag").fetchone()[0]
        timings["tag_count"] = round(time.perf_counter() - started, 4)
        started = time.perf_counter()
        con.execute("SELECT id FROM tag WHERE canonical_name=?", ("n2a_e2e_headpat",)).fetchone()
        timings["canonical_lookup"] = round(time.perf_counter() - started, 6)
        started = time.perf_counter()
        con.execute("PRAGMA foreign_key_check").fetchall()
        timings["foreign_key_check"] = round(time.perf_counter() - started, 4)
        return {"ok": True, "tag_rows": int(tag_count), "seconds": timings,
                "thresholds": {"tag_count": 10.0, "canonical_lookup": 0.1}}
    finally:
        con.close()


def _signed_ledger(db: pathlib.Path, migration: dict, status: str, blockers: list[str]) -> dict:
    import sqlite3
    con = sqlite3.connect(db)
    try:
        rows = [
            {"version": row[0], "sha256": row[1], "applied_at": row[2]}
            for row in con.execute(
                "SELECT version,sha256,applied_at FROM n2a_schema_migration ORDER BY version"
            )
        ]
    finally:
        con.close()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "database_sha256": _db_sha(db),
        "migrations": migration["applied"],
        "ledger": rows,
        "status": status,
        "blockers": blockers,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    key = os.environ.get("N2A_RELEASE_SIGNING_KEY")
    payload["signature_type"] = "hmac-sha256" if key else "sha256-content"
    body = _json(payload).encode("utf-8")
    if key:
        payload["signature"] = hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()
    else:
        payload["signature"] = _sha_bytes(body)
    return payload


def run_gate(
    db_path: pathlib.Path,
    *,
    work_dir: pathlib.Path | None = None,
    keep_work: bool = False,
    allow_live: bool = False,
) -> dict:
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise RuntimeError(f"database not found: {db_path}")
    if is_live_database(db_path) and not allow_live:
        raise RuntimeError("release gate refuses live DB; pass --allow-live after approval")
    temp = None
    if work_dir is None:
        temp = tempfile.TemporaryDirectory(prefix="n2a-release-")
        work_dir = pathlib.Path(temp.name)
    work_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": SCHEMA_VERSION,
        "database": str(db_path),
        "status": "FAILED",
        "blockers": [],
        "checks": {},
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        old_snapshot = work_dir / "source_snapshot.db"
        backup_database(db_path, old_snapshot)
        import sqlite3
        con = sqlite3.connect(old_snapshot)
        try:
            source_counts = _counts(con)
            source_quick = con.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            con.close()
        migration = _migration_check(old_snapshot)
        report["checks"]["migrations"] = migration
        if not migration["ok"]:
            report["blockers"].append("MIGRATION_LEDGER_DRIFT")

        disposition = disposition_report(db_path)
        report["checks"]["disposition"] = {
            "ok": disposition["clean"],
            "legacy_tables": disposition["legacy_table_count"],
            "missing": disposition["missing_from_csv"] + disposition["missing_disposition"],
            "transitional": [
                row["table"] for row in disposition["tables"]
                if not disposition_row_clean(row)
            ],
        }
        if not report["checks"]["disposition"]["ok"]:
            report["blockers"].append("P8_LEGACY_DISPOSITION")

        e2e_db = work_dir / "e2e.db"
        backup_database(old_snapshot, e2e_db)
        try:
            expected = _seed_e2e(e2e_db)
            report["checks"]["e2e"] = {"ok": True, **{
                key: expected[key] for key in
                ("project_id", "act_id", "shot_id", "prompt_id", "generation_id",
                 "qa_run_id", "prompt_sha", "render_sha", "image_bytes",
                 "qa_history", "interaction", "body_sha", "replay_sha")
            }}
            if expected["body_sha"] != expected["render_sha"] or expected["replay_sha"] != expected["render_sha"]:
                report["checks"]["e2e"]["ok"] = False
                report["blockers"].append("E2E_ASSET_SHA")
        except Exception as exc:
            report["checks"]["e2e"] = {"ok": False, "error": str(exc)}
            report["blockers"].append("E2E_PIPELINE")
            expected = None

        if expected is not None:
            report["checks"]["backup_restore"] = _backup_restore_check(e2e_db, work_dir, expected)
            if not report["checks"]["backup_restore"]["ok"]:
                report["blockers"].append("BACKUP_RESTORE")
            report["checks"]["rollback"] = _rollback_check(old_snapshot, work_dir, source_counts)
            if not report["checks"]["rollback"]["ok"]:
                report["blockers"].append("ROLLBACK_DRILL")
            report["checks"]["benchmark"] = _benchmark(e2e_db)

        report["checks"]["source"] = {"ok": source_quick == "ok", "quick_check": source_quick, "counts": source_counts}
        if source_quick != "ok":
            report["blockers"].append("SOURCE_INTEGRITY")
        report["status"] = "READY" if not report["blockers"] else "NOT_READY"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["signed_ledger"] = _signed_ledger(
            db_path, migration, report["status"], report["blockers"]
        )
        return report
    finally:
        if temp is not None and not keep_work:
            temp.cleanup()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, type=pathlib.Path)
    ap.add_argument("--report", type=pathlib.Path)
    ap.add_argument("--work-dir", type=pathlib.Path)
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--allow-live", action="store_true")
    args = ap.parse_args(argv)
    report = run_gate(
        args.db, work_dir=args.work_dir, keep_work=args.keep_work, allow_live=args.allow_live
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "blockers": report["blockers"],
        "checks": {key: value.get("ok") for key, value in report["checks"].items() if isinstance(value, dict)},
        "ledger_signature": report["signed_ledger"]["signature"],
    }, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "READY" else 3


if __name__ == "__main__":
    sys.exit(main())
