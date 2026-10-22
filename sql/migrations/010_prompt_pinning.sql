-- Migration 010 - pin compiled prompt inputs and lock approved prompts.
-- Additive only. Existing prompt rows get empty snapshot hashes; new compiler
-- writes populated values. Assets remain content-addressed in asset_blob.

ALTER TABLE shot_prompt_spec ADD COLUMN catalog_snapshot_sha256 TEXT NOT NULL DEFAULT '';
ALTER TABLE shot_prompt_spec ADD COLUMN outfit_snapshot_sha256 TEXT NOT NULL DEFAULT '';

ALTER TABLE shot_prompt_tag ADD COLUMN target_character_id INTEGER
 REFERENCES character_profile(id) ON DELETE RESTRICT;

CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_tag_direction
BEFORE INSERT ON shot_prompt_tag
WHEN NEW.character_id IS NOT NULL AND NEW.character_id=NEW.target_character_id
BEGIN SELECT RAISE(ABORT,'prompt interaction actor and target must differ'); END;

CREATE TABLE IF NOT EXISTS shot_prompt_outfit_input (
 shot_prompt_revision_id INTEGER NOT NULL REFERENCES shot_prompt_revision(id) ON DELETE RESTRICT,
 character_id INTEGER NOT NULL REFERENCES character_profile(id) ON DELETE RESTRICT,
 outfit_revision_id INTEGER NOT NULL REFERENCES outfit_revision(id) ON DELETE RESTRICT,
 PRIMARY KEY(shot_prompt_revision_id,character_id)
);
CREATE INDEX IF NOT EXISTS idx_prompt_outfit_revision
 ON shot_prompt_outfit_input(outfit_revision_id);

CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_lock_insert
BEFORE INSERT ON shot_prompt_tag
WHEN (SELECT status FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id) <> 'draft'
BEGIN SELECT RAISE(ABORT,'approved prompt tags are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_lock_update
BEFORE UPDATE ON shot_prompt_tag
WHEN (SELECT status FROM shot_prompt_revision WHERE id=OLD.shot_prompt_revision_id) <> 'draft'
BEGIN SELECT RAISE(ABORT,'approved prompt tags are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_lock_delete
BEFORE DELETE ON shot_prompt_tag
WHEN (SELECT status FROM shot_prompt_revision WHERE id=OLD.shot_prompt_revision_id) <> 'draft'
BEGIN SELECT RAISE(ABORT,'approved prompt tags are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_content_lock
BEFORE UPDATE OF positive_tags,negative_prompt,natural_prompt,source_shot_spec_sha256,
 compiler_version,content_sha256 ON shot_prompt_revision
WHEN OLD.status <> 'draft'
BEGIN SELECT RAISE(ABORT,'approved prompt revision is immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_outfit_lock
BEFORE INSERT ON shot_prompt_outfit_input
WHEN (SELECT status FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id) <> 'draft'
BEGIN SELECT RAISE(ABORT,'approved prompt outfit inputs are immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_outfit_lock_update
BEFORE UPDATE ON shot_prompt_outfit_input
WHEN (SELECT status FROM shot_prompt_revision WHERE id=OLD.shot_prompt_revision_id) <> 'draft'
BEGIN SELECT RAISE(ABORT,'approved prompt outfit inputs are immutable'); END;
