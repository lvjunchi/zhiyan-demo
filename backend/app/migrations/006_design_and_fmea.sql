CREATE TABLE history_projects (
    id TEXT PRIMARY KEY,
    display_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    customer TEXT NOT NULL,
    transmission_type TEXT NOT NULL
        CHECK (transmission_type IN ('AMT', 'MT', 'AT')),
    gear_count INTEGER NOT NULL,
    rated_input_torque REAL NOT NULL,
    has_pto INTEGER NOT NULL CHECK (has_pto IN (0, 1)),
    assembly_weight_kg REAL NOT NULL,
    top_gear_type TEXT NOT NULL
        CHECK (top_gear_type IN ('direct', 'overdrive')),
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE design_reviews (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL UNIQUE,
    base_id TEXT REFERENCES product_bases(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'rejected')),
    inputs_snapshot TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_design_reviews_project ON design_reviews(project_id);

CREATE TABLE design_review_items (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES design_reviews(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (review_id, display_code)
);

CREATE TABLE design_review_item_revisions (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL
        REFERENCES design_review_items(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL,
    check_point TEXT NOT NULL,
    standard_basis TEXT NOT NULL,
    responsible_role TEXT NOT NULL,
    dependencies TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'current'
        CHECK (status IN ('current', 'stale')),
    created_at TEXT NOT NULL,
    UNIQUE (item_id, revision)
);

CREATE TABLE design_review_confirmations (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES design_reviews(id) ON DELETE RESTRICT,
    review_revision INTEGER NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'rejected')),
    comment TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (review_id, review_revision)
);

CREATE TABLE fmea_documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL UNIQUE,
    base_id TEXT REFERENCES product_bases(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'rejected')),
    inputs_snapshot TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_fmea_documents_project ON fmea_documents(project_id);

CREATE TABLE fmea_items (
    id TEXT PRIMARY KEY,
    fmea_id TEXT NOT NULL REFERENCES fmea_documents(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (fmea_id, display_code)
);

CREATE TABLE fmea_item_revisions (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES fmea_items(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL,
    function_text TEXT NOT NULL,
    failure_mode TEXT NOT NULL,
    cause TEXT NOT NULL,
    effect TEXT NOT NULL,
    control TEXT NOT NULL,
    action_text TEXT NOT NULL,
    severity INTEGER CHECK (severity BETWEEN 1 AND 10),
    occurrence INTEGER CHECK (occurrence BETWEEN 1 AND 10),
    detection INTEGER CHECK (detection BETWEEN 1 AND 10),
    scores_confirmed INTEGER NOT NULL DEFAULT 0
        CHECK (scores_confirmed IN (0, 1)),
    dependencies TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'current'
        CHECK (status IN ('current', 'stale')),
    created_at TEXT NOT NULL,
    UNIQUE (item_id, revision)
);

CREATE TABLE fmea_confirmations (
    id TEXT PRIMARY KEY,
    fmea_id TEXT NOT NULL REFERENCES fmea_documents(id) ON DELETE RESTRICT,
    fmea_revision INTEGER NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'rejected')),
    comment TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (fmea_id, fmea_revision)
);
