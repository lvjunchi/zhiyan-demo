from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .db import transaction, utc_now
from . import source_files, engineering_versions
from .domain.parser import ParsedIssue, parse_protocol
from .domain.spectrum import (
    CandidateBase,
    MatchRequirement,
    recommend_bases,
)
from .domain.values import normalize_value
from .domain.variant import PARAMETER_PARTS, BasePart, compute_variants
from .domain.testing import VALIDATION_SCOPE
from .errors import (
    DomainValidationError,
    DuplicateDisplayCodeError,
    InvalidReferenceError,
    IssueStateConflictError,
    NotFoundError,
    VersionConflictError,
)
from .schemas import (
    CloseIssueRequest,
    ConfirmationCreate,
    ProjectCreate,
    ReopenIssueRequest,
    RequirementCreate,
    RequirementUpdate,
    SourceDocumentCreate,
)

SUBSTANTIVE_REQUIREMENT_FIELDS = (
    "category",
    "parameter_name",
    "data_type",
    "operator",
    "value_text",
    "value_num",
    "value_num_high",
    "unit",
    "raw_expression",
    "source_document_id",
    "source_location",
    "source_excerpt",
)

ISSUE_SEVERITY = {
    "contradictory": "high",
    "missing": "high",
    "ambiguous": "medium",
    "unparsed": "high",
    "invalid": "high",
}

CATALOG_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "product_catalog.json"
PARSER_KEY_ALIASES = {
    "换挡方式": "transmissionType",
    "档位数": "gearCount",
    "变速器最低额定输入扭矩": "gearboxRatedInputTorque",
    "一档速比": "firstGearRatio",
    "取力器": "pto",
    "总成重量上限": "assemblyWeight",
    "最高档形式": "topGearType",
}
SPECTRUM_REQUIREMENT_KEYS = {
    "transmissionType",
    "gearCount",
    "gearboxRatedInputTorque",
    "firstGearRatio",
    "pto",
    "assemblyWeight",
    "topGearType",
}


def _get_project_row(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("项目不存在", {"project_id": project_id})
    return row


def _get_requirement_row(
    connection: sqlite3.Connection, requirement_id: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM requirements WHERE id = ?", (requirement_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("需求不存在", {"requirement_id": requirement_id})
    return row


def _get_source_row(
    connection: sqlite3.Connection, source_document_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM source_documents WHERE id = ?", (source_document_id,)
    ).fetchone()


def _audit(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    object_type: str,
    object_id: str,
    object_revision: int | None,
    action: str,
    actor: str = "system",
    role: str = "system",
    decision: str | None = None,
    comment: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> str:
    event_id = str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO audit_events(
            id, project_id, object_type, object_id, object_revision,
            action, actor, role, decision, comment,
            before_json, after_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            project_id,
            object_type,
            object_id,
            object_revision,
            action,
            actor,
            role,
            decision,
            comment,
            json.dumps(before, ensure_ascii=False) if before is not None else None,
            json.dumps(after, ensure_ascii=False) if after is not None else None,
            utc_now(),
        ),
    )
    return event_id


def _audit_engineering_change(connection: sqlite3.Connection, **event: Any) -> str:
    from . import engineering_versions

    kinds = {"variant_point": "variant", "reusable_part_decision": "part"}
    kind = kinds.get(event["object_type"])
    if kind:
        object_id = event["object_id"]
        changed = False
        if not event["action"].endswith(".stale"):
            revision, changed = engineering_versions.capture(
                connection, kind, object_id
            )
        else:
            revision = engineering_versions.record(connection, kind, object_id)[
                "revision"
            ]
        event["object_revision"] = revision
        event["after"] = engineering_versions.record(connection, kind, object_id)
        if changed:
            current = event["after"]
            for table in ("design_reviews", "fmea_documents"):
                for document in connection.execute(
                    f"SELECT id,revision FROM {table} WHERE project_id=? AND base_id=? AND validity='current'",
                    (current["project_id"], current["base_id"]),
                ).fetchall():
                    connection.execute(
                        f"UPDATE {table} SET validity='stale' WHERE id=?",
                        (document["id"],),
                    )
                    _audit(
                        connection,
                        project_id=current["project_id"],
                        object_type=table,
                        object_id=document["id"],
                        object_revision=document["revision"],
                        action="design.engineering_dependency_stale",
                        after={"engineering_id": object_id, "revision": revision},
                    )
    return _audit(connection, **event)


def _audit_event_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    before_json = data.pop("before_json")
    after_json = data.pop("after_json")
    data["before"] = json.loads(before_json) if before_json else None
    data["after"] = json.loads(after_json) if after_json else None
    return data


def _requirement_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _insert_revision(
    connection: sqlite3.Connection,
    requirement_row: sqlite3.Row,
    *,
    status: str,
    created_by: str = "system",
    change_reason: str = "",
) -> str:
    revision_id = str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO requirement_revisions(
            id, requirement_id, revision_no, snapshot_json, status,
            source_document_id, source_location, source_excerpt,
            created_at, created_by, change_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revision_id,
            requirement_row["id"],
            requirement_row["current_revision"],
            json.dumps(_requirement_snapshot(requirement_row), ensure_ascii=False),
            status,
            requirement_row["source_document_id"],
            requirement_row["source_location"],
            requirement_row["source_excerpt"],
            utc_now(),
            created_by,
            change_reason,
        ),
    )
    return revision_id


def _next_sequence(connection: sqlite3.Connection, scope: str, start: int = 1) -> int:
    row = connection.execute(
        "SELECT next_value FROM sequences WHERE scope = ?", (scope,)
    ).fetchone()
    if row is None:
        value = start
        connection.execute(
            "INSERT INTO sequences(scope, next_value) VALUES(?, ?)",
            (scope, value + 1),
        )
    else:
        value = int(row["next_value"])
        connection.execute(
            "UPDATE sequences SET next_value = ? WHERE scope = ?",
            (value + 1, scope),
        )
    return value


def _allocate_project_display_code(connection: sqlite3.Connection) -> str:
    while True:
        value = _next_sequence(connection, "project")
        code = f"P{value:02d}"
        exists = connection.execute(
            "SELECT 1 FROM projects WHERE display_code = ?", (code,)
        ).fetchone()
        if exists is None:
            return code


def _allocate_requirement_display_code(
    connection: sqlite3.Connection,
    project: sqlite3.Row,
    category: str,
    reserved_codes: set[str] | None = None,
) -> str:
    scope = f"requirement:{project['id']}:{category}"
    reserved = reserved_codes or set()
    while True:
        value = _next_sequence(connection, scope)
        code = f"REQ-{project['display_code']}-{category}-{value:03d}"
        if code in reserved:
            continue
        exists = connection.execute(
            "SELECT 1 FROM requirements WHERE project_id = ? AND display_code = ?",
            (project["id"], code),
        ).fetchone()
        if exists is None:
            return code


def _display_code_exists(
    connection: sqlite3.Connection, project_id: str, display_code: str
) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM requirements WHERE project_id = ? AND display_code = ?",
            (project_id, display_code),
        ).fetchone()
        is not None
    )


def _ensure_unique_project_display_code(
    connection: sqlite3.Connection, display_code: str
) -> None:
    exists = connection.execute(
        "SELECT 1 FROM projects WHERE display_code = ?", (display_code,)
    ).fetchone()
    if exists is not None:
        raise DuplicateDisplayCodeError(
            "项目显示编号已存在", {"display_code": display_code}
        )


