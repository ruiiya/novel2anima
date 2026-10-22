-- Novel2Anima — current SQLite schema
-- Generated from: db/novel_anima.db
-- Generated at: 2026-10-22T09:06:22
-- Git commit: e64835f388a5a87a59d5706dd2ca7d15b6187f4f
-- Source files: sql/schema_v1.sql + sql/migrations/*.sql
-- Excluded: sqlite_* internal tables and visual_concept_fts_* shadow tables.
-- Table descriptions: sql/table_descriptions.md

-- ---------------------------------------------------------------------------
-- [table] source_snapshot — Mỗi lần nhập một nguồn dữ liệu (5 nguồn pinned + các dump local).
-- group: Catalog / provenance | rows: 11
-- ---------------------------------------------------------------------------
CREATE TABLE source_snapshot (
  id INTEGER PRIMARY KEY,
  source_key TEXT NOT NULL,
  source_url TEXT NOT NULL,
  revision TEXT NOT NULL,
  license_note TEXT,
  sha256 TEXT,
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (source_key, revision)
);

-- ---------------------------------------------------------------------------
-- [table] tag — Từ điển tag canonical dùng làm cú pháp prompt.
-- group: Catalog / vocabulary | rows: 1208773
-- ---------------------------------------------------------------------------
CREATE TABLE tag (
  id INTEGER PRIMARY KEY,
  canonical_name TEXT NOT NULL UNIQUE,  -- Danbooru form: looking_back
  search_name TEXT NOT NULL,            -- search form: looking back
  danbooru_category TEXT,
  post_count INTEGER NOT NULL DEFAULT 0 CHECK(post_count >= 0),
  taxonomy_status TEXT NOT NULL DEFAULT 'unreviewed'
    CHECK(taxonomy_status IN ('approved','needs_review','unreviewed'))
);

-- ---------------------------------------------------------------------------
-- [table] tag_source — Provenance chi tiết của từng tag theo từng nguồn.
-- group: Catalog / provenance | rows: 1479995
-- ---------------------------------------------------------------------------
CREATE TABLE tag_source (
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  source_id INTEGER NOT NULL REFERENCES source_snapshot(id) ON DELETE CASCADE,
  source_ref TEXT NOT NULL DEFAULT '',
  source_metadata TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(source_metadata)),
  PRIMARY KEY (tag_id, source_id, source_ref)
);

-- ---------------------------------------------------------------------------
-- [table] tag_alias — Alias name trỏ về một tag canonical.
-- group: Catalog / vocabulary | rows: 149546
-- ---------------------------------------------------------------------------
CREATE TABLE tag_alias (
  alias_name TEXT PRIMARY KEY,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  source_id INTEGER REFERENCES source_snapshot(id),
  CHECK(length(alias_name) > 0)
);

-- ---------------------------------------------------------------------------
-- [table] tag_role — Vai trò của tag khi dựng prompt.
-- group: Catalog / vocabulary | rows: 30265
-- ---------------------------------------------------------------------------
CREATE TABLE tag_role (
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN (
    'identity','outfit','action','expression','pose','motion','camera',
    'composition','background','style','interaction','other'
  )),
  confidence REAL NOT NULL DEFAULT 1.0 CHECK(confidence BETWEEN 0 AND 1),
  source_id INTEGER REFERENCES source_snapshot(id),
  PRIMARY KEY (tag_id, role)
);

-- ---------------------------------------------------------------------------
-- [table] tag_relation — Quan hệ có hướng giữa hai tag.
-- group: Catalog / relations | rows: 213175
-- ---------------------------------------------------------------------------
CREATE TABLE tag_relation (
  from_tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  to_tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  relation TEXT NOT NULL CHECK(relation IN ('implies','conflicts','compatible','recommends')),
  weight REAL NOT NULL DEFAULT 1.0,
  source_id INTEGER REFERENCES source_snapshot(id),
  note TEXT,
  PRIMARY KEY (from_tag_id, to_tag_id, relation),
  CHECK(from_tag_id <> to_tag_id)
);

-- ---------------------------------------------------------------------------
-- [table] tag_content_label — Nhãn nội dung gắn với tag.
-- group: Catalog / content metadata | rows: 9994
-- ---------------------------------------------------------------------------
CREATE TABLE tag_content_label (
  tag_id INTEGER PRIMARY KEY REFERENCES tag(id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK(scope IN ('neutral','adult','contextual','unreviewed','blocked')),
  confidence REAL NOT NULL DEFAULT 1.0 CHECK(confidence BETWEEN 0 AND 1),
  rationale TEXT,
  reviewed_at TEXT
);

-- ---------------------------------------------------------------------------
-- [table] visual_concept — Khái niệm thị giác dùng cho planning và retrieval.
-- group: Catalog / concepts | rows: 583
-- ---------------------------------------------------------------------------
CREATE TABLE visual_concept (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('action','expression','pose','motion','camera','interaction','other')),
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  search_terms TEXT NOT NULL DEFAULT '',
  energy INTEGER CHECK(energy BETWEEN 0 AND 5),
  content_scope TEXT NOT NULL DEFAULT 'contextual'
    CHECK(content_scope IN ('neutral','adult','contextual','unreviewed','blocked')),
  review_status TEXT NOT NULL DEFAULT 'draft'
    CHECK(review_status IN ('draft','approved','rejected')),
  prompt_template TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(metadata_json))
);

-- ---------------------------------------------------------------------------
-- [table] concept_tag — Map khái niệm sang tag cú pháp.
-- group: Catalog / concepts | rows: 9741
-- ---------------------------------------------------------------------------
CREATE TABLE concept_tag (
  concept_id INTEGER NOT NULL REFERENCES visual_concept(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  usage TEXT NOT NULL CHECK(usage IN ('primary','optional','alternative')),
  priority INTEGER NOT NULL DEFAULT 100,
  PRIMARY KEY (concept_id, tag_id, usage)
);

-- ---------------------------------------------------------------------------
-- [table] concept_relation — Quan hệ có hướng giữa hai visual concept.
-- group: Catalog / concepts | rows: 0
-- ---------------------------------------------------------------------------
CREATE TABLE concept_relation (
  from_concept_id INTEGER NOT NULL REFERENCES visual_concept(id) ON DELETE CASCADE,
  to_concept_id INTEGER NOT NULL REFERENCES visual_concept(id) ON DELETE CASCADE,
  relation TEXT NOT NULL CHECK(relation IN ('compatible','recommends','conflicts','subtype_of')),
  weight REAL NOT NULL DEFAULT 1.0,
  note TEXT,
  PRIMARY KEY (from_concept_id, to_concept_id, relation),
  CHECK(from_concept_id <> to_concept_id)
);

-- ---------------------------------------------------------------------------
-- [table] model_profile — Cấu hình model và workflow render.
-- group: Runtime / render config | rows: 0
-- ---------------------------------------------------------------------------
CREATE TABLE model_profile (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  model_name TEXT NOT NULL,
  lora_name TEXT,
  steps INTEGER NOT NULL DEFAULT 4,
  cfg REAL NOT NULL DEFAULT 1.0,
  sampler TEXT NOT NULL DEFAULT 'er_sde',
  workflow_version TEXT,
  config_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(config_json))
);

-- ---------------------------------------------------------------------------
-- [table] project — Dự án truyện.
-- group: Runtime / project | rows: 31
-- ---------------------------------------------------------------------------
CREATE TABLE project (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  idea TEXT NOT NULL DEFAULT '',
  content_profile TEXT NOT NULL DEFAULT 'mixed'
    CHECK(content_profile IN ('sfw','nsfw','mixed')),
  style_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(style_json)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- [table] character_profile — Nhân vật trong một project.
-- group: Runtime / project | rows: 574
-- ---------------------------------------------------------------------------
CREATE TABLE character_profile (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  identity_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(identity_json)),
  outfit_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(outfit_json)),
  UNIQUE(project_id,code)
);

-- ---------------------------------------------------------------------------
-- [table] act — Act trong một project.
-- group: Runtime / story | rows: 77
-- ---------------------------------------------------------------------------
CREATE TABLE act (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  act_no INTEGER NOT NULL CHECK(act_no > 0),
  title TEXT NOT NULL,
  outline TEXT NOT NULL DEFAULT '',
  revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK(status IN ('draft','planned','approved','locked')),
  UNIQUE(project_id,act_no,revision)
);

-- ---------------------------------------------------------------------------
-- [table] shot — Một shot cụ thể trong act.
-- group: Runtime / story | rows: 7099
-- ---------------------------------------------------------------------------
CREATE TABLE shot (
  id INTEGER PRIMARY KEY,
  act_id INTEGER NOT NULL REFERENCES act(id) ON DELETE CASCADE,
  shot_no INTEGER NOT NULL CHECK(shot_no > 0),
  character_id INTEGER REFERENCES character_profile(id),
  action_concept_id INTEGER REFERENCES visual_concept(id),
  expression_concept_id INTEGER REFERENCES visual_concept(id),
  pose_concept_id INTEGER REFERENCES visual_concept(id),
  camera_concept_id INTEGER REFERENCES visual_concept(id),
  signature TEXT,
  shot_spec_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(shot_spec_json)),
  content_mode TEXT NOT NULL DEFAULT 'sfw'
    CHECK(content_mode IN ('sfw','nsfw')),
  status TEXT NOT NULL DEFAULT 'planned'
    CHECK(status IN ('draft','planned','approved','generated','rejected','locked')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(act_id,shot_no)
);

-- ---------------------------------------------------------------------------
-- [table] generation — Lịch sử render của shot.
-- group: Runtime / history | rows: 0
-- ---------------------------------------------------------------------------
CREATE TABLE generation (
  id INTEGER PRIMARY KEY,
  shot_id INTEGER NOT NULL REFERENCES shot(id) ON DELETE CASCADE,
  model_profile_id INTEGER NOT NULL REFERENCES model_profile(id),
  prompt TEXT NOT NULL,
  seed INTEGER,
  image_path TEXT,
  image_sha256 TEXT,
  evaluation_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(evaluation_json)),
  decision TEXT NOT NULL DEFAULT 'pending'
    CHECK(decision IN ('pending','approved','rejected')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- [table] shot_state — Continuity state theo shot/axis (experimental).
-- group: Runtime / continuity | rows: 665
-- ---------------------------------------------------------------------------
CREATE TABLE shot_state (
  shot_id       INTEGER NOT NULL REFERENCES shot(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  value_tag_id  INTEGER REFERENCES tag(id),
  severity      REAL    NOT NULL DEFAULT 0.5 CHECK(severity BETWEEN 0 AND 1),
  since_shot_no INTEGER NOT NULL,
  cause_shot_no INTEGER NOT NULL,
  source        TEXT    NOT NULL DEFAULT 'inferred:v0',
  PRIMARY KEY (shot_id, axis)
);

-- ---------------------------------------------------------------------------
-- [table] act_continuity — Continuity gốc của act theo axis.
-- group: Runtime / continuity | rows: 48
-- ---------------------------------------------------------------------------
CREATE TABLE act_continuity (
  act_id        INTEGER NOT NULL REFERENCES act(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  initial_tag_id INTEGER REFERENCES tag(id),
  notes         TEXT    NOT NULL DEFAULT '',
  PRIMARY KEY (act_id, axis)
);

-- [index] idx_tag_search (on tag)
CREATE INDEX idx_tag_search ON tag(search_name);

-- [index] idx_tag_category (on tag)
CREATE INDEX idx_tag_category ON tag(danbooru_category);

-- [index] idx_tag_alias_target (on tag_alias)
CREATE INDEX idx_tag_alias_target ON tag_alias(tag_id);

-- [index] idx_tag_role_lookup (on tag_role)
CREATE INDEX idx_tag_role_lookup ON tag_role(role, confidence DESC);

-- [index] idx_tag_relation_to (on tag_relation)
CREATE INDEX idx_tag_relation_to ON tag_relation(to_tag_id, relation);

-- [index] idx_concept_kind_status (on visual_concept)
CREATE INDEX idx_concept_kind_status ON visual_concept(kind, review_status, content_scope);

-- [index] idx_concept_tag_tag (on concept_tag)
CREATE INDEX idx_concept_tag_tag ON concept_tag(tag_id);

-- [index] idx_concept_relation_to (on concept_relation)
CREATE INDEX idx_concept_relation_to ON concept_relation(to_concept_id, relation);

-- [index] idx_act_project (on act)
CREATE INDEX idx_act_project ON act(project_id,act_no);

-- [index] idx_shot_act (on shot)
CREATE INDEX idx_shot_act ON shot(act_id,shot_no);

-- [index] idx_shot_signature (on shot)
CREATE INDEX idx_shot_signature ON shot(signature);

-- [index] idx_shot_action_expr (on shot)
CREATE INDEX idx_shot_action_expr ON shot(action_concept_id,expression_concept_id);

-- [index] idx_generation_shot (on generation)
CREATE INDEX idx_generation_shot ON generation(shot_id,created_at);

-- ---------------------------------------------------------------------------
-- [table] visual_concept_fts — FTS5 virtual table cho visual_concept.
-- group: Catalog / search index | rows: 583
-- ---------------------------------------------------------------------------
CREATE VIRTUAL TABLE visual_concept_fts USING fts5(
  name, description, search_terms,
  content='visual_concept', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);

-- [trigger] trg_concept_ai (on visual_concept)
CREATE TRIGGER trg_concept_ai AFTER INSERT ON visual_concept BEGIN
  INSERT INTO visual_concept_fts(rowid,name,description,search_terms)
    VALUES(new.id,new.name,new.description,new.search_terms);
END;

-- [trigger] trg_concept_ad (on visual_concept)
CREATE TRIGGER trg_concept_ad AFTER DELETE ON visual_concept BEGIN
  INSERT INTO visual_concept_fts(visual_concept_fts,rowid,name,description,search_terms)
    VALUES('delete',old.id,old.name,old.description,old.search_terms);
END;

-- [trigger] trg_concept_au (on visual_concept)
CREATE TRIGGER trg_concept_au AFTER UPDATE ON visual_concept BEGIN
  INSERT INTO visual_concept_fts(visual_concept_fts,rowid,name,description,search_terms)
    VALUES('delete',old.id,old.name,old.description,old.search_terms);
  INSERT INTO visual_concept_fts(rowid,name,description,search_terms)
    VALUES(new.id,new.name,new.description,new.search_terms);
END;

-- ---------------------------------------------------------------------------
-- [table] shot_observation — Observation suy luận theo shot/axis/source.
-- group: Runtime / inference | rows: 0
-- ---------------------------------------------------------------------------
CREATE TABLE shot_observation (
  shot_id       INTEGER NOT NULL REFERENCES shot(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  value_tag_id  INTEGER REFERENCES tag(id),
  severity      REAL    NOT NULL DEFAULT 0.5 CHECK(severity BETWEEN 0 AND 1),
  since_shot_no INTEGER NOT NULL,
  cause_shot_no INTEGER NOT NULL,
  source        TEXT    NOT NULL,
  PRIMARY KEY (shot_id, axis, source)
);

-- ---------------------------------------------------------------------------
-- [table] act_observation — Observation suy luận cấp act/axis/source.
-- group: Runtime / inference | rows: 0
-- ---------------------------------------------------------------------------
CREATE TABLE act_observation (
  act_id        INTEGER NOT NULL REFERENCES act(id) ON DELETE CASCADE,
  axis          TEXT    NOT NULL,
  initial_tag_id INTEGER REFERENCES tag(id),
  notes         TEXT    NOT NULL DEFAULT '',
  source        TEXT    NOT NULL,
  PRIMARY KEY (act_id, axis, source)
);

-- ---------------------------------------------------------------------------
-- [table] act_publication — Outbox publish prompt file cho act/revision.
-- group: Runtime / publication | rows: 27
-- ---------------------------------------------------------------------------
CREATE TABLE act_publication (
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

-- ---------------------------------------------------------------------------
-- [table] shot_finding — Finding QA cho một shot.
-- group: Runtime / QA | rows: 69
-- ---------------------------------------------------------------------------
CREATE TABLE shot_finding (
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

-- [index] shot_finding_shot (on shot_finding)
CREATE INDEX shot_finding_shot ON shot_finding(shot_id);
