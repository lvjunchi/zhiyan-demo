"""Read-only project overview aggregation.

The overview exposes authoritative counts and statuses from persisted
state. It does not evaluate new pass/fail rules and does not write data.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from . import (
    consistency_services,
    coordination_services,
    design_services,
    package_services,
    services,
    testing_services,
)
from .errors import NotFoundError

_SEVERITIES = ("blocking", "high", "medium", "low")


def _requirements_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT review_status, validity, COUNT(*) AS row_count
        FROM requirements
        WHERE project_id = ?
        GROUP BY review_status, validity
        """,
        (project_id,),
    ).fetchall()
    summary = {
        "total": 0,
        "confirmed": 0,
        "draft": 0,
        "pending_review": 0,
        "rejected": 0,
        "stale": 0,
    }
    for row in rows:
        count = int(row["row_count"])
        summary["total"] += count
        if row["validity"] == "stale":
            summary["stale"] += count
        status = row["review_status"]
        if status in summary:
            summary[status] += count
    return summary


def _issues_summary(connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT status, severity, COUNT(*) AS row_count
        FROM issues
        WHERE project_id = ?
        GROUP BY status, severity
        """,
        (project_id,),
    ).fetchall()
    open_by_severity = {severity: 0 for severity in _SEVERITIES}
    summary: dict[str, Any] = {
        "open": 0,
        "closed": 0,
        "open_by_severity": open_by_severity,
    }
    for row in rows:
        count = int(row["row_count"])
        status = row["status"]
        if status in ("open", "closed"):
            summary[status] += count
        if status == "open" and row["severity"] in open_by_severity:
            open_by_severity[row["severity"]] += count
    return summary


def _traceability_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any] | None:
    has_plan = connection.execute(
        "SELECT 1 FROM test_plans WHERE project_id = ? LIMIT 1",
        (project_id,),
    ).fetchone()
    if has_plan is None:
        return None
    matrix = testing_services.get_traceability_matrix(connection, project_id)
    return {
        "mode": matrix["mode"],
        "scope_label": matrix["scope_label"],
        "denominator": matrix["denominator"],
        "covered_count": matrix["covered_count"],
        "coverage_percentage": matrix["coverage_percentage"],
        "execution_summary": matrix["execution_summary"],
    }


def _design_review_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any] | None:
    try:
        payload = design_services.get_design_review(connection, project_id)
    except NotFoundError:
        return None
    review = payload["review"]
    return {
        "display_code": review["display_code"],
        "status": review["status"],
        "revision": review["revision"],
        "item_count": len(payload["items"]),
        "missing_inputs": payload["missing_inputs"],
        "needs_reconfirmation": payload["needs_reconfirmation"],
        "mode": payload["mode"],
    }


def _dfmea_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any] | None:
    try:
        payload = design_services.get_dfmea(connection, project_id)
    except NotFoundError:
        return None
    fmea = payload["fmea"]
    return {
        "display_code": fmea["display_code"],
        "status": fmea["status"],
        "revision": fmea["revision"],
        "item_count": len(payload["items"]),
        "pending_score_count": sum(
            1 for item in payload["items"] if not item["scores_confirmed"]
        ),
        "missing_inputs": payload["missing_inputs"],
        "needs_reconfirmation": payload["needs_reconfirmation"],
        "mode": payload["mode"],
    }


def _consistency_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any] | None:
    try:
        payload = consistency_services.get_latest_consistency_check(
            connection, project_id
        )
    except NotFoundError:
        return None
    check = payload["check"]
    conflicts = consistency_services.list_conflicts(connection, project_id)
    open_conflicts = [item for item in conflicts if item["status"] == "open"]
    return {
        "check": {
            "display_code": check["display_code"],
            "status": check["status"],
            "validity": check["validity"],
            "revision": check["revision"],
            "summary": check["summary"],
        },
        "open_conflicts": len(open_conflicts),
        "blocking_open": sum(1 for item in open_conflicts if item["blocking"]),
        "review_pending": sum(1 for item in open_conflicts if item["review_pending"]),
    }


def _coordination_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    overview = coordination_services.get_coordination_overview(connection, project_id)
    high_risk_topics = 0
    for topic in overview["topics"]:
        latest = topic["latest_metrics"]
        if latest is None or latest["validity"] != "current":
            continue
        if latest["risk"]["risk_level"] == "high":
            high_risk_topics += 1
    return {
        "topic_count": overview["topic_count"],
        "record_count": overview["record_count"],
        "metrics_available": overview["metrics_available"],
        "highest_risk": overview["highest_risk"],
        "high_risk_topics": high_risk_topics,
        "rule_label": overview["rule_label"],
        "source_label": overview["source_label"],
    }


def _spectrum_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, int]:
    variant_row = connection.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'current' THEN 1 ELSE 0 END) AS current,
            SUM(CASE WHEN status = 'stale' THEN 1 ELSE 0 END) AS stale
        FROM variant_points
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    part_row = connection.execute(
        """
        SELECT COUNT(*) AS current
        FROM reusable_part_decisions
        WHERE project_id = ? AND status = 'current'
        """,
        (project_id,),
    ).fetchone()
    return {
        "variant_points": int(variant_row["current"] or 0),
        "stale_variant_points": int(variant_row["stale"] or 0),
        "reusable_parts": int(part_row["current"] or 0),
    }


def _samples_summary(connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    delivery_row = connection.execute(
        "SELECT COUNT(*) AS row_count FROM sample_deliveries WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    comparison_row = connection.execute(
        """
        SELECT COUNT(*) AS row_count
        FROM sample_comparisons
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()
    latest = connection.execute(
        """
        SELECT status, overall_result
        FROM sample_comparisons
        WHERE project_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    return {
        "delivery_count": int(delivery_row["row_count"]),
        "comparison_count": int(comparison_row["row_count"]),
        "latest_status": latest["status"] if latest is not None else None,
        "latest_result": (latest["overall_result"] if latest is not None else None),
    }


def _package_summary(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any] | None:
    packages = package_services.list_material_packages(connection, project_id)
    if not packages:
        return None
    latest = packages[0]
    gate_summary = latest["gate"]["summary"]
    return {
        "requires_regeneration": latest["requires_regeneration"],
        "id": latest["id"],
        "display_code": latest["display_code"],
        "status": latest["status"],
        "blocker_count": gate_summary["blocker_count"],
        "warning_count": gate_summary["warning_count"],
        "snapshot_hash": latest["snapshot_hash"],
        "created_at": latest["created_at"],
        "frozen_at": latest["frozen_at"],
    }


def get_project_overview(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    project = services.get_project(connection, project_id)
    return {
        "project": {
            "id": project["id"],
            "display_code": project["display_code"],
            "name": project["name"],
            "customer": project["customer"],
            "product": project["product"],
            "stage": project["stage"],
            "updated_at": project["updated_at"],
        },
        "requirements": _requirements_summary(connection, project_id),
        "issues": _issues_summary(connection, project_id),
        "spectrum": _spectrum_summary(connection, project_id),
        "design_review": _design_review_summary(connection, project_id),
        "dfmea": _dfmea_summary(connection, project_id),
        "traceability": _traceability_summary(connection, project_id),
        "samples": _samples_summary(connection, project_id),
        "consistency": _consistency_summary(connection, project_id),
        "coordination": _coordination_summary(connection, project_id),
        "package": _package_summary(connection, project_id),
        "cockpit": _cockpit_details(connection, project_id),
    }


def _cockpit_details(connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    """Presentation data only; reuse existing domain conclusions verbatim."""
    parameters = connection.execute(
        """
        SELECT id AS requirement_id, parser_key AS key, display_code,
               parameter_name AS label, operator, value_text, unit,
               current_revision AS revision, review_status, validity
        FROM requirements WHERE project_id = ?
        ORDER BY display_code, id
        """,
        (project_id,),
    ).fetchall()
    has_plan = connection.execute(
        "SELECT 1 FROM test_plans WHERE project_id = ?", (project_id,)
    ).fetchone()
    matrix = (
        testing_services.get_traceability_matrix(connection, project_id)
        if has_plan
        else None
    )
    resources = {
        "source_documents": connection.execute(
            "SELECT COUNT(*) FROM source_documents WHERE project_id = ?", (project_id,)
        ).fetchone()[0],
        "product_bases": connection.execute(
            "SELECT COUNT(*) FROM product_bases"
        ).fetchone()[0],
        "history_projects": connection.execute(
            "SELECT COUNT(*) FROM history_projects"
        ).fetchone()[0],
    }
    topics = coordination_services.list_coordination_topics(connection, project_id)
    risk_topics = []
    for topic in topics:
        latest = topic["latest_metrics"]
        if latest is not None and latest["validity"] != "current":
            latest = None
        metrics = latest["metrics"] if latest else {}
        risk = latest["risk"] if latest else {}
        risk_topics.append(
            {
                "id": topic["id"],
                "name": topic["name"],
                "mode": latest["mode"] if latest else topic["mode"],
                "created_at": latest["created_at"] if latest else topic["created_at"],
                "risk_level": risk.get("risk_level", "insufficient"),
                "reasons": risk.get("reasons", []),
                "average_response_hours": metrics.get("average_response_hours"),
                "iteration_count": metrics.get("iteration_count"),
                "absence_rate": metrics.get("absence_rate"),
                "response_latencies_hours": metrics.get("response_latencies_hours", []),
                "window_start": topic["window_start"],
                "window_end": topic["window_end"],
                "headline": _risk_headline(latest),
                "source_label": latest["source_label"] if latest else None,
                "rule_label": latest["rule_label"] if latest else None,
                "progress": topic["progress"],
                "records": topic["records"],
                "expected_participants": topic["expected_participants"],
                "rule_conditions": risk.get("conditions", []),
                "metric_details": {
                    key: metrics.get(key)
                    for key in (
                        "response_sample_size",
                        "expected_participants",
                        "actual_participants",
                        "absent_participants",
                        "data_gaps",
                    )
                },
            }
        )
    events = connection.execute(
        """SELECT id, project_id, object_type, object_id, object_revision,
                  action, actor, created_at
           FROM audit_events WHERE project_id = ?
           ORDER BY created_at DESC, id DESC LIMIT 30""",
        (project_id,),
    ).fetchall()
    return {
        "parameters": [dict(row) for row in parameters],
        "traceability_items": (
            _trace_links(connection, project_id, matrix["items"]) if matrix else []
        ),
        "resources": resources,
        "risk_topics": risk_topics,
        "recent_activity": [dict(row) for row in events],
    }


def _trace_links(
    connection: sqlite3.Connection, project_id: str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach explicit persisted links; never infer design links from names or scores.

    Retain old referenced revisions, review status and domain-computed validity.
    A linked review item is an engineering review checkpoint, not a CAD design.
    """
    cases = testing_services.get_test_plan(connection, project_id)["cases"]
    try:
        review = design_services.get_design_review(connection, project_id)
    except NotFoundError:
        review = None
    enriched = []
    for item in items:
        requirement_id = item["requirement_id"]
        design_items = []
        if review is not None:
            for checkpoint in review["items"]:
                for dependency in checkpoint["dependencies"]:
                    if (
                        dependency.get("object_type") == "requirement"
                        and dependency.get("object_id") == requirement_id
                    ):
                        design_items.append(
                            {
                                "id": checkpoint["item_id"],
                                "display_code": checkpoint["display_code"],
                                "check_point": checkpoint["check_point"],
                                "standard_basis": checkpoint["standard_basis"],
                                "revision": review["review"]["revision"],
                                "requirement_revision": dependency["revision"],
                                "status": review["review"]["status"],
                                "validity": review["review"]["validity"],
                            }
                        )
        enriched.append(
            {
                **item,
                "design_items": design_items,
                "test_cases": [
                    case
                    for case in cases
                    if any(
                        reference["requirement_id"] == requirement_id
                        for reference in case["requirement_refs"]
                    )
                ],
            }
        )
    return enriched


def _risk_headline(latest: dict[str, Any] | None) -> str | None:
    """Summarize an existing current finding; do not classify risk again."""
    if latest is None:
        return None
    risk = latest["risk"]
    alerts = risk.get("progress_risk", {}).get("alerts", [])
    lag_rows = [
        row
        for row in latest["inputs"].get("progress", [])
        if any(
            alert["kind"] == "schedule_lag"
            and alert["milestone"] == row["milestone"]
            and row["participant"] in alert["participants"]
            for alert in alerts
        )
    ]
    if lag_rows:
        lag = max(row["planned_percent"] - row["actual_percent"] for row in lag_rows)
        return f"最大进度落后 {lag:g} 个百分点"
    return risk["reasons"][0] if risk.get("reasons") else None
