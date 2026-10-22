-- DRAFT ONLY: Novel2Anima DB-first extension, 2026-10-22
-- Do NOT copy into sql/migrations until migration runner, backup and staging tests are approved.
-- Assumes the existing schema_v1 + migrations 002-004 are already installed.
-- This is additive schema only; does not migrate real content or remove legacy tables/columns.

CREATE TABLE IF NOT EXISTS n2a_schema_migration (
 version TEXT PRIMARY KEY,
 sha256 TEXT NOT NULL,
 applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Source configuration is not the same as existing source_snapshot (actual imports).
CREATE TABLE IF NOT EXISTS catalog_source_config (
 source_key TEXT PRIMARY KEY,
 enabled INTEGER NOT NULL CHECK (enabled IN (0,1)),
 revision TEXT NOT NULL,
 url_template TEXT,
 file_list_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(file_list_json)),
 policy_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(policy_json)),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Immutable imported project documents (published entities remain in existing tables).
CREATE TABLE IF NOT EXISTS project_document_revision (
 id INTEGER PRIMARY KEY,
 project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
 act_id INTEGER REFERENCES act(id) ON DELETE RESTRICT,
 scope_key TEXT NOT NULL DEFAULT '',
 kind TEXT NOT NULL CHECK(kind IN ('brief','story','act_spec','shot_plan','legacy_plan','other')),
 revision INTEGER NOT NULL CHECK(revision>0),
 schema_version TEXT NOT NULL,
 body_json TEXT NOT NULL CHECK(json_valid(body_json)),
 body_sha256 TEXT NOT NULL,
 lifecycle TEXT NOT NULL DEFAULT 'draft' CHECK(lifecycle IN ('draft','approved','superseded')),
 provenance_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(provenance_json)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(project_id,scope_key,kind,revision)
);
CREATE INDEX IF NOT EXISTS idx_document_act ON project_document_revision(act_id, kind, revision);

-- Global or per-project editable settings, never hardcoded JSON settings at runtime.
CREATE TABLE IF NOT EXISTS n2a_setting_revision (
 id INTEGER PRIMARY KEY,
 scope TEXT NOT NULL DEFAULT 'global',
 setting_key TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0),
 value_json TEXT NOT NULL CHECK(json_valid(value_json)),
 content_sha256 TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active','retired')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(scope,setting_key,revision)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_n2a_setting_active ON n2a_setting_revision(scope,setting_key)
 WHERE status='active';

-- LLM folder .txt files are zero-byte placeholders, NOT production prompt storage.
CREATE TABLE IF NOT EXISTS llm_prompt_template (
 id INTEGER PRIMARY KEY,
 stage TEXT NOT NULL CHECK(stage IN
  ('01_brief','02_story','03_character','04_wardrobe','05_act_beats',
   '06_shot_direction','07_catalog_selection','08_natural_prompt',
   '09_semantic_review','10_visual_qc','11_targeted_revision')),
 revision INTEGER NOT NULL CHECK(revision>0),
 system_text TEXT NOT NULL DEFAULT '',
 task_text TEXT NOT NULL DEFAULT '',
 examples_text TEXT NOT NULL DEFAULT '',
 input_schema_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(input_schema_json)),
 output_schema_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(output_schema_json)),
 content_sha256 TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active','retired')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(stage,revision),
 CHECK(status<>'active' OR (length(trim(system_text))>0 AND length(trim(task_text))>0))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_llm_template_active ON llm_prompt_template(stage) WHERE status='active';

-- Store binary content, not just path/hash. Deduplicated by digest. Check hash in application.
CREATE TABLE IF NOT EXISTS asset_blob (
 id INTEGER PRIMARY KEY,
 sha256 TEXT NOT NULL UNIQUE,
 mime_type TEXT NOT NULL,
 original_name TEXT,
 byte_length INTEGER NOT NULL CHECK(byte_length>=0),
 body BLOB NOT NULL,
 metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(byte_length=length(body))
);

