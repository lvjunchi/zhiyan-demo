from datetime import datetime, timedelta, timezone

from app.domain.coordination import (
    CoordinationRecord,
    CoordinationTopic,
    evaluate_coordination,
)

START = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)


def _topic(expected=("主机厂", "法士特", "S-02")):
    return CoordinationTopic(
        expected_participants=tuple(expected),
        window_start=START,
        window_end=END,
    )


def _record(
    external_id,
    record_type="message",
    sender="法士特",
    hours=0,
    reply_to=None,
):
    return CoordinationRecord(
        external_id=external_id,
        record_type=record_type,
        sender=sender,
        sent_at=START + timedelta(hours=hours),
        reply_to_external_id=reply_to,
        content_summary=f"合成记录 {external_id}",
    )


def _fixture_records():
    records = []
    for index, latency in enumerate((48, 52, 56), start=1):
        records.append(
            _record(
                f"REQ-{index}",
                sender="法士特",
                hours=index,
            )
        )
        records.append(
            _record(
                f"RES-{index}",
                sender="S-02",
                hours=index + latency,
                reply_to=f"REQ-{index}",
            )
        )
    for index in range(1, 5):
        records.append(
            _record(
                f"REOPENED-{index}",
                record_type="reopened",
                sender="法士特",
                hours=100 + index,
            )
        )
    return tuple(records)


def test_fixture_metrics_hit_all_three_rules_and_cost():
    evaluation = evaluate_coordination(
        _topic(),
        _fixture_records(),
        labor_hours=6,
        hourly_rate=200,
    )

    metrics = evaluation.metrics
    assert metrics.average_response_hours == 52.0
    assert metrics.response_sample_size == 3
    assert metrics.response_latencies_hours == (48.0, 52.0, 56.0)
    assert metrics.iteration_count == 4
    assert metrics.expected_participants == ("主机厂", "法士特", "S-02")
    assert metrics.actual_participants == ("S-02", "法士特")
    assert metrics.absent_participants == ("主机厂",)
    assert abs(metrics.absence_rate - 1 / 3) < 1e-9
    assert metrics.pending_count == 0

    risk = evaluation.risk
    assert risk.rule_label == "COORD-DEMO-V1"
    assert risk.risk_level == "high"
    assert risk.hit_count == 3
    assert risk.score == 100.0
    assert len(risk.reasons) == 3
    assert evaluation.cost_amount == 1200.0
    assert evaluation.cost_inputs == {
        "labor_hours": 6.0,
        "hourly_rate": 200.0,
    }


def test_pending_reply_is_separate_from_average_and_waiting_to_window_end():
    records = (
        _record("REQ-1", hours=1),
        _record("RES-1", sender="S-02", hours=49, reply_to="REQ-1"),
        _record("REQ-PENDING", hours=100),
    )

    evaluation = evaluate_coordination(_topic(), records)
    metrics = evaluation.metrics

    assert metrics.average_response_hours == 48.0
    assert metrics.response_sample_size == 1
    assert metrics.pending_count == 1
    pending = metrics.pending_requests[0]
    assert pending["external_id"] == "REQ-PENDING"
    assert pending["waiting_hours"] == (END - (START + timedelta(hours=100))).total_seconds() / 3600


def test_unknown_response_data_is_insufficient_not_low():
    records = (_record("REQ-1", hours=1),)

    evaluation = evaluate_coordination(_topic(), records)
    metrics = evaluation.metrics
    risk = evaluation.risk

    assert metrics.average_response_hours is None
    assert metrics.response_sample_size == 0
    assert metrics.pending_count == 1
    assert risk.risk_level == "insufficient"
    assert risk.score is None
    assert any("平均响应" in gap for gap in metrics.data_gaps)


def test_orphan_response_and_missing_expected_participants_are_flagged():
    records = (
        _record("RES-ORPHAN", sender="S-02", hours=10, reply_to="MISSING"),
    )

    evaluation = evaluate_coordination(_topic(expected=()), records)
    metrics = evaluation.metrics
    risk = evaluation.risk

    assert metrics.orphan_response_count == 1
    assert metrics.average_response_hours is None
    assert metrics.absence_rate is None
    assert risk.risk_level == "insufficient"
    assert any("未找到请求" in gap for gap in metrics.data_gaps)
    assert any("应参与方" in gap for gap in metrics.data_gaps)


def test_cost_requires_both_manual_inputs_and_never_defaults_to_zero():
    without_hours = evaluate_coordination(
        _topic(), _fixture_records(), hourly_rate=200
    )
    without_rate = evaluate_coordination(
        _topic(), _fixture_records(), labor_hours=6
    )

    assert without_hours.cost_amount is None
    assert without_hours.cost_inputs["labor_hours"] is None
    assert without_rate.cost_amount is None
    assert any("成本" in gap for gap in without_hours.cost_data_gaps)


def test_rule_thresholds_are_exact():
    records = []
    for index in range(1, 4):
        records.append(_record(f"REQ-{index}", hours=index))
        records.append(
            _record(
                f"RES-{index}",
                sender="S-02",
                hours=index + 48,
                reply_to=f"REQ-{index}",
            )
        )
    for index in range(1, 4):
        records.append(
            _record(
                f"REOPENED-{index}",
                record_type="reopened",
                sender="法士特",
                hours=60 + index,
            )
        )

    evaluation = evaluate_coordination(_topic(), tuple(records))
    conditions = {
        item["key"]: item for item in evaluation.risk.conditions
    }

    assert evaluation.metrics.average_response_hours == 48.0
    assert conditions["average_response"]["hit"] is False
    assert conditions["iterations"]["hit"] is True
    assert conditions["absence"]["hit"] is True
    assert evaluation.risk.risk_level == "high"
    assert evaluation.risk.hit_count == 2
    assert evaluation.risk.score == 66.7
