from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict
from typing import Any

from .db import transaction, utc_now
from .domain.sample import (
    ParameterMeasurement,
    ParameterSpec,
    combine_results,
    compare_parameter,
    visual_finding,
)
from .errors import (
    DomainValidationError,
    DuplicateDisplayCodeError,
    NotFoundError,
    VersionConflictError,
)
from .schemas import (
    ArtifactConfirmationCreate,
    SampleComparisonCreate,
    SampleDeliveryCreate,
)
from .services import _audit, _get_project_row, _next_sequence

MAX_FILE_SIZE = 8 * 1024 * 1024
DELIVERY_SOURCE_LABEL = "样件交付记录（合成数据）"
COMPARISON_SOURCE_LABEL = "合成样件比对规则 V1（演示规则）"


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _get_delivery_row(connection: sqlite3.Connection, delivery_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM sample_deliveries WHERE id = ?", (delivery_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("样件交付记录不存在", {"delivery_id": delivery_id})
    return row


def _file_row(connection: sqlite3.Connection, delivery_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM sample_delivery_files WHERE sample_id = ?",
        (delivery_id,),
    ).fetchone()


def _drawing_parameters(
    connection: sqlite3.Connection, delivery_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT * FROM sample_drawing_parameters
        WHERE sample_id = ?
        ORDER BY created_at ASC, parameter_key ASC
        """,
        (delivery_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "parameter_key": row["parameter_key"],
            "parameter_name": row["parameter_name"],
            "expected_value": row["expected_value"],
            "tolerance": row["tolerance"],
            "unit": row["unit"],
            "source_note": row["source_note"],
        }
        for row in rows
    ]


def _delivery_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    file_row = _file_row(connection, row["id"])
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "display_code": row["display_code"],
        "supplier": row["supplier"],
        "part_display_code": row["part_display_code"],
        "drawing_display_code": row["drawing_display_code"],
        "drawing_revision": row["drawing_revision"],
        "delivered_at": row["delivered_at"],
        "quantity": row["quantity"],
        "notes": row["notes"],
        "mode": row["mode"],
        "source_label": DELIVERY_SOURCE_LABEL,
        "drawing_parameters": _drawing_parameters(connection, row["id"]),
        "file_uploaded": file_row is not None,
        "file": (
            {
                "file_name": file_row["file_name"],
                "content_type": file_row["content_type"],
                "content_hash": file_row["content_hash"],
                "size_bytes": file_row["size_bytes"],
                "uploaded_by": file_row["uploaded_by"],
                "uploaded_at": file_row["uploaded_at"],
            }
            if file_row is not None
            else None
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _allocate_delivery_code(connection: sqlite3.Connection, project_id: str) -> str:
    scope = f"sample:{project_id}"
    while True:
        value = _next_sequence(connection, scope)
        code = f"SD-{value:02d}"
        exists = connection.execute(
            """
            SELECT 1 FROM sample_deliveries
            WHERE project_id = ? AND display_code = ?
            """,
            (project_id, code),
        ).fetchone()
        if exists is None:
            return code


def create_sample_delivery(
    connection: sqlite3.Connection,
    project_id: str,
    payload: SampleDeliveryCreate,
) -> dict[str, Any]:
    with transaction(connection):
        project = _get_project_row(connection, project_id)
        if payload.display_code is None:
            display_code = _allocate_delivery_code(connection, project_id)
        else:
            display_code = payload.display_code
            exists = connection.execute(
                """
                SELECT 1 FROM sample_deliveries
                WHERE project_id = ? AND display_code = ?
                """,
                (project_id, display_code),
            ).fetchone()
            if exists is not None:
                raise DuplicateDisplayCodeError(
                    "样件交付显示编号已存在",
                    {"display_code": display_code},
                )
        delivery_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO sample_deliveries(
                id, project_id, display_code, supplier, part_display_code,
                drawing_display_code, drawing_revision, delivered_at,
                quantity, notes, mode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (
                delivery_id,
                project_id,
                display_code,
                payload.supplier,
                payload.part_display_code,
                payload.drawing_display_code,
                payload.drawing_revision,
                payload.delivered_at,
                payload.quantity,
                payload.notes,
                now,
                now,
            ),
        )
        for parameter in payload.drawing_parameters:
            connection.execute(
                """
                INSERT INTO sample_drawing_parameters(
                    id, sample_id, parameter_key, parameter_name,
                    expected_value, tolerance, unit, source_note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    delivery_id,
                    parameter.parameter_key,
                    parameter.parameter_name,
                    parameter.expected_value,
                    parameter.tolerance,
                    parameter.unit,
                    parameter.source_note,
                    now,
                ),
            )
        _audit(
            connection,
            project_id=project_id,
            object_type="sample_delivery",
            object_id=delivery_id,
            object_revision=1,
            action="sample_delivery.created",
            actor="manual_entry",
            role="system",
            after={
                "display_code": display_code,
                "drawing_display_code": payload.drawing_display_code,
                "drawing_revision": payload.drawing_revision,
                "parameter_count": len(payload.drawing_parameters),
            },
        )
        row = _get_delivery_row(connection, delivery_id)
        result = _delivery_dict(connection, row)
        result["project_display_code"] = project["display_code"]
        return result


def list_sample_deliveries(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _get_project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM sample_deliveries
        WHERE project_id = ? ORDER BY created_at ASC, display_code ASC
        """,
        (project_id,),
    ).fetchall()
    return [_delivery_dict(connection, row) for row in rows]


def get_sample_delivery(
    connection: sqlite3.Connection, delivery_id: str
) -> dict[str, Any]:
    row = _get_delivery_row(connection, delivery_id)
    return _delivery_dict(connection, row)


def upload_sample_file(
    connection: sqlite3.Connection,
    delivery_id: str,
    *,
    file_name: str,
    content_type: str,
    content: bytes,
    actor: str,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_delivery_row(connection, delivery_id)
        if _file_row(connection, delivery_id) is not None:
            raise VersionConflictError(
                "该样件记录已有上传文件，不能静默覆盖",
                {"delivery_id": delivery_id},
            )
        cleaned_name = file_name.strip()
        if (
            not cleaned_name
            or len(cleaned_name) > 255
            or "/" in cleaned_name
            or "\\" in cleaned_name
            or ".." in cleaned_name
        ):
            raise DomainValidationError(
                "文件名不合法",
                {"file_name": file_name},
            )
        if not content:
            raise DomainValidationError(
                "上传文件不能为空", {"delivery_id": delivery_id}
            )
        if len(content) > MAX_FILE_SIZE:
            raise DomainValidationError(
                "上传文件超过 8 MiB 上限",
                {
                    "size_bytes": len(content),
                    "max_size_bytes": MAX_FILE_SIZE,
                },
            )
        now = utc_now()
        content_hash = hashlib.sha256(content).hexdigest()
        connection.execute(
            """
            INSERT INTO sample_delivery_files(
                id, sample_id, file_name, content_type, content_hash,
                size_bytes, content, uploaded_by, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                delivery_id,
                cleaned_name,
                content_type or "application/octet-stream",
                content_hash,
                len(content),
                content,
                actor,
                now,
            ),
        )
        connection.execute(
            "UPDATE sample_deliveries SET updated_at = ? WHERE id = ?",
            (now, delivery_id),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="sample_delivery",
            object_id=delivery_id,
            object_revision=1,
            action="sample_delivery.file_uploaded",
            actor=actor,
            role="manual",
            after={
                "file_name": cleaned_name,
                "content_hash": content_hash,
                "size_bytes": len(content),
            },
        )
        return _delivery_dict(connection, _get_delivery_row(connection, delivery_id))


def get_sample_file(connection: sqlite3.Connection, delivery_id: str) -> sqlite3.Row:
    _get_delivery_row(connection, delivery_id)
    row = _file_row(connection, delivery_id)
    if row is None:
        raise NotFoundError("样件文件尚未上传", {"delivery_id": delivery_id})
    return row


def _comparison_row(
    connection: sqlite3.Connection, delivery_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM sample_comparisons WHERE sample_id = ?",
        (delivery_id,),
    ).fetchone()


def _comparison_issues(
    connection: sqlite3.Connection, comparison_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT i.* FROM issues i
        WHERE i.id IN (
            SELECT issue_id FROM sample_comparison_issues
            WHERE comparison_id = ?
        )
        ORDER BY i.created_at ASC, i.id ASC
        """,
        (comparison_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _comparison_confirmation_dict(
    row: sqlite3.Row,
) -> dict[str, Any]:
    data = dict(row)
    snapshot = _parse_json(data.pop("snapshot_json"), {})
    data["findings"] = snapshot.get("findings", [])
    return data


def _comparison_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "sample_id": row["sample_id"],
        "display_code": row["display_code"],
        "revision": row["revision"],
        "status": row["status"],
        "mode": row["mode"],
        "overall_result": row["overall_result"],
        "findings": _parse_json(row["findings"], []),
        "visual_check": _parse_json(row["visual_check"], {}),
        "evidence": row["evidence"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _comparison_payload(
    connection: sqlite3.Connection, comparison_id: str
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM sample_comparisons WHERE id = ?",
        (comparison_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("样件比对不存在", {"comparison_id": comparison_id})
    confirmations = connection.execute(
        """
        SELECT * FROM sample_comparison_confirmations
        WHERE comparison_id = ? ORDER BY created_at ASC, id ASC
        """,
        (comparison_id,),
    ).fetchall()
    return {
        "mode": row["mode"],
        "source_label": COMPARISON_SOURCE_LABEL,
        "comparison": _comparison_dict(row),
        "versions": [
            {
                "revision": version["revision"],
                "snapshot": json.loads(version["snapshot_json"]),
            }
            for version in connection.execute(
                "SELECT revision,snapshot_json FROM sample_comparison_versions WHERE comparison_id=? ORDER BY revision",
                (comparison_id,),
            )
        ],
        "issues": _comparison_issues(connection, comparison_id),
        "confirmations": [
            _comparison_confirmation_dict(item) for item in confirmations
        ],
    }


def _parameter_specs(
    connection: sqlite3.Connection, delivery_id: str
) -> list[ParameterSpec]:
    return [
        ParameterSpec(
            parameter_key=item["parameter_key"],
            parameter_name=item["parameter_name"],
            expected_value=item["expected_value"],
            tolerance=item["tolerance"],
            unit=item["unit"],
            source_note=item["source_note"],
        )
        for item in _drawing_parameters(connection, delivery_id)
    ]


def _create_comparison_issue(
    connection: sqlite3.Connection,
    *,
    delivery: sqlite3.Row,
    comparison_id: str,
    revision: int,
    findings: list[Any],
    evidence: str,
) -> str:
    failing = [finding for finding in findings if finding.result == "fail"]
    issue_id = str(uuid.uuid4())
    now = utc_now()
    names = "、".join(finding.parameter_name for finding in failing)
    reasons = "；".join(finding.reason for finding in failing)
    connection.execute(
        """
        INSERT INTO issues(
            id, project_id, source_document_id, requirement_id, parser_key,
            issue_type, category, severity, message, source_location,
            source_excerpt, blocking_reason, suggestion, status, created_at
        ) VALUES (?, ?, NULL, NULL, 'sampleComparison', 'contradictory',
                  'sample', 'high', ?, ?, ?, ?, ?, 'open', ?)
        """,
        (
            issue_id,
            delivery["project_id"],
            f"样件比对失败：{names}与图纸标注不一致",
            (f"{delivery['drawing_display_code']} " f"{delivery['drawing_revision']}"),
            reasons,
            "样件与图纸标注不一致，需复检或明确处置",
            "复核测量与图纸，或记录让步/风险接受依据",
            now,
        ),
    )
    connection.execute(
        """
        INSERT INTO sample_comparison_issues(
            id, comparison_id, comparison_revision, issue_id, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            comparison_id,
            revision,
            issue_id,
            now,
        ),
    )
    row = connection.execute(
        "SELECT * FROM issues WHERE id = ?", (issue_id,)
    ).fetchone()
    _audit(
        connection,
        project_id=delivery["project_id"],
        object_type="issue",
        object_id=issue_id,
        object_revision=None,
        action="issue.opened",
        actor="sample_comparison_rule",
        role="system",
        comment=evidence,
        after=dict(row),
    )
    return issue_id


def _link_existing_open_issue(
    connection: sqlite3.Connection,
    *,
    comparison_id: str,
    revision: int,
) -> bool:
    row = connection.execute(
        """
        SELECT i.id FROM issues i
        JOIN sample_comparison_issues l ON l.issue_id = i.id
        WHERE l.comparison_id = ? AND i.status = 'open'
        ORDER BY i.created_at ASC LIMIT 1
        """,
        (comparison_id,),
    ).fetchone()
    if row is None:
        return False
    exists = connection.execute(
        """
        SELECT 1 FROM sample_comparison_issues
        WHERE comparison_id = ? AND comparison_revision = ?
          AND issue_id = ?
        """,
        (comparison_id, revision, row["id"]),
    ).fetchone()
    if exists is None:
        connection.execute(
            """
            INSERT INTO sample_comparison_issues(
                id, comparison_id, comparison_revision, issue_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                comparison_id,
                revision,
                row["id"],
                utc_now(),
            ),
        )
    return True


def create_sample_comparison(
    connection: sqlite3.Connection,
    delivery_id: str,
    payload: SampleComparisonCreate,
) -> dict[str, Any]:
    with transaction(connection):
        delivery = _get_delivery_row(connection, delivery_id)
        if _file_row(connection, delivery_id) is None:
            raise DomainValidationError(
                "样件文件尚未上传，不能进行比对",
                {"delivery_id": delivery_id},
            )
        specs = _parameter_specs(connection, delivery_id)
        spec_by_key = {spec.parameter_key: spec for spec in specs}
        unknown = [
            measurement.parameter_key
            for measurement in payload.parameters
            if measurement.parameter_key not in spec_by_key
        ]
        if unknown:
            unknown_keys = sorted(set(unknown))
            raise DomainValidationError(
                "实测参数不在图纸结构化标注中：" + "、".join(unknown_keys),
                {"unknown_parameters": unknown_keys},
            )
        measurements = {
            item.parameter_key: ParameterMeasurement(
                parameter_key=item.parameter_key,
                measured_value=item.measured_value,
                unit=item.unit,
            )
            for item in payload.parameters
        }
        findings = [
            compare_parameter(
                spec,
                measurements.get(
                    spec.parameter_key,
                    ParameterMeasurement(
                        parameter_key=spec.parameter_key,
                        measured_value=None,
                        unit=spec.unit,
                    ),
                ),
            )
            for spec in specs
        ]
        findings.append(
            visual_finding(
                payload.visual_check.mode,
                payload.visual_check.result,
                payload.visual_check.note,
            )
        )
        overall = combine_results([finding.result for finding in findings])
        visual_check = {
            "mode": payload.visual_check.mode,
            "result": payload.visual_check.result,
            "note": payload.visual_check.note,
        }
        snapshot = _json_text(
            {
                "parameters": [
                    {
                        "parameter_key": item.parameter_key,
                        "measured_value": item.measured_value,
                        "unit": item.unit,
                    }
                    for item in sorted(
                        payload.parameters,
                        key=lambda item: item.parameter_key,
                    )
                ],
                "visual_check": visual_check,
            }
        )
        findings_json = _json_text([asdict(finding) for finding in findings])
        existing = _comparison_row(connection, delivery_id)
        if payload.expected_revision is not None and (
            existing is None or payload.expected_revision != existing["revision"]
        ):
            raise VersionConflictError(
                "比对记录版本已变化，请刷新后重新核对",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": (
                        existing["revision"] if existing is not None else None
                    ),
                },
            )
        now = utc_now()
        if existing is None:
            comparison_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO sample_comparisons(
                    id, project_id, sample_id, display_code, revision,
                    status, mode, overall_result, findings, visual_check,
                    inputs_snapshot, evidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 'draft', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comparison_id,
                    delivery["project_id"],
                    delivery_id,
                    f"CMP-{delivery['display_code']}",
                    payload.visual_check.mode,
                    overall,
                    findings_json,
                    _json_text(visual_check),
                    snapshot,
                    payload.evidence,
                    now,
                    now,
                ),
            )
            revision = 1
            action = "sample_comparison.created"
        else:
            comparison_id = existing["id"]
            if (
                existing["inputs_snapshot"] == snapshot
                and existing["evidence"] == payload.evidence
            ):
                return _comparison_payload(connection, comparison_id)
            if payload.expected_revision is None:
                raise VersionConflictError(
                    "修订已有比对必须提交 expected_revision",
                    {
                        "current_revision": existing["revision"],
                    },
                )
            revision = int(existing["revision"]) + 1
            connection.execute(
                """
                UPDATE sample_comparisons SET
                    revision = ?, status = 'draft', mode = ?,
                    overall_result = ?, findings = ?, visual_check = ?,
                    inputs_snapshot = ?, evidence = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    revision,
                    payload.visual_check.mode,
                    overall,
                    findings_json,
                    _json_text(visual_check),
                    snapshot,
                    payload.evidence,
                    now,
                    comparison_id,
                ),
            )
            action = "sample_comparison.updated"
        saved = connection.execute(
            "SELECT * FROM sample_comparisons WHERE id=?", (comparison_id,)
        ).fetchone()
        connection.execute(
            "INSERT INTO sample_comparison_versions(comparison_id,revision,snapshot_json,created_at) VALUES (?,?,?,?)",
            (comparison_id, revision, _json_text(_comparison_dict(saved)), now),
        )
        from .consistency_services import mark_consistency_checks_stale

        mark_consistency_checks_stale(
            connection, delivery["project_id"], "样件比对或证据已变化，请重新检查"
        )
        if any(finding.result == "fail" for finding in findings):
            if not _link_existing_open_issue(
                connection,
                comparison_id=comparison_id,
                revision=revision,
            ):
                _create_comparison_issue(
                    connection,
                    delivery=delivery,
                    comparison_id=comparison_id,
                    revision=revision,
                    findings=findings,
                    evidence=payload.evidence,
                )
        _audit(
            connection,
            project_id=delivery["project_id"],
            object_type="sample_comparison",
            object_id=comparison_id,
            object_revision=revision,
            action=action,
            actor=payload.actor,
            role=payload.role,
            comment=payload.evidence,
            after={
                "overall_result": overall,
                "mode": payload.visual_check.mode,
                "findings": len(findings),
            },
        )
        return _comparison_payload(connection, comparison_id)