def _ensure_unique_requirement_display_code(
    connection: sqlite3.Connection, project_id: str, display_code: str
) -> None:
    exists = connection.execute(
        "SELECT 1 FROM requirements WHERE project_id = ? AND display_code = ?",
        (project_id, display_code),
    ).fetchone()
    if exists is not None:
        raise DuplicateDisplayCodeError(
            "需求显示编号已存在",
            {"display_code": display_code, "project_id": project_id},
        )


def create_project(
    connection: sqlite3.Connection, payload: ProjectCreate
) -> dict[str, Any]:
    with transaction(connection):
        display_code = payload.display_code
        if display_code is None:
            display_code = _allocate_project_display_code(connection)
        else:
            _ensure_unique_project_display_code(connection, display_code)

        project_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO projects(
                id, display_code, name, customer, product, stage,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                display_code,
                payload.name,
                payload.customer,
                payload.product,
                "requirement_parsing",
                now,
                now,
            ),
        )
        row = _get_project_row(connection, project_id)
        project = dict(row)
        _audit(
            connection,
            project_id=project_id,
            object_type="project",
            object_id=project_id,
            object_revision=None,
            action="project.created",
            after=project,
        )
        return project


def list_projects(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM projects ORDER BY created_at ASC, display_code ASC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_project(connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    return dict(_get_project_row(connection, project_id))


def create_source_document(
    connection: sqlite3.Connection,
    project_id: str,
    payload: SourceDocumentCreate,
) -> dict[str, Any]:
    with transaction(connection):
        _get_project_row(connection, project_id)
        document_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()
        try:
            connection.execute(
                """
                INSERT INTO source_documents(
                    id, project_id, display_code, doc_type, version,
                    content_hash, original_text, mode, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    project_id,
                    payload.display_code,
                    payload.doc_type,
                    payload.version,
                    content_hash,
                    payload.content,
                    payload.mode,
                    utc_now(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateDisplayCodeError(
                "同一项目、编号和版本的文件已存在",
                {
                    "display_code": payload.display_code,
                    "version": payload.version,
                    "project_id": project_id,
                },
            ) from exc
        row = connection.execute(
            "SELECT * FROM source_documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError("来源文档创建失败")
        document = dict(row)
        if payload.original_file is not None:
            source_files.store(
                connection, document_id, payload.original_file, payload.content
            )
        document["original_file"] = source_files.metadata(connection, document_id)
        if payload.import_id is not None:
            from . import document_imports

            document_imports.link(
                connection,
                project_id,
                document_id,
                payload.import_id,
                payload.original_file,
            )
        audit_document = {
            key: value for key, value in document.items() if key != "original_text"
        }
        _audit(
            connection,
            project_id=project_id,
            object_type="source_document",
            object_id=document_id,
            object_revision=None,
            action="source_document.created",
            after=audit_document,
        )
        return document


def list_requirements(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _get_project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM requirements
        WHERE project_id = ?
        ORDER BY created_at ASC, display_code ASC
        """,
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_requirement(
    connection: sqlite3.Connection, requirement_id: str
) -> dict[str, Any]:
    row = _get_requirement_row(connection, requirement_id)
    requirement = dict(row)
    reference_rows = connection.execute(
        """
        SELECT rr.id, rr.project_id, rr.requirement_id,
               rr.referenced_requirement_id, rr.relation, rr.created_at,
               r.display_code AS referenced_display_code,
               r.parameter_name AS referenced_parameter_name
        FROM requirement_references rr
        JOIN requirements r ON r.id = rr.referenced_requirement_id
        WHERE rr.requirement_id = ?
        ORDER BY rr.created_at ASC, rr.id ASC
        """,
        (requirement_id,),
    ).fetchall()
    requirement["references"] = [dict(ref) for ref in reference_rows]
    return requirement


def create_requirement(
    connection: sqlite3.Connection,
    project_id: str,
    payload: RequirementCreate,
) -> dict[str, Any]:
    with transaction(connection):
        project = _get_project_row(connection, project_id)

        if payload.source_document_id is not None:
            source = _get_source_row(connection, payload.source_document_id)
            if source is None or source["project_id"] != project_id:
                raise InvalidReferenceError(
                    "来源文档不存在或不属于当前项目",
                    {
                        "source_document_id": payload.source_document_id,
                        "project_id": project_id,
                    },
                )

        try:
            normalized = normalize_value(
                payload.data_type, payload.operator, payload.value_text
            )
        except ValueError as exc:
            raise DomainValidationError(str(exc)) from exc

        if payload.display_code is None:
            display_code = _allocate_requirement_display_code(
                connection, project, payload.category
            )
        else:
            display_code = payload.display_code
            _ensure_unique_requirement_display_code(
                connection, project_id, display_code
            )

        requirement_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO requirements(
                id, project_id, display_code, category, parameter_name,
                data_type, operator, value_text, value_num, value_num_high,
                unit, raw_expression, source_document_id, source_location,
                source_excerpt, review_status, validity, current_revision,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                requirement_id,
                project_id,
                display_code,
                payload.category,
                payload.parameter_name,
                payload.data_type,
                normalized.operator,
                normalized.value_text,
                normalized.value_num,
                normalized.value_num_high,
                payload.unit,
                payload.raw_expression or payload.value_text,
                payload.source_document_id,
                payload.source_location,
                payload.source_excerpt,
                "draft",
                "current",
                1,
                now,
                now,
            ),
        )
        row = _get_requirement_row(connection, requirement_id)
        _insert_revision(connection, row, status="current", change_reason="创建")
        _audit(
            connection,
            project_id=project_id,
            object_type="requirement",
            object_id=requirement_id,
            object_revision=1,
            action="requirement.created",
            after=_requirement_snapshot(row),
        )
        return dict(row)


def update_requirement(
    connection: sqlite3.Connection,
    requirement_id: str,
    payload: RequirementUpdate,
) -> dict[str, Any]:
    with transaction(connection):
        return _update_requirement_in_transaction(connection, requirement_id, payload)


def _update_requirement_in_transaction(
    connection: sqlite3.Connection,
    requirement_id: str,
    payload: RequirementUpdate,
) -> dict[str, Any]:
    row = _get_requirement_row(connection, requirement_id)
    if payload.expected_revision != row["current_revision"]:
        raise VersionConflictError(
            "需求已被更新，请刷新后重试",
            {
                "expected_revision": payload.expected_revision,
                "current_revision": row["current_revision"],
            },
        )

    updates = payload.model_dump(exclude_unset=True)
    updates.pop("expected_revision", None)
    if not updates:
        return dict(row)

    candidate = dict(row)
    for field in SUBSTANTIVE_REQUIREMENT_FIELDS:
        if field in updates:
            candidate[field] = updates[field]

    if "source_document_id" in updates:
        source_document_id = updates["source_document_id"]
        if source_document_id is not None:
            source = _get_source_row(connection, source_document_id)
            if source is None or source["project_id"] != row["project_id"]:
                raise InvalidReferenceError(
                    "来源文档不存在或不属于当前项目",
                    {
                        "source_document_id": source_document_id,
                        "project_id": row["project_id"],
                    },
                )

    try:
        normalized = normalize_value(
            candidate["data_type"],
            candidate["operator"],
            candidate["value_text"],
        )
    except ValueError as exc:
        raise DomainValidationError(str(exc)) from exc

    candidate["operator"] = normalized.operator
    candidate["value_text"] = normalized.value_text
    candidate["value_num"] = normalized.value_num
    candidate["value_num_high"] = normalized.value_num_high

    changed = {
        field: candidate[field]
        for field in SUBSTANTIVE_REQUIREMENT_FIELDS
        if candidate[field] != row[field]
    }
    if not changed:
        return dict(row)

    new_revision = row["current_revision"] + 1
    connection.execute(
        """
        UPDATE requirement_revisions
        SET status = 'superseded'
        WHERE requirement_id = ? AND status = 'current'
        """,
        (requirement_id,),
    )
    connection.execute(
        """
        UPDATE requirements SET
            category = ?, parameter_name = ?, data_type = ?,
            operator = ?, value_text = ?, value_num = ?,
            value_num_high = ?, unit = ?, raw_expression = ?,
            source_document_id = ?, source_location = ?,
            source_excerpt = ?, review_status = 'draft',
            current_revision = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            candidate["category"],
            candidate["parameter_name"],
            candidate["data_type"],
            candidate["operator"],
            candidate["value_text"],
            candidate["value_num"],
            candidate["value_num_high"],
            candidate["unit"],
            candidate["raw_expression"],
            candidate["source_document_id"],
            candidate["source_location"],
            candidate["source_excerpt"],
            new_revision,
            utc_now(),
            requirement_id,
        ),
    )
    updated_row = _get_requirement_row(connection, requirement_id)
    _insert_revision(
        connection,
        updated_row,
        status="current",
        change_reason="需求实质变更",
    )
    _audit(
        connection,
        project_id=row["project_id"],
        object_type="requirement",
        object_id=requirement_id,
        object_revision=new_revision,
        action="requirement.updated",
        before=_requirement_snapshot(row),
        after=_requirement_snapshot(updated_row),
    )
    from .testing_services import (
        mark_test_cases_stale_for_requirement,
    )

    mark_test_cases_stale_for_requirement(connection, requirement_id, new_revision)
    from .consistency_services import mark_consistency_checks_stale

    mark_consistency_checks_stale(
        connection,
        row["project_id"],
        f"需求 {row['display_code']} 升至版本 {new_revision}",
    )
    _mark_variant_decisions_stale(
        connection, row["project_id"], requirement_id, _infer_parser_key(row)
    )
    from .design_services import mark_design_stale_for_requirement

    mark_design_stale_for_requirement(connection, row["project_id"], requirement_id)
    if row["parser_key"] == "engineMaxTorque":
        derived_rows = connection.execute(
            """SELECT r.* FROM requirement_references rr
               JOIN requirements r ON r.id = rr.requirement_id
               WHERE rr.referenced_requirement_id = ? AND rr.relation = '>='
                 AND r.parser_key = 'gearboxRatedInputTorque' AND r.project_id = ?""",
            (requirement_id, row["project_id"]),
        ).fetchall()
        for derived in derived_rows:
            if candidate["value_num"] is None or candidate["unit"] != derived["unit"]:
                raise DomainValidationError(
                    "发动机扭矩与派生要求必须使用相同的有效数值单位"
                )
            updated_derived = _update_requirement_in_transaction(
                connection,
                derived["id"],
                RequirementUpdate(
                    expected_revision=derived["current_revision"],
                    value_text=candidate["value_text"],
                    raw_expression=f"gearboxRatedInputTorque >= engineMaxTorque (source V{new_revision})",
                ),
            )
            connection.execute(
                """INSERT INTO object_dependencies(id, project_id, upstream_type, upstream_id,
                   upstream_revision, downstream_type, downstream_id, downstream_revision, created_at)
                   VALUES (?, ?, 'requirement', ?, ?, 'requirement', ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    row["project_id"],
                    requirement_id,
                    new_revision,
                    derived["id"],
                    updated_derived["current_revision"],
                    utc_now(),
                ),
            )
    return dict(updated_row)


def confirm_requirement(
    connection: sqlite3.Connection,
    requirement_id: str,
    payload: ConfirmationCreate,
) -> dict[str, Any]:
    with transaction(connection):
        return _confirm_requirement_in_transaction(connection, requirement_id, payload)


def _confirm_requirement_in_transaction(
    connection: sqlite3.Connection,
    requirement_id: str,
    payload: ConfirmationCreate,
) -> dict[str, Any]:
    row = _get_requirement_row(connection, requirement_id)
    if payload.expected_revision != row["current_revision"]:
        raise VersionConflictError(
            "需求已被更新，请刷新后重试",
            {
                "expected_revision": payload.expected_revision,
                "current_revision": row["current_revision"],
            },
        )

    new_status = "confirmed" if payload.decision == "confirmed" else "rejected"
    action = (
        "requirement.confirmed"
        if payload.decision == "confirmed"
        else "requirement.rejected"
    )
    before = _requirement_snapshot(row)
    connection.execute(
        "UPDATE requirements SET review_status = ?, updated_at = ? WHERE id = ?",
        (new_status, utc_now(), requirement_id),
    )
    updated_row = _get_requirement_row(connection, requirement_id)
    event_id = _audit(
        connection,
        project_id=row["project_id"],
        object_type="requirement",
        object_id=requirement_id,
        object_revision=row["current_revision"],
        action=action,
        actor=payload.actor,
        role=payload.role,
        decision=payload.decision,
        comment=payload.comment,
        before=before,
        after=_requirement_snapshot(updated_row),
    )
    event = connection.execute(
        "SELECT * FROM audit_events WHERE id = ?", (event_id,)
    ).fetchone()
    if event is None:
        raise NotFoundError("确认记录创建失败")
    return _audit_event_dict(event)


def _list_requirements_by_source(
    connection: sqlite3.Connection, source_document_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT * FROM requirements
        WHERE source_document_id = ?
        ORDER BY created_at ASC, display_code ASC
        """,
        (source_document_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _list_issues_by_source(
    connection: sqlite3.Connection, source_document_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT * FROM issues
        WHERE source_document_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (source_document_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _list_references_by_source(
    connection: sqlite3.Connection, source_document_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT rr.*
        FROM requirement_references rr
        JOIN requirements r ON r.id = rr.requirement_id
        WHERE r.source_document_id = ?
        ORDER BY rr.created_at ASC, rr.id ASC
        """,
        (source_document_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _insert_issue(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    source_document_id: str,
    issue: ParsedIssue,
    key_to_ids: dict[str, list[str]],
) -> dict[str, Any]:
    issue_id = str(uuid.uuid4())
    requirement_id = None
    if issue.requirement_key:
        ids = key_to_ids.get(issue.requirement_key, [])
        if len(ids) == 1:
            requirement_id = ids[0]
    severity = ISSUE_SEVERITY.get(issue.issue_type, "medium")
    if issue.issue_type == "ambiguous" and any(
        item.key == issue.requirement_key for item in VALIDATION_SCOPE
    ):
        severity = "high"
    connection.execute(
        """
        INSERT INTO issues(
            id, project_id, source_document_id, requirement_id, parser_key,
            issue_type, category, severity, message, source_location,
            source_excerpt, blocking_reason, suggestion, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            issue_id,
            project_id,
            source_document_id,
            requirement_id,
            issue.requirement_key or "",
            issue.issue_type,
            issue.category,
            severity,
            issue.message,
            issue.source_location,
            issue.source_excerpt,
            issue.blocking_reason,
            issue.suggestion,
            "open",
            utc_now(),
        ),
    )
    row = connection.execute(
        "SELECT * FROM issues WHERE id = ?", (issue_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("问题记录创建失败")
    issue_dict = dict(row)
    _audit(
        connection,
        project_id=project_id,
        object_type="issue",
        object_id=issue_id,
        object_revision=None,
        action="issue.opened",
        actor="rule_parser",
        role="system",
        after=issue_dict,
    )
    return issue_dict


def list_issues(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _get_project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM issues
        WHERE project_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def parse_source_document(
    connection: sqlite3.Connection,
    source_document_id: str,
    display_code_map: dict[str, str],
) -> dict[str, Any]:
    with transaction(connection):
        source = connection.execute(
            "SELECT * FROM source_documents WHERE id = ?",
            (source_document_id,),
        ).fetchone()
        if source is None:
            raise NotFoundError(
                "来源文档不存在",
                {"source_document_id": source_document_id},
            )
        project = _get_project_row(connection, source["project_id"])
        parse_result = parse_protocol(source["original_text"])

        if source["parsed_at"] is not None:
            existing_requirements = _list_requirements_by_source(
                connection, source_document_id
            )
            existing_issues = _list_issues_by_source(connection, source_document_id)
            return {
                "source_document_id": source_document_id,
                "project_id": project["id"],
                "mode": parse_result.mode,
                "status": (
                    "parsed" if existing_requirements else "needs_manual_review"
                ),
                "already_parsed": True,
                "parsed_at": source["parsed_at"],
                "requirements": existing_requirements,
                "issues": existing_issues,
                "missing_categories": parse_result.missing_categories,
                "unrecognized_clauses": parse_result.unrecognized_clauses,
                "references": _list_references_by_source(
                    connection, source_document_id
                ),
            }

        reserved_codes = set(display_code_map.values())
        used_codes: set[str] = set()
        key_to_ids: dict[str, list[str]] = {}
        created_requirements: list[dict[str, Any]] = []
        created_references: list[dict[str, Any]] = []
        extra_issues: list[ParsedIssue] = []

        for parsed in parse_result.requirements:
            try:
                normalized = normalize_value(
                    parsed.data_type, parsed.operator, parsed.value_text
                )
            except ValueError as exc:
                extra_issues.append(
                    ParsedIssue(
                        issue_type="invalid",
                        category=parsed.category,
                        message=(f"{parsed.parameter_name}数值无效：{exc}"),
                        source_location=parsed.source_location,
                        source_excerpt=parsed.source_excerpt,
                        blocking_reason="规则解析得到的值无法通过领域校验",
                        suggestion="请人工核对数值、单位或比较关系",
                        requirement_key=parsed.key,
                    )
                )
                continue

            mapped = display_code_map.get(parsed.key)
            if mapped is not None and mapped not in used_codes:
                if _display_code_exists(connection, project["id"], mapped):
                    raise DuplicateDisplayCodeError(
                        "解析映射的显示编号已存在",
                        {
                            "display_code": mapped,
                            "project_id": project["id"],
                        },
                    )
                display_code = mapped
            else:
                display_code = _allocate_requirement_display_code(
                    connection,
                    project,
                    parsed.category,
                    reserved_codes,
                )
            used_codes.add(display_code)

            requirement_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO requirements(
                    id, project_id, display_code, category, parameter_name,
                    data_type, operator, value_text, value_num, value_num_high,
                    unit, raw_expression, source_document_id, source_location,
                    source_excerpt, review_status, validity, current_revision,
                    created_at, updated_at, parser_key, condition_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    requirement_id,
                    project["id"],
                    display_code,
                    parsed.category,
                    parsed.parameter_name,
                    parsed.data_type,
                    normalized.operator,
                    normalized.value_text,
                    normalized.value_num,
                    normalized.value_num_high,
                    parsed.unit,
                    parsed.raw_expression,
                    source_document_id,
                    parsed.source_location,
                    parsed.source_excerpt,
                    "draft",
                    "current",
                    1,
                    now,
                    now,
                    parsed.key,
                    parsed.condition_text,
                ),
            )
            row = _get_requirement_row(connection, requirement_id)
            _insert_revision(
                connection,
                row,
                status="current",
                change_reason="协议解析",
                created_by="rule_parser",
            )
            _audit(
                connection,
                project_id=project["id"],
                object_type="requirement",
                object_id=requirement_id,
                object_revision=1,
                action="requirement.created",
                actor="rule_parser",
                role="system",
                after=_requirement_snapshot(row),
            )
            key_to_ids.setdefault(parsed.key, []).append(requirement_id)
            created_requirements.append(dict(row))

        for parsed in parse_result.requirements:
            if not parsed.reference_key:
                continue
            downstream_ids = key_to_ids.get(parsed.key, [])
            upstream_ids = key_to_ids.get(parsed.reference_key, [])
            if not downstream_ids or not upstream_ids:
                extra_issues.append(
                    ParsedIssue(
                        issue_type="missing",
                        category=parsed.category,
                        message=(
                            f"无法建立派生引用：{parsed.parameter_name}"
                            f" -> {parsed.reference_key}"
                        ),
                        source_location=parsed.source_location,
                        source_excerpt=parsed.source_excerpt,
                        blocking_reason="派生引用的上游或下游需求未成功创建",
                        suggestion="请人工补录或重新解析",
                        requirement_key=parsed.key,
                    )
                )
                continue
            for downstream_id in downstream_ids:
                downstream_row = _get_requirement_row(connection, downstream_id)
                for upstream_id in upstream_ids:
                    upstream_row = _get_requirement_row(connection, upstream_id)
                    reference_id = str(uuid.uuid4())
                    connection.execute(
                        """
                        INSERT INTO requirement_references(
                            id, project_id, requirement_id,
                            referenced_requirement_id, relation, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            reference_id,
                            project["id"],
                            downstream_id,
                            upstream_id,
                            parsed.reference_relation or "=",
                            utc_now(),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO object_dependencies(
                            id, project_id, upstream_type, upstream_id,
                            upstream_revision, downstream_type, downstream_id,
                            downstream_revision, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            project["id"],
                            "requirement",
                            upstream_id,
                            upstream_row["current_revision"],
                            "requirement",
                            downstream_id,
                            downstream_row["current_revision"],
                            utc_now(),
                        ),
                    )
                    reference_row = connection.execute(
                        "SELECT * FROM requirement_references WHERE id = ?",
                        (reference_id,),
                    ).fetchone()
                    if reference_row is not None:
                        created_references.append(dict(reference_row))

        all_issues = list(parse_result.issues) + extra_issues
        created_issues = [
            _insert_issue(
                connection,
                project_id=project["id"],
                source_document_id=source_document_id,
                issue=issue,
                key_to_ids=key_to_ids,
            )
            for issue in all_issues
        ]

        parsed_at = utc_now()
        from . import document_imports

        document_imports.mark_parse(connection, source_document_id)
        connection.execute(
            "UPDATE source_documents SET parsed_at = ? WHERE id = ?",
            (parsed_at, source_document_id),
        )
        _audit(
            connection,
            project_id=project["id"],
            object_type="source_document",
            object_id=source_document_id,
            object_revision=None,
            action="source_document.parsed",
            actor="rule_parser",
            role="system",
            after={
                "mode": parse_result.mode,
                "requirement_count": len(created_requirements),
                "issue_count": len(created_issues),
                "missing_categories": parse_result.missing_categories,
            },
        )

        return {
            "source_document_id": source_document_id,
            "project_id": project["id"],
            "mode": parse_result.mode,
            "status": ("parsed" if created_requirements else "needs_manual_review"),
            "already_parsed": False,
            "parsed_at": parsed_at,
            "requirements": created_requirements,
            "issues": created_issues,
            "missing_categories": parse_result.missing_categories,
            "unrecognized_clauses": parse_result.unrecognized_clauses,
            "references": created_references,
        }


def list_revisions(
    connection: sqlite3.Connection, requirement_id: str
) -> list[dict[str, Any]]:
    _get_requirement_row(connection, requirement_id)
    rows = connection.execute(
        """
        SELECT * FROM requirement_revisions
        WHERE requirement_id = ?
        ORDER BY revision_no ASC
        """,
        (requirement_id,),
    ).fetchall()
    revisions: list[dict[str, Any]] = []
    for row in rows:
        revisions.append(
            {
                "id": row["id"],
                "requirement_id": row["requirement_id"],
                "revision_no": row["revision_no"],
                "snapshot": json.loads(row["snapshot_json"]),
                "status": row["status"],
                "source_document_id": row["source_document_id"],
                "source_location": row["source_location"],
                "source_excerpt": row["source_excerpt"],
                "created_at": row["created_at"],
                "created_by": row["created_by"],
                "change_reason": row["change_reason"],
            }
        )
    return revisions


def list_confirmations(
    connection: sqlite3.Connection, requirement_id: str
) -> list[dict[str, Any]]:
    _get_requirement_row(connection, requirement_id)
    rows = connection.execute(
        """
        SELECT * FROM audit_events
        WHERE object_type = 'requirement'
          AND object_id = ?
          AND action IN ('requirement.confirmed', 'requirement.rejected')
        ORDER BY created_at ASC, id ASC
        """,
        (requirement_id,),
    ).fetchall()
    return [_audit_event_dict(row) for row in rows]


def list_audit_events(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _get_project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM audit_events
        WHERE project_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (project_id,),
    ).fetchall()
    return [_audit_event_dict(row) for row in rows]


def seed_catalog(
    connection: sqlite3.Connection,
    catalog_path: str | Path | None = None,
) -> dict[str, int]:
    path = Path(catalog_path) if catalog_path is not None else CATALOG_PATH
    if not path.exists():
        raise DomainValidationError("型谱库文件不存在", {"path": str(path)})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainValidationError(
            "型谱库文件无法读取", {"path": str(path), "error": str(exc)}
        ) from exc

    with transaction(connection):
        bases_inserted = 0
        for item in data.get("product_bases", []):
            existing = connection.execute(
                "SELECT 1 FROM product_bases WHERE display_code = ?",
                (item["display_code"],),
            ).fetchone()
            if existing is not None:
                continue
            connection.execute(
                """
                INSERT INTO product_bases(
                    id, display_code, name, transmission_type, gear_count,
                    rated_input_torque, first_gear_ratio, top_gear_type,
                    has_pto, weight_kg, source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    item["display_code"],
                    item["name"],
                    item["transmission_type"],
                    int(item["gear_count"]),
                    float(item["rated_input_torque"]),
                    float(item["first_gear_ratio"]),
                    item["top_gear_type"],
                    1 if item["has_pto"] else 0,
                    float(item["weight_kg"]),
                    item["source"],
                    utc_now(),
                ),
            )
            bases_inserted += 1

        parts_inserted = 0
        for item in data.get("base_parts", []):
            base = connection.execute(
                "SELECT id FROM product_bases WHERE display_code = ?",
                (item["base_display_code"],),
            ).fetchone()
            if base is None:
                raise DomainValidationError(
                    "可复用件引用的基型不存在",
                    {"base_display_code": item["base_display_code"]},
                )
            existing = connection.execute(
                """
                SELECT 1 FROM base_parts
                WHERE base_id = ? AND display_code = ?
                """,
                (base["id"], item["display_code"]),
            ).fetchone()
            if existing is not None:
                continue
            connection.execute(
                """
                INSERT INTO base_parts(
                    id, base_id, display_code, name, part_number,
                    category, source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    base["id"],
                    item["display_code"],
                    item["name"],
                    item["part_number"],
                    item["category"],
                    item["source"],
                    utc_now(),
                ),
            )
            parts_inserted += 1

        return {
            "bases_inserted": bases_inserted,
            "parts_inserted": parts_inserted,
        }


def _infer_parser_key(row: sqlite3.Row) -> str:
    if row["parser_key"]:
        return row["parser_key"]
    return PARSER_KEY_ALIASES.get(row["parameter_name"], row["parameter_name"])


def _load_match_requirements(
    connection: sqlite3.Connection, project_id: str
) -> tuple[list[MatchRequirement], list[str]]:
    requirement_rows = connection.execute(
        """
        SELECT * FROM requirements
        WHERE project_id = ? AND validity = 'current'
        ORDER BY created_at ASC, display_code ASC
        """,
        (project_id,),
    ).fetchall()

    requirements: list[MatchRequirement] = []
    seen_keys: set[str] = set()
    duplicate_keys: list[str] = []
    for row in requirement_rows:
        key = _infer_parser_key(row)
        if key in seen_keys:
            duplicate_keys.append(key)
            continue
        seen_keys.add(key)
        requirements.append(
            MatchRequirement(
                key=key,
                requirement_id=row["id"],
                display_code=row["display_code"],
                revision=row["current_revision"],
                value=row["value_text"],
                unit=row["unit"],
                operator=row["operator"],
            )
        )
    return requirements, duplicate_keys


def recommend_project_bases(
    connection: sqlite3.Connection,
    project_id: str,
    top_n: int = 3,
) -> dict[str, Any]:
    with transaction(connection):
        _get_project_row(connection, project_id)
        base_rows = connection.execute(
            "SELECT * FROM product_bases ORDER BY display_code ASC"
        ).fetchall()
        if not base_rows:
            raise DomainValidationError("型谱库为空，请先执行 scripts/seed_catalog.py")

        requirements, duplicate_keys = _load_match_requirements(connection, project_id)
        relevant_duplicates = sorted(set(duplicate_keys) & SPECTRUM_REQUIREMENT_KEYS)
        if relevant_duplicates:
            raise DomainValidationError(
                "存在多个同参数需求，请先处理冲突",
                {"duplicate_keys": relevant_duplicates},
            )

        candidates = [
            CandidateBase(
                id=row["id"],
                display_code=row["display_code"],
                name=row["name"],
                transmission_type=row["transmission_type"],
                gear_count=int(row["gear_count"]),
                rated_input_torque=float(row["rated_input_torque"]),
                first_gear_ratio=float(row["first_gear_ratio"]),
                top_gear_type=row["top_gear_type"],
                has_pto=bool(row["has_pto"]),
                weight_kg=float(row["weight_kg"]),
                source=row["source"],
            )
            for row in base_rows
        ]

        result = recommend_bases(candidates, requirements, top_n)
        if result.missing_requirements:
            raise DomainValidationError(
                "型谱匹配缺少必要需求",
                {"missing_requirements": result.missing_requirements},
            )

        payload = {
            "project_id": project_id,
            "top_n": top_n,
            "candidate_count": result.candidate_count,
            "candidate_shortage": result.candidate_shortage,
            "missing_requirements": result.missing_requirements,
            "requirement_versions": result.requirement_versions,
            "top3": [asdict(evaluation) for evaluation in result.top3],
        }
        _audit(
            connection,
            project_id=project_id,
            object_type="project",
            object_id=project_id,
            object_revision=None,
            action="recommendation.generated",
            actor="rule_engine",
            role="system",
            after={
                "mode": "rule",
                "top_n": top_n,
                "candidate_count": result.candidate_count,
                "candidate_shortage": result.candidate_shortage,
                "top3": [
                    {
                        "display_code": evaluation.base.display_code,
                        "score": evaluation.score,
                        "hard_failures": evaluation.hard_failures,
                    }
                    for evaluation in result.top3
                ],
                "requirement_versions": result.requirement_versions,
            },
        )
        return payload


def _variant_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["dependency_versions"] = json.loads(data["dependency_versions"])
    data["affected_parts"] = (
        json.loads(data["affected_parts"]) if data["affected_parts"] else []
    )
    data["upstream_requirement_ids"] = (
        json.loads(data["upstream_requirement_ids"])
        if data["upstream_requirement_ids"]
        else []
    )
    return data


def _part_decision_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["dependency_versions"] = json.loads(data["dependency_versions"])
    data["variant_keys"] = (
        json.loads(data["variant_keys"]) if data["variant_keys"] else []
    )
    return data


def _allocate_variant_display_code(
    connection: sqlite3.Connection, project_id: str, base_id: str
) -> str:
    scope = f"variant:{project_id}:{base_id}"
    while True:
        value = _next_sequence(connection, scope)
        code = f"V-{value:02d}"
        exists = connection.execute(
            """
            SELECT 1 FROM variant_points
            WHERE project_id = ? AND base_id = ? AND display_code = ?
            """,
            (project_id, base_id, code),
        ).fetchone()
        if exists is None:
            return code


def run_variant_analysis(
    connection: sqlite3.Connection,
    project_id: str,
    base_display_code: str,
) -> dict[str, Any]:
    with transaction(connection):
        _get_project_row(connection, project_id)
        base_row = connection.execute(
            "SELECT * FROM product_bases WHERE display_code = ?",
            (base_display_code,),
        ).fetchone()
        if base_row is None:
            raise NotFoundError("基型不存在", {"display_code": base_display_code})

        base = CandidateBase(
            id=base_row["id"],
            display_code=base_row["display_code"],
            name=base_row["name"],
            transmission_type=base_row["transmission_type"],
            gear_count=int(base_row["gear_count"]),
            rated_input_torque=float(base_row["rated_input_torque"]),
            first_gear_ratio=float(base_row["first_gear_ratio"]),
            top_gear_type=base_row["top_gear_type"],
            has_pto=bool(base_row["has_pto"]),
            weight_kg=float(base_row["weight_kg"]),
            source=base_row["source"],
        )

        base_parts = [
            BasePart(
                display_code=row["display_code"],
                name=row["name"],
                part_number=row["part_number"],
                category=row["category"],
                source=row["source"],
            )
            for row in connection.execute(
                """
                SELECT * FROM base_parts
                WHERE base_id = ?
                ORDER BY display_code ASC
                """,
                (base_row["id"],),
            ).fetchall()
        ]

        requirements, duplicate_keys = _load_match_requirements(connection, project_id)
        relevant_duplicates = sorted(set(duplicate_keys) & SPECTRUM_REQUIREMENT_KEYS)
        if relevant_duplicates:
            raise DomainValidationError(
                "存在多个同参数需求，请先处理冲突",
                {"duplicate_keys": relevant_duplicates},
            )

        analysis = compute_variants(base, base_parts, requirements)

        existing_variant_rows = connection.execute(
            """
            SELECT * FROM variant_points
            WHERE project_id = ? AND base_id = ?
            """,
            (project_id, base_row["id"]),
        ).fetchall()
        existing_variants = {row["parameter_key"]: row for row in existing_variant_rows}

        computed_keys: set[str] = set()
        for variant in analysis.variants:
            affected_parts_json = json.dumps(
                list(variant.affected_parts), ensure_ascii=False
            )
            upstream_json = json.dumps(
                list(variant.upstream_requirements), ensure_ascii=False
            )
            existing = existing_variants.get(variant.parameter_key)
            if existing is not None:
                connection.execute(
                    "UPDATE variant_points SET is_applicable=1 WHERE id=?",
                    (existing["id"],),
                )
                new_values = {
                    "parameter_name": variant.parameter_name,
                    "base_value": variant.base_value,
                    "requirement_value": variant.requirement_value,
                    "variant_type": variant.variant_type,
                    "affected_parts": affected_parts_json,
                    "upstream_requirement_ids": upstream_json,
                    "basis": variant.basis,
                    "status": "current",
                }
                changed = any(
                    existing[key] != value for key, value in new_values.items()
                )
                changed = changed or engineering_versions.needs_capture(
                    connection, "variant", existing["id"]
                )
                if changed:
                    before = _variant_row_to_dict(existing)
                    connection.execute(
                        """
                        UPDATE variant_points SET
                            parameter_name = ?, base_value = ?,
                            requirement_value = ?, variant_type = ?,
                            affected_parts = ?, upstream_requirement_ids = ?,
                            basis = ?, status = 'current', updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            variant.parameter_name,
                            variant.base_value,
                            variant.requirement_value,
                            variant.variant_type,
                            affected_parts_json,
                            upstream_json,
                            variant.basis,
                            utc_now(),
                            existing["id"],
                        ),
                    )
                    after_row = connection.execute(
                        "SELECT * FROM variant_points WHERE id = ?",
                        (existing["id"],),
                    ).fetchone()
                    _audit_engineering_change(
                        connection,
                        project_id=project_id,
                        object_type="variant_point",
                        object_id=existing["id"],
                        object_revision=None,
                        action="variant.updated",
                        actor="rule_engine",
                        role="system",
                        before=before,
                        after=_variant_row_to_dict(after_row),
                    )
                elif existing["status"] != "current":
                    before = _variant_row_to_dict(existing)
                    connection.execute(
                        """
                        UPDATE variant_points
                        SET status = 'current', updated_at = ?
                        WHERE id = ?
                        """,
                        (utc_now(), existing["id"]),
                    )
                    after_row = connection.execute(
                        "SELECT * FROM variant_points WHERE id = ?",
                        (existing["id"],),
                    ).fetchone()
                    _audit_engineering_change(
                        connection,
                        project_id=project_id,
                        object_type="variant_point",
                        object_id=existing["id"],
                        object_revision=None,
                        action="variant.reactivated",
                        actor="rule_engine",
                        role="system",
                        before=before,
                        after=_variant_row_to_dict(after_row),
                    )
            else:
                variant_id = str(uuid.uuid4())
                display_code = _allocate_variant_display_code(
                    connection, project_id, base_row["id"]
                )
                now = utc_now()
                connection.execute(
                    """
                    INSERT INTO variant_points(
                        id, project_id, base_id, display_code, parameter_key,
                        parameter_name, base_value, requirement_value,
                        variant_type, affected_parts, upstream_requirement_ids,
                        basis, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        variant_id,
                        project_id,
                        base_row["id"],
                        display_code,
                        variant.parameter_key,
                        variant.parameter_name,
                        variant.base_value,
                        variant.requirement_value,
                        variant.variant_type,
                        affected_parts_json,
                        upstream_json,
                        variant.basis,
                        "current",
                        now,
                        now,
                    ),
                )
                created_row = connection.execute(
                    "SELECT * FROM variant_points WHERE id = ?",
                    (variant_id,),
                ).fetchone()
                _audit_engineering_change(
                    connection,
                    project_id=project_id,
                    object_type="variant_point",
                    object_id=variant_id,
                    object_revision=None,
                    action="variant.created",
                    actor="rule_engine",
                    role="system",
                    after=_variant_row_to_dict(created_row),
                )
            computed_keys.add(variant.parameter_key)

        for existing in existing_variant_rows:
            if (
                existing["parameter_key"] not in computed_keys
                and existing["is_applicable"] == 1
            ):
                before = _variant_row_to_dict(existing)
                connection.execute(
                    """
                    UPDATE variant_points
                    SET status = 'stale', is_applicable=0, updated_at = ?
                    WHERE id = ?
                    """,
                    (utc_now(), existing["id"]),
                )
                after_row = connection.execute(
                    "SELECT * FROM variant_points WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
                _audit_engineering_change(
                    connection,
                    project_id=project_id,
                    object_type="variant_point",
                    object_id=existing["id"],
                    object_revision=None,
                    action="variant.stale",
                    actor="rule_engine",
                    role="system",
                    before=before,
                    after=_variant_row_to_dict(after_row),
                )

        current_variant_rows = connection.execute(
            """
            SELECT * FROM variant_points
            WHERE project_id = ? AND base_id = ? AND status = 'current'
            ORDER BY display_code ASC
            """,
            (project_id, base_row["id"]),
        ).fetchall()
        stale_variant_rows = connection.execute(
            """
            SELECT * FROM variant_points
            WHERE project_id = ? AND base_id = ? AND status = 'stale'
            ORDER BY display_code ASC
            """,
            (project_id, base_row["id"]),
        ).fetchall()
        variant_ids = {row["parameter_key"]: row["id"] for row in current_variant_rows}

        existing_part_rows = connection.execute(
            """
            SELECT * FROM reusable_part_decisions
            WHERE project_id = ? AND base_id = ?
            """,
            (project_id, base_row["id"]),
        ).fetchall()
        existing_parts = {row["part_display_code"]: row for row in existing_part_rows}

        computed_part_codes: set[str] = set()
        for decision in analysis.reusable_parts:
            variant_point_id = None
            for key in decision.variant_keys:
                if key in variant_ids:
                    variant_point_id = variant_ids[key]
                    break
            variant_keys_json = json.dumps(
                list(decision.variant_keys), ensure_ascii=False
            )
            existing = existing_parts.get(decision.part_display_code)
            if existing is not None:
                connection.execute(
                    "UPDATE reusable_part_decisions SET is_applicable=1 WHERE id=?",
                    (existing["id"],),
                )
                chosen_candidate = connection.execute(
                    "SELECT * FROM part_candidates WHERE model_code=? AND part_name=?",
                    (existing["part_number"], decision.part_name),
                ).fetchone()
                chosen_number = (
                    existing["part_number"]
                    if chosen_candidate
                    else decision.part_number
                )
                chosen_source = (
                    existing["source"] if chosen_candidate else decision.source
                )
                chosen_reason = (
                    existing["reason"] if chosen_candidate else decision.reason
                )
                new_values = {
                    "part_name": decision.part_name,
                    "part_number": chosen_number,
                    "classification": decision.classification,
                    "reason": chosen_reason,
                    "source": chosen_source,
                    "variant_point_id": variant_point_id,
                    "variant_keys": variant_keys_json,
                    "status": "current",
                }
                changed = any(
                    existing[key] != value for key, value in new_values.items()
                )
                changed = changed or engineering_versions.needs_capture(
                    connection, "part", existing["id"]
                )
                if changed:
                    before = _part_decision_row_to_dict(existing)
                    connection.execute(
                        """
                        UPDATE reusable_part_decisions SET
                            part_name = ?, part_number = ?,
                            classification = ?, reason = ?, source = ?,
                            variant_point_id = ?, variant_keys = ?,
                            status = 'current', updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            decision.part_name,
                            chosen_number,
                            decision.classification,
                            chosen_reason,
                            chosen_source,
                            variant_point_id,
                            variant_keys_json,
                            utc_now(),
                            existing["id"],
                        ),
                    )
                    after_row = connection.execute(
                        """
                        SELECT * FROM reusable_part_decisions
                        WHERE id = ?
                        """,
                        (existing["id"],),
                    ).fetchone()
                    _audit_engineering_change(
                        connection,
                        project_id=project_id,
                        object_type="reusable_part_decision",
                        object_id=existing["id"],
                        object_revision=None,
                        action="part_decision.updated",
                        actor="rule_engine",
                        role="system",
                        before=before,
                        after=_part_decision_row_to_dict(after_row),
                    )
                elif existing["status"] != "current":
                    before = _part_decision_row_to_dict(existing)
                    connection.execute(
                        """
                        UPDATE reusable_part_decisions
                        SET status = 'current', updated_at = ?
                        WHERE id = ?
                        """,
                        (utc_now(), existing["id"]),
                    )
                    after_row = connection.execute(
                        """
                        SELECT * FROM reusable_part_decisions
                        WHERE id = ?
                        """,
                        (existing["id"],),
                    ).fetchone()
                    _audit_engineering_change(
                        connection,
                        project_id=project_id,
                        object_type="reusable_part_decision",
                        object_id=existing["id"],
                        object_revision=None,
                        action="part_decision.reactivated",
                        actor="rule_engine",
                        role="system",
                        before=before,
                        after=_part_decision_row_to_dict(after_row),
                    )
            else:
                part_id = str(uuid.uuid4())
                now = utc_now()
                connection.execute(
                    """
                    INSERT INTO reusable_part_decisions(
                        id, project_id, base_id, variant_point_id,
                        part_display_code, part_name, part_number,
                        classification, reason, source, created_at,
                        updated_at, status, variant_keys
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        part_id,
                        project_id,
                        base_row["id"],
                        variant_point_id,
                        decision.part_display_code,
                        decision.part_name,
                        decision.part_number,
                        decision.classification,
                        decision.reason,
                        decision.source,
                        now,
                        now,
                        "current",
                        variant_keys_json,
                    ),
                )
                created_row = connection.execute(
                    """
                    SELECT * FROM reusable_part_decisions
                    WHERE id = ?
                    """,
                    (part_id,),
                ).fetchone()
                _audit_engineering_change(
                    connection,
                    project_id=project_id,
                    object_type="reusable_part_decision",
                    object_id=part_id,
                    object_revision=None,
                    action="part_decision.created",
                    actor="rule_engine",
                    role="system",
                    after=_part_decision_row_to_dict(created_row),
                )
            computed_part_codes.add(decision.part_display_code)

        for existing in existing_part_rows:
            if (
                existing["part_display_code"] not in computed_part_codes
                and existing["is_applicable"] == 1
            ):
                before = _part_decision_row_to_dict(existing)
                connection.execute(
                    """
                    UPDATE reusable_part_decisions
                    SET status = 'stale', is_applicable=0, updated_at = ?
                    WHERE id = ?
                    """,
                    (utc_now(), existing["id"]),
                )
                after_row = connection.execute(
                    """
                    SELECT * FROM reusable_part_decisions
                    WHERE id = ?
                    """,
                    (existing["id"],),
                ).fetchone()
                _audit_engineering_change(
                    connection,
                    project_id=project_id,
                    object_type="reusable_part_decision",
                    object_id=existing["id"],
                    object_revision=None,
                    action="part_decision.stale",
                    actor="rule_engine",
                    role="system",
                    before=before,
                    after=_part_decision_row_to_dict(after_row),
                )

        current_part_rows = connection.execute(
            """
            SELECT * FROM reusable_part_decisions
            WHERE project_id = ? AND base_id = ? AND status = 'current'
            ORDER BY part_display_code ASC
            """,
            (project_id, base_row["id"]),
        ).fetchall()
        stale_part_rows = connection.execute(
            """
            SELECT * FROM reusable_part_decisions
            WHERE project_id = ? AND base_id = ? AND status = 'stale'
            ORDER BY part_display_code ASC
            """,
            (project_id, base_row["id"]),
        ).fetchall()

        _audit_engineering_change(
            connection,
            project_id=project_id,
            object_type="project",
            object_id=project_id,
            object_revision=None,
            action="variant_analysis.generated",
            actor="rule_engine",
            role="system",
            after={
                "mode": "rule",
                "base_display_code": base_display_code,
                "variant_codes": [row["display_code"] for row in current_variant_rows],
                "part_classifications": {
                    row["part_display_code"]: row["classification"]
                    for row in current_part_rows
                },
                "pending_items": analysis.pending_items,
                "requirement_versions": analysis.requirement_versions,
            },
        )

        return {
            "project_id": project_id,
            "base": asdict(base),
            "variants": [_variant_row_to_dict(row) for row in current_variant_rows],
            "stale_variants": [_variant_row_to_dict(row) for row in stale_variant_rows],
            "reusable_parts": [
                _part_decision_row_to_dict(row) for row in current_part_rows
            ],
            "stale_reusable_parts": [
                _part_decision_row_to_dict(row) for row in stale_part_rows
            ],
            "pending_items": analysis.pending_items,
            "requirement_versions": analysis.requirement_versions,
        }


def _get_issue_row(connection: sqlite3.Connection, issue_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM issues WHERE id = ?", (issue_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("问题不存在", {"issue_id": issue_id})
    return row


def get_issue(connection: sqlite3.Connection, issue_id: str) -> dict[str, Any]:
    return dict(_get_issue_row(connection, issue_id))


def close_issue(
    connection: sqlite3.Connection,
    issue_id: str,
    payload: CloseIssueRequest,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_issue_row(connection, issue_id)
        if payload.expected_status != row["status"] or row["status"] != "open":
            raise IssueStateConflictError(
                "问题状态已变化，无法关闭",
                {
                    "expected_status": payload.expected_status,
                    "current_status": row["status"],
                },
            )

        if payload.linked_requirement_id is not None:
            linked = connection.execute(
                "SELECT * FROM requirements WHERE id = ?",
                (payload.linked_requirement_id,),
            ).fetchone()
            if linked is None or linked["project_id"] != row["project_id"]:
                raise InvalidReferenceError(
                    "关联需求不存在或不属于当前项目",
                    {
                        "linked_requirement_id": payload.linked_requirement_id,
                        "project_id": row["project_id"],
                    },
                )

        before = dict(row)
        connection.execute(
            """
            UPDATE issues SET
                status = 'closed',
                close_reason = ?,
                resolution_type = ?,
                evidence_text = ?,
                closed_by = ?,
                closed_role = ?,
                resolution_requirement_id = ?,
                closed_at = ?
            WHERE id = ?
            """,
            (
                payload.resolution_note,
                payload.resolution_type,
                payload.evidence,
                payload.actor,
                payload.role,
                payload.linked_requirement_id,
                utc_now(),
                issue_id,
            ),
        )
        updated_row = _get_issue_row(connection, issue_id)
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="issue",
            object_id=issue_id,
            object_revision=None,
            action="issue.closed",
            actor=payload.actor,
            role=payload.role,
            decision="closed",
            comment=f"{payload.resolution_note}；证据：{payload.evidence}",
            before=before,
            after=dict(updated_row),
        )
        return dict(updated_row)


def reopen_issue(
    connection: sqlite3.Connection,
    issue_id: str,
    payload: ReopenIssueRequest,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_issue_row(connection, issue_id)
        if payload.expected_status != row["status"] or row["status"] != "closed":
            raise IssueStateConflictError(
                "问题状态已变化，无法重开",
                {
                    "expected_status": payload.expected_status,
                    "current_status": row["status"],
                },
            )

        before = dict(row)
        connection.execute(
            """
            UPDATE issues SET
                status = 'open',
                close_reason = '',
                resolution_type = '',
                evidence_text = '',
                closed_by = '',
                closed_role = '',
                resolution_requirement_id = NULL,
                closed_at = NULL
            WHERE id = ?
            """,
            (issue_id,),
        )
        updated_row = _get_issue_row(connection, issue_id)
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="issue",
            object_id=issue_id,
            object_revision=None,
            action="issue.reopened",
            actor=payload.actor,
            role=payload.role,
            decision="reopened",
            comment=payload.reason,
            before=before,
            after=dict(updated_row),
        )
        return dict(updated_row)


def health(connection: sqlite3.Connection) -> dict[str, Any]:
    connection.execute("SELECT 1").fetchone()
    version_row = connection.execute(
        "SELECT version FROM schema_migrations ORDER BY applied_at DESC, version DESC LIMIT 1"
    ).fetchone()
    return {
        "status": "ok",
        "database": "connected",
        "schema_version": version_row["version"] if version_row else None,
    }


def _mark_variant_decisions_stale(
    connection: sqlite3.Connection,
    project_id: str,
    requirement_id: str,
    parameter_key: str,
) -> None:
    for row in connection.execute(
        "SELECT * FROM variant_points WHERE project_id=? AND status='current'",
        (project_id,),
    ).fetchall():
        upstream = json.loads(row["upstream_requirement_ids"])
        if any(item["requirement_id"] == requirement_id for item in upstream):
            before = _variant_row_to_dict(row)
            connection.execute(
                "UPDATE variant_points SET status='stale', updated_at=? WHERE id=?",
                (utc_now(), row["id"]),
            )
            _audit_engineering_change(
                connection,
                project_id=project_id,
                object_type="variant_point",
                object_id=row["id"],
                object_revision=None,
                action="variant.stale",
                before=before,
                after={
                    **before,
                    "status": "stale",
                    "changed_requirement_id": requirement_id,
                },
            )
    affected_parts = PARAMETER_PARTS.get(parameter_key, ())
    for row in connection.execute(
        "SELECT * FROM reusable_part_decisions WHERE project_id=? AND status='current'",
        (project_id,),
    ).fetchall():
        if (
            not (
                str(row["part_number"]).startswith("DEMO-")
                and parameter_key
                in ("engineMaxTorque", "gearboxRatedInputTorque", "gearCount")
            )
            and row["part_name"] not in affected_parts
            and parameter_key not in json.loads(row["variant_keys"])
        ):
            continue
        before = _part_decision_row_to_dict(row)
        connection.execute(
            "UPDATE reusable_part_decisions SET status='stale', updated_at=? WHERE id=?",
            (utc_now(), row["id"]),
        )
        _audit_engineering_change(
            connection,
            project_id=project_id,
            object_type="reusable_part_decision",
            object_id=row["id"],
            object_revision=None,
            action="part_decision.stale",
            before=before,
            after={
                **before,
                "status": "stale",
                "changed_requirement_id": requirement_id,
            },
        )
