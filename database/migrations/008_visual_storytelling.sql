PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- An immutable storyboard is an approved plan, not a renderer job.
CREATE TABLE storyboards (
  id TEXT PRIMARY KEY,
  story_id TEXT NOT NULL REFERENCES stories(id),
  story_revision INTEGER NOT NULL CHECK(story_revision >= 1),
  plan_id TEXT NOT NULL REFERENCES story_revisions(id),
  revision INTEGER NOT NULL CHECK(revision >= 1),
  plan_json TEXT NOT NULL CHECK(json_valid(plan_json)),
  plan_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(story_id, revision)
);
CREATE TABLE story_locations (
  storyboard_id TEXT NOT NULL REFERENCES storyboards(id),
  location_key TEXT NOT NULL,
  spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
  PRIMARY KEY(storyboard_id, location_key)
);
CREATE TABLE story_props (
  storyboard_id TEXT NOT NULL REFERENCES storyboards(id),
  prop_key TEXT NOT NULL,
  spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
  PRIMARY KEY(storyboard_id, prop_key)
);
CREATE TABLE visual_style_profiles (
  storyboard_id TEXT NOT NULL REFERENCES storyboards(id),
  style_key TEXT NOT NULL,
  spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
  PRIMARY KEY(storyboard_id, style_key)
);
CREATE TABLE storyboard_shots (
  storyboard_id TEXT NOT NULL REFERENCES storyboards(id),
  shot_key TEXT NOT NULL,
  shot_order INTEGER NOT NULL CHECK(shot_order >= 1),
  beat_id TEXT NOT NULL REFERENCES beats(id),
  branch_key TEXT NOT NULL,
  purpose TEXT NOT NULL CHECK(purpose IN ('ESTABLISHING','ACTION','REACTION','DETAIL','TRANSITION','CLIMAX','AFTERMATH')),
  context_sha256 TEXT NOT NULL,
  spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
  PRIMARY KEY(storyboard_id, shot_key),
  UNIQUE(storyboard_id, shot_order)
);
CREATE TABLE shot_dependencies (
  storyboard_id TEXT NOT NULL,
  shot_key TEXT NOT NULL,
  previous_shot_key TEXT NOT NULL,
  transition TEXT NOT NULL CHECK(transition IN ('CONTINUOUS','CAMERA_CUT','TIME_CUT','LOCATION_CUT','BRANCH')),
  PRIMARY KEY(storyboard_id, shot_key),
  FOREIGN KEY(storyboard_id, shot_key) REFERENCES storyboard_shots(storyboard_id, shot_key),
  FOREIGN KEY(storyboard_id, previous_shot_key) REFERENCES storyboard_shots(storyboard_id, shot_key),
  CHECK(shot_key <> previous_shot_key)
);
CREATE TABLE event_shot_mappings (
  storyboard_id TEXT NOT NULL REFERENCES storyboards(id),
  event_id TEXT NOT NULL REFERENCES story_events(id),
  status TEXT NOT NULL CHECK(status IN ('VISUALIZED','CONTEXT_ONLY','UNRESOLVED','UNSUPPORTED_CONTENT')),
  shot_key TEXT,
  evidence TEXT NOT NULL CHECK(length(trim(evidence)) > 0),
  FOREIGN KEY(storyboard_id, shot_key) REFERENCES storyboard_shots(storyboard_id, shot_key),
  CHECK((status = 'VISUALIZED' AND shot_key IS NOT NULL) OR (status <> 'VISUALIZED' AND shot_key IS NULL)),
  UNIQUE(storyboard_id, event_id, shot_key)
);
CREATE UNIQUE INDEX ux_coverage_nonvisual ON event_shot_mappings(storyboard_id,event_id) WHERE shot_key IS NULL;

-- Pin exact Shot/Prompt/QA and continuity digests after validating the whole sequence.
CREATE TABLE storyboard_seals (
  storyboard_id TEXT PRIMARY KEY REFERENCES storyboards(id),
  seal_json TEXT NOT NULL CHECK(json_valid(seal_json)),
  seal_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER storyboard_no_update BEFORE UPDATE ON storyboards BEGIN SELECT RAISE(ABORT,'Storyboard immutable'); END;
CREATE TRIGGER storyboard_no_delete BEFORE DELETE ON storyboards BEGIN SELECT RAISE(ABORT,'Storyboard immutable'); END;
CREATE TRIGGER board_shot_no_update BEFORE UPDATE ON storyboard_shots BEGIN SELECT RAISE(ABORT,'Storyboard shot immutable'); END;
CREATE TRIGGER board_shot_no_delete BEFORE DELETE ON storyboard_shots BEGIN SELECT RAISE(ABORT,'Storyboard shot immutable'); END;
CREATE TRIGGER board_loc_no_update BEFORE UPDATE ON story_locations BEGIN SELECT RAISE(ABORT,'Location bible immutable'); END;
CREATE TRIGGER board_loc_no_delete BEFORE DELETE ON story_locations BEGIN SELECT RAISE(ABORT,'Location bible immutable'); END;
CREATE TRIGGER board_prop_no_update BEFORE UPDATE ON story_props BEGIN SELECT RAISE(ABORT,'Prop bible immutable'); END;
CREATE TRIGGER board_prop_no_delete BEFORE DELETE ON story_props BEGIN SELECT RAISE(ABORT,'Prop bible immutable'); END;
CREATE TRIGGER board_style_no_update BEFORE UPDATE ON visual_style_profiles BEGIN SELECT RAISE(ABORT,'Style bible immutable'); END;
CREATE TRIGGER board_style_no_delete BEFORE DELETE ON visual_style_profiles BEGIN SELECT RAISE(ABORT,'Style bible immutable'); END;
CREATE TRIGGER board_dep_no_update BEFORE UPDATE ON shot_dependencies BEGIN SELECT RAISE(ABORT,'Shot dependency immutable'); END;
CREATE TRIGGER board_dep_no_delete BEFORE DELETE ON shot_dependencies BEGIN SELECT RAISE(ABORT,'Shot dependency immutable'); END;
CREATE TRIGGER board_event_no_update BEFORE UPDATE ON event_shot_mappings BEGIN SELECT RAISE(ABORT,'Event coverage immutable'); END;
CREATE TRIGGER board_event_no_delete BEFORE DELETE ON event_shot_mappings BEGIN SELECT RAISE(ABORT,'Event coverage immutable'); END;
CREATE TRIGGER board_seal_no_update BEFORE UPDATE ON storyboard_seals BEGIN SELECT RAISE(ABORT,'Storyboard seal immutable'); END;
CREATE TRIGGER board_seal_no_delete BEFORE DELETE ON storyboard_seals BEGIN SELECT RAISE(ABORT,'Storyboard seal immutable'); END;
INSERT INTO schema_migrations(version) VALUES('008_visual_storytelling');
COMMIT;
