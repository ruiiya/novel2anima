-- Migration 007 - Reconciliation queue for deterministic legacy backfills.
-- Additive only. Rows are evidence that a later import/curation step needs a
-- decision; they do not change any legacy table.
CREATE TABLE IF NOT EXISTS reconciliation_item (
  id INTEGER PRIMARY KEY,
  gap_key TEXT NOT NULL UNIQUE,
  domain TEXT NOT NULL CHECK(domain IN (
    'project','identity','outfit','shot','participant','interaction',
    'prompt','continuity','catalog','asset','other'
  )),
  severity TEXT NOT NULL DEFAULT 'warning' CHECK(severity IN ('info','warning','blocked')),
  project_id INTEGER REFERENCES project(id) ON DELETE RESTRICT,
  act_id INTEGER REFERENCES act(id) ON DELETE RESTRICT,
  shot_id INTEGER REFERENCES shot(id) ON DELETE RESTRICT,
  character_id INTEGER REFERENCES character_profile(id) ON DELETE RESTRICT,
  entity_table TEXT,
  entity_id INTEGER,
  rule_code TEXT NOT NULL CHECK(length(trim(rule_code)) > 0),
  evidence_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(evidence_json) AND json_type(evidence_json) = 'object'),
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','ignored')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reconciliation_status_domain
  ON reconciliation_item(status, domain, severity);
CREATE INDEX IF NOT EXISTS idx_reconciliation_shot
  ON reconciliation_item(shot_id, status);
CREATE INDEX IF NOT EXISTS idx_reconciliation_character
  ON reconciliation_item(character_id, status);
