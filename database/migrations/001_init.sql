-- Novel2Anima: SQLite local-first schema v1. Không có phụ thuộc Novel2Anima.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 1. Provenance: mỗi bản import có nguồn, external ID, payload gốc và giấy phép.
CREATE TABLE source_registry (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  homepage_url TEXT,
  license_label TEXT,
  license_url TEXT,
  usage_notes TEXT,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE import_runs (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source_registry(id),
  status TEXT NOT NULL CHECK(status IN ('RUNNING','COMPLETE','FAILED')),
  imported_count INTEGER NOT NULL DEFAULT 0,
  skipped_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json)),
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT
);
CREATE TABLE source_records (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES source_registry(id),
  external_key TEXT NOT NULL,
  entity_kind TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  retrieved_at TEXT NOT NULL DEFAULT (datetime('now')),
  import_run_id TEXT REFERENCES import_runs(id),
  UNIQUE(source_id, external_key)
);

CREATE TABLE source_record_versions (
  source_record_id TEXT NOT NULL REFERENCES source_records(id),
  content_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  imported_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (source_record_id, content_sha256)
);

-- 2. Catalog: vũ trụ, nhân vật, alias, identity, outfit, từ vựng, pose.
CREATE TABLE universes (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE characters (
  id TEXT PRIMARY KEY,
  universe_id TEXT REFERENCES universes(id),
  slug TEXT NOT NULL,
  display_name TEXT NOT NULL,
  age_status TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK(age_status IN ('UNKNOWN','CONFIRMED_ADULT','OTHER')),
  identity_description TEXT,
  identity_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(identity_json)),
  identity_review TEXT NOT NULL DEFAULT 'UNVERIFIED' CHECK(identity_review IN ('UNVERIFIED','REVIEWED','VERIFIED')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(universe_id, slug)
);
CREATE UNIQUE INDEX ux_original_character_slug ON characters(slug) WHERE universe_id IS NULL;
CREATE TABLE character_aliases (
  id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'und',
  source_record_id TEXT REFERENCES source_records(id),
  UNIQUE(character_id, name, language)
);
CREATE TABLE character_traits (
  id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  trait_group TEXT NOT NULL,
  trait_key TEXT NOT NULL,
  trait_value TEXT NOT NULL,
  source_record_id TEXT REFERENCES source_records(id),
  confidence TEXT NOT NULL DEFAULT 'CANDIDATE' CHECK(confidence IN ('CANDIDATE','REVIEWED','VERIFIED')),
  is_locked INTEGER NOT NULL DEFAULT 0 CHECK(is_locked IN (0,1)),
  UNIQUE(character_id, trait_group, trait_key, trait_value)
);
CREATE TABLE outfits (
  id TEXT PRIMARY KEY,
  character_id TEXT REFERENCES characters(id),
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  outfit_kind TEXT NOT NULL DEFAULT 'CUSTOM' CHECK(outfit_kind IN ('ORIGINAL','VARIANT','CUSTOM','GENERIC')),
  description TEXT,
  palette_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(palette_json)),
  verification TEXT NOT NULL DEFAULT 'UNVERIFIED' CHECK(verification IN ('UNVERIFIED','REVIEWED','VERIFIED')),
  source_record_id TEXT REFERENCES source_records(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(character_id, slug)
);
CREATE UNIQUE INDEX ux_generic_outfit_slug ON outfits(slug) WHERE character_id IS NULL;
CREATE TABLE outfit_parts (
  id TEXT PRIMARY KEY,
  outfit_id TEXT NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
  slot TEXT NOT NULL,
  description TEXT NOT NULL,
  color_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(color_json)),
  source_record_id TEXT REFERENCES source_records(id),
  UNIQUE(outfit_id, slot)
);
CREATE TABLE catalog_tags (
  id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL DEFAULT 'danbooru',
  name TEXT NOT NULL,
  category INTEGER,
  post_count INTEGER,
  deprecated INTEGER NOT NULL DEFAULT 0 CHECK(deprecated IN (0,1)),
  source_record_id TEXT REFERENCES source_records(id),
  UNIQUE(namespace, name)
);
CREATE TABLE character_tags (
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  tag_id TEXT NOT NULL REFERENCES catalog_tags(id),
  source_record_id TEXT REFERENCES source_records(id),
  tag_role TEXT NOT NULL DEFAULT 'CORE_CANDIDATE',
  PRIMARY KEY (character_id, tag_id)
);
CREATE TABLE vocabulary (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL CHECK(category IN
    ('POSE','ACTION','EXPRESSION','CAMERA','LIGHTING','LOCATION','STYLE','SPATIAL','GARMENT','OBJECT')),
  code TEXT NOT NULL,
  label_en TEXT NOT NULL,
  label_vi TEXT,
  description_en TEXT,
  synonyms_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(synonyms_json)),
  source_record_id TEXT REFERENCES source_records(id),
  review TEXT NOT NULL DEFAULT 'REVIEWED' CHECK(review IN ('UNVERIFIED','REVIEWED','VERIFIED')),
  UNIQUE(category, code)
);
CREATE TABLE vocabulary_relations (
  from_id TEXT NOT NULL REFERENCES vocabulary(id),
  relation TEXT NOT NULL,
  to_id TEXT NOT NULL REFERENCES vocabulary(id),
  PRIMARY KEY (from_id, relation, to_id)
);
CREATE TABLE pose_references (
  id TEXT PRIMARY KEY,
  vocabulary_id TEXT REFERENCES vocabulary(id),
  skeleton_format TEXT,
  skeleton_json TEXT CHECK(skeleton_json IS NULL OR json_valid(skeleton_json)),
  caption_en TEXT NOT NULL,
  source_record_id TEXT REFERENCES source_records(id),
  provenance_note TEXT
);
CREATE TABLE layout_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  participant_count INTEGER NOT NULL DEFAULT 1 CHECK(participant_count >= 0),
  scene_tags_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(scene_tags_json)),
  draft_json TEXT NOT NULL CHECK(json_valid(draft_json)),
  source_record_id TEXT REFERENCES source_records(id),
  verified INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1))
);

