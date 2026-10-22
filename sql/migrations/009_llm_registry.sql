-- Migration 009 - LLM prompt registry audit trail
-- Additive only. The prompt body stays in llm_prompt_template; this table makes
-- every create/status change auditable even when written outside the service.

CREATE TABLE IF NOT EXISTS llm_prompt_template_event (
 id INTEGER PRIMARY KEY,
 template_id INTEGER NOT NULL REFERENCES llm_prompt_template(id) ON DELETE RESTRICT,
 stage TEXT NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('draft','active','retired')),
 content_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_llm_template_event_stage
 ON llm_prompt_template_event(stage, created_at);

CREATE TRIGGER IF NOT EXISTS trg_llm_template_event_insert
AFTER INSERT ON llm_prompt_template
BEGIN
 INSERT INTO llm_prompt_template_event(template_id, stage, action, content_sha256)
 VALUES(NEW.id, NEW.stage, NEW.status, NEW.content_sha256);
END;

CREATE TRIGGER IF NOT EXISTS trg_llm_template_event_status
AFTER UPDATE OF status ON llm_prompt_template
WHEN OLD.status <> NEW.status
BEGIN
 INSERT INTO llm_prompt_template_event(template_id, stage, action, content_sha256)
 VALUES(NEW.id, NEW.stage, NEW.status, NEW.content_sha256);
END;

CREATE TRIGGER IF NOT EXISTS trg_llm_template_event_immutable_update
BEFORE UPDATE ON llm_prompt_template_event
BEGIN SELECT RAISE(ABORT,'llm prompt event is immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_llm_template_event_immutable_delete
BEFORE DELETE ON llm_prompt_template_event
BEGIN SELECT RAISE(ABORT,'llm prompt event is immutable'); END;
