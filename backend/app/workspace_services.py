"""Read-only work navigation and persisted dependency evidence, never a gate."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import overview_services, services

# Only these controlled tables/columns are interpolated into SQL.
RECORDS = (
    (
        "requirement",
        "requirements",
        "requirements",
        "current_revision",
        "review_status",
        "validity",
        "display_code",
    ),
    (
        "variant",
        "variant_points",
        "bases",
        "revision",
        "review_status",
        "status",
        "display_code",
    ),
    (
        "part",
        "reusable_part_decisions",
        "bases",
        "revision",
        "review_status",
        "status",
        "part_display_code",
    ),
    (
        "design_review",
        "design_reviews",
        "design",
        "revision",
        "status",
        "validity",
        "display_code",
    ),
    (
        "fmea_document",
        "fmea_documents",
        "design",
        "revision",
        "status",
        "validity",
        "display_code",
    ),
    (
        "test_case",
        "test_cases",
        "testing",
        "revision",
        "review_status",
        "validity",
        "display_code",
    ),
    (
        "consistency_check",
        "consistency_checks",
        "consistency",
        "revision",
        "status",
        "validity",
        "display_code",
    ),
)
STAGES = (
    ("parsing", "协议解析与澄清", "导入协议，核对解析草案并处理开放问题"),
    ("requirements", "需求确认", "核对来源与版本，确认当前需求"),
    ("bases", "型谱与变型", "计算选型、分析差异并复核工程决策"),
    ("design", "设计成果", "生成并分别确认设计评审与 DFMEA"),
    ("testing", "试验验证", "补齐用例条件、确认并记录当前版本执行"),
    ("samples", "样件检验", "登记样件、比对参数并审核证据"),
    ("consistency", "一致性检测", "重新检测当前版本，复核并处置冲突"),
    ("coordination", "协同风险", "计算协同指标，查看依据并记录处置"),
    ("packages", "评审材料", "生成当前材料快照并逐项处理门禁阻断"),
)


def _records(
    connection: sqlite3.Connection, project_id: str
) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for kind, table, tab, rev, review, validity, code in RECORDS:
        for row in connection.execute(
            f"SELECT * FROM {table} WHERE project_id=? ORDER BY id", (project_id,)
        ):
            item = dict(row)
            result[(kind, row["id"])] = {
                "object_type": kind,
                "object_id": row["id"],
                "display_code": row[code],
                "revision": row[rev],
                "review_status": row[review],
                "validity": row[validity],
                "tab": tab,
                "applicable": bool(item.get("is_applicable", 1)),
                "raw": item,
            }
    return result


def _stages(
    connection: sqlite3.Connection, project_id: str, records: dict, overview: dict
) -> list[dict[str, Any]]:
    result = []
    for key, label, action in STAGES:
        items = [r for r in records.values() if r["tab"] == key and r["applicable"]]
        # Only the latest consistency report is actionable; old reports are history.
        if key == "consistency" and items:
            items = [max(items, key=lambda r: r["raw"]["check_no"])]
        total = len(items)
        pending = sum(r["review_status"] != "confirmed" for r in items)
        stale = sum(r["validity"] == "stale" for r in items)
        notes = []
        if key == "parsing":
            total = connection.execute(
                "SELECT COUNT(*) FROM source_documents WHERE project_id=?",
                (project_id,),
            ).fetchone()[0]
            pending = overview["issues"]["open"]
            notes.append(f"{pending} 项开放问题")
        elif key == "design":
            pending += max(0, 2 - total)
        elif key == "testing":
            matrix = overview["traceability"]
            if matrix:
                notes.append(
                    f"有效覆盖 {matrix['covered_count']}/{matrix['denominator']}；执行通过 {matrix['execution_summary'].get('pass', 0)} 条"
                )
                pending += matrix["denominator"] - matrix["covered_count"]
                pending += matrix["denominator"] - matrix["execution_summary"].get(
                    "pass", 0
                )
        elif key == "samples":
            rows = connection.execute(
                "SELECT status,overall_result FROM sample_comparisons WHERE project_id=?",
                (project_id,),
            ).fetchall()
            total = len(rows)
            pending = sum(
                r["status"] != "confirmed" or r["overall_result"] != "pass"
                for r in rows
            )
        elif key == "consistency" and overview["consistency"]:
            pending += overview["consistency"]["open_conflicts"]
            notes.append(f"{overview['consistency']['open_conflicts']} 项开放冲突")
        elif key == "coordination":
            summary = overview["coordination"]
            total = summary["topic_count"]
            pending = total - summary["metrics_available"]
            notes.append(
                f"{summary['high_risk_topics']} 个高风险议题；风险不代表产品不合格"
            )
        elif key == "packages":
            package = overview["package"]
            total = int(package is not None)
            pending = int(
                package is not None
                and (
                    package["requires_regeneration"]
                    or package["status"] != "human_approved"
                )
            )
            notes.append("快照门禁以生成时状态为准，请重新生成以检查当前数据")
        result.append(
            {
                "key": key,
                "label": label,
                "action": action,
                "record_count": total,
                "pending_count": pending,
                "stale_count": stale,
                "state": (
                    "empty"
                    if not total
                    else "attention" if pending or stale else "reviewed"
                ),
                "notes": notes,
            }
        )
    return result


def _edges(
    connection: sqlite3.Connection, project_id: str, records: dict
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []

    def add(
        kind: str, source: str, revision: int, target: tuple[str, str], evidence: str
    ) -> None:
        upstream = records.get((kind, source))
        if upstream is None or target not in records:
            return  # Never expose a dangling or other-project reference as a live object.
        edge = {
            "upstream_type": kind,
            "upstream_id": source,
            "upstream_display_code": upstream["display_code"],
            "referenced_revision": revision,
            "current_revision": upstream["revision"],
            "downstream_type": target[0],
            "downstream_id": target[1],
            "evidence": evidence,
        }
        if edge not in edges:
            edges.append(edge)

    for row in connection.execute(
        "SELECT * FROM object_dependencies WHERE project_id=? ORDER BY id",
        (project_id,),
    ):
        target = (row["downstream_type"], row["downstream_id"])
        if (
            target in records
            and records[target]["revision"] == row["downstream_revision"]
        ):
            add(
                row["upstream_type"],
                row["upstream_id"],
                row["upstream_revision"],
                target,
                "持久化对象依赖",
            )
    for target, node in records.items():
        row = node["raw"]
        if target[0] in ("variant", "part"):
            for ref in json.loads(row["dependency_versions"]):
                add(
                    ref["object_type"],
                    ref["object_id"],
                    ref["revision"],
                    target,
                    "工程决策版本引用",
                )
        elif target[0] in ("design_review", "fmea_document"):
            snapshot = json.loads(row["inputs_snapshot"])
            for ref in snapshot.get("requirements", []):
                add(
                    "requirement",
                    ref["requirement_id"],
                    ref["revision"],
                    target,
                    "设计输入快照",
                )
        elif target[0] == "test_case":
            for ref in json.loads(row["requirement_refs"]):
                add(
                    "requirement",
                    ref["requirement_id"],
                    ref["revision"],
                    target,
                    "用例需求版本引用",
                )
    return edges


def get_workspace(connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    services.get_project(connection, project_id)
    overview = overview_services.get_project_overview(connection, project_id)
    records = _records(connection, project_id)
    edges = _edges(connection, project_id, records)
    changes = []
    for (kind, object_id), node in records.items():
        if kind != "requirement" or node["revision"] <= 1:
            continue
        versions = connection.execute(
            "SELECT revision_no,snapshot_json,created_at FROM requirement_revisions WHERE requirement_id=? ORDER BY revision_no DESC LIMIT 2",
            (object_id,),
        ).fetchall()
        if len(versions) != 2:
            continue
        reached = {("requirement", object_id)}
        while True:
            following = {
                (e["downstream_type"], e["downstream_id"])
                for e in edges
                if (e["upstream_type"], e["upstream_id"]) in reached
            }
            if following <= reached:
                break
            reached |= following
        impacts = []
        for target in sorted(reached - {("requirement", object_id)}):
            item = {
                key: value for key, value in records[target].items() if key != "raw"
            }
            item["references"] = [
                e
                for e in edges
                if (e["downstream_type"], e["downstream_id"]) == target
                and (e["upstream_type"], e["upstream_id"]) in reached
            ]
            impacts.append(item)
        changes.append(
            {
                "requirement_id": object_id,
                "display_code": node["display_code"],
                "parameter_name": node["raw"]["parameter_name"],
                "from_revision": versions[1]["revision_no"],
                "to_revision": versions[0]["revision_no"],
                "before": json.loads(versions[1]["snapshot_json"]),
                "after": json.loads(versions[0]["snapshot_json"]),
                "created_at": versions[0]["created_at"],
                "impacts": impacts,
            }
        )
    changes.sort(key=lambda c: (c["created_at"], c["requirement_id"]), reverse=True)
    return {
        "project_id": project_id,
        "stages": _stages(connection, project_id, records, overview),
        "changes": changes,
        "scope_note": "展示当前对象已保存的需求、工程决策、设计输入及用例引用；不推断未记录依赖。旧执行和材料包保留历史，当前门禁须重新生成检查。",
    }
