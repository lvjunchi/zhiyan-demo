ALTER TABLE source_documents ADD COLUMN parsed_at TEXT;

ALTER TABLE requirements ADD COLUMN parser_key TEXT NOT NULL DEFAULT '';
ALTER TABLE requirements ADD COLUMN condition_text TEXT NOT NULL DEFAULT '';

CREATE INDEX idx_requirements_project_parser_key
    ON requirements(project_id, parser_key);

CREATE TABLE issues (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    source_document_id TEXT REFERENCES source_documents(id) ON DELETE RESTRICT,
    requirement_id TEXT REFERENCES requirements(id) ON DELETE RESTRICT,
    parser_key TEXT NOT NULL DEFAULT '',
    issue_type TEXT NOT NULL
        CHECK (issue_type IN ('missing', 'ambiguous', 'contradictory', 'unparsed', 'invalid')),
    category TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'medium'
        CHECK (severity IN ('low', 'medium', 'high', 'blocking')),
    message TEXT NOT NULL,
    source_location TEXT NOT NULL DEFAULT '',
    source_excerpt TEXT NOT NULL DEFAULT '',
    blocking_reason TEXT NOT NULL DEFAULT '',
    suggestion TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed')),
    created_at TEXT NOT NULL,
    closed_at TEXT,
    close_reason TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_issues_project_status ON issues(project_id, status);

CREATE TABLE requirement_references (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    requirement_id TEXT NOT NULL REFERENCES requirements(id) ON DELETE RESTRICT,
    referenced_requirement_id TEXT NOT NULL REFERENCES requirements(id) ON DELETE RESTRICT,
    relation TEXT NOT NULL CHECK (relation IN ('>=', '>', '<=', '<', '=')),
    created_at TEXT NOT NULL,
    UNIQUE (requirement_id, referenced_requirement_id, relation)
);

CREATE INDEX idx_requirement_references_requirement
    ON requirement_references(requirement_id);
