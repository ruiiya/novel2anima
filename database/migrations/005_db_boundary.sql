-- V2 database boundary: renderer state and post-render QA are outside Novel2Anima.
-- Render rows must be backed up by the Python preflight before this migration runs.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

DROP TABLE IF EXISTS render_assets;
DROP TABLE IF EXISTS render_jobs;

-- SQLite cannot alter a CHECK constraint in place. Rebuild qa_reports without
-- the RENDER subject kind; non-RENDER QA rows are preserved.
ALTER TABLE qa_reports RENAME TO qa_reports_legacy;
CREATE TABLE qa_reports (
  id TEXT PRIMARY KEY,
  subject_kind TEXT NOT NULL CHECK(subject_kind IN ('STORY','SHOT','LAYOUT')),
  subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('PASS','WARN','BLOCKED','SKIP')),
  policy_ref TEXT,
  report_json TEXT NOT NULL CHECK(json_valid(report_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO qa_reports(id,subject_kind,subject_id,verdict,policy_ref,report_json,created_at)
  SELECT id,subject_kind,subject_id,verdict,policy_ref,report_json,created_at
  FROM qa_reports_legacy
  WHERE subject_kind IN ('STORY','SHOT','LAYOUT');
DROP TABLE qa_reports_legacy;

-- Sources explicitly rejected by the V2 scope are removed if unused.
DELETE FROM source_registry
 WHERE id IN ('coco','openpose','grounded_sam')
   AND NOT EXISTS (SELECT 1 FROM import_runs WHERE source_id=source_registry.id)
   AND NOT EXISTS (SELECT 1 FROM source_records WHERE source_id=source_registry.id);

INSERT INTO schema_migrations(version) VALUES('005_db_boundary');
COMMIT;
