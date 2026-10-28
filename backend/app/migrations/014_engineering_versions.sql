ALTER TABLE variant_points ADD COLUMN is_applicable INTEGER NOT NULL DEFAULT 1 CHECK (is_applicable IN (0,1));
ALTER TABLE reusable_part_decisions ADD COLUMN is_applicable INTEGER NOT NULL DEFAULT 1 CHECK (is_applicable IN (0,1));
ALTER TABLE variant_points ADD COLUMN revision INTEGER NOT NULL DEFAULT 1 CHECK (revision>=1);
ALTER TABLE variant_points ADD COLUMN review_status TEXT NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft','pending_review','confirmed','rejected'));
ALTER TABLE variant_points ADD COLUMN dependency_versions TEXT NOT NULL DEFAULT '[]';
ALTER TABLE reusable_part_decisions ADD COLUMN revision INTEGER NOT NULL DEFAULT 1 CHECK (revision>=1);
ALTER TABLE reusable_part_decisions ADD COLUMN review_status TEXT NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft','pending_review','confirmed','rejected'));
ALTER TABLE reusable_part_decisions ADD COLUMN dependency_versions TEXT NOT NULL DEFAULT '[]';
CREATE TABLE engineering_record_versions (
 object_type TEXT NOT NULL CHECK (object_type IN ('variant','part')),
 object_id TEXT NOT NULL,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK (revision>=1),
 snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY (object_type,object_id,revision)
);
CREATE TABLE engineering_record_confirmations (
 id TEXT PRIMARY KEY,
 object_type TEXT NOT NULL,
 object_id TEXT NOT NULL,
 object_revision INTEGER NOT NULL,
 actor TEXT NOT NULL,
 role TEXT NOT NULL,
 decision TEXT NOT NULL CHECK (decision IN ('confirmed','rejected')),
 comment TEXT NOT NULL,
 created_at TEXT NOT NULL,
 FOREIGN KEY (object_type,object_id,object_revision) REFERENCES engineering_record_versions(object_type,object_id,revision) ON DELETE RESTRICT
);
INSERT INTO engineering_record_versions SELECT 'variant',id,project_id,1,json_object('id',id,'project_id',project_id,'base_id',base_id,'display_code',display_code,'parameter_key',parameter_key,'parameter_name',parameter_name,'base_value',base_value,'requirement_value',requirement_value,'variant_type',variant_type,'affected_parts',json(affected_parts),'upstream_requirement_ids',json(upstream_requirement_ids),'basis',basis,'status',status,'created_at',created_at,'updated_at',updated_at,'revision',1,'review_status','draft','dependency_versions',json('[]'),'migration_note','Only the current legacy row was retained; prior revisions unavailable'),updated_at FROM variant_points;
CREATE TRIGGER variant_points_retain_identity BEFORE DELETE ON variant_points
BEGIN SELECT RAISE(ABORT, 'versioned engineering records cannot be deleted'); END;
INSERT INTO engineering_record_versions SELECT 'part',id,project_id,1,json_object('id',id,'project_id',project_id,'base_id',base_id,'variant_point_id',variant_point_id,'part_display_code',part_display_code,'part_name',part_name,'part_number',part_number,'classification',classification,'reason',reason,'source',source,'created_at',created_at,'updated_at',updated_at,'status',status,'variant_keys',json(variant_keys),'revision',1,'review_status','draft','dependency_versions',json('[]'),'migration_note','Only the current legacy row was retained; prior revisions unavailable'),updated_at FROM reusable_part_decisions;
CREATE TRIGGER reusable_part_decisions_retain_identity BEFORE DELETE ON reusable_part_decisions
BEGIN SELECT RAISE(ABORT, 'versioned engineering records cannot be deleted'); END;
CREATE TRIGGER engineering_record_versions_immutable_update BEFORE UPDATE ON engineering_record_versions
BEGIN SELECT RAISE(ABORT, 'engineering history is immutable'); END;
CREATE TRIGGER engineering_record_versions_immutable_delete BEFORE DELETE ON engineering_record_versions
BEGIN SELECT RAISE(ABORT, 'engineering history is immutable'); END;
CREATE TRIGGER engineering_record_confirmations_immutable_update BEFORE UPDATE ON engineering_record_confirmations
BEGIN SELECT RAISE(ABORT, 'engineering history is immutable'); END;
CREATE TRIGGER engineering_record_confirmations_immutable_delete BEFORE DELETE ON engineering_record_confirmations
BEGIN SELECT RAISE(ABORT, 'engineering history is immutable'); END;