-- 3. Story: role tồn tại từ đầu, casting có thể thực hiện sau (Blind).
CREATE TABLE stories (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  cast_mode TEXT NOT NULL CHECK(cast_mode IN ('BLIND','NON_BLIND')),
  status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','PLANNED','READY','ARCHIVED')),
  current_revision INTEGER NOT NULL DEFAULT 1 CHECK(current_revision >= 1),
  content_policy_path TEXT NOT NULL DEFAULT 'docs/novel2anima/CONTENT_POLICY.md',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE story_sources (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  source_kind TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  raw_labels_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(raw_labels_json)),
  content_sha256 TEXT NOT NULL,
  source_record_id TEXT REFERENCES source_records(id),
  recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER story_sources_immutable_u BEFORE UPDATE ON story_sources
BEGIN SELECT RAISE(ABORT,'story_sources immutable: append a new version'); END;
CREATE TRIGGER story_sources_immutable_d BEFORE DELETE ON story_sources
BEGIN SELECT RAISE(ABORT,'story_sources immutable: append a new version'); END;
CREATE TABLE story_revisions (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  revision INTEGER NOT NULL CHECK(revision >= 1),
  plan_json TEXT NOT NULL CHECK(json_valid(plan_json)),
  source_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(story_id, revision)
);
CREATE TABLE story_roles (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  role_key TEXT NOT NULL,
  role_description TEXT,
  role_spec_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(role_spec_json)),
  UNIQUE(story_id, role_key)
);
CREATE TABLE story_castings (
  id TEXT PRIMARY KEY,
  story_role_id TEXT NOT NULL REFERENCES story_roles(id),
  character_id TEXT NOT NULL REFERENCES characters(id),
  outfit_id TEXT REFERENCES outfits(id),
  from_revision INTEGER NOT NULL CHECK(from_revision >= 1),
  until_revision INTEGER CHECK(until_revision IS NULL OR until_revision >= from_revision),
  assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
  note TEXT
);
CREATE UNIQUE INDEX ux_active_casting ON story_castings(story_role_id) WHERE until_revision IS NULL;
CREATE TABLE acts (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  act_order INTEGER NOT NULL CHECK(act_order >= 1),
  title TEXT,
  summary TEXT,
  spec_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(spec_json)),
  UNIQUE(story_id, act_order)
);
CREATE TABLE beats (
  id TEXT PRIMARY KEY,
  act_id TEXT NOT NULL REFERENCES acts(id),
  beat_order INTEGER NOT NULL CHECK(beat_order >= 1),
  summary TEXT,
  spec_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(spec_json)),
  UNIQUE(act_id, beat_order)
);
CREATE TABLE story_events (
  id TEXT PRIMARY KEY,
  beat_id TEXT NOT NULL REFERENCES beats(id),
  event_order INTEGER NOT NULL CHECK(event_order >= 1),
  actor_role_id TEXT REFERENCES story_roles(id),
  target_role_id TEXT REFERENCES story_roles(id),
  action TEXT NOT NULL,
  reaction TEXT,
  raw_labels_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(raw_labels_json)),
  source_fragment TEXT,
  spec_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(spec_json)),
  UNIQUE(beat_id, event_order)
);
CREATE TABLE shots (
  id TEXT PRIMARY KEY,
  beat_id TEXT NOT NULL REFERENCES beats(id),
  shot_key TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision >= 1),
  source_event_id TEXT REFERENCES story_events(id),
  shot_spec_json TEXT NOT NULL CHECK(json_valid(shot_spec_json)),
  fidelity_status TEXT NOT NULL DEFAULT 'PENDING',
  supersedes_shot_id TEXT REFERENCES shots(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(beat_id, shot_key, revision)
);
CREATE TABLE shot_participants (
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  story_role_id TEXT NOT NULL REFERENCES story_roles(id),
  pose_vocab_id TEXT REFERENCES vocabulary(id),
  outfit_override_id TEXT REFERENCES outfits(id),
  spec_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(spec_json)),
  PRIMARY KEY(shot_id, story_role_id)
);
CREATE TABLE shot_interactions (
  id TEXT PRIMARY KEY,
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  actor_role_id TEXT NOT NULL REFERENCES story_roles(id),
  target_role_id TEXT REFERENCES story_roles(id),
  action_vocab_id TEXT REFERENCES vocabulary(id),
  action_text TEXT NOT NULL,
  reaction_text TEXT,
  constraints_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(constraints_json))
);
CREATE TABLE continuity_snapshots (
  id TEXT PRIMARY KEY,
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  story_role_id TEXT REFERENCES story_roles(id),
  before_json TEXT NOT NULL CHECK(json_valid(before_json)),
  delta_json TEXT NOT NULL CHECK(json_valid(delta_json)),
  after_json TEXT NOT NULL CHECK(json_valid(after_json))
);
CREATE UNIQUE INDEX ux_continuity_by_role ON continuity_snapshots(shot_id, story_role_id) WHERE story_role_id IS NOT NULL;
CREATE UNIQUE INDEX ux_continuity_scene ON continuity_snapshots(shot_id) WHERE story_role_id IS NULL;

