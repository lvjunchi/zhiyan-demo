CREATE TABLE coordination_topics (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    display_code TEXT NOT NULL,
    name TEXT NOT NULL,
    expected_participants TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('rule', 'mock', 'manual')),
    source_label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (project_id, display_code)
);

CREATE INDEX idx_coordination_topics_project
    ON coordination_topics(project_id, created_at);

CREATE TABLE coordination_records (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL
        REFERENCES coordination_topics(id) ON DELETE RESTRICT,
    external_id TEXT NOT NULL,
    record_type TEXT NOT NULL
        CHECK (record_type IN ('message', 'reopened')),
    sender TEXT NOT NULL,
    content_summary TEXT NOT NULL DEFAULT '',
    sent_at TEXT NOT NULL,
    reply_to_external_id TEXT,
    mode TEXT NOT NULL CHECK (mode IN ('rule', 'mock', 'manual')),
    created_at TEXT NOT NULL,
    UNIQUE (topic_id, external_id)
);

CREATE INDEX idx_coordination_records_topic
    ON coordination_records(topic_id, sent_at);

CREATE TABLE coordination_metric_runs (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL
        REFERENCES coordination_topics(id) ON DELETE RESTRICT,
    run_no INTEGER NOT NULL,
    rule_label TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    risk_json TEXT NOT NULL,
    cost_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (topic_id, run_no)
);
