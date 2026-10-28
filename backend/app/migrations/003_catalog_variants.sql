CREATE TABLE product_bases (
    id TEXT PRIMARY KEY,
    display_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    transmission_type TEXT NOT NULL
        CHECK (transmission_type IN ('AMT', 'MT', 'AT')),
    gear_count INTEGER NOT NULL,
    rated_input_torque REAL NOT NULL,
    first_gear_ratio REAL NOT NULL,
    top_gear_type TEXT NOT NULL
        CHECK (top_gear_type IN ('direct', 'overdrive')),
    has_pto INTEGER NOT NULL CHECK (has_pto IN (0, 1)),
    weight_kg REAL NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE base_parts (
    id TEXT PRIMARY KEY,
    base_id TEXT NOT NULL REFERENCES product_bases(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    name TEXT NOT NULL,
    part_number TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (base_id, display_code)
);

CREATE INDEX idx_base_parts_base ON base_parts(base_id);

CREATE TABLE variant_points (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    base_id TEXT NOT NULL REFERENCES product_bases(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    parameter_key TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    base_value TEXT NOT NULL DEFAULT '',
    requirement_value TEXT NOT NULL DEFAULT '',
    variant_type TEXT NOT NULL
        CHECK (variant_type IN ('parameter_adjustment', 'structural_change', 'new_function')),
    affected_parts TEXT NOT NULL DEFAULT '[]',
    upstream_requirement_ids TEXT NOT NULL DEFAULT '[]',
    basis TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'current'
        CHECK (status IN ('current', 'stale')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, base_id, parameter_key)
);

CREATE TABLE reusable_part_decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    base_id TEXT NOT NULL REFERENCES product_bases(id) ON DELETE RESTRICT,
    variant_point_id TEXT REFERENCES variant_points(id) ON DELETE RESTRICT,
    part_display_code TEXT NOT NULL,
    part_name TEXT NOT NULL,
    part_number TEXT NOT NULL,
    classification TEXT NOT NULL
        CHECK (classification IN ('carryover', 'modify', 'new_design')),
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (project_id, base_id, part_display_code)
);
