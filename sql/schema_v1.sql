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
CREATE TABLE tag (
  id INTEGER PRIMARY KEY,
  canonical_name TEXT NOT NULL UNIQUE,  -- Danbooru form: looking_back
  search_name TEXT NOT NULL,            -- search form: looking back
  danbooru_category TEXT,
  post_count INTEGER NOT NULL DEFAULT 0 CHECK(post_count >= 0),
  taxonomy_status TEXT NOT NULL DEFAULT 'unreviewed'
    CHECK(taxonomy_status IN ('approved','needs_review','unreviewed'))
);
CREATE INDEX idx_tag_search ON tag(search_name);
CREATE INDEX idx_tag_category ON tag(danbooru_category);
CREATE TABLE tag_source (
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  source_id INTEGER NOT NULL REFERENCES source_snapshot(id) ON DELETE CASCADE,
  source_ref TEXT NOT NULL DEFAULT '',
  source_metadata TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(source_metadata)),
  PRIMARY KEY (tag_id, source_id, source_ref)
);
CREATE TABLE tag_alias (
  alias_name TEXT PRIMARY KEY,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  source_id INTEGER REFERENCES source_snapshot(id),
  CHECK(length(alias_name) > 0)
);
CREATE INDEX idx_tag_alias_target ON tag_alias(tag_id);
CREATE TABLE tag_role (
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN (
    'identity','outfit','body_state','action','expression','pose','motion','camera',
    'composition','background','style','interaction','other'
  )),
  confidence REAL NOT NULL DEFAULT 1.0 CHECK(confidence BETWEEN 0 AND 1),
  source_id INTEGER REFERENCES source_snapshot(id),
  PRIMARY KEY (tag_id, role)
);
CREATE INDEX idx_tag_role_lookup ON tag_role(role, confidence DESC);
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
CREATE INDEX idx_tag_relation_to ON tag_relation(to_tag_id, relation);
CREATE TABLE tag_content_label (
  tag_id INTEGER PRIMARY KEY REFERENCES tag(id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK(scope IN ('neutral','adult','contextual','unreviewed','blocked')),
  confidence REAL NOT NULL DEFAULT 1.0 CHECK(confidence BETWEEN 0 AND 1),
  rationale TEXT,
  reviewed_at TEXT
);
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
CREATE INDEX idx_concept_kind_status ON visual_concept(kind, review_status, content_scope);
CREATE TABLE concept_tag (
  concept_id INTEGER NOT NULL REFERENCES visual_concept(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  usage TEXT NOT NULL CHECK(usage IN ('primary','optional','alternative')),
  priority INTEGER NOT NULL DEFAULT 100,
  PRIMARY KEY (concept_id, tag_id, usage)
);
CREATE INDEX idx_concept_tag_tag ON concept_tag(tag_id);
CREATE TABLE concept_relation (
  from_concept_id INTEGER NOT NULL REFERENCES visual_concept(id) ON DELETE CASCADE,
  to_concept_id INTEGER NOT NULL REFERENCES visual_concept(id) ON DELETE CASCADE,
  relation TEXT NOT NULL CHECK(relation IN ('compatible','recommends','conflicts','subtype_of')),
  weight REAL NOT NULL DEFAULT 1.0,
  note TEXT,
  PRIMARY KEY (from_concept_id, to_concept_id, relation),
  CHECK(from_concept_id <> to_concept_id)
);
CREATE INDEX idx_concept_relation_to ON concept_relation(to_concept_id, relation);
CREATE VIRTUAL TABLE visual_concept_fts USING fts5(
  name, description, search_terms,
  content='visual_concept', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
)
/* visual_concept_fts(name,description,search_terms) */;
CREATE TRIGGER trg_concept_ai AFTER INSERT ON visual_concept BEGIN
  INSERT INTO visual_concept_fts(rowid,name,description,search_terms)
    VALUES(new.id,new.name,new.description,new.search_terms);
END;
CREATE TRIGGER trg_concept_ad AFTER DELETE ON visual_concept BEGIN
  INSERT INTO visual_concept_fts(visual_concept_fts,rowid,name,description,search_terms)
    VALUES('delete',old.id,old.name,old.description,old.search_terms);
END;
CREATE TRIGGER trg_concept_au AFTER UPDATE ON visual_concept BEGIN
  INSERT INTO visual_concept_fts(visual_concept_fts,rowid,name,description,search_terms)
    VALUES('delete',old.id,old.name,old.description,old.search_terms);
  INSERT INTO visual_concept_fts(rowid,name,description,search_terms)
    VALUES(new.id,new.name,new.description,new.search_terms);
END;
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
CREATE TABLE project (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  idea TEXT NOT NULL DEFAULT '',
  content_profile TEXT NOT NULL DEFAULT 'mixed'
    CHECK(content_profile IN ('sfw','nsfw','mixed')),
  style_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(style_json)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE character_profile (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  identity_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(identity_json)),
  outfit_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(outfit_json)),
  UNIQUE(project_id,code)
);
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
CREATE INDEX idx_act_project ON act(project_id,act_no);
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
CREATE INDEX idx_shot_act ON shot(act_id,shot_no);
CREATE INDEX idx_shot_signature ON shot(signature);
CREATE INDEX idx_shot_action_expr ON shot(action_concept_id,expression_concept_id);
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
CREATE INDEX idx_generation_shot ON generation(shot_id,created_at);
