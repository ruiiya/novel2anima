-- Inference outputs are OBSERVATIONS, not confirmed continuity.
-- shot_state / act_continuity stay the authoritative (manual/curated) tables;
-- infer_state.py only ever writes and deletes its own rows in these tables.
CREATE TABLE IF NOT EXISTS shot_observation (
  shot_id       INTEGER NOT NULL REFERENCES shot(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  value_tag_id  INTEGER REFERENCES tag(id),
  severity      REAL    NOT NULL DEFAULT 0.5 CHECK(severity BETWEEN 0 AND 1),
  since_shot_no INTEGER NOT NULL,
  cause_shot_no INTEGER NOT NULL,
  source        TEXT    NOT NULL,
  PRIMARY KEY (shot_id, axis, source)
);

CREATE TABLE IF NOT EXISTS act_observation (
  act_id        INTEGER NOT NULL REFERENCES act(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  initial_tag_id INTEGER REFERENCES tag(id),
  notes         TEXT    NOT NULL DEFAULT '',
  source        TEXT    NOT NULL,
  PRIMARY KEY (act_id, axis, source)
);

-- Outbox for prompt publication: row is pending=1 between the DB commit and the
-- file replace; rerunning the same plan reconciles and clears it.
CREATE TABLE IF NOT EXISTS act_publication (
  act_id        INTEGER NOT NULL REFERENCES act(id) ON DELETE CASCADE,
  revision      INTEGER NOT NULL,
  prompt_path   TEXT    NOT NULL,
  prompt_sha256 TEXT    NOT NULL,
  negative_path TEXT,
  negative_sha256 TEXT,
  pending       INTEGER NOT NULL DEFAULT 1,
  updated_at    TEXT    NOT NULL,
  PRIMARY KEY (act_id, revision)
);
