CREATE TABLE coordination_progress (
 id TEXT PRIMARY KEY,
 topic_id TEXT NOT NULL REFERENCES coordination_topics(id) ON DELETE RESTRICT,
 participant TEXT NOT NULL,
 milestone TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>=1),
 snapshot_json TEXT NOT NULL,
 UNIQUE(topic_id,participant,milestone)
);
CREATE TABLE coordination_progress_revisions (
 progress_id TEXT NOT NULL REFERENCES coordination_progress(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK(revision>=1),
 snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(progress_id,revision)
);
CREATE TRIGGER progress_history_immutable_update BEFORE UPDATE ON coordination_progress_revisions
BEGIN SELECT RAISE(ABORT,'progress history is immutable'); END;
CREATE TRIGGER progress_history_immutable_delete BEFORE DELETE ON coordination_progress_revisions
BEGIN SELECT RAISE(ABORT,'progress history is immutable'); END;
