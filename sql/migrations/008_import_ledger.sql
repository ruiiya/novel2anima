-- Migration 008 - External import ledger (additive)
-- Reviewed for PR-03. Apply only through src/novel2anima/storage/migrations.py
-- on a staging copy. This migration does not touch legacy catalog tables.
--
-- The existing import_batch/import_batch_file tables require every file to have
-- an asset_blob. PR-03 intentionally does not store render/reference images or
-- raw catalog caches in asset_blob yet, so the per-file ledger is separate and
-- records hashes, classification, parser version, target and staged errors.
CREATE TABLE IF NOT EXISTS import_file_ledger (
  id INTEGER PRIMARY KEY,
  import_batch_id INTEGER NOT NULL REFERENCES import_batch(id) ON DELETE RESTRICT,
  source_relative_path TEXT NOT NULL CHECK(length(trim(source_relative_path)) > 0),
  source_sha256 TEXT NOT NULL CHECK(length(source_sha256) = 64),
  source_bytes INTEGER NOT NULL CHECK(source_bytes >= 0),
  classified_as TEXT NOT NULL CHECK(classified_as IN (
    'plan','prompt','review','wardrobe','roster','catalog','asset',
    'source_controlled','legacy_workspace','legacy_report','llm_scaffold',
    'canonical_database','generated_artifact','unknown'
  )),
  target_table TEXT,
  target_pk INTEGER,
  parser_version TEXT NOT NULL CHECK(length(trim(parser_version)) > 0),
  status TEXT NOT NULL CHECK(status IN ('imported','duplicate','blocked','skipped_by_policy')),
  exception TEXT,
  verified_sha256 TEXT CHECK(verified_sha256 IS NULL OR length(verified_sha256) = 64),
  details_json TEXT NOT NULL DEFAULT '{}'
    CHECK(json_valid(details_json) AND json_type(details_json) = 'object'),
  checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  imported_at TEXT,
  UNIQUE(source_relative_path, source_sha256, parser_version)
);
CREATE INDEX IF NOT EXISTS idx_import_ledger_status
  ON import_file_ledger(status, classified_as);
CREATE INDEX IF NOT EXISTS idx_import_ledger_batch
  ON import_file_ledger(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_import_ledger_path
  ON import_file_ledger(source_relative_path);

-- Reviews are LLM/QA artifacts. Keep the complete raw review JSON beside the
-- normalized qa_run/qa_issue projection so a finding can be audited later.
CREATE TABLE IF NOT EXISTS qa_run_source (
  qa_run_id INTEGER PRIMARY KEY REFERENCES qa_run(id) ON DELETE RESTRICT,
  source_relative_path TEXT NOT NULL CHECK(length(trim(source_relative_path)) > 0),
  source_sha256 TEXT NOT NULL CHECK(length(source_sha256) = 64),
  parser_version TEXT NOT NULL CHECK(length(trim(parser_version)) > 0),
  raw_json TEXT NOT NULL CHECK(json_valid(raw_json)),
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_relative_path, source_sha256)
);