-- New outfit spec revisions avoid silently replacing character_profile.outfit_json.
CREATE TABLE IF NOT EXISTS outfit_revision (
 id INTEGER PRIMARY KEY,
 character_id INTEGER NOT NULL REFERENCES character_profile(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK(revision>0),
 spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
 anchor_asset_id INTEGER REFERENCES asset_blob(id) ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','retired')),
 spec_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(character_id,revision)
);
CREATE TABLE IF NOT EXISTS shot_outfit_binding (
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE RESTRICT,
 character_id INTEGER NOT NULL REFERENCES character_profile(id) ON DELETE RESTRICT,
 outfit_revision_id INTEGER NOT NULL REFERENCES outfit_revision(id) ON DELETE RESTRICT,
 PRIMARY KEY(shot_id,character_id)
);

-- Prompt for each shot and its exact revision; a generated TXT is only an export.
CREATE TABLE IF NOT EXISTS shot_prompt_revision (
 id INTEGER PRIMARY KEY,
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK(revision>0),
 positive_tags TEXT NOT NULL,
 negative_prompt TEXT NOT NULL,
 natural_prompt TEXT,
 source_shot_spec_sha256 TEXT NOT NULL,
 compiler_version TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','retired')),
 content_sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(shot_id,revision)
);
CREATE INDEX IF NOT EXISTS idx_shot_prompt_shot ON shot_prompt_revision(shot_id,status);

CREATE TABLE IF NOT EXISTS pipeline_run (
 id INTEGER PRIMARY KEY,
 project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
 act_id INTEGER REFERENCES act(id) ON DELETE RESTRICT,
 run_key TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','blocked')),
 input_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(input_json)),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT
);
CREATE TABLE IF NOT EXISTS llm_run (
 id INTEGER PRIMARY KEY,
 pipeline_run_id INTEGER REFERENCES pipeline_run(id) ON DELETE RESTRICT,
 project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE RESTRICT,
 act_id INTEGER REFERENCES act(id) ON DELETE RESTRICT,
 shot_id INTEGER REFERENCES shot(id) ON DELETE RESTRICT,
 template_id INTEGER NOT NULL REFERENCES llm_prompt_template(id) ON DELETE RESTRICT,
 execution_key TEXT NOT NULL UNIQUE,
 model_provider TEXT NOT NULL,
 model_name TEXT NOT NULL,
 request_json TEXT NOT NULL CHECK(json_valid(request_json)),
 response_json TEXT CHECK(response_json IS NULL OR json_valid(response_json)),
 output_json TEXT CHECK(output_json IS NULL OR json_valid(output_json)),
 validation_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(validation_json)),
 status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','invalid','failed')),
 error_text TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_run_act ON llm_run(act_id,created_at);

-- Keep raw source snapshots when complete reproducibility is required.
CREATE TABLE IF NOT EXISTS import_batch (
 id INTEGER PRIMARY KEY,
 source_snapshot_id INTEGER REFERENCES source_snapshot(id) ON DELETE RESTRICT,
 import_key TEXT NOT NULL UNIQUE,
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
 summary_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(summary_json))
);
CREATE TABLE IF NOT EXISTS import_batch_file (
 import_batch_id INTEGER NOT NULL REFERENCES import_batch(id) ON DELETE RESTRICT,
 asset_id INTEGER NOT NULL REFERENCES asset_blob(id) ON DELETE RESTRICT,
 source_relative_name TEXT NOT NULL,
 PRIMARY KEY(import_batch_id,source_relative_name)
);

-- Instead of relying on generation.image_path or filesystem asset links.
CREATE TABLE IF NOT EXISTS generation_asset (
 generation_id INTEGER NOT NULL REFERENCES generation(id) ON DELETE RESTRICT,
 role TEXT NOT NULL CHECK(role IN ('render','thumbnail','mask','control','other')),
 asset_id INTEGER NOT NULL REFERENCES asset_blob(id) ON DELETE RESTRICT,
 PRIMARY KEY(generation_id,role,asset_id)
);
CREATE TABLE IF NOT EXISTS llm_run_asset (
 llm_run_id INTEGER NOT NULL REFERENCES llm_run(id) ON DELETE RESTRICT,
 asset_id INTEGER NOT NULL REFERENCES asset_blob(id) ON DELETE RESTRICT,
 role TEXT NOT NULL,
 PRIMARY KEY(llm_run_id,asset_id,role)
);

-- SQL-level guards: an approved text/spec body must not be changed in-place.
CREATE TRIGGER IF NOT EXISTS trg_n2a_approved_document_immutable
BEFORE UPDATE OF body_json,body_sha256,schema_version ON project_document_revision
WHEN OLD.lifecycle='approved'
BEGIN SELECT RAISE(ABORT,'approved document content is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_n2a_approved_outfit_immutable
BEFORE UPDATE OF spec_json,spec_sha256,anchor_asset_id ON outfit_revision
WHEN OLD.status='approved'
BEGIN SELECT RAISE(ABORT,'approved outfit content is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_n2a_approved_prompt_immutable
BEFORE UPDATE OF positive_tags,negative_prompt,natural_prompt,content_sha256,source_shot_spec_sha256
ON shot_prompt_revision WHEN OLD.status='approved'
BEGIN SELECT RAISE(ABORT,'approved shot prompt is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_n2a_asset_blob_immutable
BEFORE UPDATE OF body,sha256,byte_length ON asset_blob
BEGIN SELECT RAISE(ABORT,'asset blob is immutable'); END;
