ALTER TABLE design_reviews ADD COLUMN validity TEXT NOT NULL DEFAULT 'current'
    CHECK (validity IN ('current', 'stale'));
ALTER TABLE fmea_documents ADD COLUMN validity TEXT NOT NULL DEFAULT 'current'
    CHECK (validity IN ('current', 'stale'));