def get_sample_comparison(
    connection: sqlite3.Connection, delivery_id: str
) -> dict[str, Any]:
    _get_delivery_row(connection, delivery_id)
    row = _comparison_row(connection, delivery_id)
    if row is None:
        raise NotFoundError("样件比对不存在", {"delivery_id": delivery_id})
    return _comparison_payload(connection, row["id"])


def confirm_sample_comparison(
    connection: sqlite3.Connection,
    comparison_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, Any]:
    with transaction(connection):
        row = connection.execute(
            "SELECT * FROM sample_comparisons WHERE id = ?",
            (comparison_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("样件比对不存在", {"comparison_id": comparison_id})
        if payload.expected_revision != row["revision"]:
            raise VersionConflictError(
                "样件比对已被更新，请刷新后重试",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": row["revision"],
                },
            )
        duplicate = connection.execute(
            """
            SELECT id FROM sample_comparison_confirmations
            WHERE comparison_id = ? AND comparison_revision = ?
            """,
            (comparison_id, row["revision"]),
        ).fetchone()
        if duplicate is not None:
            raise VersionConflictError(
                "该版本样件比对已有确认记录",
                {"comparison_revision": row["revision"]},
            )
        status = "confirmed" if payload.decision == "confirmed" else "rejected"
        snapshot = {
            "comparison_revision": row["revision"],
            "overall_result": row["overall_result"],
            "mode": row["mode"],
            "findings": _parse_json(row["findings"], []),
            "issue_ids": [
                issue["id"] for issue in _comparison_issues(connection, comparison_id)
            ],
        }
        connection.execute(
            """
            UPDATE sample_comparisons
            SET status = ?, updated_at = ? WHERE id = ?
            """,
            (status, utc_now(), comparison_id),
        )
        confirmation_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO sample_comparison_confirmations(
                id, comparison_id, comparison_revision, actor, role,
                decision, comment, snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                confirmation_id,
                comparison_id,
                row["revision"],
                payload.actor,
                payload.role,
                payload.decision,
                payload.comment,
                _json_text(snapshot),
                utc_now(),
            ),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="sample_comparison",
            object_id=comparison_id,
            object_revision=row["revision"],
            action=f"sample_comparison.{status}",
            actor=payload.actor,
            role=payload.role,
            decision=payload.decision,
            comment=payload.comment,
            before={"status": row["status"]},
            after={"status": status},
        )
        result = _comparison_payload(connection, comparison_id)
        confirmation = connection.execute(
            """
            SELECT * FROM sample_comparison_confirmations
            WHERE id = ?
            """,
            (confirmation_id,),
        ).fetchone()
        result["confirmation"] = _comparison_confirmation_dict(confirmation)
        return result
