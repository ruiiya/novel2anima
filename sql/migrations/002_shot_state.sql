-- EXPERIMENTAL / REFERENCE ONLY.
-- Continuity state inferred from shot specs. This is provisional placeholder data to be
-- refined over repeated runs; it is NOT authoritative content and nothing should treat a
-- missing row as proof that a state element is absent from the scene.
-- Sketch documented in skills/novel2anima-shot-pipeline/references/continuity-state.md

CREATE TABLE IF NOT EXISTS shot_state (
  shot_id       INTEGER NOT NULL REFERENCES shot(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  value_tag_id  INTEGER REFERENCES tag(id),
  severity      REAL    NOT NULL DEFAULT 0.5 CHECK(severity BETWEEN 0 AND 1),
  since_shot_no INTEGER NOT NULL,
  cause_shot_no INTEGER NOT NULL,
  source        TEXT    NOT NULL DEFAULT 'inferred:v0',
  PRIMARY KEY (shot_id, axis)
);

CREATE TABLE IF NOT EXISTS act_continuity (
  act_id        INTEGER NOT NULL REFERENCES act(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  initial_tag_id INTEGER REFERENCES tag(id),
  notes         TEXT    NOT NULL DEFAULT '',
  PRIMARY KEY (act_id, axis)
);
