"""Read-only business progress, always computed from persisted revisions and results."""

from __future__ import annotations
import json
import sqlite3
from . import services, testing_services, sample_services, engineering_versions
from .errors import NotFoundError


def summary(connection: sqlite3.Connection, project_id: str) -> dict[str, object]:
    services._get_project_row(connection, project_id)
    try:
        plan = testing_services.get_test_plan(connection, project_id)
    except NotFoundError:
        plan = None
    cases = plan["cases"] if plan else []
    review = {
        key: sum(row["review_status"] == key for row in cases)
        for key in ("draft", "pending_review", "confirmed", "rejected")
    }
    execution = {key: 0 for key in ("not_run", "pass", "fail", "incomplete", "invalid")}
    case_states = []
    for row in cases:
        runs = [
            run
            for run in row["runs"]
            if run["case_revision"] == row["revision"] and row["validity"] == "current"
        ]
        latest = runs[-1] if runs else None
        state = (
            latest["result"]
            if latest and latest["status"] == "completed"
            else "not_run"
        )
        execution[state] += 1
        case_states.append(
            {
                "id": row["id"],
                "revision": row["revision"],
                "execution": state,
                "review_status": row["review_status"],
                "validity": row["validity"],
                "historical_runs": len(row["runs"]) - len(runs),
            }
        )
    deliveries = sample_services.list_sample_deliveries(connection, project_id)
    samples = []
    changes = []
    for row in deliveries:
        try:
            payload = sample_services.get_sample_comparison(connection, row["id"])
        except NotFoundError:
            payload = None
        comparison = payload["comparison"] if payload else None
        issues = payload["issues"] if payload else []
        steps = [
            {"label": "样件登记", "done": True},
            {
                "label": "图纸基准",
                "done": bool(row["file_uploaded"] and row["drawing_parameters"]),
            },
            {"label": "实测比对", "done": comparison is not None},
            {
                "label": "问题处置",
                "done": comparison is not None
                and not any(issue["status"] == "open" for issue in issues),
            },
            {
                "label": "审核确认",
                "done": comparison is not None and comparison["status"] == "confirmed",
            },
        ]
        samples.append(
            {
                "id": row["id"],
                "display_code": row["display_code"],
                "steps": steps,
                "current_step": next(
                    (index for index, step in enumerate(steps) if not step["done"]),
                    len(steps),
                ),
                "result": comparison["overall_result"] if comparison else "not_run",
                "review_status": comparison["status"] if comparison else "not_started",
                "open_issues": sum(issue["status"] == "open" for issue in issues),
            }
        )
        if comparison:
            for finding in comparison["findings"]:
                changes.append(
                    {
                        "id": f"sample:{row['id']}:{finding['parameter_key']}",
                        "label": row["display_code"],
                        "kind": "图纸与实测",
                        "parameter": finding["parameter_name"],
                        "before": str(
                            finding.get("expected_value")
                            if finding.get("expected_value") is not None
                            else "未提供"
                        ),
                        "after": str(
                            finding.get("measured_value")
                            if finding.get("measured_value") is not None
                            else "未提供"
                        ),
                        "unit": finding["unit"],
                        "versions": f"图纸{row['drawing_revision']} / 比对V{comparison['revision']}",
                        "state": finding["result"],
                        "evidence": finding["reason"],
                    }
                )
    for row in connection.execute(
        "SELECT * FROM requirements WHERE project_id=? ORDER BY display_code",
        (project_id,),
    ):
        revisions = connection.execute(
            "SELECT snapshot_json FROM requirement_revisions WHERE requirement_id=? ORDER BY revision_no DESC LIMIT 2",
            (row["id"],),
        ).fetchall()
        if len(revisions) < 2:
            continue
        latest, previous = [json.loads(item["snapshot_json"]) for item in revisions]
        changes.append(
            {
                "id": f"requirement:{row['id']}",
                "label": row["display_code"],
                "kind": "需求修订",
                "parameter": row["parameter_name"],
                "before": previous["value_text"],
                "after": latest["value_text"],
                "unit": row["unit"],
                "versions": f"V{row['current_revision']-1} → V{row['current_revision']}",
                "state": "changed",
                "evidence": row["source_excerpt"],
            }
        )
    for row in engineering_versions.list_records(connection, project_id):
        if row["kind"] != "part" or not row["is_applicable"]:
            continue
        versions = engineering_versions.detail(connection, "part", row["id"])[
            "versions"
        ]
        previous = versions[-2]["snapshot"] if len(versions) > 1 else None
        if (previous and previous["part_number"] != row["part_number"]) or (
            not previous and row["classification"] == "new_design"
        ):
            changes.append(
                {
                    "id": f"part:{row['id']}",
                    "label": row["part_display_code"],
                    "kind": "型号变更" if previous else "新增零件",
                    "parameter": row["part_name"],
                    "before": previous["part_number"] if previous else "无基型件",
                    "after": row["part_number"],
                    "unit": "",
                    "versions": f"{row['base_display_code']} / V{row['revision']}",
                    "state": "changed",
                    "evidence": row["reason"],
                }
            )
    return {
        "testing": {
            "total": len(cases),
            "review": review,
            "stale": sum(row["validity"] == "stale" for row in cases),
            "valid_coverage_cases": sum(row["coverage_valid"] for row in cases),
            "execution": execution,
            "cases": case_states,
            "plan_status": plan["plan"]["status"] if plan else "not_started",
        },
        "samples": {
            "total": len(samples),
            "compared": sum(row["result"] != "not_run" for row in samples),
            "confirmed": sum(row["review_status"] == "confirmed" for row in samples),
            "rows": samples,
        },
        "consistency": {
            "scope": [
                "需求参数与派生关系",
                "工程零件及版本引用",
                "试验工况、当前加载与结果",
                "样件图纸基准与实测",
            ],
            "changes": changes,
        },
    }
