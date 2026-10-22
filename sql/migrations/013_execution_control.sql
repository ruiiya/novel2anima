-- V4.1 PR-10 execution control, adapted from sql/proposals/007_execution_control_DRAFT.
-- Actual repo already has SQL versions 007..010 and Python cleanup ledger 011/012,
-- so this reviewed migration is version 013. Apply only to a DB copy/staging first.
PRAGMA defer_foreign_keys=ON;

-- The old run status vocabulary was lower-case and had no workflow pin. Rebuild
-- in place so llm_run FK ids remain valid; checks are deferred to COMMIT.
CREATE TABLE pipeline_run_new (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
  act_id INTEGER REFERENCES act(id) ON DELETE RESTRICT,
  run_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN
    ('QUEUED','RUNNING','WAITING_APPROVAL','BLOCKED_CONFIG',
     'BLOCKED_DEPENDENCY','FAILED','COMPLETED','CANCELLED')),
  input_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(input_json)),
  result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);
INSERT INTO pipeline_run_new(id,project_id,act_id,run_key,status,input_json,result_json,created_at,finished_at)
SELECT id,project_id,act_id,run_key,
  CASE status
    WHEN 'queued' THEN 'QUEUED'
    WHEN 'running' THEN 'RUNNING'
    WHEN 'completed' THEN 'COMPLETED'
    WHEN 'failed' THEN 'FAILED'
    WHEN 'blocked' THEN 'BLOCKED_CONFIG'
    ELSE 'FAILED'
  END,
  input_json,result_json,created_at,finished_at
FROM pipeline_run;
DROP TABLE pipeline_run;
ALTER TABLE pipeline_run_new RENAME TO pipeline_run;

CREATE TABLE IF NOT EXISTS pipeline_run_execution (
  pipeline_run_id INTEGER PRIMARY KEY
    REFERENCES pipeline_run(id) ON DELETE RESTRICT,
  workflow_code TEXT NOT NULL,
  workflow_version TEXT NOT NULL,
  workflow_definition_sha256 TEXT NOT NULL
    CHECK(length(workflow_definition_sha256)=64),
  request_sha256 TEXT NOT NULL CHECK(length(request_sha256)=64),
  runtime_mode TEXT NOT NULL
    CHECK(runtime_mode IN ('LEGACY','MIGRATING','V4_ACTIVE')),
  trigger_source TEXT NOT NULL
    CHECK(trigger_source IN ('USER','API','SCHEDULED','ADMIN')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pipeline_step_run_new (
  id INTEGER PRIMARY KEY,
  pipeline_run_id INTEGER NOT NULL
    REFERENCES pipeline_run(id) ON DELETE RESTRICT,
  step_code TEXT NOT NULL CHECK(length(trim(step_code)) BETWEEN 1 AND 100),
  workflow_version TEXT NOT NULL,
  attempt_no INTEGER NOT NULL CHECK(attempt_no >= 1),
  execution_key TEXT NOT NULL UNIQUE,
  input_fingerprint TEXT NOT NULL CHECK(length(input_fingerprint)=64),
  dependency_snapshot_json TEXT NOT NULL DEFAULT '[]'
    CHECK(json_valid(dependency_snapshot_json)),
  output_revision_refs_json TEXT
    CHECK(output_revision_refs_json IS NULL OR json_valid(output_revision_refs_json)),
  status TEXT NOT NULL
    CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED',
      'BLOCKED_CONFIG','BLOCKED_DEPENDENCY','NEEDS_REVIEW',
      'SKIPPED_CONDITION','CANCELLED')),
  error_code TEXT,
  retry_of_step_run_id INTEGER REFERENCES pipeline_step_run_new(id) ON DELETE RESTRICT,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json)),
  UNIQUE(pipeline_run_id,step_code,attempt_no),
  CHECK(status <> 'SUCCEEDED' OR output_revision_refs_json IS NOT NULL),
  CHECK(retry_of_step_run_id IS NULL OR retry_of_step_run_id <> id)
);
INSERT INTO pipeline_step_run_new
(id,pipeline_run_id,step_code,workflow_version,attempt_no,execution_key,
 input_fingerprint,dependency_snapshot_json,output_revision_refs_json,status,
 error_code,retry_of_step_run_id,started_at,finished_at,created_at,details_json)
SELECT id,pipeline_run_id,stage_key,'legacy-v4',attempt,
  'legacy:' || pipeline_run_id || ':' || stage_key || ':' || attempt,
  input_sha256,'[]',
  CASE WHEN output_sha256 IS NULL THEN NULL
       ELSE json_array('sha256:' || output_sha256) END,
  CASE status
    WHEN 'queued' THEN 'QUEUED'
    WHEN 'running' THEN 'RUNNING'
    WHEN 'completed' THEN 'SUCCEEDED'
    WHEN 'failed' THEN 'FAILED'
    WHEN 'skipped' THEN 'SKIPPED_CONDITION'
    ELSE 'FAILED'
  END,
  NULL,NULL,started_at,completed_at,started_at,details_json
FROM pipeline_step_run;
DROP TABLE pipeline_step_run;
ALTER TABLE pipeline_step_run_new RENAME TO pipeline_step_run;

CREATE INDEX IF NOT EXISTS idx_step_run_status
  ON pipeline_step_run(pipeline_run_id,status,step_code);
CREATE INDEX IF NOT EXISTS idx_step_run_fingerprint
  ON pipeline_step_run(step_code,input_fingerprint);

CREATE TRIGGER IF NOT EXISTS trg_step_retry_same_run
BEFORE INSERT ON pipeline_step_run
WHEN NEW.retry_of_step_run_id IS NOT NULL
BEGIN
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM pipeline_step_run prior
    WHERE prior.id=NEW.retry_of_step_run_id
      AND prior.pipeline_run_id=NEW.pipeline_run_id
      AND prior.step_code=NEW.step_code
  ) THEN RAISE(ABORT, 'retry must reference same run and step') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_step_terminal_immutable
BEFORE UPDATE ON pipeline_step_run
WHEN OLD.status IN ('SUCCEEDED','FAILED','BLOCKED_CONFIG','BLOCKED_DEPENDENCY',
                    'NEEDS_REVIEW','SKIPPED_CONDITION','CANCELLED')
BEGIN
  SELECT RAISE(ABORT, 'terminal step run is immutable');
END;

CREATE TABLE IF NOT EXISTS catalog_job (
  id INTEGER PRIMARY KEY,
  job_key TEXT NOT NULL UNIQUE,
  job_code TEXT NOT NULL,
  actor TEXT NOT NULL,
  approved_by TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','BLOCKED')),
  payload_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(payload_json)),
  result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
  error_text TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS runtime_setting (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO runtime_setting(key,value) VALUES
  ('runtime_mode','LEGACY'),
  ('strict_execution_control','off');
