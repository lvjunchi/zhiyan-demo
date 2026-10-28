CREATE TABLE sample_deliveries (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    supplier TEXT NOT NULL,
    part_display_code TEXT NOT NULL,
    drawing_display_code TEXT NOT NULL,
    drawing_revision TEXT NOT NULL,
    delivered_at TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 1),
    notes TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'manual'
        CHECK (mode IN ('rule', 'mock', 'manual')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, display_code)
);

CREATE INDEX idx_sample_deliveries_project
    ON sample_deliveries(project_id);

CREATE TABLE sample_drawing_parameters (
    id TEXT PRIMARY KEY,
    sample_id TEXT NOT NULL
        REFERENCES sample_deliveries(id) ON DELETE RESTRICT,
    parameter_key TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    expected_value REAL NOT NULL,
    tolerance REAL NOT NULL CHECK (tolerance >= 0),
    unit TEXT NOT NULL DEFAULT '',
    source_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (sample_id, parameter_key)
);

CREATE TABLE sample_delivery_files (
    id TEXT PRIMARY KEY,
    sample_id TEXT NOT NULL UNIQUE
        REFERENCES sample_deliveries(id) ON DELETE RESTRICT,
    file_name TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    content_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
    content BLOB NOT NULL,
    uploaded_by TEXT NOT NULL,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE sample_comparisons (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    sample_id TEXT NOT NULL UNIQUE
        REFERENCES sample_deliveries(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'rejected')),
    mode TEXT NOT NULL CHECK (mode IN ('rule', 'mock', 'manual')),
    overall_result TEXT NOT NULL
        CHECK (overall_result IN ('pass', 'fail', 'incomplete', 'invalid')),
    findings TEXT NOT NULL DEFAULT '[]',
    visual_check TEXT NOT NULL DEFAULT '{}',
    inputs_snapshot TEXT NOT NULL DEFAULT '{}',
    evidence TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_sample_comparisons_project
    ON sample_comparisons(project_id);

CREATE TABLE sample_comparison_confirmations (
    id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL
        REFERENCES sample_comparisons(id) ON DELETE RESTRICT,
    comparison_revision INTEGER NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'rejected')),
    comment TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (comparison_id, comparison_revision)
);

CREATE TABLE sample_comparison_issues (
    id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL
        REFERENCES sample_comparisons(id) ON DELETE RESTRICT,
    comparison_revision INTEGER NOT NULL,
    issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    UNIQUE (comparison_id, comparison_revision, issue_id)
);
