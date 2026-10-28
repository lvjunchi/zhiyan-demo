from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

RULE_LABEL = "COORD-DEMO-V1"
AVERAGE_RESPONSE_THRESHOLD_HOURS = 48.0
ITERATION_THRESHOLD = 3
ABSENCE_RATE_THRESHOLD = 1 / 3


@dataclass(frozen=True)
class CoordinationTopic:
    expected_participants: tuple[str, ...]
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class CoordinationRecord:
    external_id: str
    record_type: str
    sender: str
    sent_at: datetime
    reply_to_external_id: str | None
    content_summary: str = ""


@dataclass(frozen=True)
class CoordinationMetrics:
    window_start: str
    window_end: str
    response_latencies_hours: tuple[float, ...]
    average_response_hours: float | None
    response_sample_size: int
    pending_requests: tuple[dict[str, Any], ...]
    pending_count: int
    iteration_count: int
    expected_participants: tuple[str, ...]
    actual_participants: tuple[str, ...]
    absent_participants: tuple[str, ...]
    absence_rate: float | None
    orphan_response_count: int
    invalid_pair_count: int
    data_gaps: tuple[str, ...]


@dataclass(frozen=True)
class RiskEvaluation:
    rule_label: str
    risk_level: str
    score: float | None
    hit_count: int
    reasons: tuple[str, ...]
    conditions: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class CoordinationEvaluation:
    metrics: CoordinationMetrics
    risk: RiskEvaluation
    cost_amount: float | None
    cost_inputs: dict[str, float | None]
    cost_data_gaps: tuple[str, ...]


def _hours_between(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds() / 3600, 2)


def _coordination_cost(
    labor_hours: float | None, hourly_rate: float | None
) -> tuple[float | None, tuple[str, ...]]:
    gaps: list[str] = []
    if labor_hours is None:
        gaps.append("人工协调工时未提供，协调成本不计算")
    if hourly_rate is None:
        gaps.append("演示费率未提供，协调成本不计算")
    if gaps:
        return None, tuple(gaps)
    if labor_hours < 0 or hourly_rate < 0:
        return None, ("协调工时或费率不能为负数，协调成本不计算",)
    return round(labor_hours * hourly_rate, 2), ()


def _risk(
    metrics: CoordinationMetrics,
) -> RiskEvaluation:
    average_available = metrics.average_response_hours is not None
    absence_available = metrics.absence_rate is not None
    conditions = (
        {
            "key": "average_response",
            "label": "平均响应时延 > 48 小时",
            "actual": metrics.average_response_hours,
            "threshold": AVERAGE_RESPONSE_THRESHOLD_HOURS,
            "hit": bool(
                average_available
                and metrics.average_response_hours
                > AVERAGE_RESPONSE_THRESHOLD_HOURS
            ),
            "available": average_available,
        },
        {
            "key": "iterations",
            "label": "反复次数 ≥ 3 次",
            "actual": metrics.iteration_count,
            "threshold": ITERATION_THRESHOLD,
            "hit": metrics.iteration_count >= ITERATION_THRESHOLD,
            "available": True,
        },
        {
            "key": "absence",
            "label": "应参与方缺席率 ≥ 1/3",
            "actual": metrics.absence_rate,
            "threshold": round(ABSENCE_RATE_THRESHOLD, 4),
            "hit": bool(
                absence_available
                and metrics.absence_rate
                >= ABSENCE_RATE_THRESHOLD - 1e-9
            ),
            "available": absence_available,
        },
    )
    hit_count = sum(1 for item in conditions if item["hit"])
    if not average_available or not absence_available:
        return RiskEvaluation(
            rule_label=RULE_LABEL,
            risk_level="insufficient",
            score=None,
            hit_count=hit_count,
            reasons=metrics.data_gaps,
            conditions=conditions,
        )
    if hit_count >= 2:
        level = "high"
    elif hit_count == 1:
        level = "medium"
    else:
        level = "low"
    reasons = tuple(
        item["label"]
        for item in conditions
        if item["hit"]
    )
    return RiskEvaluation(
        rule_label=RULE_LABEL,
        risk_level=level,
        score=round(hit_count / 3 * 100, 1),
        hit_count=hit_count,
        reasons=reasons,
        conditions=conditions,
    )


