from __future__ import annotations

import json
import hashlib
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from . import coordination_progress
from .db import transaction, utc_now
from .domain.coordination import (
    RULE_LABEL,
    CoordinationRecord,
    CoordinationTopic,
    evaluate_coordination,
)
from .errors import (
    DomainValidationError,
    DuplicateDisplayCodeError,
    DuplicateRecordError,
    NotFoundError,
)
from .schemas import (
    CoordinationMetricRequest,
    CoordinationRecordCreate,
    CoordinationRiskAcceptanceCreate,
    CoordinationTopicCreate,
)
from .services import _audit, _next_sequence

TOPIC_SOURCE_LABEL = "协同记录（合成数据）"
RULE_SOURCE_LABEL = f"{RULE_LABEL}（演示规则）"

_RISK_ORDER = {"insufficient": 0, "low": 1, "medium": 2, "high": 3}


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


def _topic_row(connection: sqlite3.Connection, topic_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM coordination_topics WHERE id = ?", (topic_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("协同议题不存在", {"topic_id": topic_id})
    return row


def _topic_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["expected_participants"] = _parse_json(data["expected_participants"], [])
    data["mode"] = row["mode"]
    return data


def _record_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _records(connection: sqlite3.Connection, topic_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT * FROM coordination_records
        WHERE topic_id = ?
        ORDER BY sent_at ASC, created_at ASC, id ASC
        """,
        (topic_id,),
    ).fetchall()


def _latest_metric_row(
    connection: sqlite3.Connection, topic_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM coordination_metric_runs
        WHERE topic_id = ?
        ORDER BY run_no DESC
        LIMIT 1
        """,
        (topic_id,),
    ).fetchone()


def _record_inputs(records: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [
        {
            key: (
                datetime.fromisoformat(row[key]).isoformat()
                if key == "sent_at"
                else row[key]
            )
            for key in (
                "external_id",
                "record_type",
                "sender",
                "sent_at",
                "reply_to_external_id",
            )
        }
        for row in records
    ]


def _metric_run_dict(
    row: sqlite3.Row, connection: sqlite3.Connection
) -> dict[str, Any]:
    inputs = _parse_json(row["inputs_json"], {})
    topic = _topic_row(connection, row["topic_id"])
    topic_inputs = {
        "window_start": datetime.fromisoformat(topic["window_start"]).isoformat(),
        "window_end": datetime.fromisoformat(topic["window_end"]).isoformat(),
        "expected_participants": _parse_json(topic["expected_participants"], []),
    }
    current = (
        inputs.get("progress", [])
        == coordination_progress.inputs(connection, row["topic_id"])
        and inputs.get("topic") == topic_inputs
        and inputs.get("records")
        == _record_inputs(_records(connection, row["topic_id"]))
    )
    return {
        "validity": "current" if current else "stale",
        "inputs_sha256": hashlib.sha256(_json_text(inputs).encode("utf-8")).hexdigest(),
        "id": row["id"],
        "topic_id": row["topic_id"],
        "run_no": row["run_no"],
        "rule_label": row["rule_label"],
        "mode": "rule",
        "source_label": f"{row['rule_label']}（演示规则）",
        "inputs": inputs,
        "metrics": _parse_json(row["metrics_json"], {}),
        "risk": _parse_json(row["risk_json"], {}),
        "cost": _parse_json(row["cost_json"], {}),
        "created_at": row["created_at"],
    }


def _risk_acceptances(
    connection: sqlite3.Connection, topic_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT a.*, m.risk_json
        FROM coordination_risk_acceptances a
        JOIN coordination_metric_runs m ON m.id = a.metric_run_id
        WHERE a.topic_id = ?
        ORDER BY a.created_at ASC, a.id ASC
        """,
        (topic_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "topic_id": row["topic_id"],
            "metric_run_id": row["metric_run_id"],
            "risk_level": _parse_json(row["risk_json"], {}).get("risk_level"),
            "actor": row["actor"],
            "role": row["role"],
            "note": row["note"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _topic_detail(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    data = _topic_dict(row)
    records = _records(connection, row["id"])
    data["records"] = [_record_dict(record) for record in records]
    data["record_count"] = len(records)
    latest = _latest_metric_row(connection, row["id"])
    data["latest_metrics"] = (
        _metric_run_dict(latest, connection) if latest is not None else None
    )
    data["progress"] = coordination_progress.detail(connection, row["id"])
    data["risk_acceptances"] = _risk_acceptances(connection, row["id"])
    return data


def _allocate_topic_code(connection: sqlite3.Connection, project_id: str) -> str:
    while True:
        value = _next_sequence(connection, f"coordination_topic:{project_id}")
        code = f"CT-{value:02d}"
        exists = connection.execute(
            """
            SELECT 1 FROM coordination_topics
            WHERE project_id = ? AND display_code = ?
            """,
            (project_id, code),
        ).fetchone()
        if exists is None:
            return code


def create_coordination_topic(
    connection: sqlite3.Connection,
    project_id: str,
    payload: CoordinationTopicCreate,
) -> dict[str, Any]:
    with transaction(connection):
        _project_row(connection, project_id)
        display_code = payload.display_code
        if display_code is None:
            display_code = _allocate_topic_code(connection, project_id)
        else:
            exists = connection.execute(
                """
                SELECT 1 FROM coordination_topics
                WHERE project_id = ? AND display_code = ?
                """,
                (project_id, display_code),
            ).fetchone()
            if exists is not None:
                raise DuplicateDisplayCodeError(
                    "协同议题显示编号已存在",
                    {"display_code": display_code},
                )
        topic_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO coordination_topics(
                id, project_id, display_code, name,
                expected_participants, window_start, window_end,
                mode, source_label, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
            """,
            (
                topic_id,
                project_id,
                display_code,
                payload.name,
                _json_text(payload.expected_participants),
                payload.window_start.isoformat(),
                payload.window_end.isoformat(),
                TOPIC_SOURCE_LABEL,
                now,
            ),
        )
        row = _topic_row(connection, topic_id)
        _audit(
            connection,
            project_id=project_id,
            object_type="coordination_topic",
            object_id=topic_id,
            object_revision=None,
            action="coordination.topic.created",
            after=_topic_dict(row),
        )
        return _topic_detail(connection, row)


def list_coordination_topics(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, Any]]:
    _project_row(connection, project_id)
    rows = connection.execute(
        """
        SELECT * FROM coordination_topics
        WHERE project_id = ?
        ORDER BY created_at ASC, display_code ASC
        """,
        (project_id,),
    ).fetchall()
    return [_topic_detail(connection, row) for row in rows]


def get_coordination_topic(
    connection: sqlite3.Connection, topic_id: str
) -> dict[str, Any]:
    return _topic_detail(connection, _topic_row(connection, topic_id))


def _parse_aware(value: str) -> datetime:
    return datetime.fromisoformat(value)


def create_coordination_record(
    connection: sqlite3.Connection,
    topic_id: str,
    payload: CoordinationRecordCreate,
) -> dict[str, Any]:
    with transaction(connection):
        topic = _topic_row(connection, topic_id)
        window_start = _parse_aware(topic["window_start"])
        window_end = _parse_aware(topic["window_end"])
        if not (window_start <= payload.sent_at <= window_end):
            raise DomainValidationError(
                "记录时间不在协同议题统计窗口内",
                {
                    "sent_at": payload.sent_at.isoformat(),
                    "window_start": topic["window_start"],
                    "window_end": topic["window_end"],
                },
            )
        exists = connection.execute(
            """
            SELECT 1 FROM coordination_records
            WHERE topic_id = ? AND external_id = ?
            """,
            (topic_id, payload.external_id),
        ).fetchone()
        if exists is not None:
            raise DuplicateRecordError(
                "协同记录外部编号已存在",
                {
                    "topic_id": topic_id,
                    "external_id": payload.external_id,
                },
            )
        if payload.record_type == "reopened" and payload.reply_to_external_id:
            raise DomainValidationError(
                "reopened 事件不能作为响应关联请求",
                {"external_id": payload.external_id},
            )
        if payload.reply_to_external_id is not None:
            target = connection.execute(
                """
                SELECT * FROM coordination_records
                WHERE topic_id = ? AND external_id = ?
                """,
                (topic_id, payload.reply_to_external_id),
            ).fetchone()
            if target is None:
                raise DomainValidationError(
                    "reply_to_external_id 指向的记录不存在",
                    {"reply_to_external_id": payload.reply_to_external_id},
                )
            if target["record_type"] != "message":
                raise DomainValidationError(
                    "只能回复 message 类型的请求记录",
                    {"reply_to_external_id": payload.reply_to_external_id},
                )
            if _parse_aware(target["sent_at"]) > payload.sent_at:
                raise DomainValidationError(
                    "响应时间不能早于被回复请求",
                    {
                        "sent_at": payload.sent_at.isoformat(),
                        "request_sent_at": target["sent_at"],
                    },
                )

        record_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO coordination_records(
                id, topic_id, external_id, record_type, sender,
                content_summary, sent_at, reply_to_external_id,
                mode, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?)
            """,
            (
                record_id,
                topic_id,
                payload.external_id,
                payload.record_type,
                payload.sender,
                payload.content_summary,
                payload.sent_at.isoformat(),
                payload.reply_to_external_id,
                now,
            ),
        )
        _audit(
            connection,
            project_id=topic["project_id"],
            object_type="coordination_record",
            object_id=record_id,
            object_revision=None,
            action="coordination.record.created",
            after={
                "external_id": payload.external_id,
                "record_type": payload.record_type,
                "sender": payload.sender,
                "sent_at": payload.sent_at.isoformat(),
            },
        )
        return _topic_detail(connection, _topic_row(connection, topic_id))


def calculate_coordination_metrics(
    connection: sqlite3.Connection,
    topic_id: str,
    payload: CoordinationMetricRequest,
) -> dict[str, Any]:
    with transaction(connection):
        topic = _topic_row(connection, topic_id)
        records = _records(connection, topic_id)
        input_topic = CoordinationTopic(
            expected_participants=tuple(
                _parse_json(topic["expected_participants"], [])
            ),
            window_start=_parse_aware(topic["window_start"]),
            window_end=_parse_aware(topic["window_end"]),
        )
        input_records = tuple(
            CoordinationRecord(
                external_id=row["external_id"],
                record_type=row["record_type"],
                sender=row["sender"],
                sent_at=_parse_aware(row["sent_at"]),
                reply_to_external_id=row["reply_to_external_id"],
                content_summary=row["content_summary"],
            )
            for row in records
        )
        evaluation = evaluate_coordination(
            input_topic,
            input_records,
            labor_hours=payload.labor_hours,
            hourly_rate=payload.hourly_rate,
        )
        metrics = asdict(evaluation.metrics)
        risk = asdict(evaluation.risk)
        progress = coordination_progress.detail(connection, topic_id)
        if progress["rows"]:
            risk["communication_risk"] = dict(risk)
            risk["progress_risk"] = progress["assessment"]
            progress_level = progress["assessment"]["risk_level"]
            if _RISK_ORDER.get(progress_level, 0) > _RISK_ORDER.get(
                risk["risk_level"], 0
            ):
                risk["risk_level"] = progress_level
            risk["reasons"] = list(risk["reasons"]) + [
                item["reason"] for item in progress["assessment"]["alerts"]
            ]
            risk["rule_label"] = RULE_LABEL + " + PROGRESS-DEMO-V1"
        cost = {
            "labor_hours": evaluation.cost_inputs["labor_hours"],
            "hourly_rate": evaluation.cost_inputs["hourly_rate"],
            "amount": evaluation.cost_amount,
            "currency": "CNY（演示）",
            "basis": "人工输入工时 × 演示费率，不由消息条数推算",
            "data_gaps": list(evaluation.cost_data_gaps),
        }
        inputs = {
            "topic": {
                "window_start": input_topic.window_start.isoformat(),
                "window_end": input_topic.window_end.isoformat(),
                "expected_participants": list(input_topic.expected_participants),
            },
            "records": [
                {
                    "external_id": record.external_id,
                    "record_type": record.record_type,
                    "sender": record.sender,
                    "sent_at": record.sent_at.isoformat(),
                    "reply_to_external_id": record.reply_to_external_id,
                }
                for record in input_records
            ],
            "labor_hours": evaluation.cost_inputs["labor_hours"],
            "hourly_rate": evaluation.cost_inputs["hourly_rate"],
            "progress": progress["rows"],
        }
        run_no = _next_sequence(connection, f"coordination_metric:{topic_id}")
        run_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO coordination_metric_runs(
                id, topic_id, run_no, rule_label, inputs_json,
                metrics_json, risk_json, cost_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                topic_id,
                run_no,
                risk["rule_label"],
                _json_text(inputs),
                _json_text(metrics),
                _json_text(risk),
                _json_text(cost),
                now,
            ),
        )
        _audit(
            connection,
            project_id=topic["project_id"],
            object_type="coordination_metric_run",
            object_id=run_id,
            object_revision=run_no,
            action="coordination.metrics.calculated",
            after={
                "rule_label": RULE_LABEL,
                "run_no": run_no,
                "risk_level": risk["risk_level"],
                "score": risk["score"],
                "cost_amount": cost["amount"],
            },
        )
        row = connection.execute(
            "SELECT * FROM coordination_metric_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        return {
            "topic": _topic_dict(topic),
            "metric_run": _metric_run_dict(row, connection),
        }


def get_latest_coordination_metrics(
    connection: sqlite3.Connection, topic_id: str
) -> dict[str, Any]:
    topic = _topic_row(connection, topic_id)
    row = _latest_metric_row(connection, topic_id)
    if row is None:
        raise NotFoundError("该协同议题尚无指标计算记录", {"topic_id": topic_id})
    return {
        "topic": _topic_dict(topic),
        "metric_run": _metric_run_dict(row, connection),
    }


def get_coordination_overview(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    _project_row(connection, project_id)
    topics = list_coordination_topics(connection, project_id)
    latest_runs = [
        topic["latest_metrics"]
        for topic in topics
        if topic["latest_metrics"] is not None
        and topic["latest_metrics"]["validity"] == "current"
    ]
    risk_levels = [run["risk"]["risk_level"] for run in latest_runs]
    if len(latest_runs) < len(topics) or not latest_runs:
        highest_risk = "insufficient"
    elif "insufficient" in risk_levels:
        highest_risk = "insufficient"
    else:
        highest_risk = max(risk_levels, key=lambda level: _RISK_ORDER.get(level, 0))
    return {
        "project_id": project_id,
        "rule_label": RULE_LABEL,
        "source_label": RULE_SOURCE_LABEL,
        "topic_count": len(topics),
        "record_count": sum(topic["record_count"] for topic in topics),
        "metrics_available": len(latest_runs),
        "highest_risk": highest_risk,
        "topics": topics,
    }


def accept_coordination_risk(
    connection: sqlite3.Connection,
    topic_id: str,
    payload: CoordinationRiskAcceptanceCreate,
) -> dict[str, Any]:
    with transaction(connection):
        topic = _topic_row(connection, topic_id)
        run = connection.execute(
            """
            SELECT * FROM coordination_metric_runs
            WHERE id = ? AND topic_id = ?
            """,
            (payload.metric_run_id, topic_id),
        ).fetchone()
        if run is None:
            raise DomainValidationError(
                "指标计算结果不存在或不属于该协同议题",
                {
                    "topic_id": topic_id,
                    "metric_run_id": payload.metric_run_id,
                },
            )
        latest = _latest_metric_row(connection, topic_id)
        if latest is None or latest["id"] != run["id"]:
            raise DomainValidationError(
                "只能接受最新一次指标计算的风险",
                {
                    "metric_run_id": payload.metric_run_id,
                    "latest_metric_run_id": (
                        latest["id"] if latest is not None else None
                    ),
                },
            )
        risk = _parse_json(run["risk_json"], {})
        if _metric_run_dict(run, connection)["validity"] != "current":
            raise DomainValidationError("沟通记录已变化，请重算指标后重新核对风险")
        risk_level = risk.get("risk_level")
        if risk_level not in ("high", "insufficient"):
            raise DomainValidationError(
                "当前风险等级不需要显式接受",
                {
                    "metric_run_id": payload.metric_run_id,
                    "risk_level": risk_level,
                },
            )
        duplicate = connection.execute(
            """
            SELECT 1 FROM coordination_risk_acceptances
            WHERE metric_run_id = ?
            """,
            (payload.metric_run_id,),
        ).fetchone()
        if duplicate is not None:
            raise DuplicateRecordError(
                "该指标结果已有人工风险接受记录",
                {"metric_run_id": payload.metric_run_id},
            )
        acceptance_id = str(uuid.uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO coordination_risk_acceptances(
                id, topic_id, metric_run_id, actor, role, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                acceptance_id,
                topic_id,
                payload.metric_run_id,
                payload.actor,
                payload.role,
                payload.note,
                now,
            ),
        )
        _audit(
            connection,
            project_id=topic["project_id"],
            object_type="coordination_metric_run",
            object_id=payload.metric_run_id,
            object_revision=run["run_no"],
            action="coordination.risk.accepted",
            actor=payload.actor,
            role=payload.role,
            decision="accepted_risk",
            comment=payload.note,
            after={
                "topic_id": topic_id,
                "risk_level": risk_level,
                "score": risk.get("score"),
                "reasons": risk.get("reasons", []),
            },
        )
        acceptance = next(
            item
            for item in _risk_acceptances(connection, topic_id)
            if item["id"] == acceptance_id
        )
        return {
            "topic": _topic_dict(topic),
            "acceptance": acceptance,
        }
