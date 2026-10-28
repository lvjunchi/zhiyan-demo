CREATE TABLE source_document_files (
    source_document_id TEXT PRIMARY KEY REFERENCES source_documents(id) ON DELETE RESTRICT,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 8388608),
    content BLOB NOT NULL,
    extracted_text_hash TEXT NOT NULL,
    reviewed_text_changed INTEGER NOT NULL CHECK (reviewed_text_changed IN (0,1)),
    archived_at TEXT NOT NULL
);
CREATE TRIGGER source_file_immutable_update BEFORE UPDATE ON source_document_files
BEGIN SELECT RAISE(ABORT, 'source originals are immutable'); END;
CREATE TRIGGER source_file_immutable_delete BEFORE DELETE ON source_document_files
BEGIN SELECT RAISE(ABORT, 'source originals are immutable'); END;