def evaluate_coordination(
    topic: CoordinationTopic,
    records: tuple[CoordinationRecord, ...] | list[CoordinationRecord],
    *,
    labor_hours: float | None = None,
    hourly_rate: float | None = None,
) -> CoordinationEvaluation:
    in_window = [
        record
        for record in records
        if topic.window_start <= record.sent_at <= topic.window_end
    ]
    messages = [
        record for record in in_window if record.record_type == "message"
    ]
    records_by_external = {
        record.external_id: record for record in messages
    }
    latencies: list[float] = []
    orphan_responses = 0
    invalid_pairs = 0
    responded_request_ids: set[str] = set()
    for response in messages:
        if not response.reply_to_external_id:
            continue
        request = records_by_external.get(
            response.reply_to_external_id
        )
        if request is None:
            orphan_responses += 1
            continue
        if request.sent_at > response.sent_at:
            invalid_pairs += 1
            continue
        responded_request_ids.add(request.external_id)
        latencies.append(
            _hours_between(request.sent_at, response.sent_at)
        )

    pending = [
        {
            "external_id": record.external_id,
            "sender": record.sender,
            "sent_at": record.sent_at.isoformat(),
            "waiting_hours": _hours_between(
                record.sent_at, topic.window_end
            ),
        }
        for record in messages
        if record.reply_to_external_id is None
        and record.external_id not in responded_request_ids
    ]
    iteration_count = sum(
        1 for record in in_window if record.record_type == "reopened"
    )
    expected = tuple(topic.expected_participants)
    actual = tuple(sorted({record.sender for record in in_window}))
    absent = tuple(
        participant
        for participant in expected
        if participant not in actual
    )
    absence_rate = (
        len(absent) / len(expected) if expected else None
    )

    data_gaps: list[str] = []
    if not latencies:
        data_gaps.append("无已配对请求/响应，平均响应时延不可计算")
    if orphan_responses:
        data_gaps.append(
            f"存在 {orphan_responses} 条未找到请求的响应，未计入平均时延"
        )
    if invalid_pairs:
        data_gaps.append(
            f"存在 {invalid_pairs} 条响应早于请求，未计入平均时延"
        )
    if not expected:
        data_gaps.append("应参与方清单缺失，缺席率不可计算")
    if not in_window:
        data_gaps.append("统计窗口内无协同记录")

    average_response = (
        round(sum(latencies) / len(latencies), 2)
        if latencies
        else None
    )
    metrics = CoordinationMetrics(
        window_start=topic.window_start.isoformat(),
        window_end=topic.window_end.isoformat(),
        response_latencies_hours=tuple(latencies),
        average_response_hours=average_response,
        response_sample_size=len(latencies),
        pending_requests=tuple(pending),
        pending_count=len(pending),
        iteration_count=iteration_count,
        expected_participants=expected,
        actual_participants=actual,
        absent_participants=absent,
        absence_rate=absence_rate,
        orphan_response_count=orphan_responses,
        invalid_pair_count=invalid_pairs,
        data_gaps=tuple(data_gaps),
    )
    cost_amount, cost_gaps = _coordination_cost(
        labor_hours, hourly_rate
    )
    return CoordinationEvaluation(
        metrics=metrics,
        risk=_risk(metrics),
        cost_amount=cost_amount,
        cost_inputs={
            "labor_hours": None if labor_hours is None else float(labor_hours),
            "hourly_rate": None if hourly_rate is None else float(hourly_rate),
        },
        cost_data_gaps=cost_gaps,
    )
