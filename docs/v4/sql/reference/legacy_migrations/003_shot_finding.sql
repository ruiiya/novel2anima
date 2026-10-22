-- QA findings are evidence, not continuity state. Keep them separate so two
-- producers (rule engine, LLM review) cannot overwrite each other.
CREATE TABLE IF NOT EXISTS shot_finding (
  id            INTEGER PRIMARY KEY,
  shot_id       INTEGER NOT NULL REFERENCES shot(id) ON DELETE CASCADE,
  rule_id       TEXT    NOT NULL,
  source        TEXT    NOT NULL,
  axis          TEXT,
  value_tag_id  INTEGER REFERENCES tag(id),
  severity      REAL    NOT NULL DEFAULT 0.5 CHECK(severity BETWEEN 0 AND 1),
  evidence_json TEXT    NOT NULL DEFAULT '{}',
  status        TEXT    NOT NULL DEFAULT 'open',
  created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(shot_id, rule_id, source)
);

CREATE INDEX IF NOT EXISTS shot_finding_shot ON shot_finding(shot_id);
