CREATE TABLE sample_comparison_versions (
    comparison_id TEXT NOT NULL REFERENCES sample_comparisons(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json)),
    created_at TEXT NOT NULL,
    PRIMARY KEY (comparison_id, revision)
);
INSERT INTO sample_comparison_versions
SELECT id, revision, json_object(
    'id',id,'project_id',project_id,'sample_id',sample_id,'display_code',display_code,
    'revision',revision,'status',status,'mode',mode,'overall_result',overall_result,
    'findings',json(findings),'visual_check',json(visual_check),'evidence',evidence,
    'created_at',created_at,'updated_at',updated_at,
    'migration_note','Only the current legacy comparison was available; earlier revisions were not reconstructed'
), updated_at FROM sample_comparisons;
CREATE TRIGGER sample_comparison_versions_immutable_update BEFORE UPDATE ON sample_comparison_versions
BEGIN SELECT RAISE(ABORT, 'sample comparison history is immutable'); END;
CREATE TRIGGER sample_comparison_versions_immutable_delete BEFORE DELETE ON sample_comparison_versions
BEGIN SELECT RAISE(ABORT, 'sample comparison history is immutable'); END;
