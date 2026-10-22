-- Migration 006 - Relational normalization (additive)
-- Reviewed from V4 DRAFT (docs/v4/sql/proposals/006_normalization_DRAFT.sql), 2026-10-22.
-- Apply only through src/novel2anima/storage/migrations.py on a staging copy.
-- Legacy columns are retained for backward compatibility; content backfill is a later PR.

-- Versioned character identity: old character_profile.identity_json becomes a legacy projection.
CREATE TABLE IF NOT EXISTS character_identity_revision (
 id INTEGER PRIMARY KEY,
 character_id INTEGER NOT NULL REFERENCES character_profile(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK(revision>0),
 identity_json TEXT NOT NULL CHECK(json_valid(identity_json) AND json_type(identity_json)='object'),
 reference_asset_id INTEGER REFERENCES asset_blob(id) ON DELETE RESTRICT,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','retired')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(character_id,revision)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_character_identity_approved ON character_identity_revision(character_id)
 WHERE status='approved';

-- One shot = one page/panel. One shot can contain one or two (or more) participants.
-- A character may be used only inside the same project as the act's project.
CREATE TABLE IF NOT EXISTS shot_participant (
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE RESTRICT,
 character_id INTEGER NOT NULL REFERENCES character_profile(id) ON DELETE RESTRICT,
 slot_no INTEGER NOT NULL CHECK(slot_no BETWEEN 1 AND 8),
 scene_role TEXT NOT NULL DEFAULT 'subject' CHECK(scene_role IN ('subject','support','background')),
 PRIMARY KEY(shot_id,character_id),
 UNIQUE(shot_id,slot_no)
);
CREATE INDEX IF NOT EXISTS idx_shot_participant_character ON shot_participant(character_id,shot_id);
CREATE TRIGGER IF NOT EXISTS trg_shot_participant_project_insert
BEFORE INSERT ON shot_participant
WHEN (SELECT a.project_id FROM shot s JOIN act a ON a.id=s.act_id WHERE s.id=NEW.shot_id)
   <> (SELECT c.project_id FROM character_profile c WHERE c.id=NEW.character_id)
BEGIN SELECT RAISE(ABORT,'participant character belongs to another project'); END;
CREATE TRIGGER IF NOT EXISTS trg_shot_participant_project_update
BEFORE UPDATE OF shot_id,character_id ON shot_participant
WHEN (SELECT a.project_id FROM shot s JOIN act a ON a.id=s.act_id WHERE s.id=NEW.shot_id)
   <> (SELECT c.project_id FROM character_profile c WHERE c.id=NEW.character_id)
BEGIN SELECT RAISE(ABORT,'participant character belongs to another project'); END;

-- Directed action is explicit: actor != target; both MUST belong to this shot.
CREATE TABLE IF NOT EXISTS shot_interaction (
 id INTEGER PRIMARY KEY,
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE RESTRICT,
 actor_character_id INTEGER NOT NULL,
 target_character_id INTEGER NOT NULL,
 action_code TEXT NOT NULL CHECK(length(trim(action_code))>0),
 action_concept_id INTEGER REFERENCES visual_concept(id) ON DELETE RESTRICT,
 body_target TEXT,
 instruction TEXT NOT NULL DEFAULT '',
 sort_order INTEGER NOT NULL DEFAULT 1 CHECK(sort_order>0),
 CHECK(actor_character_id<>target_character_id),
 FOREIGN KEY(shot_id,actor_character_id) REFERENCES shot_participant(shot_id,character_id) ON DELETE RESTRICT,
 FOREIGN KEY(shot_id,target_character_id) REFERENCES shot_participant(shot_id,character_id) ON DELETE RESTRICT,
 UNIQUE(shot_id,sort_order)
);
CREATE INDEX IF NOT EXISTS idx_shot_interaction_actor ON shot_interaction(actor_character_id,shot_id);

-- Split garment identity into immutable per-item details. No LLM-dependent unnamed garment substitution.
CREATE TABLE IF NOT EXISTS outfit_item (
 id INTEGER PRIMARY KEY,
 outfit_revision_id INTEGER NOT NULL REFERENCES outfit_revision(id) ON DELETE RESTRICT,
 item_code TEXT NOT NULL CHECK(length(trim(item_code))>0),
 slot TEXT NOT NULL CHECK(length(trim(slot))>0),
 garment_type TEXT NOT NULL,
 silhouette TEXT NOT NULL DEFAULT '',
 cut TEXT NOT NULL DEFAULT '',
 material TEXT NOT NULL DEFAULT '',
 base_color TEXT NOT NULL DEFAULT '',
 pattern TEXT NOT NULL DEFAULT '',
 details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json) AND json_type(details_json)='object'),
 exact_anchor_asset_id INTEGER REFERENCES asset_blob(id) ON DELETE RESTRICT,
 UNIQUE(outfit_revision_id,item_code)
);
CREATE INDEX IF NOT EXISTS idx_outfit_item_revision_slot ON outfit_item(outfit_revision_id,slot);

