from app.domain.progress import ProgressRecord, evaluate_progress


def row(p, plan=80, actual=80, version="V1", milestone="冻结"):
    return ProgressRecord(
        p, milestone, plan, actual, version, "周报", "2026-10-23T08:00:00+00:00"
    )


def test_empty_and_missing_data_are_not_zero_risk():
    assert evaluate_progress([], ("A", "B"))["risk_level"] == "insufficient"
    assert evaluate_progress([row("A")], ("A", "B"))["data_gaps"]


def test_equal_milestones_and_unmatched_milestones_are_distinct():
    assert evaluate_progress([row("A"), row("B")], ("A", "B"))["risk_level"] == "low"
    result = evaluate_progress([row("A"), row("B", milestone="样件")], ("A", "B"))
    assert not result["alerts"] and result["risk_level"] == "insufficient"


def test_progress_gap_lag_versions_and_boundaries():
    high = evaluate_progress(
        [row("A", actual=100, version="V2"), row("B", actual=40)], ("A", "B")
    )
    assert high["risk_level"] == "high"
    assert {"progress_gap", "schedule_lag", "delivery_version"} == {
        item["kind"] for item in high["alerts"]
    }
    medium = evaluate_progress([row("A"), row("B", actual=60)], ("A", "B"))
    assert medium["risk_level"] == "medium"
    assert (
        evaluate_progress([row("A"), row("B", actual=61)], ("A", "B"))["risk_level"]
        == "low"
    )
    assert (
        evaluate_progress([row("A", actual=60), row("B", actual=60)], ("A", "B"))[
            "risk_level"
        ]
        == "medium"
    )
