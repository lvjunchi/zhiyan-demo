CREATE TABLE consistency_checks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    check_no INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'rejected')),
    validity TEXT NOT NULL DEFAULT 'current'
        CHECK (validity IN ('current', 'stale')),
    mode TEXT NOT NULL CHECK (mode IN ('rule', 'mock', 'manual')),
    source_label TEXT NOT NULL,
    input_snapshot TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    conflicts_json TEXT NOT NULL DEFAULT '[]',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, display_code),
    UNIQUE (project_id, check_no)
);

CREATE INDEX idx_consistency_checks_project
    ON consistency_checks(project_id, check_no DESC);

CREATE TABLE consistency_check_confirmations (
    id TEXT PRIMARY KEY,
    check_id TEXT NOT NULL
        REFERENCES consistency_checks(id) ON DELETE RESTRICT,
    check_revision INTEGER NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'rejected')),
    comment TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (check_id, check_revision)
);

CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    check_id TEXT NOT NULL
        REFERENCES consistency_checks(id) ON DELETE RESTRICT,
    last_check_id TEXT NOT NULL
        REFERENCES consistency_checks(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    stable_key TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    conflict_type TEXT NOT NULL
        CHECK (conflict_type IN ('parameter', 'version', 'reference', 'condition', 'rule')),
    severity TEXT NOT NULL
        CHECK (severity IN ('low', 'medium', 'high', 'blocking')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed')),
    detected INTEGER NOT NULL DEFAULT 1 CHECK (detected IN (0, 1)),
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_revision INTEGER NOT NULL,
    object_review_status TEXT NOT NULL DEFAULT '',
    last_check_no INTEGER NOT NULL,
    last_checked_at TEXT NOT NULL,
    recheck_status TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    resolution_type TEXT NOT NULL DEFAULT '',
    resolution_note TEXT NOT NULL DEFAULT '',
    evidence_text TEXT NOT NULL DEFAULT '',
    accepted_risk INTEGER NOT NULL DEFAULT 0
        CHECK (accepted_risk IN (0, 1)),
    closed_by TEXT NOT NULL DEFAULT '',
    closed_role TEXT NOT NULL DEFAULT '',
    closed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, stable_key)
);

CREATE INDEX idx_conflicts_project_status
    ON conflicts(project_id, status, severity);
CREATE INDEX idx_conflicts_object ON conflicts(object_type, object_id);

CREATE TABLE conflict_events (
    id TEXT PRIMARY KEY,
    conflict_id TEXT NOT NULL REFERENCES conflicts(id) ON DELETE RESTRICT,
    check_id TEXT REFERENCES consistency_checks(id) ON DELETE RESTRICT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_conflict_events_conflict
    ON conflict_events(conflict_id, created_at);