-- 4. MOSS Layout: lưu draft top-left xyxy và bản render đã compile riêng.
CREATE TABLE shot_layouts (
  id TEXT PRIMARY KEY,
  shot_id TEXT NOT NULL REFERENCES shots(id),
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision >= 1),
  width INTEGER NOT NULL CHECK(width > 0 AND width % 16 = 0),
  height INTEGER NOT NULL CHECK(height > 0 AND height % 16 = 0),
  canvas TEXT NOT NULL DEFAULT 'single',
  meta_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(meta_json)),
  summary_caption TEXT NOT NULL CHECK(length(summary_caption) > 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(shot_id,revision)
);
CREATE TABLE shot_layout_items (
  id TEXT PRIMARY KEY,
  layout_id TEXT NOT NULL REFERENCES shot_layouts(id) ON DELETE CASCADE,
  item_order INTEGER NOT NULL CHECK(item_order >= 1),
  label TEXT NOT NULL CHECK(label IN ('character','object','text')),
  story_role_id TEXT REFERENCES story_roles(id),
  caption TEXT NOT NULL CHECK(length(caption)>0),
  text_content TEXT,
  x_min INTEGER NOT NULL, y_min INTEGER NOT NULL, x_max INTEGER NOT NULL, y_max INTEGER NOT NULL,
  CHECK(x_min < x_max AND y_min < y_max),
  CHECK(label <> 'text' OR (text_content IS NOT NULL AND length(text_content) > 0)),
  UNIQUE(layout_id,item_order)
);
CREATE TABLE layout_exports (
  id TEXT PRIMARY KEY,
  layout_id TEXT NOT NULL REFERENCES shot_layouts(id),
  compiler_version TEXT NOT NULL,
  prompt_json TEXT NOT NULL CHECK(json_valid(prompt_json)),
  prompt_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(layout_id,prompt_sha256)
);
CREATE TABLE render_jobs (
  id TEXT PRIMARY KEY,
  layout_export_id TEXT NOT NULL REFERENCES layout_exports(id),
  backend TEXT NOT NULL,
  model_ref TEXT,
  seed INTEGER,
  parameters_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(parameters_json)),
  status TEXT NOT NULL DEFAULT 'QUEUED' CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
  output_dir TEXT,
  error_text TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT
);
CREATE TABLE render_assets (
  id TEXT PRIMARY KEY,
  render_job_id TEXT NOT NULL REFERENCES render_jobs(id),
  asset_kind TEXT NOT NULL,
  file_path TEXT NOT NULL,
  checksum_sha256 TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE qa_reports (
  id TEXT PRIMARY KEY,
  subject_kind TEXT NOT NULL CHECK(subject_kind IN ('STORY','SHOT','LAYOUT','RENDER')),
  subject_id TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('PASS','WARN','BLOCKED','SKIP')),
  policy_ref TEXT,
  report_json TEXT NOT NULL CHECK(json_valid(report_json)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX ix_characters_universe ON characters(universe_id);
CREATE INDEX ix_traits_char ON character_traits(character_id,trait_group);
CREATE INDEX ix_character_tags_tag ON character_tags(tag_id);
CREATE INDEX ix_vocab_cat ON vocabulary(category);
CREATE INDEX ix_external_entity ON source_records(source_id,entity_kind);
CREATE INDEX ix_story_roles_story ON story_roles(story_id);
CREATE INDEX ix_story_castings_char ON story_castings(character_id);
CREATE INDEX ix_story_sources_story ON story_sources(story_id);
CREATE INDEX ix_acts_story ON acts(story_id,act_order);
CREATE INDEX ix_beats_act ON beats(act_id,beat_order);
CREATE INDEX ix_events_beat ON story_events(beat_id,event_order);
CREATE INDEX ix_shots_beat ON shots(beat_id,shot_key,revision);
CREATE INDEX ix_layout_items_layout ON shot_layout_items(layout_id,item_order);
CREATE INDEX ix_render_job_status ON render_jobs(status);

-- FTS tách riêng, truy vấn trực tiếp theo ID để bảo đảm FTS không làm hỏng dữ liệu chuẩn.
CREATE VIRTUAL TABLE character_search USING fts5(display_name, slug, identity_description, content='characters',content_rowid='rowid');
CREATE TRIGGER characters_ai AFTER INSERT ON characters BEGIN
 INSERT INTO character_search(rowid,display_name,slug,identity_description) VALUES(new.rowid,new.display_name,new.slug,coalesce(new.identity_description,''));
END;
CREATE TRIGGER characters_ad AFTER DELETE ON characters BEGIN
 INSERT INTO character_search(character_search,rowid,display_name,slug,identity_description) VALUES('delete',old.rowid,old.display_name,old.slug,coalesce(old.identity_description,''));
END;
CREATE TRIGGER characters_au AFTER UPDATE ON characters BEGIN
 INSERT INTO character_search(character_search,rowid,display_name,slug,identity_description) VALUES('delete',old.rowid,old.display_name,old.slug,coalesce(old.identity_description,''));
 INSERT INTO character_search(rowid,display_name,slug,identity_description) VALUES(new.rowid,new.display_name,new.slug,coalesce(new.identity_description,''));
END;

INSERT INTO schema_migrations(version) VALUES('001_init');
COMMIT;
