CREATE TABLE document_imports (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 filename TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
 status TEXT NOT NULL CHECK(status IN ('awaiting_review','failed','archived','completed','cancelled')),
 stage TEXT NOT NULL,
 error_message TEXT NOT NULL DEFAULT '',
 source_document_id TEXT UNIQUE REFERENCES source_documents(id) ON DELETE RESTRICT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX idx_document_imports_project ON document_imports(project_id,created_at,id);
