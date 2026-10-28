CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    display_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    customer TEXT NOT NULL,
    product TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'requirement_parsing'
        CHECK (stage IN ('requirement_parsing', 'variant_design', 'test_verification', 'gate_review', 'completed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE sequences (
    scope TEXT PRIMARY KEY,
    next_value INTEGER NOT NULL
);

CREATE TABLE source_documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    doc_type TEXT NOT NULL
        CHECK (doc_type IN ('protocol', 'change_notice', 'drawing', 'test_report', 'communication', 'other')),
    version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    original_text TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('rule', 'mock', 'manual')),
    created_at TEXT NOT NULL,
    UNIQUE (project_id, display_code, version)
);

CREATE TABLE requirements (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I')),
    parameter_name TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK (data_type IN ('numeric', 'range', 'boolean', 'text')),
    operator TEXT NOT NULL,
    value_text TEXT NOT NULL,
    value_num REAL,
    value_num_high REAL,
    unit TEXT NOT NULL DEFAULT '',
    raw_expression TEXT NOT NULL DEFAULT '',
    source_document_id TEXT REFERENCES source_documents(id) ON DELETE RESTRICT,
    source_location TEXT NOT NULL DEFAULT '',
    source_excerpt TEXT NOT NULL DEFAULT '',
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft', 'pending_review', 'confirmed', 'rejected')),
    validity TEXT NOT NULL DEFAULT 'current'
        CHECK (validity IN ('current', 'stale')),
    current_revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, display_code)
);

CREATE TABLE requirement_revisions (
    id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL REFERENCES requirements(id) ON DELETE RESTRICT,
    revision_no INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('current', 'superseded')),
    source_document_id TEXT REFERENCES source_documents(id) ON DELETE RESTRICT,
    source_location TEXT NOT NULL DEFAULT '',
    source_excerpt TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    change_reason TEXT NOT NULL DEFAULT '',
    UNIQUE (requirement_id, revision_no)
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_revision INTEGER,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT,
    comment TEXT NOT NULL DEFAULT '',
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_audit_project_created ON audit_events(project_id, created_at);
CREATE INDEX idx_audit_object ON audit_events(object_type, object_id);

CREATE TABLE object_dependencies (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    upstream_type TEXT NOT NULL,
    upstream_id TEXT NOT NULL,
    upstream_revision INTEGER NOT NULL,
    downstream_type TEXT NOT NULL,
    downstream_id TEXT NOT NULL,
    downstream_revision INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (upstream_type, upstream_id, upstream_revision, downstream_type, downstream_id)
);

CREATE INDEX idx_dependencies_downstream ON object_dependencies(downstream_type, downstream_id);
