-- Widen storyboard shot purpose vocabulary for explicit fan-service albums.
-- Legacy purposes stay valid; new ones add staged tease, undress, POV and self-touch beats.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

DROP TRIGGER board_shot_no_update;
DROP TRIGGER board_shot_no_delete;
DROP TRIGGER board_event_no_update;
DROP TRIGGER board_event_no_delete;
DROP TRIGGER board_dep_no_update;
DROP TRIGGER board_dep_no_delete;

CREATE TABLE event_shot_mappings_v10 AS SELECT * FROM event_shot_mappings;
CREATE TABLE shot_dependencies_v10 AS SELECT * FROM shot_dependencies;
DROP TABLE event_shot_mappings;
DROP TABLE shot_dependencies;

CREATE TABLE storyboard_shots_v10 (
  storyboard_id TEXT NOT NULL REFERENCES storyboards(id),
  shot_key TEXT NOT NULL,
  shot_order INTEGER NOT NULL CHECK(shot_order >= 1),
  beat_id TEXT NOT NULL REFERENCES beats(id),
  branch_key TEXT NOT NULL,
  purpose TEXT NOT NULL CHECK(purpose IN ('ESTABLISHING','ACTION','REACTION','DETAIL','TRANSITION','CLIMAX',
    'AFTERMATH','TEASE','UNDRESS','POV','SELF_TOUCH','AFTERGLOW')),
  context_sha256 TEXT NOT NULL,
  spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
  PRIMARY KEY(storyboard_id, shot_key),
  UNIQUE(storyboard_id, shot_order)
);
INSERT INTO storyboard_shots_v10 SELECT * FROM storyboard_shots;
DROP TABLE storyboard_shots;
ALTER TABLE storyboard_shots_v10 RENAME TO storyboard_shots;

CREATE TABLE shot_dependencies_v5 (
  storyboard_id TEXT NOT NULL,
  shot_key TEXT NOT NULL,
  previous_shot_key TEXT NOT NULL,
  transition TEXT NOT NULL CHECK(transition IN ('CONTINUOUS','CAMERA_CUT','TIME_CUT','LOCATION_CUT','BRANCH','SAME_MOMENT','FLASHBACK')),
  PRIMARY KEY(storyboard_id,shot_key),
  FOREIGN KEY(storyboard_id,shot_key) REFERENCES storyboard_shots(storyboard_id,shot_key),
  FOREIGN KEY(storyboard_id,previous_shot_key) REFERENCES storyboard_shots(storyboard_id,shot_key),
  CHECK(shot_key <> previous_shot_key)
);
INSERT INTO shot_dependencies_v5 SELECT * FROM shot_dependencies_v10;
DROP TABLE shot_dependencies_v10;
ALTER TABLE shot_dependencies_v5 RENAME TO shot_dependencies;

CREATE TABLE event_shot_mappings_v5 (
  storyboard_id TEXT NOT NULL REFERENCES storyboards(id),
  event_id TEXT NOT NULL REFERENCES story_events(id),
  status TEXT NOT NULL CHECK(status IN ('VISUALIZED','CONTEXT_ONLY','UNRESOLVED','UNSUPPORTED_CONTENT')),
  shot_key TEXT,
  evidence TEXT NOT NULL CHECK(length(trim(evidence)) > 0),
  FOREIGN KEY(storyboard_id, shot_key) REFERENCES storyboard_shots(storyboard_id, shot_key),
  CHECK((status = 'VISUALIZED' AND shot_key IS NOT NULL) OR (status <> 'VISUALIZED' AND shot_key IS NULL)),
  UNIQUE(storyboard_id, event_id, shot_key)
);
INSERT INTO event_shot_mappings_v5 SELECT * FROM event_shot_mappings_v10;
DROP TABLE event_shot_mappings_v10;
ALTER TABLE event_shot_mappings_v5 RENAME TO event_shot_mappings;
CREATE UNIQUE INDEX ux_coverage_nonvisual_v5 ON event_shot_mappings(storyboard_id,event_id) WHERE shot_key IS NULL;

CREATE TRIGGER board_shot_no_update BEFORE UPDATE ON storyboard_shots BEGIN SELECT RAISE(ABORT,'Storyboard shot immutable'); END;
CREATE TRIGGER board_shot_no_delete BEFORE DELETE ON storyboard_shots BEGIN SELECT RAISE(ABORT,'Storyboard shot immutable'); END;
CREATE TRIGGER board_dep_no_update BEFORE UPDATE ON shot_dependencies BEGIN SELECT RAISE(ABORT,'Shot dependency immutable'); END;
CREATE TRIGGER board_dep_no_delete BEFORE DELETE ON shot_dependencies BEGIN SELECT RAISE(ABORT,'Shot dependency immutable'); END;
CREATE TRIGGER board_event_no_update BEFORE UPDATE ON event_shot_mappings BEGIN SELECT RAISE(ABORT,'Event coverage immutable'); END;
CREATE TRIGGER board_event_no_delete BEFORE DELETE ON event_shot_mappings BEGIN SELECT RAISE(ABORT,'Event coverage immutable'); END;

INSERT INTO schema_migrations(version) VALUES('010_shot_purposes');
COMMIT;
