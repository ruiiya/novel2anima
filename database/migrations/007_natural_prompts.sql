-- Natural prompt is now the canonical image prompt. Historical layout tables
-- remain read-only for traceability; they are not part of the active pipeline.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

CREATE TABLE shot_prompts (
  id TEXT PRIMARY KEY,
  shot_id TEXT NOT NULL REFERENCES shots(id),
  revision INTEGER NOT NULL CHECK(revision >= 1),
  language TEXT NOT NULL DEFAULT 'en' CHECK(language IN ('en','vi','zh')),
  prompt_text TEXT NOT NULL CHECK(length(trim(prompt_text)) > 0),
  prompt_sha256 TEXT NOT NULL,
  shot_spec_sha256 TEXT NOT NULL,
  supersedes_prompt_id TEXT REFERENCES shot_prompts(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(shot_id, revision)
);
CREATE INDEX ix_shot_prompts_current ON shot_prompts(shot_id,revision DESC);
CREATE TRIGGER shot_prompts_immutable_update BEFORE UPDATE ON shot_prompts
BEGIN SELECT RAISE(ABORT,'Shot prompts are immutable; create a new revision'); END;
CREATE TRIGGER shot_prompts_immutable_delete BEFORE DELETE ON shot_prompts
BEGIN SELECT RAISE(ABORT,'Shot prompts are immutable; create a new revision'); END;

-- Retain old LAYOUT QA for audit. New writes use PROMPT only.
DROP TRIGGER IF EXISTS qa_report_immutable_update;
DROP TRIGGER IF EXISTS qa_report_immutable_delete;
ALTER TABLE qa_reports RENAME TO qa_reports_before_007;
CREATE TABLE qa_reports (
  id TEXT PRIMARY KEY,
  subject_kind TEXT NOT NULL CHECK(subject_kind IN ('STORY','SHOT','LAYOUT','PROMPT')),
  subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('PASS','WARN','BLOCKED','SKIP')),
  policy_ref TEXT,
  report_json TEXT NOT NULL CHECK(json_valid(report_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO qa_reports(id,subject_kind,subject_id,verdict,policy_ref,report_json,created_at)
  SELECT id,subject_kind,subject_id,verdict,policy_ref,report_json,created_at
  FROM qa_reports_before_007;
DROP TABLE qa_reports_before_007;
CREATE TRIGGER qa_report_immutable_update BEFORE UPDATE ON qa_reports
BEGIN SELECT RAISE(ABORT,'QA reports are immutable'); END;
CREATE TRIGGER qa_report_immutable_delete BEFORE DELETE ON qa_reports
BEGIN SELECT RAISE(ABORT,'QA reports are immutable'); END;

INSERT INTO schema_migrations(version) VALUES('007_natural_prompts');
COMMIT;
