from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import re
import sqlite3
import uuid
import zipfile
from typing import Any, Callable, TypeVar

from . import (
    consistency_services,
    coordination_services,
    design_services,
    sample_services,
    services,
    source_files,
    engineering_versions,
    testing_services,
)
from .db import transaction, utc_now
from .domain.package import (
    ArtifactGateItem,
    ConflictGateItem,
    ConsistencyGateItem,
    CoordinationRiskGateItem,
    IssueGateItem,
    PackageGateInputs,
    RequirementGateItem,
    ValidationGateItem,
    evaluate_package_gate,
)
from .errors import (
    DomainValidationError,
    MaterialPackageStateError,
    NotFoundError,
    VersionConflictError,
)
from .schemas import (
    MaterialPackageApprovalCreate,
    MaterialPackageCreate,
)

PACKAGE_SCHEMA_VERSION = "O13-1.2"
PACKAGE_SOURCE_LABEL = "门径评审材料包 V1（本地快照）"
FIXED_VALIDATION_DENOMINATOR = 5
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
PACKAGE_CREATED_BY_DEFAULT = "演示用户（未认证）"
PACKAGE_DEMO_ROLE = "演示角色"

T = TypeVar("T")


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_json(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_segment(value: str, fallback: str = "file") -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._\-一-鿿]+", "_", value)
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def _project_row(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("项目不存在", {"project_id": project_id})
    return row


def _optional(call: Callable[[], T]) -> T | None:
    try:
        return call()
    except NotFoundError:
        return None


def _references(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT rr.*, r.display_code AS referenced_display_code,
               r.parameter_name AS referenced_parameter_name
        FROM requirement_references rr
        JOIN requirements r ON r.id = rr.referenced_requirement_id
        WHERE rr.project_id = ?
        ORDER BY rr.created_at ASC, rr.id ASC
        """,
        (project_id,),
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["requirement_id"], []).append(dict(row))
    return grouped


def _source_documents(
    connection: sqlite3.Connection, project_id: str
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT * FROM source_documents
        WHERE project_id = ?
        ORDER BY created_at ASC, display_code ASC, version ASC
        """,
        (project_id,),
    ).fetchall()


def _requirements_snapshot(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    source_rows = _source_documents(connection, project_id)
    source_map = {row["id"]: row for row in source_rows}
    references = _references(connection, project_id)
    requirements = services.list_requirements(connection, project_id)
    for requirement in requirements:
        source = source_map.get(requirement.get("source_document_id"))
        requirement["source_document_display_code"] = (
            source["display_code"] if source is not None else None
        )
        requirement["source_document_version"] = (
            source["version"] if source is not None else None
        )
        requirement["references"] = references.get(requirement["id"], [])
    return requirements


def _variant_snapshot(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    variants = connection.execute(
        """
        SELECT v.*, b.display_code AS base_display_code
        FROM variant_points v
        JOIN product_bases b ON b.id = v.base_id
        WHERE v.project_id = ?
        ORDER BY b.display_code ASC, v.display_code ASC
        """,
        (project_id,),
    ).fetchall()
    reusable = connection.execute(
        """
        SELECT d.*, b.display_code AS base_display_code,
               v.display_code AS variant_display_code
        FROM reusable_part_decisions d
        JOIN product_bases b ON b.id = d.base_id
        LEFT JOIN variant_points v ON v.id = d.variant_point_id
        WHERE d.project_id = ?
        ORDER BY b.display_code ASC, d.part_display_code ASC
        """,
        (project_id,),
    ).fetchall()
    variant_items = []
    for row in variants:
        item = dict(row)
        item["affected_parts"] = _parse_json(item.get("affected_parts"), [])
        item["upstream_requirement_ids"] = _parse_json(
            item.get("upstream_requirement_ids"), []
        )
        variant_items.append(item)
    return {
        "variant_points": variant_items,
        "reusable_parts": [dict(row) for row in reusable],
    }


def _sample_snapshot(
    connection: sqlite3.Connection, project_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    deliveries = sample_services.list_sample_deliveries(connection, project_id)
    comparisons: list[dict[str, Any]] = []
    for delivery in deliveries:
        payload = _optional(
            lambda delivery_id=delivery["id"]: (
                sample_services.get_sample_comparison(connection, delivery_id)
            )
        )
        if payload is not None:
            comparisons.append(
                {
                    "delivery_id": delivery["id"],
                    "delivery_display_code": delivery["display_code"],
                    "payload": payload,
                }
            )
    return deliveries, comparisons


def _coordination_snapshot(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    return coordination_services.get_coordination_overview(connection, project_id)


def _originals(
    connection: sqlite3.Connection,
    project_id: str,
    deliveries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    originals: list[dict[str, Any]] = []
    for document in _source_documents(connection, project_id):
        original = source_files.metadata(connection, document["id"])
        if original:
            data, filename, media_type = source_files.download(
                connection, document["id"]
            )
            originals.append(
                {
                    "path": f"originals/source_files/{document['id']}/{_safe_segment(filename)}",
                    "sha256": _sha256(data),
                    "size_bytes": len(data),
                    "media_type": media_type,
                    "description": f"归档来源原件 {filename} ({document['version']})",
                    "source_object_type": "source_document_file",
                    "source_object_id": document["id"],
                    "content_base64": base64.b64encode(data).decode("ascii"),
                }
            )
        content = document["original_text"].encode("utf-8")
        path = (
            "originals/source_documents/"
            f"{_safe_segment(document['display_code'])}_"
            f"{_safe_segment(document['version'])}.txt"
        )
        originals.append(
            {
                "path": path,
                "sha256": _sha256(content),
                "size_bytes": len(content),
                "media_type": "text/plain; charset=utf-8",
                "description": (
                    f"来源文档 {document['display_code']} " f"{document['version']}"
                ),
                "source_object_type": "source_document",
                "source_object_id": document["id"],
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        )
    delivery_map = {item["id"]: item for item in deliveries}
    file_rows = connection.execute(
        """
        SELECT f.*, d.project_id
        FROM sample_delivery_files f
        JOIN sample_deliveries d ON d.id = f.sample_id
        WHERE d.project_id = ?
        ORDER BY d.display_code ASC
        """,
        (project_id,),
    ).fetchall()
    for row in file_rows:
        content = bytes(row["content"])
        delivery = delivery_map.get(row["sample_id"])
        display_code = (
            delivery["display_code"] if delivery is not None else row["sample_id"]
        )
        path = (
            "originals/samples/"
            f"{_safe_segment(display_code)}/"
            f"{_safe_segment(row['file_name'])}"
        )
        originals.append(
            {
                "path": path,
                "sha256": _sha256(content),
                "size_bytes": len(content),
                "media_type": row["content_type"],
                "description": (
                    f"样件原始文件 {row['file_name']}" f"（{display_code}）"
                ),
                "source_object_type": "sample_delivery_file",
                "source_object_id": row["id"],
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        )
    return originals


def _snapshot_data(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    package_id: str,
    display_code: str,
    package_no: int,
    include_originals: bool,
    now: str,
) -> dict[str, Any]:
    project = dict(_project_row(connection, project_id))
    requirements = _requirements_snapshot(connection, project_id)
    sources = _source_documents(connection, project_id)
    source_metadata = [
        {
            "id": row["id"],
            "display_code": row["display_code"],
            "doc_type": row["doc_type"],
            "version": row["version"],
            "content_hash": row["content_hash"],
            "original_file": source_files.metadata(connection, row["id"]),
            "mode": row["mode"],
            "created_at": row["created_at"],
        }
        for row in sources
    ]
    design_review = _optional(
        lambda: design_services.get_design_review(connection, project_id)
    )
    dfmea = _optional(lambda: design_services.get_dfmea(connection, project_id))
    test_plan = _optional(
        lambda: testing_services.get_test_plan(connection, project_id)
    )
    traceability = testing_services.get_traceability_matrix(connection, project_id)
    deliveries, comparisons = _sample_snapshot(connection, project_id)
    consistency = _optional(
        lambda: consistency_services.get_latest_consistency_check(
            connection, project_id
        )
    )
    conflicts = consistency_services.list_conflicts(connection, project_id)
    issues = services.list_issues(connection, project_id)
    coordination = _coordination_snapshot(connection, project_id)
    audit_events = services.list_audit_events(connection, project_id)
    originals = (
        _originals(connection, project_id, deliveries) if include_originals else []
    )
    snapshot = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "generated_at": now,
        "timezone": "UTC",
        "mode": "rule",
        "source_label": PACKAGE_SOURCE_LABEL,
        "package": {
            "id": package_id,
            "display_code": display_code,
            "package_no": package_no,
            "include_originals": include_originals,
            "status": None,
        },
        "project": project,
        "source_documents": source_metadata,
        "requirements": requirements,
        "variant_analysis": _variant_snapshot(connection, project_id),
        "engineering_records": engineering_versions.list_records(
            connection, project_id
        ),
        "design_review": design_review,
        "dfmea": dfmea,
        "test_plan": test_plan,
        "traceability": traceability,
        "sample_deliveries": deliveries,
        "sample_comparisons": comparisons,
        "consistency": consistency,
        "conflicts": conflicts,
        "issues": issues,
        "coordination": coordination,
        "audit_events": audit_events,
        "originals": originals,
    }
    return snapshot


def _required_requirement_ids(
    snapshot: dict[str, Any],
) -> set[str]:
    required: set[str] = set()
    for item in snapshot["traceability"]["items"]:
        if item.get("requirement_id"):
            required.add(item["requirement_id"])
    plan = snapshot.get("test_plan")
    if plan is not None:
        for case in plan.get("cases", []):
            for reference in case.get("requirement_refs", []):
                if reference.get("requirement_id"):
                    required.add(reference["requirement_id"])
            if case.get("load_basis_requirement_id"):
                required.add(case["load_basis_requirement_id"])
    return required


def _is_accepted(topic: dict[str, Any], metric_run_id: str | None) -> bool:
    if metric_run_id is None:
        return False
    return any(
        acceptance.get("metric_run_id") == metric_run_id
        for acceptance in topic.get("risk_acceptances", [])
    )


def _sample_artifacts(
    snapshot: dict[str, Any],
) -> tuple[ArtifactGateItem, ...]:
    comparisons = {item["delivery_id"]: item for item in snapshot["sample_comparisons"]}
    artifacts: list[ArtifactGateItem] = []
    for delivery in snapshot["sample_deliveries"]:
        comparison = comparisons.get(delivery["id"])
        if comparison is None:
            artifacts.append(
                ArtifactGateItem(
                    key=f"sample_comparison:{delivery['id']}",
                    label=f"样件比对 {delivery['display_code']}",
                    object_type="sample_comparison",
                    object_id=None,
                    display_code=delivery["display_code"],
                    revision=None,
                    status=None,
                    exists=False,
                )
            )
            continue
        item = comparison["payload"]["comparison"]
        confirmations = comparison["payload"].get("confirmations", [])
        needs_reconfirmation = bool(confirmations) and (
            confirmations[-1]["comparison_revision"] < item["revision"]
        )
        artifacts.append(
            ArtifactGateItem(
                key=f"sample_comparison:{delivery['id']}",
                label=f"样件比对 {delivery['display_code']}",
                object_type="sample_comparison",
                object_id=item["id"],
                display_code=delivery["display_code"],
                revision=item["revision"],
                status=item["status"],
                needs_reconfirmation=needs_reconfirmation,
            )
        )
    return tuple(artifacts)


def _artifact(
    snapshot: dict[str, Any],
    *,
    key: str,
    label: str,
    object_type: str,
    payload_key: str,
    document_key: str,
) -> ArtifactGateItem:
    payload = snapshot.get(payload_key)
    if payload is None:
        return ArtifactGateItem(
            key=key,
            label=label,
            object_type=object_type,
            exists=False,
        )
    document = payload[document_key]
    failure_messages: list[str] = []
    if key == "dfmea":
        for item in payload.get("items", []):
            if not item.get("scores_confirmed"):
                failure_messages.append(
                    f"{item.get('display_code', 'DFMEA 条目')} 的 S/O/D 尚未确认"
                )
    return ArtifactGateItem(
        key=key,
        label=label,
        object_type=object_type,
        object_id=document["id"],
        display_code=document["display_code"],
        revision=document["revision"],
        status=document["status"],
        needs_reconfirmation=bool(payload.get("needs_reconfirmation", False)),
        failure_messages=tuple(failure_messages),
    )


def _gate_inputs(snapshot: dict[str, Any]) -> PackageGateInputs:
    requirement_map = {item["id"]: item for item in snapshot["requirements"]}
    required_ids = _required_requirement_ids(snapshot)
    requirements = tuple(
        RequirementGateItem(
            requirement_id=requirement_id,
            display_code=requirement_map[requirement_id]["display_code"],
            revision=requirement_map[requirement_id]["current_revision"],
            review_status=requirement_map[requirement_id]["review_status"],
            validity=requirement_map[requirement_id]["validity"],
        )
        for requirement_id in sorted(required_ids)
        if requirement_id in requirement_map
    )

    validation = tuple(
        ValidationGateItem(
            key=item["key"],
            label=item["label"],
            requirement_id=item.get("requirement_id"),
            display_code=item.get("display_code"),
            requirement_revision=item.get("requirement_revision"),
            covered=bool(item["covered"]),
            execution=item["execution"],
        )
        for item in snapshot["traceability"]["items"]
    )

    artifacts = (
        _artifact(
            snapshot,
            key="test_plan",
            label="试验方案",
            object_type="test_plan",
            payload_key="test_plan",
            document_key="plan",
        ),
        _artifact(
            snapshot,
            key="design_review",
            label="设计评审清单",
            object_type="design_review",
            payload_key="design_review",
            document_key="review",
        ),
        _artifact(
            snapshot,
            key="dfmea",
            label="DFMEA",
            object_type="fmea_document",
            payload_key="dfmea",
            document_key="fmea",
        ),
    )

    review_base = (
        snapshot.get("design_review", {}).get("review", {}).get("base_id")
        if snapshot.get("design_review")
        else None
    )
    engineering = [
        row
        for row in snapshot.get("engineering_records", [])
        if not review_base or row["base_id"] == review_base
    ]
    engineering_artifacts = tuple(
        ArtifactGateItem(
            key=f"{row['kind']}:{row['id']}",
            label=f"{'变型点' if row['kind'] == 'variant' else '复用决策'} {row.get('display_code', row.get('part_display_code'))}",
            object_type=(
                "variant_point"
                if row["kind"] == "variant"
                else "reusable_part_decision"
            ),
            object_id=row["id"],
            display_code=row.get("display_code", row.get("part_display_code")),
            revision=row["revision"],
            status=row["review_status"],
            needs_reconfirmation=row["status"] != "current",
        )
        for row in engineering
        if row["is_applicable"]
    )
    if not any(
        row["kind"] == "part" and row["status"] == "current" for row in engineering
    ):
        engineering_artifacts += (
            ArtifactGateItem(
                key="reusable_decisions",
                label="当前可复用件决策",
                object_type="reusable_part_decision",
                exists=False,
            ),
        )
    artifacts += engineering_artifacts

    consistency_payload = snapshot.get("consistency")
    if consistency_payload is None:
        consistency = ConsistencyGateItem(
            check_id=None,
            display_code=None,
            status=None,
            validity=None,
            blocking_conflicts=(),
        )
    else:
        check = consistency_payload["check"]
        check_conflicts = consistency_payload.get("conflicts", [])
        blocking_conflicts = tuple(
            ConflictGateItem(
                conflict_id=item["id"],
                display_code=item["display_code"],
                severity=item["severity"],
                status=item["status"],
            )
            for item in check_conflicts
            if item["severity"] == "blocking" and item["status"] == "open"
        )
        open_high_count = sum(
            1
            for item in check_conflicts
            if item["severity"] == "high" and item["status"] == "open"
        )
        consistency = ConsistencyGateItem(
            check_id=check["id"],
            display_code=check["display_code"],
            status=check["status"],
            validity=check["validity"],
            blocking_conflicts=blocking_conflicts,
            open_high_count=open_high_count,
        )

    issues = tuple(
        IssueGateItem(
            issue_id=item["id"],
            issue_type=item["issue_type"],
            severity=item["severity"],
            status=item["status"],
            message=item["message"],
        )
        for item in snapshot["issues"]
    )

    coordination_items: list[CoordinationRiskGateItem] = []
    for topic in snapshot["coordination"]["topics"]:
        latest = topic.get("latest_metrics")
        metric_run_id = latest["id"] if latest is not None else None
        risk_level = latest["risk"]["risk_level"] if latest is not None else None
        coordination_items.append(
            CoordinationRiskGateItem(
                topic_id=topic["id"],
                display_code=topic["display_code"],
                metric_run_id=metric_run_id,
                risk_level=risk_level,
                accepted=_is_accepted(topic, metric_run_id),
                validity=latest["validity"] if latest is not None else "current",
            )
        )

    return PackageGateInputs(
        requirements=requirements,
        validation=validation,
        artifacts=artifacts,
        sample_artifacts=_sample_artifacts(snapshot),
        consistency=consistency,
        issues=issues,
        coordination=tuple(coordination_items),
        expected_denominator=FIXED_VALIDATION_DENOMINATOR,
    )


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "；".join(str(item) for item in value)
    if isinstance(value, dict):
        return _json_text(value)
    return str(value)


def _csv_bytes(headers: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return buffer.getvalue().encode("utf-8-sig")


def _requirement_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            item["display_code"],
            item["category"],
            item["parameter_name"],
            item["data_type"],
            item["operator"],
            item["value_text"],
            item["unit"],
            item["raw_expression"],
            item["review_status"],
            item["validity"],
            item["current_revision"],
            item.get("source_document_display_code"),
            item.get("source_document_version"),
            item["source_location"],
            item["source_excerpt"],
            "；".join(
                f"{ref.get('referenced_display_code', '')} "
                f"{ref.get('relation', '')}"
                for ref in item.get("references", [])
            ),
        ]
        for item in snapshot["requirements"]
    ]


def _design_review_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    payload = snapshot.get("design_review")
    if payload is None:
        return []
    return [
        [
            item["display_code"],
            item["revision"],
            item["check_point"],
            item["standard_basis"],
            item["responsible_role"],
            "；".join(
                dependency.get("display_code", "")
                for dependency in item.get("dependencies", [])
            ),
            item["status"],
        ]
        for item in payload.get("items", [])
    ]


def _dfmea_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    payload = snapshot.get("dfmea")
    if payload is None:
        return []
    rows = []
    for item in payload.get("items", []):
        rows.append(
            [
                item["display_code"],
                item["revision"],
                item["function_text"],
                item["failure_mode"],
                item["cause"],
                item["effect"],
                item["control"],
                item["action_text"],
                item["severity"],
                item["occurrence"],
                item["detection"],
                "是" if item["scores_confirmed"] else "否",
                item["rpn"],
                item["rpn_status"],
                item["status"],
            ]
        )
    return rows


def _latest_current_run(case: dict[str, Any]) -> dict[str, Any] | None:
    runs = [
        run
        for run in case.get("runs", [])
        if run.get("case_revision") == case.get("revision")
    ]
    return runs[-1] if runs else None


def _test_plan_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    payload = snapshot.get("test_plan")
    if payload is None:
        return []
    rows = []
    for case in payload.get("cases", []):
        latest = _latest_current_run(case)
        rows.append(
            [
                case["display_code"],
                case["title"],
                case["revision"],
                case["review_status"],
                case["validity"],
                case["conditions_text"],
                case["load_conditions_text"],
                case["acceptance_criteria"],
                "；".join(
                    reference.get("display_code", "")
                    for reference in case.get("requirement_refs", [])
                ),
                latest["run_no"] if latest else None,
                latest["result"] if latest else None,
                latest["mode"] if latest else None,
                latest["load_basis_numeric"] if latest else None,
                latest["backup_coefficient"] if latest else None,
                latest["created_at"] if latest else None,
            ]
        )
    return rows


def _traceability_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            item["key"],
            item["label"],
            item.get("display_code"),
            item.get("requirement_revision"),
            "是" if item["covered"] else "否",
            "；".join(item.get("valid_case_ids", [])),
            "；".join(item.get("pending_case_ids", [])),
            item["execution"],
            item.get("reason"),
        ]
        for item in snapshot["traceability"]["items"]
    ]


def _conflict_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            item["display_code"],
            item["conflict_type"],
            item["severity"],
            item["status"],
            item["detected"],
            item["title"],
            item["detail"],
            item["object_type"],
            item["object_id"],
            item["object_revision"],
            item["object_review_status"],
            item["first_seen_at"],
            item["last_seen_at"],
            item["recheck_status"],
            item["resolution_type"],
            item["resolution_note"],
            item["evidence_text"],
            "是" if item["accepted_risk"] else "否",
            item["closed_by"],
            item["closed_at"],
        ]
        for item in snapshot["conflicts"]
    ]


def _coordination_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for topic in snapshot["coordination"]["topics"]:
        latest = topic.get("latest_metrics")
        metrics = latest["metrics"] if latest else {}
        risk = latest["risk"] if latest else {}
        cost = latest["cost"] if latest else {}
        rows.append(
            [
                topic["display_code"],
                topic["name"],
                "；".join(topic.get("expected_participants", [])),
                "；".join(metrics.get("actual_participants", [])),
                metrics.get("average_response_hours"),
                metrics.get("response_sample_size"),
                metrics.get("iteration_count"),
                metrics.get("absence_rate"),
                metrics.get("pending_count"),
                risk.get("risk_level"),
                risk.get("score"),
                cost.get("amount"),
                latest["run_no"] if latest else None,
                latest["rule_label"] if latest else None,
                "是" if _is_accepted(topic, latest["id"] if latest else None) else "否",
            ]
        )
    return rows


def _coordination_record_rows(
    snapshot: dict[str, Any],
) -> list[list[Any]]:
    rows = []
    for topic in snapshot["coordination"]["topics"]:
        for record in topic.get("records", []):
            rows.append(
                [
                    topic["display_code"],
                    record["external_id"],
                    record["record_type"],
                    record["sender"],
                    record["record_type"],
                    record["content_summary"],
                    record["sent_at"],
                    record["reply_to_external_id"],
                ]
            )
    return rows


def _audit_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            event["created_at"],
            event["action"],
            event["object_type"],
            event["object_id"],
            event["object_revision"],
            event["actor"],
            event["role"],
            event["decision"],
            event["comment"],
            _json_text(event.get("before")) if event.get("before") else "",
            _json_text(event.get("after")) if event.get("after") else "",
        ]
        for event in snapshot["audit_events"]
    ]