-- Exactly identify ShotSpec version independently of the mutable legacy JSON field.
CREATE TABLE IF NOT EXISTS shot_spec_revision (
 id INTEGER PRIMARY KEY,
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK(revision>0),
 source_document_revision_id INTEGER REFERENCES project_document_revision(id) ON DELETE RESTRICT,
 spec_json TEXT NOT NULL CHECK(json_valid(spec_json) AND json_type(spec_json)='object'),
 spec_sha256 TEXT NOT NULL CHECK(length(spec_sha256)=64),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','retired')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(shot_id,revision)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_shot_spec_approved ON shot_spec_revision(shot_id) WHERE status='approved';

-- Relational tag retrieval/role bindings; positive_tags stays a deterministic frozen export snapshot.
CREATE TABLE IF NOT EXISTS shot_prompt_tag (
 shot_prompt_revision_id INTEGER NOT NULL REFERENCES shot_prompt_revision(id) ON DELETE RESTRICT,
 seq INTEGER NOT NULL CHECK(seq>0),
 tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE RESTRICT,
 character_id INTEGER REFERENCES character_profile(id) ON DELETE RESTRICT,
 token_role TEXT NOT NULL CHECK(token_role IN ('identity','outfit','action','expression','pose','camera','background','style','interaction','other')),
 weight REAL NOT NULL DEFAULT 1.0 CHECK(weight>0),
 PRIMARY KEY(shot_prompt_revision_id,seq)
);
CREATE INDEX IF NOT EXISTS idx_shot_prompt_tag_tag ON shot_prompt_tag(tag_id);

-- Existing shot_outfit_binding lacks multi-table verification. Repair only after
-- backfilling shot_participant in the staging migration.
CREATE TRIGGER IF NOT EXISTS trg_shot_outfit_binding_insert
BEFORE INSERT ON shot_outfit_binding
WHEN (SELECT character_id FROM outfit_revision WHERE id=NEW.outfit_revision_id)<>NEW.character_id
  OR NOT EXISTS (SELECT 1 FROM shot_participant
                 WHERE shot_id=NEW.shot_id AND character_id=NEW.character_id)
BEGIN SELECT RAISE(ABORT,'outfit must belong to a shot participant and the same character'); END;
CREATE TRIGGER IF NOT EXISTS trg_shot_outfit_binding_update
BEFORE UPDATE OF shot_id,character_id,outfit_revision_id ON shot_outfit_binding
WHEN (SELECT character_id FROM outfit_revision WHERE id=NEW.outfit_revision_id)<>NEW.character_id
  OR NOT EXISTS (SELECT 1 FROM shot_participant
                 WHERE shot_id=NEW.shot_id AND character_id=NEW.character_id)
BEGIN SELECT RAISE(ABORT,'outfit must belong to a shot participant and the same character'); END;

-- Cross-check that a prompt revision used for a render belongs to the same shot.
CREATE TABLE IF NOT EXISTS generation_provenance (
 generation_id INTEGER PRIMARY KEY REFERENCES generation(id) ON DELETE RESTRICT,
 shot_prompt_revision_id INTEGER NOT NULL REFERENCES shot_prompt_revision(id) ON DELETE RESTRICT,
 pipeline_run_id INTEGER REFERENCES pipeline_run(id) ON DELETE RESTRICT,
 model_settings_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(model_settings_json)),
 outfit_snapshot_sha256 TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TRIGGER IF NOT EXISTS trg_generation_provenance_insert
BEFORE INSERT ON generation_provenance
WHEN (SELECT shot_id FROM generation WHERE id=NEW.generation_id)
   <> (SELECT shot_id FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id)
BEGIN SELECT RAISE(ABORT,'generation and prompt must belong to same shot'); END;
CREATE TRIGGER IF NOT EXISTS trg_generation_provenance_update
BEFORE UPDATE OF generation_id,shot_prompt_revision_id ON generation_provenance
WHEN (SELECT shot_id FROM generation WHERE id=NEW.generation_id)
   <> (SELECT shot_id FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id)
BEGIN SELECT RAISE(ABORT,'generation and prompt must belong to same shot'); END;

-- QA findings need run/attempt history; legacy shot_finding remains a latest-state projection.
CREATE TABLE IF NOT EXISTS qa_run (
 id INTEGER PRIMARY KEY,
 pipeline_run_id INTEGER REFERENCES pipeline_run(id) ON DELETE RESTRICT,
 act_id INTEGER NOT NULL REFERENCES act(id) ON DELETE RESTRICT,
 run_key TEXT NOT NULL UNIQUE,
 evaluator_version TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TEXT
);
CREATE TABLE IF NOT EXISTS qa_issue (
 id INTEGER PRIMARY KEY,
 qa_run_id INTEGER NOT NULL REFERENCES qa_run(id) ON DELETE RESTRICT,
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE RESTRICT,
 rule_id TEXT NOT NULL,
 source TEXT NOT NULL,
 actor_character_id INTEGER REFERENCES character_profile(id) ON DELETE RESTRICT,
 target_character_id INTEGER REFERENCES character_profile(id) ON DELETE RESTRICT,
 severity REAL NOT NULL CHECK(severity BETWEEN 0 AND 1),
 evidence_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(evidence_json)),
 decision TEXT NOT NULL DEFAULT 'open' CHECK(decision IN ('open','fixed','accepted','dismissed')),
 UNIQUE(qa_run_id,shot_id,rule_id,source)
);
CREATE INDEX IF NOT EXISTS idx_qa_issue_shot ON qa_issue(shot_id,qa_run_id);

