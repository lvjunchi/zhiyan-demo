from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from typing import Any

from .db import transaction, utc_now
from .domain.consistency import (
    ArtifactRecord,
    ConflictCandidate,
    ConsistencyInputs,
    RequirementRecord,
    RequirementReferenceRecord,
    TestCaseRecord,
    TestRunRecord,
    detect_conflicts,
    summarize_conflicts,
)
from .errors import (
    ConflictStateError,
    DomainValidationError,
    NotFoundError,
    VersionConflictError,
)
from .schemas import ArtifactConfirmationCreate, ConflictCloseRequest
from .services import _audit, _next_sequence

CONSISTENCY_SOURCE = "一致性规则 V1（演示规则）"
_SYSTEM_ACTOR = "system"
_SYSTEM_ROLE = "一致性规则引擎（演示）"


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _project_row(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("项目不存在", {"project_id": project_id})
    return row


def _get_check_row(connection: sqlite3.Connection, check_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM consistency_checks WHERE id = ?", (check_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("一致性检查不存在", {"check_id": check_id})
    return row


def _get_conflict_row(connection: sqlite3.Connection, conflict_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM conflicts WHERE id = ?", (conflict_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("冲突不存在", {"conflict_id": conflict_id})
    return row


def _requirement_records(
    connection: sqlite3.Connection, project_id: str
) -> tuple[list[RequirementRecord], list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT * FROM requirements
        WHERE project_id = ?
        ORDER BY display_code ASC, id ASC
        """,
        (project_id,),
    ).fetchall()
    records: list[RequirementRecord] = []
    snapshot: list[dict[str, Any]] = []
    for row in rows:
        record = RequirementRecord(
            id=row["id"],
            display_code=row["display_code"],
            parameter_name=row["parameter_name"],
            data_type=row["data_type"],
            operator=row["operator"],
            value_num=row["value_num"],
            unit=row["unit"],
            review_status=row["review_status"],
            validity=row["validity"],
            current_revision=row["current_revision"],
            source_document_id=row["source_document_id"],
            source_excerpt=row["source_excerpt"],
        )
        records.append(record)
        snapshot.append(
            {
                "id": row["id"],
                "display_code": row["display_code"],
                "current_revision": row["current_revision"],
                "review_status": row["review_status"],
                "validity": row["validity"],
                "operator": row["operator"],
                "value_num": row["value_num"],
                "unit": row["unit"],
                "source_document_id": row["source_document_id"],
                "source_excerpt": row["source_excerpt"],
            }
        )
    return records, snapshot


def _reference_records(
    connection: sqlite3.Connection, project_id: str
) -> tuple[list[RequirementReferenceRecord], list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT rr.*
        FROM requirement_references rr
        JOIN requirements r ON r.id = rr.requirement_id
        WHERE r.project_id = ?
        ORDER BY rr.id ASC
        """,
        (project_id,),
    ).fetchall()
    records = [
        RequirementReferenceRecord(
            id=row["id"],
            requirement_id=row["requirement_id"],
            referenced_requirement_id=row["referenced_requirement_id"],
            relation=row["relation"],
        )
        for row in rows
    ]
    snapshot = [
        {
            "id": row["id"],
            "requirement_id": row["requirement_id"],
            "referenced_requirement_id": row["referenced_requirement_id"],
            "relation": row["relation"],
        }
        for row in rows
    ]
    return records, snapshot


def _stale_artifacts(
    connection: sqlite3.Connection, project_id: str
) -> tuple[list[ArtifactRecord], list[dict[str, Any]]]:
    records: list[ArtifactRecord] = []
    for table, object_type in (
        ("design_reviews", "design_review"),
        ("fmea_documents", "fmea_document"),
    ):
        rows = connection.execute(
            f"SELECT id, display_code, revision, status FROM {table} WHERE project_id = ? AND validity = 'stale' ORDER BY display_code",
            (project_id,),
        ).fetchall()
        records.extend(
            ArtifactRecord(
                object_type=object_type,
                object_id=row["id"],
                display_code=row["display_code"],
                revision=row["revision"],
                review_status=row["status"],
                reason="上游需求已变化，文档需重新生成并独立复核",
            )
            for row in rows
        )
    stale_test_case_rows = connection.execute(
        """
        SELECT id, display_code, revision, review_status
        FROM test_cases
        WHERE project_id = ? AND validity = 'stale'
        ORDER BY display_code ASC
        """,
        (project_id,),
    ).fetchall()
    for row in stale_test_case_rows:
        records.append(
            ArtifactRecord(
                object_type="test_case",
                object_id=row["id"],
                display_code=row["display_code"],
                revision=row["revision"],
                review_status=row["review_status"],
                reason="引用的需求版本已更新，当前用例不再适用",
            )
        )

    variant_rows = connection.execute(
        """
        SELECT id, display_code, revision, review_status
        FROM variant_points
        WHERE project_id = ? AND status = 'stale'
        ORDER BY display_code ASC
        """,
        (project_id,),
    ).fetchall()
    for row in variant_rows:
        records.append(
            ArtifactRecord(
                object_type="variant_point",
                object_id=row["id"],
                display_code=row["display_code"],
                revision=row["revision"],
                review_status=row["review_status"],
                reason="上游需求变化，变型点不再适用",
            )
        )

    part_rows = connection.execute(
        """
        SELECT id, part_display_code, revision, review_status
        FROM reusable_part_decisions
        WHERE project_id = ? AND status = 'stale'
        ORDER BY part_display_code ASC
        """,
        (project_id,),
    ).fetchall()
    for row in part_rows:
        records.append(
            ArtifactRecord(
                object_type="reusable_part",
                object_id=row["id"],
                display_code=row["part_display_code"],
                revision=row["revision"],
                review_status=row["review_status"],
                reason="变型点失效，零件决策需要复核",
            )
        )

    # Removed draft items retain a latest "stale" history row. They are not
    # current applicable artifacts. Active design/FMEA invalidity is reported
    # from the owning document above; retired item history must not block a
    # regenerated and reviewed current document.
    snapshot = [
        {
            "object_type": item.object_type,
            "object_id": item.object_id,
            "display_code": item.display_code,
            "revision": item.revision,
            "review_status": item.review_status,
            "reason": item.reason,
        }
        for item in records
    ]
    return records, snapshot


def _test_case_records(
    connection: sqlite3.Connection, project_id: str
) -> tuple[list[TestCaseRecord], list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT * FROM test_cases
        WHERE project_id = ?
        ORDER BY display_code ASC, id ASC
        """,
        (project_id,),
    ).fetchall()
    records: list[TestCaseRecord] = []
    snapshot: list[dict[str, Any]] = []
    for row in rows:
        coefficient = row["minimum_coefficient"]
        record = TestCaseRecord(
            id=row["id"],
            display_code=row["display_code"],
            revision=row["revision"],
            review_status=row["review_status"],
            validity=row["validity"],
            minimum_coefficient=(2.5 if coefficient is None else float(coefficient)),
            load_basis_requirement_id=row["load_basis_requirement_id"],
            is_static_torsion=row["case_kind"] == "static_torsion",
        )
        records.append(record)
        snapshot.append(
            {
                "id": row["id"],
                "display_code": row["display_code"],
                "revision": row["revision"],
                "review_status": row["review_status"],
                "validity": row["validity"],
                "case_kind": row["case_kind"],
                "minimum_coefficient": coefficient,
                "load_basis_requirement_id": row["load_basis_requirement_id"],
            }
        )
    return records, snapshot


def _latest_runs(
    connection: sqlite3.Connection, project_id: str
) -> tuple[list[TestRunRecord], list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT tr.*
        FROM test_runs tr
        WHERE tr.project_id = ?
          AND tr.status = 'completed'
          AND tr.run_no = (
              SELECT MAX(t2.run_no)
              FROM test_runs t2
              WHERE t2.case_id = tr.case_id
                AND t2.status = 'completed'
          )
        ORDER BY tr.case_id ASC
        """,
        (project_id,),
    ).fetchall()
    records = [
        TestRunRecord(
            id=row["id"],
            case_id=row["case_id"],
            case_revision=row["case_revision"],
            status=row["status"],
            result=row["result"],
            load_basis_numeric=row["load_basis_numeric"],
            backup_coefficient=row["backup_coefficient"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    snapshot = [
        {
            "id": row["id"],
            "case_id": row["case_id"],
            "case_revision": row["case_revision"],
            "status": row["status"],
            "result": row["result"],
            "load_basis_numeric": row["load_basis_numeric"],
            "backup_coefficient": row["backup_coefficient"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return records, snapshot


def _load_inputs(
    connection: sqlite3.Connection, project_id: str
) -> tuple[ConsistencyInputs, dict[str, Any]]:
    requirements, requirement_snapshot = _requirement_records(connection, project_id)
    references, reference_snapshot = _reference_records(connection, project_id)
    stale_artifacts, stale_snapshot = _stale_artifacts(connection, project_id)
    test_cases, case_snapshot = _test_case_records(connection, project_id)
    latest_runs, run_snapshot = _latest_runs(connection, project_id)
    inputs = ConsistencyInputs(
        requirements=tuple(requirements),
        references=tuple(references),
        stale_artifacts=tuple(stale_artifacts),
        test_cases=tuple(test_cases),
        latest_runs=tuple(latest_runs),
    )
    snapshot = {
        "requirements": requirement_snapshot,
        "references": reference_snapshot,
        "stale_artifacts": stale_snapshot,
        "test_cases": case_snapshot,
        "latest_runs": run_snapshot,
    }
    return inputs, snapshot


def _input_hash(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(_json_text(snapshot).encode("utf-8")).hexdigest()


def _conflict_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["evidence"] = _parse_json(data.pop("evidence_json"), {})
    data["detected"] = bool(data["detected"])
    data["accepted_risk"] = bool(data["accepted_risk"])
    data["blocking"] = data["severity"] == "blocking"
    data["review_pending"] = data["object_review_status"] in (
        "draft",
        "pending_review",
        "rejected",
    )
    return data


def _confirmation_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["snapshot"] = _parse_json(data.pop("snapshot_json"), {})
    return data


def _check_conflicts(
    connection: sqlite3.Connection, check: sqlite3.Row
) -> list[dict[str, Any]]:
    if check["validity"] == "current":
        rows = connection.execute(
            """
            SELECT * FROM conflicts
            WHERE last_check_id = ?
            ORDER BY
                CASE severity
                    WHEN 'blocking' THEN 0
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                display_code ASC
            """,
            (check["id"],),
        ).fetchall()
        return [_conflict_dict(row) for row in rows]
    snapshot = _parse_json(check["conflicts_json"], [])
    return [item for item in snapshot if isinstance(item, dict)]


def _check_summary(
    connection: sqlite3.Connection,
    check: sqlite3.Row,
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = _parse_json(check["summary_json"], {})
    all_rows = connection.execute(
        "SELECT status, severity FROM conflicts WHERE project_id = ?",
        (check["project_id"],),
    ).fetchall()
    open_count = sum(1 for row in all_rows if row["status"] == "open")
    closed_count = sum(1 for row in all_rows if row["status"] == "closed")
    blocking_open = sum(
        1
        for row in all_rows
        if row["status"] == "open" and row["severity"] == "blocking"
    )
    summary["open"] = open_count
    summary["closed"] = closed_count
    summary["blocking_open"] = blocking_open
    summary["detected"] = sum(1 for item in conflicts if item.get("detected"))
    summary["not_detected_open"] = sum(
        1
        for item in conflicts
        if item.get("status") == "open" and not item.get("detected")
    )
    summary["review_pending"] = sum(
        1 for item in conflicts if item.get("review_pending")
    )
    summary["accepted_risk"] = sum(
        1
        for item in conflicts
        if item.get("status") == "closed" and item.get("accepted_risk")
    )
    return summary


def _check_payload(
    connection: sqlite3.Connection, check: sqlite3.Row
) -> dict[str, Any]:
    conflicts = _check_conflicts(connection, check)
    data = dict(check)
    data["input_snapshot"] = _parse_json(data.pop("input_snapshot"), {})
    data.pop("conflicts_json", None)
    data["summary"] = _check_summary(connection, check, conflicts)
    confirmations = connection.execute(
        """
        SELECT * FROM consistency_check_confirmations
        WHERE check_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (check["id"],),
    ).fetchall()
    data["confirmations"] = [_confirmation_dict(row) for row in confirmations]
    return {"check": data, "conflicts": conflicts}


def _insert_event(
    connection: sqlite3.Connection,
    *,
    conflict_id: str,
    check_id: str | None,
    action: str,
    actor: str = _SYSTEM_ACTOR,
    role: str = _SYSTEM_ROLE,
    note: str = "",
    evidence: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO conflict_events(
            id, conflict_id, check_id, action, actor, role,
            note, evidence, before_json, after_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            conflict_id,
            check_id,
            action,
            actor,
            role,
            note,
            evidence,
            _json_text(before) if before is not None else None,
            _json_text(after) if after is not None else None,
            utc_now(),
        ),
    )


def _allocate_conflict_code(
    connection: sqlite3.Connection, project: sqlite3.Row
) -> str:
    while True:
        value = _next_sequence(connection, f"conflict:{project['id']}")
        code = f"CF-{project['display_code']}-{value:03d}"
        exists = connection.execute(
            "SELECT 1 FROM conflicts WHERE project_id = ? AND display_code = ?",
            (project["id"], code),
        ).fetchone()
        if exists is None:
            return code


def _upsert_conflict(
    connection: sqlite3.Connection,
    *,
    project: sqlite3.Row,
    check: sqlite3.Row,
    candidate: ConflictCandidate,
    now: str,
) -> None:
    existing = connection.execute(
        """
        SELECT * FROM conflicts
        WHERE project_id = ? AND stable_key = ?
        """,
        (project["id"], candidate.stable_key),
    ).fetchone()
    evidence_text = _json_text(candidate.evidence)
    if existing is None:
        conflict_id = str(uuid.uuid4())
        display_code = _allocate_conflict_code(connection, project)
        connection.execute(
            """
            INSERT INTO conflicts(
                id, project_id, check_id, last_check_id, display_code,
                stable_key, revision, conflict_type, severity, status,
                detected, title, detail, evidence_json,
                object_type, object_id, object_revision,
                object_review_status, last_check_no, last_checked_at,
                recheck_status, first_seen_at, last_seen_at,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, 1, ?, ?, 'open', 1, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, 'present', ?, ?, ?, ?
            )
            """,
            (
                conflict_id,
                project["id"],
                check["id"],
                check["id"],
                display_code,
                candidate.stable_key,
                candidate.conflict_type,
                candidate.severity,
                candidate.title,
                candidate.detail,
                evidence_text,
                candidate.object_type,
                candidate.object_id,
                candidate.object_revision,
                candidate.object_review_status,
                check["check_no"],
                now,
                now,
                now,
                now,
                now,
            ),
        )
        row = _get_conflict_row(connection, conflict_id)
        _insert_event(
            connection,
            conflict_id=conflict_id,
            check_id=check["id"],
            action="conflict.detected",
            note=candidate.title,
            after=_conflict_dict(row),
        )
        return

    before = dict(existing)
    revision = existing["revision"]
    status = existing["status"]
    accepted_risk = bool(existing["accepted_risk"])
    recheck_status = "present"
    accepted_risk_still_present = (
        status == "closed"
        and accepted_risk
        and existing["recheck_status"] not in ("accepted_risk_cleared", "cleared")
    )
    reopened = status == "closed" and not accepted_risk_still_present
    event_action: str | None = None
    event_note = ""
    if reopened:
        revision += 1
        status = "open"
        accepted_risk = False
        event_action = "conflict.reopened"
        event_note = "复检仍检出冲突，自动重开"
    elif accepted_risk_still_present:
        recheck_status = "accepted_risk_present"
        if existing["recheck_status"] != recheck_status:
            event_action = "conflict.recheck_accepted_risk"
            event_note = "已接受风险，复检仍检出"
    else:
        substantive = (
            candidate.severity != existing["severity"]
            or candidate.title != existing["title"]
            or candidate.detail != existing["detail"]
            or candidate.object_revision != existing["object_revision"]
            or candidate.object_review_status != existing["object_review_status"]
        )
        if substantive:
            revision += 1
            event_action = "conflict.updated"
            event_note = "冲突证据或严重度发生变化"

    connection.execute(
        """
        UPDATE conflicts SET
            last_check_id = ?, revision = ?, conflict_type = ?,
            severity = ?, status = ?, detected = 1, title = ?,
            detail = ?, evidence_json = ?, object_type = ?,
            object_id = ?, object_revision = ?,
            object_review_status = ?, last_check_no = ?,
            last_checked_at = ?, recheck_status = ?,
            last_seen_at = ?, resolution_type = ?,
            resolution_note = ?, evidence_text = ?, accepted_risk = ?,
            closed_by = ?, closed_role = ?, closed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            check["id"],
            revision,
            candidate.conflict_type,
            candidate.severity,
            status,
            candidate.title,
            candidate.detail,
            evidence_text,
            candidate.object_type,
            candidate.object_id,
            candidate.object_revision,
            candidate.object_review_status,
            check["check_no"],
            now,
            recheck_status,
            now,
            "" if reopened else existing["resolution_type"],
            "" if reopened else existing["resolution_note"],
            "" if reopened else existing["evidence_text"],
            1 if accepted_risk else 0,
            "" if reopened else existing["closed_by"],
            "" if reopened else existing["closed_role"],
            None if reopened else existing["closed_at"],
            now,
            existing["id"],
        ),
    )
    updated = _get_conflict_row(connection, existing["id"])
    if event_action is not None:
        _insert_event(
            connection,
            conflict_id=existing["id"],
            check_id=check["id"],
            action=event_action,
            note=event_note,
            before=before,
            after=_conflict_dict(updated),
        )


def _mark_unseen_conflicts(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    check: sqlite3.Row,
    seen_keys: set[str],
    now: str,
) -> None:
    rows = connection.execute(
        "SELECT * FROM conflicts WHERE project_id = ? ORDER BY id ASC",
        (project_id,),
    ).fetchall()
    for row in rows:
        if row["stable_key"] in seen_keys:
            continue
        before = dict(row)
        recheck_status = (
            "accepted_risk_cleared"
            if row["status"] == "closed" and row["accepted_risk"]
            else "cleared"
        )
        connection.execute(
            """
            UPDATE conflicts SET
                last_check_id = ?, detected = 0, last_check_no = ?,
                last_checked_at = ?, recheck_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                check["id"],
                check["check_no"],
                now,
                recheck_status,
                now,
                row["id"],
            ),
        )
        if row["recheck_status"] != recheck_status:
            updated = _get_conflict_row(connection, row["id"])
            _insert_event(
                connection,
                conflict_id=row["id"],
                check_id=check["id"],
                action=(
                    "conflict.not_detected"
                    if row["status"] == "open"
                    else "conflict.recheck_cleared"
                ),
                note=(
                    "本次复检未再检出，保持待人工关闭"
                    if row["status"] == "open"
                    else "复检未再检出，维持关闭"
                ),
                before=before,
                after=_conflict_dict(updated),
            )


def mark_consistency_checks_stale(
    connection: sqlite3.Connection,
    project_id: str,
    reason: str = "",
) -> int:
    cursor = connection.execute(
        """
        UPDATE consistency_checks
        SET validity = 'stale', updated_at = ?
        WHERE project_id = ? AND validity = 'current'
        """,
        (utc_now(), project_id),
    )
    if cursor.rowcount:
        connection.execute(
            """
            INSERT INTO audit_events(
                id, project_id, object_type, object_id, object_revision,
                action, actor, role, decision, comment,
                before_json, after_json, created_at
            ) VALUES (?, ?, 'consistency_check', ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                project_id,
                project_id,
                "consistency.check.stale",
                _SYSTEM_ACTOR,
                _SYSTEM_ROLE,
                "stale",
                reason or "上游对象发生变化，需要重新检查",
                None,
                None,
                utc_now(),
            ),
        )
    return cursor.rowcount


def run_consistency_check(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    with transaction(connection):
        project = _project_row(connection, project_id)
        inputs, snapshot = _load_inputs(connection, project_id)
        input_hash = _input_hash(snapshot)
        latest = connection.execute(
            """
            SELECT * FROM consistency_checks
            WHERE project_id = ?
            ORDER BY check_no DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        last_event = connection.execute(
            """
            SELECT MAX(e.created_at) AS latest
            FROM conflict_events e
            JOIN conflicts c ON c.id = e.conflict_id
            WHERE c.project_id = ?
            """,
            (project_id,),
        ).fetchone()
        if (
            latest is not None
            and latest["input_hash"] == input_hash
            and (
                last_event is None
                or last_event["latest"] is None
                or last_event["latest"] <= latest["updated_at"]
            )
        ):
            return _check_payload(connection, latest)

        now = utc_now()
        connection.execute(
            """
            UPDATE consistency_checks
            SET validity = 'stale', updated_at = ?
            WHERE project_id = ? AND validity = 'current'
            """,
            (now, project_id),
        )
        check_no = _next_sequence(connection, f"consistency_check:{project_id}")
        check_id = str(uuid.uuid4())
        display_code = f"CR-{project['display_code']}-{check_no:03d}"
        connection.execute(
            """
            INSERT INTO consistency_checks(
                id, project_id, display_code, check_no, revision,
                status, validity, mode, source_label, input_snapshot,
                input_hash, summary_json, conflicts_json, created_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 'draft', 'current', 'rule', ?, ?, ?, '{}', '[]', ?, ?, ?)
            """,
            (
                check_id,
                project_id,
                display_code,
                check_no,
                CONSISTENCY_SOURCE,
                _json_text(snapshot),
                input_hash,
                _SYSTEM_ACTOR,
                now,
                now,
            ),
        )
        check = _get_check_row(connection, check_id)
        candidates = detect_conflicts(inputs)
        seen_keys: set[str] = set()
        for candidate in candidates:
            seen_keys.add(candidate.stable_key)
            _upsert_conflict(
                connection,
                project=project,
                check=check,
                candidate=candidate,
                now=now,
            )
        _mark_unseen_conflicts(
            connection,
            project_id=project_id,
            check=check,
            seen_keys=seen_keys,
            now=now,
        )
        conflicts = _check_conflicts(connection, check)
        summary = summarize_conflicts(candidates)
        summary["open"] = sum(1 for item in conflicts if item["status"] == "open")
        summary["closed"] = sum(1 for item in conflicts if item["status"] == "closed")
        summary["blocking_open"] = sum(
            1
            for item in conflicts
            if item["status"] == "open" and item["severity"] == "blocking"
        )
        summary["detected"] = sum(1 for item in conflicts if item["detected"])
        summary["not_detected_open"] = sum(
            1 for item in conflicts if item["status"] == "open" and not item["detected"]
        )
        summary["accepted_risk"] = sum(
            1
            for item in conflicts
            if item["status"] == "closed" and item["accepted_risk"]
        )
        final_now = utc_now()
        connection.execute(
            """
            UPDATE consistency_checks
            SET summary_json = ?, conflicts_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                _json_text(summary),
                _json_text(conflicts),
                final_now,
                check_id,
            ),
        )
        _audit(
            connection,
            project_id=project_id,
            object_type="consistency_check",
            object_id=check_id,
            object_revision=1,
            action="consistency.check.created",
            actor=_SYSTEM_ACTOR,
            role=_SYSTEM_ROLE,
            after={
                "display_code": display_code,
                "check_no": check_no,
                "summary": summary,
                "source_label": CONSISTENCY_SOURCE,
            },
        )
        check = _get_check_row(connection, check_id)
        return _check_payload(connection, check)


def list_consistency_checks(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM consistency_checks
        WHERE project_id = ?
        ORDER BY check_no DESC
        """,
        (project_id,),
    ).fetchall()
    return [_check_payload(connection, row) for row in rows]


def get_consistency_check(
    connection: sqlite3.Connection, check_id: str
) -> dict[str, Any]:
    return _check_payload(connection, _get_check_row(connection, check_id))


def get_latest_consistency_check(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    _project_row(connection, project_id)
    row = connection.execute(
        """
        SELECT * FROM consistency_checks
        WHERE project_id = ?
        ORDER BY check_no DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("项目尚无一致性检查", {"project_id": project_id})
    return _check_payload(connection, row)


def list_conflicts(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM conflicts
        WHERE project_id = ?
        ORDER BY
            CASE status WHEN 'open' THEN 0 ELSE 1 END,
            CASE severity
                WHEN 'blocking' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                ELSE 3
            END,
            display_code ASC
        """,
        (project_id,),
    ).fetchall()
    result = []
    for row in rows:
        data = _conflict_dict(row)
        events = connection.execute(
            """
            SELECT * FROM conflict_events
            WHERE conflict_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (row["id"],),
        ).fetchall()
        data["events"] = [
            {
                **dict(event),
                "before": _parse_json(event["before_json"], None),
                "after": _parse_json(event["after_json"], None),
            }
            for event in events
        ]
        for event in data["events"]:
            event.pop("before_json", None)
            event.pop("after_json", None)
        result.append(data)
    return result


def get_conflict(connection: sqlite3.Connection, conflict_id: str) -> dict[str, Any]:
    row = _get_conflict_row(connection, conflict_id)
    data = _conflict_dict(row)
    events = connection.execute(
        """
        SELECT * FROM conflict_events
        WHERE conflict_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (conflict_id,),
    ).fetchall()
    data["events"] = []
    for event in events:
        item = dict(event)
        item["before"] = _parse_json(item.pop("before_json"), None)
        item["after"] = _parse_json(item.pop("after_json"), None)
        data["events"].append(item)
    return data


def confirm_consistency_check(
    connection: sqlite3.Connection,
    check_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, Any]:
    with transaction(connection):
        check = _get_check_row(connection, check_id)
        if check["validity"] != "current":
            raise VersionConflictError(
                "该一致性检查已被新检查取代",
                {
                    "check_id": check_id,
                    "current_check_no": check["check_no"],
                },
            )
        if payload.expected_revision != check["revision"]:
            raise VersionConflictError(
                "一致性检查已被更新，请刷新后重试",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": check["revision"],
                },
            )
        existing = connection.execute(
            """
            SELECT 1 FROM consistency_check_confirmations
            WHERE check_id = ? AND check_revision = ?
            """,
            (check_id, check["revision"]),
        ).fetchone()
        if existing is not None:
            raise VersionConflictError(
                "该一致性检查版本已确认或驳回",
                {"check_id": check_id, "revision": check["revision"]},
            )
        if check["status"] != "draft":
            raise ConflictStateError(
                "一致性检查状态已变化",
                {"status": check["status"]},
            )

        now = utc_now()
        confirmation_id = str(uuid.uuid4())
        check_payload = _check_payload(connection, check)
        connection.execute(
            """
            INSERT INTO consistency_check_confirmations(
                id, check_id, check_revision, actor, role, decision,
                comment, snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                confirmation_id,
                check_id,
                check["revision"],
                payload.actor,
                payload.role,
                payload.decision,
                payload.comment,
                _json_text(check_payload),
                now,
            ),
        )
        connection.execute(
            """
            UPDATE consistency_checks
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (payload.decision, now, check_id),
        )
        _audit(
            connection,
            project_id=check["project_id"],
            object_type="consistency_check",
            object_id=check_id,
            object_revision=check["revision"],
            action=(
                "consistency.check.confirmed"
                if payload.decision == "confirmed"
                else "consistency.check.rejected"
            ),
            actor=payload.actor,
            role=payload.role,
            decision=payload.decision,
            comment=payload.comment,
            before={
                "status": "draft",
                "summary": _parse_json(check["summary_json"], {}),
            },
            after={
                "status": payload.decision,
                "summary": _parse_json(check["summary_json"], {}),
            },
        )
        updated = _get_check_row(connection, check_id)
        result = _check_payload(connection, updated)
        result["confirmation"] = _confirmation_dict(
            connection.execute(
                """
                SELECT * FROM consistency_check_confirmations
                WHERE id = ?
                """,
                (confirmation_id,),
            ).fetchone()
        )
        return result


def close_conflict(
    connection: sqlite3.Connection,
    conflict_id: str,
    payload: ConflictCloseRequest,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_conflict_row(connection, conflict_id)
        if payload.expected_revision != row["revision"]:
            raise VersionConflictError(
                "冲突记录已被更新，请刷新后重试",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": row["revision"],
                },
            )
        if row["status"] != "open":
            raise ConflictStateError(
                "冲突已关闭，不能重复关闭",
                {"status": row["status"]},
            )
        if payload.resolution_type in ("fixed", "evidence_added") and row["detected"]:
            raise DomainValidationError(
                "本次复检仍检出冲突，不能按已修复或已补证关闭；"
                "如确认接受风险，请使用 accepted_risk 并留存理由",
                {
                    "conflict_id": conflict_id,
                    "detected": bool(row["detected"]),
                },
            )

        before = _conflict_dict(row)
        now = utc_now()
        accepted_risk = payload.resolution_type == "accepted_risk"
        connection.execute(
            """
            UPDATE conflicts SET
                status = 'closed', revision = revision + 1,
                resolution_type = ?, resolution_note = ?,
                evidence_text = ?, accepted_risk = ?,
                closed_by = ?, closed_role = ?, closed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                payload.resolution_type,
                payload.note,
                payload.evidence,
                1 if accepted_risk else 0,
                payload.actor,
                payload.role,
                now,
                now,
                conflict_id,
            ),
        )
        updated = _get_conflict_row(connection, conflict_id)
        _insert_event(
            connection,
            conflict_id=conflict_id,
            check_id=row["last_check_id"],
            action="conflict.closed",
            actor=payload.actor,
            role=payload.role,
            note=payload.note,
            evidence=payload.evidence,
            before=before,
            after=_conflict_dict(updated),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="conflict",
            object_id=conflict_id,
            object_revision=updated["revision"],
            action="conflict.closed",
            actor=payload.actor,
            role=payload.role,
            decision=payload.resolution_type,
            comment=f"{payload.note}；证据：{payload.evidence}",
            before=before,
            after=_conflict_dict(updated),
        )
        return _conflict_dict(updated)