def _issue_rows(snapshot: dict[str, Any]) -> list[list[Any]]:
    return [
        [
            item["id"],
            item["issue_type"],
            item["category"],
            item["severity"],
            item["status"],
            item["message"],
            item["source_location"],
            item["source_excerpt"],
            item["blocking_reason"],
            item["suggestion"],
            item["close_reason"],
            item["closed_at"],
        ]
        for item in snapshot["issues"]
    ]


def _status_label(status: str | None) -> str:
    return {
        "draft": "草稿",
        "ready_to_submit": "可提交",
        "human_approved": "人工已批准",
        "confirmed": "已确认",
        "rejected": "已驳回",
        "open": "开放",
        "closed": "已关闭",
        "current": "当前有效",
        "stale": "已失效",
        "pass": "通过",
        "fail": "未通过",
        "incomplete": "证据不足",
        "invalid": "无效",
        "not_run": "未执行",
        "running": "执行中",
        "completed": "已完成",
        "high": "高",
        "medium": "中",
        "low": "低",
        "insufficient": "数据不足",
        "blocking": "阻断",
    }.get(status or "", status or "未提供")


def _h(value: Any) -> str:
    return html.escape(_cell(value))


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{_h(value)}</th>" for value in headers)
    if not rows:
        body = (
            f'<tr><td colspan="{len(headers)}" class="empty">'
            "无记录（未生成或尚未发生）</td></tr>"
        )
    else:
        body = "".join(
            "<tr>" + "".join(f"<td>{_h(value)}</td>" for value in row) + "</tr>"
            for row in rows
        )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _report_html(snapshot: dict[str, Any], snapshot_hash: str) -> bytes:
    package = snapshot["package"]
    status = package["status"]
    gate = snapshot["gate"]
    project = snapshot["project"]
    traceability = snapshot["traceability"]
    coverage = f"{traceability['covered_count']} / {traceability['denominator']}"
    status_text = status
    if status == "ready_to_submit":
        status_text = "可提交（ready_to_submit）"
    elif status == "draft":
        status_text = "草稿（draft）"
    elif status == "human_approved":
        status_text = "人工已批准（human_approved）"

    gate_rows = [
        [
            check["label"],
            _status_label(check["status"]),
            check.get("summary", ""),
            len(check.get("failures", [])),
        ]
        for check in gate["checks"]
    ]
    blocker_rows = [
        [
            blocker["code"],
            blocker["message"],
            blocker.get("object_type", ""),
            blocker.get("object_id", ""),
            blocker.get("revision", ""),
        ]
        for blocker in gate["blockers"]
    ]
    warning_rows = [
        [warning["code"], warning["message"]] for warning in gate["warnings"]
    ]
    requirement_rows = [
        [
            item["display_code"],
            item["parameter_name"],
            f"{item['operator']} {item['value_text']} {item['unit']}",
            _status_label(item["review_status"]),
            _status_label(item["validity"]),
            item["current_revision"],
            item.get("source_document_display_code") or "",
        ]
        for item in snapshot["requirements"]
    ]
    trace_rows = [
        [
            item["key"],
            item["label"],
            item.get("display_code") or "缺失",
            "是" if item["covered"] else "否",
            _status_label(item["execution"]),
            item.get("reason") or "",
        ]
        for item in traceability["items"]
    ]
    design_rows = _design_review_rows(snapshot)
    dfmea_rows = _dfmea_rows(snapshot)
    test_rows = _test_plan_rows(snapshot)
    conflict_rows = _conflict_rows(snapshot)
    coordination_rows = _coordination_rows(snapshot)
    coordination_record_rows = _coordination_record_rows(snapshot)
    issue_rows = _issue_rows(snapshot)
    completed_runs = [row for row in test_rows if row[10] is not None]

    gap_text = (
        "以下条目未满足门禁条件，材料包仅作为草稿导出，不能提交。"
        if gate["status"] != "ready"
        else "系统门禁未发现阻断缺口。仍需人工审批后才能成为 human_approved。"
    )
    limitation_items = [
        "本材料包是本地单用户演示材料，不代表真实工程认证或企业验收。",
        "规则生成的解析、评分、试验判定和一致性检查均标注为 rule；模拟视觉判断标注为 mock。",
        "未接入真实台架、OCR、视觉模型、供应商系统或生产环境。",
        "报告不依赖外网脚本、字体或图片，可离线打开和打印。",
    ]

    sections = []
    sections.append(
        f"""
        <section class="summary">
          <h2>一、项目与材料包</h2>
          <div class="grid">
            <div><span>项目</span><strong>{_h(project['display_code'])} · {_h(project['name'])}</strong></div>
            <div><span>客户</span><strong>{_h(project['customer'])}</strong></div>
            <div><span>产品</span><strong>{_h(project['product'])}</strong></div>
            <div><span>材料包</span><strong>{_h(package['display_code'])}（第 {_h(package['package_no'])} 次生成）</strong></div>
            <div><span>生成时间</span><strong>{_h(snapshot['generated_at'])}（UTC）</strong></div>
            <div><span>状态</span><strong>{_h(status_text)}</strong></div>
            <div><span>快照哈希</span><code>{_h(snapshot_hash)}</code></div>
            <div><span>验证覆盖</span><strong>{_h(coverage)}</strong></div>
          </div>
          <p class="notice">{_h(gap_text)}</p>
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>二、门禁结论</h2>
          {_table(['检查项', '结论', '说明', '缺口数'], gate_rows)}
          <h3>阻断项</h3>
          {_table(['代码', '说明', '对象类型', '对象 ID', '版本'], blocker_rows)}
          <h3>警告</h3>
          {_table(['代码', '说明'], warning_rows)}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>三、需求（O1）</h2>
          {_table(['显示编号', '参数', '要求', '审核状态', '有效性', '版本', '来源文档'], requirement_rows)}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>四、追溯矩阵与验证（O9–O11）</h2>
          <p>覆盖按“已确认 + current + 条件/加载/判定完整 + 引用当前需求版本”计算；执行结论单独统计。</p>
          {_table(['需求键', '范围', '需求编号', '已覆盖', '执行结论', '原因'], trace_rows)}
          <p>覆盖汇总：{_h(coverage)}；执行已记录用例：{len(completed_runs)} / {len(test_rows)}。</p>
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>五、设计评审（O7）与 DFMEA（O8）</h2>
          <h3>设计评审清单</h3>
          {_table(['条目', '版本', '检查点', '标准依据', '责任角色', '依赖', '状态'], design_rows)}
          <h3>DFMEA</h3>
          {_table(['条目', '版本', '功能', '失效模式', '原因', '影响', '控制', '措施', 'S', 'O', 'D', '评分确认', 'RPN', 'RPN 状态', '条目状态'], dfmea_rows)}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>六、试验方案与执行（O9–O10）</h2>
          {_table(['用例', '标题', '版本', '审核', '有效性', '工况', '加载条件', '判定标准', '引用需求', '运行号', '结果', '模式', '加载基准', '后备系数', '执行时间'], test_rows)}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>七、样件交付与比对（O12）</h2>
          {_table(['样件', '供应商', '图纸', '图纸版本', '数量', '文件已上传', '比对状态'], [
              [item['display_code'], item['supplier'], item['drawing_display_code'], item['drawing_revision'], item['quantity'], '是' if item['file_uploaded'] else '否', next((comparison['payload']['comparison']['status'] for comparison in snapshot['sample_comparisons'] if comparison['delivery_id'] == item['id']), '未生成')]
              for item in snapshot['sample_deliveries']
          ])}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>八、一致性与冲突处理</h2>
          {_table(['冲突', '类型', '严重度', '状态', '仍检出', '标题', '对象', '版本', '对象审核'], conflict_rows)}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>九、协同指标（O14）</h2>
          <p>COORD-DEMO-V1 为透明演示规则；未知数据不按 0 处理。</p>
          {_table(['议题', '名称', '应参与方', '实际参与方', '平均响应(h)', '样本', '反复', '缺席率', '待响应', '风险', '指数', '成本', '计算号', '规则', '风险已接受'], coordination_rows)}
          <h3>协同记录</h3>
          {_table(['议题', '外部编号', '类型', '发送方', '类型', '摘要', '发送时间', '回复对象'], coordination_record_rows)}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>十、问题闭环</h2>
          {_table(['问题 ID', '类型', '分类', '严重度', '状态', '说明', '来源位置', '原文摘录', '阻塞原因', '建议', '关闭原因', '关闭时间'], issue_rows)}
        </section>
        """
    )
    sections.append(
        f"""
        <section>
          <h2>十一、缺口与限制</h2>
          <ul>{''.join(f'<li>{_h(item)}</li>' for item in limitation_items)}</ul>
          <p>原件纳入选项：{'是' if package['include_originals'] else '否'}。未授权或不相关的原件不会自动纳入。</p>
          <p>审核日志与证据索引见 audit_log.csv、evidence_index.csv；CSV 使用 UTF-8 BOM，便于本地表格软件打开。</p>
        </section>
        """
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>智研引擎 · 门径评审材料包 · {_h(package['display_code'])}</title>
<style>
body {{ font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; margin: 28px; color: #1f2933; line-height: 1.55; }}
h1 {{ font-size: 26px; margin: 0 0 4px; }}
h2 {{ font-size: 19px; border-left: 5px solid #1d4ed8; padding-left: 10px; margin-top: 30px; }}
h3 {{ font-size: 16px; margin-top: 22px; }}
.sub {{ color: #52606d; margin-bottom: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 24px; margin: 12px 0; }}
.grid span {{ display: block; color: #616e7c; font-size: 12px; }}
.grid strong {{ display: block; }}
.notice {{ background: #f1f5f9; border: 1px solid #cbd5e1; padding: 10px 12px; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0 16px; font-size: 12px; }}
th, td {{ border: 1px solid #cbd5e1; padding: 6px 7px; vertical-align: top; text-align: left; }}
th {{ background: #e2e8f0; }}
tr:nth-child(even) td {{ background: #f8fafc; }}
.empty {{ color: #7b8794; text-align: center; }}
code {{ word-break: break-all; font-size: 11px; }}
ul {{ padding-left: 22px; }}
section {{ page-break-inside: avoid; }}
@media print {{
  body {{ margin: 10mm; }}
  section {{ page-break-inside: avoid; }}
}}
</style>
</head>
<body>
<h1>智研引擎 · 门径评审材料包</h1>
<div class="sub">本地合成/脱敏演示材料 · {_h(PACKAGE_SOURCE_LABEL)} · 快照 {_h(snapshot_hash[:16])}…</div>
{''.join(sections)}
</body>
</html>
""".encode(
        "utf-8"
    )


def _add_file(
    files: dict[str, bytes],
    descriptions: dict[str, str],
    media_types: dict[str, str],
    path: str,
    content: bytes,
    media_type: str,
    description: str,
) -> None:
    files[path] = content
    descriptions[path] = description
    media_types[path] = media_type


def _build_content_files(
    snapshot: dict[str, Any], snapshot_hash: str
) -> tuple[dict[str, bytes], dict[str, str], dict[str, str]]:
    files: dict[str, bytes] = {}
    descriptions: dict[str, str] = {}
    media_types: dict[str, str] = {}

    def add_csv(
        path: str, headers: list[str], rows: list[list[Any]], description: str
    ) -> None:
        _add_file(
            files,
            descriptions,
            media_types,
            path,
            _csv_bytes(headers, rows),
            "text/csv; charset=utf-8",
            description,
        )

    add_csv(
        "requirements.csv",
        [
            "显示编号",
            "类别",
            "参数",
            "数据类型",
            "运算符",
            "值",
            "单位",
            "原始表达",
            "审核状态",
            "有效性",
            "当前版本",
            "来源文档",
            "文档版本",
            "来源位置",
            "原文摘录",
            "引用关系",
        ],
        _requirement_rows(snapshot),
        "O1 结构化需求与来源",
    )
    add_csv(
        "design_review.csv",
        ["条目", "版本", "检查点", "标准依据", "责任角色", "依赖", "状态"],
        _design_review_rows(snapshot),
        "O7 设计评审清单",
    )
    add_csv(
        "dfmea.csv",
        [
            "条目",
            "版本",
            "功能",
            "失效模式",
            "原因",
            "影响",
            "控制",
            "措施",
            "S",
            "O",
            "D",
            "评分已确认",
            "RPN",
            "RPN 状态",
            "条目状态",
        ],
        _dfmea_rows(snapshot),
        "O8 DFMEA 与已确认评分",
    )
    add_csv(
        "test_plan.csv",
        [
            "用例",
            "标题",
            "版本",
            "审核状态",
            "有效性",
            "工况",
            "加载条件",
            "判定标准",
            "引用需求",
            "运行号",
            "结果",
            "模式",
            "加载基准",
            "后备系数",
            "执行时间",
        ],
        _test_plan_rows(snapshot),
        "O9–O10 试验方案、用例与执行",
    )
    add_csv(
        "traceability.csv",
        [
            "需求键",
            "验证范围",
            "需求编号",
            "需求版本",
            "已覆盖",
            "有效用例",
            "待复核用例",
            "执行结论",
            "原因",
        ],
        _traceability_rows(snapshot),
        "O11 追溯矩阵与覆盖/执行结论",
    )
    add_csv(
        "conflicts.csv",
        [
            "冲突编号",
            "类型",
            "严重度",
            "状态",
            "仍检出",
            "标题",
            "详情",
            "对象类型",
            "对象 ID",
            "对象版本",
            "对象审核状态",
            "首次发现",
            "最后发现",
            "复检状态",
            "处置类型",
            "处置说明",
            "证据",
            "接受风险",
            "关闭人",
            "关闭时间",
        ],
        _conflict_rows(snapshot),
        "一致性冲突与处置记录",
    )
    add_csv(
        "coordination.csv",
        [
            "议题",
            "名称",
            "应参与方",
            "实际参与方",
            "平均响应小时",
            "响应样本",
            "反复次数",
            "缺席率",
            "待响应",
            "风险等级",
            "规则指数",
            "协调成本",
            "计算号",
            "规则",
            "风险已接受",
        ],
        _coordination_rows(snapshot),
        "O14 协同指标、风险与成本",
    )
    add_csv(
        "coordination_records.csv",
        [
            "议题",
            "外部编号",
            "记录类型",
            "发送方",
            "显示类型",
            "摘要",
            "发送时间",
            "回复对象",
        ],
        _coordination_record_rows(snapshot),
        "协同原始记录（带时间戳）",
    )
    add_csv(
        "coordination_progress.csv",
        [
            "议题",
            "参与方",
            "里程碑",
            "记录版本",
            "计划百分比",
            "实际百分比",
            "交付版本",
            "报告时间",
            "依据",
        ],
        [
            [
                topic["display_code"],
                row["participant"],
                row["milestone"],
                row["revision"],
                row["planned_percent"],
                row["actual_percent"],
                row["artifact_version"],
                row["reported_at"],
                row["evidence"],
            ]
            for topic in snapshot["coordination"]["topics"]
            for row in topic.get("progress", {}).get("rows", [])
        ],
        "参与方计划与实际进度快照（合成/人工登记）",
    )
    add_csv(
        "audit_log.csv",
        [
            "时间",
            "动作",
            "对象类型",
            "对象 ID",
            "对象版本",
            "演示身份",
            "角色",
            "决定",
            "意见",
            "变更前",
            "变更后",
        ],
        _audit_rows(snapshot),
        "项目审核日志",
    )
    add_csv(
        "issues.csv",
        [
            "问题 ID",
            "类型",
            "分类",
            "严重度",
            "状态",
            "说明",
            "来源位置",
            "原文摘录",
            "阻塞原因",
            "建议",
            "关闭原因",
            "关闭时间",
        ],
        _issue_rows(snapshot),
        "问题闭环记录",
    )

    report = _report_html(snapshot, snapshot_hash)
    _add_file(
        files,
        descriptions,
        media_types,
        "report.html",
        report,
        "text/html; charset=utf-8",
        "可离线打开和打印的中文总报告",
    )

    for original in snapshot.get("originals", []):
        _add_file(
            files,
            descriptions,
            media_types,
            original["path"],
            base64.b64decode(original["content_base64"]),
            original["media_type"],
            original["description"],
        )

    evidence_rows = [
        [
            path,
            descriptions[path],
            media_types[path],
            _sha256(files[path]),
            len(files[path]),
        ]
        for path in sorted(files)
    ]
    add_csv(
        "evidence_index.csv",
        ["文件路径", "说明", "媒体类型", "SHA-256", "字节数"],
        evidence_rows,
        "材料包文件与校验值索引",
    )
    return files, descriptions, media_types


def _latest_run_snapshot(case: dict[str, Any]) -> dict[str, Any] | None:
    latest = _latest_current_run(case)
    if latest is None:
        return None
    return {
        "id": latest["id"],
        "run_no": latest["run_no"],
        "status": latest["status"],
        "result": latest["result"],
        "case_revision": latest["case_revision"],
        "mode": latest["mode"],
        "created_at": latest["created_at"],
    }


def _object_versions(snapshot: dict[str, Any]) -> dict[str, Any]:
    requirements = [
        {
            "id": item["id"],
            "display_code": item["display_code"],
            "revision": item["current_revision"],
            "review_status": item["review_status"],
            "validity": item["validity"],
        }
        for item in snapshot["requirements"]
    ]
    plan = snapshot.get("test_plan")
    test_plan = None
    test_cases: list[dict[str, Any]] = []
    if plan is not None:
        test_plan = {
            "id": plan["plan"]["id"],
            "display_code": plan["plan"]["display_code"],
            "revision": plan["plan"]["revision"],
            "status": plan["plan"]["status"],
        }
        test_cases = [
            {
                "id": case["id"],
                "display_code": case["display_code"],
                "revision": case["revision"],
                "review_status": case["review_status"],
                "validity": case["validity"],
                "latest_run": _latest_run_snapshot(case),
            }
            for case in plan.get("cases", [])
        ]
    design_review = None
    if snapshot.get("design_review") is not None:
        review = snapshot["design_review"]["review"]
        design_review = {
            "id": review["id"],
            "display_code": review["display_code"],
            "revision": review["revision"],
            "status": review["status"],
        }
    dfmea = None
    if snapshot.get("dfmea") is not None:
        fmea = snapshot["dfmea"]["fmea"]
        dfmea = {
            "id": fmea["id"],
            "display_code": fmea["display_code"],
            "revision": fmea["revision"],
            "status": fmea["status"],
        }
    consistency = None
    if snapshot.get("consistency") is not None:
        check = snapshot["consistency"]["check"]
        consistency = {
            "id": check["id"],
            "display_code": check["display_code"],
            "revision": check["revision"],
            "status": check["status"],
            "validity": check["validity"],
        }
    sample_comparisons = [
        {
            "id": item["payload"]["comparison"]["id"],
            "display_code": item["payload"]["comparison"]["display_code"],
            "revision": item["payload"]["comparison"]["revision"],
            "status": item["payload"]["comparison"]["status"],
            "delivery_display_code": item["delivery_display_code"],
        }
        for item in snapshot["sample_comparisons"]
    ]
    coordination_runs = []
    for topic in snapshot["coordination"]["topics"]:
        latest = topic.get("latest_metrics")
        if latest is None:
            continue
        coordination_runs.append(
            {
                "id": latest["id"],
                "topic_id": topic["id"],
                "topic_display_code": topic["display_code"],
                "run_no": latest["run_no"],
                "risk_level": latest["risk"]["risk_level"],
                "accepted": _is_accepted(topic, latest["id"]),
            }
        )
    return {
        "requirements": requirements,
        "source_documents": snapshot["source_documents"],
        "test_plan": test_plan,
        "test_cases": test_cases,
        "design_review": design_review,
        "dfmea": dfmea,
        "sample_comparisons": sample_comparisons,
        "consistency_check": consistency,
        "conflicts": [
            {
                "id": item["id"],
                "display_code": item["display_code"],
                "revision": item["revision"],
                "severity": item["severity"],
                "status": item["status"],
            }
            for item in snapshot["conflicts"]
        ],
        "coordination_metric_runs": coordination_runs,
    }


def _build_manifest(
    snapshot: dict[str, Any],
    *,
    files: dict[str, bytes],
    descriptions: dict[str, str],
    media_types: dict[str, str],
    snapshot_hash: str,
) -> dict[str, Any]:
    file_entries = [
        {
            "path": path,
            "sha256": _sha256(files[path]),
            "size_bytes": len(files[path]),
            "media_type": media_types[path],
            "description": descriptions[path],
        }
        for path in sorted(files)
    ]
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "source_label": PACKAGE_SOURCE_LABEL,
        "mode": "rule",
        "timezone": "UTC",
        "generated_at": snapshot["generated_at"],
        "package": {
            **snapshot["package"],
            "snapshot_hash": snapshot_hash,
        },
        "project": snapshot["project"],
        "object_versions": _object_versions(snapshot),
        "gate": snapshot["gate"],
        "files": file_entries,
        "limitations": [
            "本地单用户演示材料，不代表真实工程或企业认证。",
            "规则/模拟/人工模式逐项保留；不接入真实台架、OCR、视觉模型或生产系统。",
            "原件仅在显式选择 include_originals=true 时纳入。",
            "JSON 备份不等同于本 O13 材料包。",
        ],
    }


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=(2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, files[path])
    return buffer.getvalue()


def _allocate_package(
    connection: sqlite3.Connection, project_row: sqlite3.Row
) -> tuple[int, str]:
    package_no = services._next_sequence(
        connection, f"material_package:{project_row['id']}"
    )
    return (
        package_no,
        f"MP-{project_row['display_code']}-{package_no:03d}",
    )


def create_material_package(
    connection: sqlite3.Connection,
    project_id: str,
    payload: MaterialPackageCreate,
) -> dict[str, Any]:
    with transaction(connection):
        project_row = _project_row(connection, project_id)
        package_no, display_code = _allocate_package(connection, project_row)
        package_id = str(uuid.uuid4())
        now = utc_now()
        snapshot = _snapshot_data(
            connection,
            project_id=project_id,
            package_id=package_id,
            display_code=display_code,
            package_no=package_no,
            include_originals=payload.include_originals,
            now=now,
        )
        gate = evaluate_package_gate(_gate_inputs(snapshot)).to_dict()
        status = "ready_to_submit" if gate["status"] == "ready" else "draft"
        snapshot["gate"] = gate
        snapshot["package"]["status"] = status
        snapshot_json = _json_text(snapshot)
        snapshot_hash = _sha256(snapshot_json.encode("utf-8"))
        files, descriptions, media_types = _build_content_files(snapshot, snapshot_hash)
        manifest = _build_manifest(
            snapshot,
            files=files,
            descriptions=descriptions,
            media_types=media_types,
            snapshot_hash=snapshot_hash,
        )
        manifest_bytes = _json_text(manifest).encode("utf-8")
        files["manifest.json"] = manifest_bytes
        descriptions["manifest.json"] = "材料包清单、对象版本、门禁与文件哈希"
        media_types["manifest.json"] = "application/json; charset=utf-8"
        manifest_json = _json_text(manifest)
        zip_content = _zip_bytes(files)
        if len(zip_content) > MAX_PACKAGE_BYTES:
            raise DomainValidationError(
                "材料包超过 32 MiB 上限",
                {
                    "size_bytes": len(zip_content),
                    "max_size_bytes": MAX_PACKAGE_BYTES,
                },
            )
        zip_hash = _sha256(zip_content)
        connection.execute(
            """
            INSERT INTO material_packages(
                id, project_id, display_code, package_no, status, mode,
                include_originals, snapshot_hash, snapshot_json,
                manifest_json, gate_json, zip_content, zip_hash, zip_size,
                created_by, created_at, frozen_at
            ) VALUES (?, ?, ?, ?, ?, 'rule', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                package_id,
                project_id,
                display_code,
                package_no,
                status,
                1 if payload.include_originals else 0,
                snapshot_hash,
                snapshot_json,
                manifest_json,
                _json_text(gate),
                zip_content,
                zip_hash,
                len(zip_content),
                payload.actor or PACKAGE_CREATED_BY_DEFAULT,
                now,
            ),
        )
        services._audit(
            connection,
            project_id=project_id,
            object_type="material_package",
            object_id=package_id,
            object_revision=package_no,
            action="material_package.generated",
            actor=payload.actor or PACKAGE_CREATED_BY_DEFAULT,
            role=PACKAGE_DEMO_ROLE,
            after={
                "display_code": display_code,
                "status": status,
                "snapshot_hash": snapshot_hash,
                "zip_hash": zip_hash,
                "include_originals": payload.include_originals,
                "blocker_count": len(gate["blockers"]),
            },
        )
        return _package_detail(connection, package_id)


def _package_row(connection: sqlite3.Connection, package_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM material_packages WHERE id = ?", (package_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("材料包不存在", {"package_id": package_id})
    return row


def _approval_row(
    connection: sqlite3.Connection, package_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM material_package_approvals
        WHERE package_id = ?
        """,
        (package_id,),
    ).fetchone()


def _package_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "requires_regeneration": _parse_json(row["snapshot_json"], {}).get(
            "schema_version"
        )
        != PACKAGE_SCHEMA_VERSION,
        "id": row["id"],
        "project_id": row["project_id"],
        "display_code": row["display_code"],
        "package_no": row["package_no"],
        "status": row["status"],
        "mode": row["mode"],
        "include_originals": bool(row["include_originals"]),
        "snapshot_hash": row["snapshot_hash"],
        "zip_sha256": row["zip_hash"],
        "zip_size": row["zip_size"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "frozen_at": row["frozen_at"],
        "gate": _parse_json(row["gate_json"], {}),
    }


def _package_detail(connection: sqlite3.Connection, package_id: str) -> dict[str, Any]:
    row = _package_row(connection, package_id)
    data = _package_summary(row)
    data["snapshot"] = _parse_json(row["snapshot_json"], {})
    data["manifest"] = _parse_json(row["manifest_json"], {})
    approval = _approval_row(connection, package_id)
    data["approval"] = dict(approval) if approval is not None else None
    return data


def list_material_packages(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM material_packages
        WHERE project_id = ?
        ORDER BY package_no DESC
        """,
        (project_id,),
    ).fetchall()
    return [_package_summary(row) for row in rows]


def get_material_package(
    connection: sqlite3.Connection, package_id: str
) -> dict[str, Any]:
    return _package_detail(connection, package_id)


def get_material_package_archive(
    connection: sqlite3.Connection, package_id: str
) -> sqlite3.Row:
    return _package_row(connection, package_id)


def approve_material_package(
    connection: sqlite3.Connection,
    package_id: str,
    payload: MaterialPackageApprovalCreate,
) -> dict[str, Any]:
    with transaction(connection):
        row = _package_row(connection, package_id)
        if (
            _parse_json(row["snapshot_json"], {}).get("schema_version")
            != PACKAGE_SCHEMA_VERSION
        ):
            raise DomainValidationError(
                "该材料包使用旧版门禁，请核对当前工程决策并重新生成材料包"
            )
        if row["status"] == "human_approved":
            raise MaterialPackageStateError(
                "材料包已完成人工审批，不能重复审批",
                {"package_id": package_id},
            )
        if row["status"] != "ready_to_submit":
            raise DomainValidationError(
                "材料包未满足门禁，不能人工审批",
                {
                    "package_id": package_id,
                    "status": row["status"],
                    "blocker_count": len(
                        _parse_json(row["gate_json"], {}).get("blockers", [])
                    ),
                },
            )
        if payload.expected_snapshot_hash != row["snapshot_hash"]:
            raise VersionConflictError(
                "材料包快照与审批时观察到的不一致",
                {
                    "expected_snapshot_hash": payload.expected_snapshot_hash,
                    "current_snapshot_hash": row["snapshot_hash"],
                },
            )
        duplicate = _approval_row(connection, package_id)
        if duplicate is not None:
            raise MaterialPackageStateError(
                "材料包已有人工审批记录",
                {"package_id": package_id},
            )
        approval_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO material_package_approvals(
                id, package_id, actor, role, decision, comment,
                snapshot_hash, zip_hash, created_at
            ) VALUES (?, ?, ?, ?, 'approved', ?, ?, ?, ?)
            """,
            (
                approval_id,
                package_id,
                payload.actor,
                payload.role,
                payload.comment,
                row["snapshot_hash"],
                row["zip_hash"],
                now,
            ),
        )
        connection.execute(
            """
            UPDATE material_packages
            SET status = 'human_approved', frozen_at = ?
            WHERE id = ?
            """,
            (now, package_id),
        )
        services._audit(
            connection,
            project_id=row["project_id"],
            object_type="material_package",
            object_id=package_id,
            object_revision=row["package_no"],
            action="material_package.approved",
            actor=payload.actor,
            role=payload.role,
            decision="approved",
            comment=payload.comment,
            before={"status": "ready_to_submit"},
            after={
                "status": "human_approved",
                "snapshot_hash": row["snapshot_hash"],
                "zip_hash": row["zip_hash"],
                "frozen_at": now,
            },
        )
        return _package_detail(connection, package_id)
