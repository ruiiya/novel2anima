PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

-- Preserve V4 rows and seals. New moment data is nullable for legacy snapshots.
ALTER TABLE continuity_snapshots ADD COLUMN moment_json TEXT CHECK(moment_json IS NULL OR json_valid(moment_json));
CREATE TRIGGER moment_no_update BEFORE UPDATE OF moment_json ON continuity_snapshots
BEGIN SELECT RAISE(ABORT,'Moment immutable'); END;
CREATE TRIGGER v5_snapshot_no_update BEFORE UPDATE ON continuity_snapshots WHEN OLD.moment_json IS NOT NULL
BEGIN SELECT RAISE(ABORT,'V5 snapshot immutable'); END;
CREATE TRIGGER v5_snapshot_no_delete BEFORE DELETE ON continuity_snapshots WHEN OLD.moment_json IS NOT NULL
BEGIN SELECT RAISE(ABORT,'V5 snapshot immutable'); END;

-- Extend the allowed dependency relationships without altering historical rows.
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
INSERT INTO shot_dependencies_v5 SELECT * FROM shot_dependencies;
DROP TABLE shot_dependencies;
ALTER TABLE shot_dependencies_v5 RENAME TO shot_dependencies;
CREATE TRIGGER board_dep_no_update BEFORE UPDATE ON shot_dependencies BEGIN SELECT RAISE(ABORT,'Shot dependency immutable'); END;
CREATE TRIGGER board_dep_no_delete BEFORE DELETE ON shot_dependencies BEGIN SELECT RAISE(ABORT,'Shot dependency immutable'); END;
INSERT INTO schema_migrations(version) VALUES('009_narrative_continuity');
COMMIT;
