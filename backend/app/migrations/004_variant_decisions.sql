ALTER TABLE reusable_part_decisions ADD COLUMN status TEXT NOT NULL DEFAULT 'current'
    CHECK (status IN ('current', 'stale'));

ALTER TABLE reusable_part_decisions ADD COLUMN variant_keys TEXT NOT NULL DEFAULT '[]';

CREATE INDEX idx_reusable_part_decisions_project
    ON reusable_part_decisions(project_id, base_id, status);