-- Immutable continuity observations or approved claims; shot_state remains derived latest view.
CREATE TABLE IF NOT EXISTS continuity_assertion (
 id INTEGER PRIMARY KEY,
 shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE RESTRICT,
 character_id INTEGER,
 axis TEXT NOT NULL,
 value_tag_id INTEGER REFERENCES tag(id) ON DELETE RESTRICT,
 source TEXT NOT NULL CHECK(source IN ('user','llm','inference','qa','system')),
 llm_run_id INTEGER REFERENCES llm_run(id) ON DELETE RESTRICT,
 evidence_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(evidence_json)),
 confidence REAL NOT NULL DEFAULT 1 CHECK(confidence BETWEEN 0 AND 1),
 state TEXT NOT NULL DEFAULT 'proposed' CHECK(state IN ('proposed','approved','rejected')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(shot_id,character_id) REFERENCES shot_participant(shot_id,character_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_continuity_shot_axis ON continuity_assertion(shot_id,axis);

-- Link multiple source snapshots to one tag relation, avoiding single-source provenance loss.
CREATE TABLE IF NOT EXISTS tag_relation_source (
 from_tag_id INTEGER NOT NULL,
 to_tag_id INTEGER NOT NULL,
 relation TEXT NOT NULL,
 source_snapshot_id INTEGER NOT NULL REFERENCES source_snapshot(id) ON DELETE RESTRICT,
 source_ref TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(from_tag_id,to_tag_id,relation,source_snapshot_id,source_ref),
 FOREIGN KEY(from_tag_id,to_tag_id,relation)
 REFERENCES tag_relation(from_tag_id,to_tag_id,relation) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tag_relation_source_snapshot ON tag_relation_source(source_snapshot_id);

-- Capture tag alias disagreements without silently overriding the chosen canonical tag.
CREATE TABLE IF NOT EXISTS tag_alias_conflict (
 id INTEGER PRIMARY KEY,
 alias_name TEXT NOT NULL,
 existing_tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE RESTRICT,
 candidate_tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE RESTRICT,
 source_snapshot_id INTEGER REFERENCES source_snapshot(id) ON DELETE RESTRICT,
 rationale TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'unresolved' CHECK(status IN ('unresolved','resolved','ignored')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(existing_tag_id<>candidate_tag_id)
);
CREATE INDEX IF NOT EXISTS idx_tag_alias_conflict_name ON tag_alias_conflict(alias_name,status);

-- Per-stage retry history (LLM/compile/render/QA). Each attempt is an immutable execution event.
CREATE TABLE IF NOT EXISTS pipeline_step_run (
 id INTEGER PRIMARY KEY,
 pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_run(id) ON DELETE RESTRICT,
 stage_key TEXT NOT NULL,
 attempt INTEGER NOT NULL CHECK(attempt>0),
 status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','skipped')),
 input_sha256 TEXT NOT NULL,
 output_sha256 TEXT,
 details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json)),
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at TEXT,
 UNIQUE(pipeline_run_id,stage_key,attempt)
);

-- Protect historical approved content even if someone first changes status.
CREATE TRIGGER IF NOT EXISTS trg_character_identity_revision_guard
BEFORE UPDATE ON character_identity_revision
WHEN OLD.status='approved' AND (
 NEW.identity_json<>OLD.identity_json OR NEW.sha256<>OLD.sha256 OR
 NEW.reference_asset_id IS NOT OLD.reference_asset_id)
BEGIN SELECT RAISE(ABORT,'approved character identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_shot_spec_revision_guard
BEFORE UPDATE ON shot_spec_revision
WHEN OLD.status='approved' AND (
 NEW.spec_json<>OLD.spec_json OR NEW.spec_sha256<>OLD.spec_sha256 OR
 NEW.source_document_revision_id IS NOT OLD.source_document_revision_id)
BEGIN SELECT RAISE(ABORT,'approved shot spec is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_outfit_item_guard_update
BEFORE UPDATE ON outfit_item
WHEN (SELECT status FROM outfit_revision WHERE id=OLD.outfit_revision_id)='approved'
BEGIN SELECT RAISE(ABORT,'approved outfit items are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_outfit_item_guard_delete
BEFORE DELETE ON outfit_item
WHEN (SELECT status FROM outfit_revision WHERE id=OLD.outfit_revision_id)='approved'
BEGIN SELECT RAISE(ABORT,'approved outfit items are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_outfit_item_guard_insert
BEFORE INSERT ON outfit_item
WHEN (SELECT status FROM outfit_revision WHERE id=NEW.outfit_revision_id)='approved'
BEGIN SELECT RAISE(ABORT,'approved outfit items are immutable'); END;

-- Supporting read paths; validate usage before indexing large catalog tables.
CREATE INDEX IF NOT EXISTS idx_shot_character_legacy ON shot(character_id);
CREATE INDEX IF NOT EXISTS idx_shot_finding_source ON shot_finding(source,shot_id);
CREATE INDEX IF NOT EXISTS idx_llm_run_shot ON llm_run(shot_id,created_at);
CREATE INDEX IF NOT EXISTS idx_outfit_revision_char ON outfit_revision(character_id,status);
CREATE INDEX IF NOT EXISTS idx_generation_asset_asset ON generation_asset(asset_id);

-- Version-to-version traceability; a prompt cannot point at a different shot's spec.
CREATE TABLE IF NOT EXISTS shot_prompt_spec (
 shot_prompt_revision_id INTEGER PRIMARY KEY REFERENCES shot_prompt_revision(id) ON DELETE RESTRICT,
 shot_spec_revision_id INTEGER NOT NULL REFERENCES shot_spec_revision(id) ON DELETE RESTRICT
);
CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_spec_insert
BEFORE INSERT ON shot_prompt_spec
WHEN (SELECT shot_id FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id)
   <> (SELECT shot_id FROM shot_spec_revision WHERE id=NEW.shot_spec_revision_id)
BEGIN SELECT RAISE(ABORT,'prompt and spec belong to different shots'); END;
CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_spec_update
BEFORE UPDATE ON shot_prompt_spec
WHEN (SELECT shot_id FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id)
   <> (SELECT shot_id FROM shot_spec_revision WHERE id=NEW.shot_spec_revision_id)
BEGIN SELECT RAISE(ABORT,'prompt and spec belong to different shots'); END;

-- Once a shot is accepted/rendered/locked, treat the participant and action
-- projection as immutable; a new act revision/shot row is required to change it.
CREATE TRIGGER IF NOT EXISTS trg_participant_insert_frozen BEFORE INSERT ON shot_participant
WHEN (SELECT status FROM shot WHERE id=NEW.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot participants are frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_participant_update_frozen BEFORE UPDATE ON shot_participant
WHEN (SELECT status FROM shot WHERE id=OLD.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot participants are frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_participant_delete_frozen BEFORE DELETE ON shot_participant
WHEN (SELECT status FROM shot WHERE id=OLD.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot participants are frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_interaction_insert_frozen BEFORE INSERT ON shot_interaction
WHEN (SELECT status FROM shot WHERE id=NEW.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot interactions are frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_interaction_update_frozen BEFORE UPDATE ON shot_interaction
WHEN (SELECT status FROM shot WHERE id=OLD.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot interactions are frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_interaction_delete_frozen BEFORE DELETE ON shot_interaction
WHEN (SELECT status FROM shot WHERE id=OLD.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot interactions are frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_binding_insert_frozen BEFORE INSERT ON shot_outfit_binding
WHEN (SELECT status FROM shot WHERE id=NEW.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot outfit binding is frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_binding_update_frozen BEFORE UPDATE ON shot_outfit_binding
WHEN (SELECT status FROM shot WHERE id=OLD.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot outfit binding is frozen'); END;
CREATE TRIGGER IF NOT EXISTS trg_binding_delete_frozen BEFORE DELETE ON shot_outfit_binding
WHEN (SELECT status FROM shot WHERE id=OLD.shot_id) IN ('approved','generated','locked')
BEGIN SELECT RAISE(ABORT,'approved shot outfit binding is frozen'); END;

-- Restrict archived statuses from returning to draft: approved -> retired only.
CREATE TRIGGER IF NOT EXISTS trg_outfit_revision_state_lock BEFORE UPDATE ON outfit_revision
WHEN OLD.status IN ('approved','retired') AND (
 NEW.status NOT IN ('approved','retired') OR NEW.spec_json<>OLD.spec_json OR
 NEW.spec_sha256<>OLD.spec_sha256 OR NEW.anchor_asset_id IS NOT OLD.anchor_asset_id)
BEGIN SELECT RAISE(ABORT,'locked outfit revision cannot be changed'); END;
CREATE TRIGGER IF NOT EXISTS trg_identity_revision_state_lock BEFORE UPDATE ON character_identity_revision
WHEN OLD.status IN ('approved','retired') AND (
 NEW.status NOT IN ('approved','retired') OR NEW.identity_json<>OLD.identity_json OR
 NEW.sha256<>OLD.sha256 OR NEW.reference_asset_id IS NOT OLD.reference_asset_id)
BEGIN SELECT RAISE(ABORT,'locked character identity revision cannot be changed'); END;
CREATE TRIGGER IF NOT EXISTS trg_shot_spec_revision_state_lock BEFORE UPDATE ON shot_spec_revision
WHEN OLD.status IN ('approved','retired') AND (
 NEW.status NOT IN ('approved','retired') OR NEW.spec_json<>OLD.spec_json OR
 NEW.spec_sha256<>OLD.spec_sha256)
BEGIN SELECT RAISE(ABORT,'locked shot spec revision cannot be changed'); END;
CREATE TRIGGER IF NOT EXISTS trg_shot_prompt_revision_state_lock BEFORE UPDATE ON shot_prompt_revision
WHEN OLD.status IN ('approved','retired') AND (
 NEW.status NOT IN ('approved','retired') OR NEW.positive_tags<>OLD.positive_tags OR
 NEW.negative_prompt<>OLD.negative_prompt OR NEW.natural_prompt IS NOT OLD.natural_prompt OR
 NEW.content_sha256<>OLD.content_sha256)
BEGIN SELECT RAISE(ABORT,'locked prompt revision cannot be changed'); END;
CREATE TRIGGER IF NOT EXISTS trg_document_revision_state_lock BEFORE UPDATE ON project_document_revision
WHEN OLD.lifecycle IN ('approved','superseded') AND (
 NEW.lifecycle='draft' OR NEW.body_json<>OLD.body_json OR NEW.body_sha256<>OLD.body_sha256)
BEGIN SELECT RAISE(ABORT,'locked document revision cannot be changed'); END;
CREATE TRIGGER IF NOT EXISTS trg_prompt_tag_locked_insert BEFORE INSERT ON shot_prompt_tag
WHEN (SELECT status FROM shot_prompt_revision WHERE id=NEW.shot_prompt_revision_id) IN ('approved','retired')
BEGIN SELECT RAISE(ABORT,'cannot edit tags of locked prompt'); END;
CREATE TRIGGER IF NOT EXISTS trg_prompt_tag_locked_update BEFORE UPDATE ON shot_prompt_tag
WHEN (SELECT status FROM shot_prompt_revision WHERE id=OLD.shot_prompt_revision_id) IN ('approved','retired')
BEGIN SELECT RAISE(ABORT,'cannot edit tags of locked prompt'); END;
CREATE TRIGGER IF NOT EXISTS trg_prompt_tag_locked_delete BEFORE DELETE ON shot_prompt_tag
WHEN (SELECT status FROM shot_prompt_revision WHERE id=OLD.shot_prompt_revision_id) IN ('approved','retired')
BEGIN SELECT RAISE(ABORT,'cannot edit tags of locked prompt'); END;

-- Prevent editing parent relationships to bypass cross-project / same-shot triggers.
CREATE TRIGGER IF NOT EXISTS trg_act_project_frozen BEFORE UPDATE OF project_id ON act
WHEN OLD.project_id<>NEW.project_id
BEGIN SELECT RAISE(ABORT,'act cannot be reassigned to another project'); END;
CREATE TRIGGER IF NOT EXISTS trg_character_project_frozen BEFORE UPDATE OF project_id ON character_profile
WHEN OLD.project_id<>NEW.project_id
BEGIN SELECT RAISE(ABORT,'character cannot be reassigned to another project'); END;
CREATE TRIGGER IF NOT EXISTS trg_shot_act_frozen BEFORE UPDATE OF act_id ON shot
WHEN OLD.act_id<>NEW.act_id
BEGIN SELECT RAISE(ABORT,'shot cannot be moved to another act'); END;
CREATE TRIGGER IF NOT EXISTS trg_outfit_character_frozen BEFORE UPDATE OF character_id ON outfit_revision
WHEN OLD.character_id<>NEW.character_id
BEGIN SELECT RAISE(ABORT,'outfit revision cannot be reassigned to another character'); END;
CREATE TRIGGER IF NOT EXISTS trg_generation_shot_frozen BEFORE UPDATE OF shot_id ON generation
WHEN OLD.shot_id<>NEW.shot_id
BEGIN SELECT RAISE(ABORT,'render cannot be reassigned to another shot'); END;
CREATE TRIGGER IF NOT EXISTS trg_prompt_shot_frozen BEFORE UPDATE OF shot_id ON shot_prompt_revision
WHEN OLD.shot_id<>NEW.shot_id
BEGIN SELECT RAISE(ABORT,'prompt revision cannot be reassigned to another shot'); END;
CREATE TRIGGER IF NOT EXISTS trg_spec_shot_frozen BEFORE UPDATE OF shot_id ON shot_spec_revision
WHEN OLD.shot_id<>NEW.shot_id
BEGIN SELECT RAISE(ABORT,'spec revision cannot be reassigned to another shot'); END;

-- Do not silently replace production LLM instructions or settings in-place.
CREATE TRIGGER IF NOT EXISTS trg_llm_prompt_template_lock BEFORE UPDATE ON llm_prompt_template
WHEN OLD.status IN ('active','retired') AND (
 NEW.status='draft' OR NEW.system_text<>OLD.system_text OR NEW.task_text<>OLD.task_text OR
 NEW.examples_text<>OLD.examples_text OR NEW.content_sha256<>OLD.content_sha256 OR
 NEW.input_schema_json<>OLD.input_schema_json OR NEW.output_schema_json<>OLD.output_schema_json)
BEGIN SELECT RAISE(ABORT,'active/retired LLM prompt template is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_setting_revision_lock BEFORE UPDATE ON n2a_setting_revision
WHEN OLD.status IN ('active','retired') AND (
 NEW.status='draft' OR NEW.value_json<>OLD.value_json OR NEW.content_sha256<>OLD.content_sha256)
BEGIN SELECT RAISE(ABORT,'active/retired setting revision is immutable'); END;
