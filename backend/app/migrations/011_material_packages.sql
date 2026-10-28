CREATE TABLE material_packages (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    package_no INTEGER NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('draft', 'ready_to_submit', 'human_approved')),
    mode TEXT NOT NULL DEFAULT 'rule'
        CHECK (mode IN ('rule', 'mock', 'manual')),
    include_originals INTEGER NOT NULL DEFAULT 0
        CHECK (include_originals IN (0, 1)),
    snapshot_hash TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    gate_json TEXT NOT NULL,
    zip_content BLOB NOT NULL,
    zip_hash TEXT NOT NULL,
    zip_size INTEGER NOT NULL CHECK (zip_size > 0),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    frozen_at TEXT,
    UNIQUE (project_id, display_code),
    UNIQUE (project_id, package_no)
);

CREATE INDEX idx_material_packages_project
    ON material_packages(project_id, package_no DESC);

CREATE TABLE material_package_approvals (
    id TEXT PRIMARY KEY,
    package_id TEXT NOT NULL UNIQUE
        REFERENCES material_packages(id) ON DELETE RESTRICT,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision = 'approved'),
    comment TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    zip_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE coordination_risk_acceptances (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL
        REFERENCES coordination_topics(id) ON DELETE RESTRICT,
    metric_run_id TEXT NOT NULL UNIQUE
        REFERENCES coordination_metric_runs(id) ON DELETE RESTRICT,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_coordination_risk_acceptances_topic
    ON coordination_risk_acceptances(topic_id, created_at DESC);
