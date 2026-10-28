CREATE TABLE test_plans (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'rejected')),
    purpose TEXT NOT NULL,
    conditions_text TEXT NOT NULL,
    sample_description TEXT NOT NULL,
    load_conditions_text TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    inputs_snapshot TEXT NOT NULL DEFAULT '{}',
    source_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_test_plans_project ON test_plans(project_id);

CREATE TABLE test_plan_confirmations (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES test_plans(id) ON DELETE RESTRICT,
    plan_revision INTEGER NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'rejected')),
    comment TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (plan_id, plan_revision)
);

CREATE TABLE test_cases (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES test_plans(id) ON DELETE RESTRICT,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    case_key TEXT NOT NULL,
    case_kind TEXT NOT NULL DEFAULT 'manual'
        CHECK (case_kind IN ('manual', 'static_torsion')),
    revision INTEGER NOT NULL DEFAULT 1,
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft', 'pending_review', 'confirmed', 'rejected')),
    validity TEXT NOT NULL DEFAULT 'current'
        CHECK (validity IN ('current', 'stale')),
    title TEXT NOT NULL,
    purpose TEXT NOT NULL,
    conditions_text TEXT NOT NULL,
    load_conditions_text TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    load_basis_requirement_id TEXT
        REFERENCES requirements(id) ON DELETE RESTRICT,
    minimum_coefficient REAL,
    requirement_refs TEXT NOT NULL DEFAULT '[]',
    fmea_refs TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (plan_id, display_code)
);

CREATE INDEX idx_test_cases_project ON test_cases(project_id);

CREATE TABLE test_case_revisions (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES test_cases(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL,
    title TEXT NOT NULL,
    purpose TEXT NOT NULL,
    conditions_text TEXT NOT NULL,
    load_conditions_text TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    load_basis_requirement_id TEXT,
    minimum_coefficient REAL,
    requirement_refs TEXT NOT NULL,
    fmea_refs TEXT NOT NULL,
    validity TEXT NOT NULL DEFAULT 'current'
        CHECK (validity IN ('current', 'stale')),
    review_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (review_status IN ('draft', 'pending_review', 'confirmed', 'rejected')),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    change_reason TEXT NOT NULL DEFAULT '',
    UNIQUE (case_id, revision)
);

CREATE TABLE test_case_confirmations (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES test_cases(id) ON DELETE RESTRICT,
    case_revision INTEGER NOT NULL,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('confirmed', 'rejected')),
    comment TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (case_id, case_revision)
);

CREATE TABLE test_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    case_id TEXT NOT NULL REFERENCES test_cases(id) ON DELETE RESTRICT,
    case_revision INTEGER NOT NULL,
    run_no INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed'
        CHECK (status IN ('not_run', 'running', 'completed')),
    result TEXT CHECK (result IN ('pass', 'fail', 'incomplete', 'invalid')),
    mode TEXT NOT NULL CHECK (mode IN ('rule', 'mock', 'manual')),
    conditions_text TEXT NOT NULL,
    evidence TEXT NOT NULL,
    load_basis_numeric REAL,
    backup_coefficient REAL,
    manual_result TEXT,
    reasons TEXT NOT NULL DEFAULT '[]',
    measured_values TEXT NOT NULL DEFAULT '{}',
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (case_id, run_no)
);

CREATE INDEX idx_test_runs_case ON test_runs(case_id, case_revision);
