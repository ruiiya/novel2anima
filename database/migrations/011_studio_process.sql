-- V6: conversation-led, prompt-only Studio. Never store render jobs or images.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;
CREATE TABLE studio_artifacts (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  stage TEXT NOT NULL CHECK(stage IN ('STORY','RESEARCH_VISUAL','STORYBOARD','PROMPTS')),
  revision INTEGER NOT NULL CHECK(revision > 0),
  source_ref TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  artifact_json TEXT NOT NULL CHECK(json_valid(artifact_json)),
  artifact_sha256 TEXT NOT NULL,
  prerequisite_id TEXT REFERENCES studio_artifacts(id),
  review_json TEXT NOT NULL CHECK(json_valid(review_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(story_id,stage,revision)
);
CREATE INDEX ix_studio_artifact_story_stage ON studio_artifacts(story_id,stage,revision DESC);
CREATE TABLE studio_decisions (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES studio_artifacts(id),
  decision TEXT NOT NULL CHECK(decision IN ('APPROVED','CHANGES_REQUESTED')),
  actor TEXT NOT NULL CHECK(actor='USER'),
  evidence TEXT NOT NULL CHECK(length(trim(evidence))>0),
  decided_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_studio_decisions_artifact ON studio_decisions(artifact_id,decided_at);
CREATE TABLE studio_feedback (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  storyboard_id TEXT REFERENCES storyboards(id),
  shot_key TEXT NOT NULL,
  prompt_id TEXT REFERENCES shot_prompts(id),
  description TEXT NOT NULL CHECK(length(trim(description))>0),
  affected_json TEXT NOT NULL CHECK(json_valid(affected_json)),
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','RESOLVED')),
  resolved_prompt_id TEXT REFERENCES shot_prompts(id),
  resolution_note TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  resolved_at TEXT
);
CREATE INDEX ix_studio_feedback_story ON studio_feedback(story_id,status,created_at);
CREATE TABLE studio_exports (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  prompts_artifact_id TEXT NOT NULL REFERENCES studio_artifacts(id),
  manifest_sha256 TEXT NOT NULL,
  export_dir TEXT NOT NULL,
  exported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER studio_artifacts_no_update BEFORE UPDATE ON studio_artifacts BEGIN SELECT RAISE(ABORT,'Studio artifact immutable'); END;
CREATE TRIGGER studio_artifacts_no_delete BEFORE DELETE ON studio_artifacts BEGIN SELECT RAISE(ABORT,'Studio artifact immutable'); END;
CREATE TRIGGER studio_decisions_no_update BEFORE UPDATE ON studio_decisions BEGIN SELECT RAISE(ABORT,'Studio decision immutable'); END;
CREATE TRIGGER studio_decisions_no_delete BEFORE DELETE ON studio_decisions BEGIN SELECT RAISE(ABORT,'Studio decision immutable'); END;
INSERT INTO schema_migrations(version) VALUES ('011_studio_process');
COMMIT;
