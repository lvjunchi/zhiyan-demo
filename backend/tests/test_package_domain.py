import pytest

from app.domain.package import (
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

REQUIREMENTS = (
    RequirementGateItem(
        requirement_id="req-b003",
        display_code="REQ-P01-B-003",
        revision=1,
        review_status="confirmed",
        validity="current",
    ),
    RequirementGateItem(
        requirement_id="req-c002",
        display_code="REQ-P01-C-002",
        revision=1,
        review_status="confirmed",
        validity="current",
    ),
)

VALIDATION = (
    ValidationGateItem(
        key="gearboxRatedInputTorque",
        label="变速器最低额定输入扭矩",
        requirement_id="req-c002",
        display_code="REQ-P01-C-002",
        requirement_revision=1,
        covered=True,
        execution="pass",
    ),
    ValidationGateItem(
        key="gearCount",
        label="档位数",
        requirement_id="req-c001",
        display_code="REQ-P01-C-001",
        requirement_revision=1,
        covered=True,
        execution="pass",
    ),
    ValidationGateItem(
        key="pto",
        label="取力器功能",
        requirement_id="req-c006",
        display_code="REQ-P01-C-006",
        requirement_revision=1,
        covered=True,
        execution="pass",
    ),
    ValidationGateItem(
        key="assemblyWeight",
        label="总成重量上限",
        requirement_id="req-d002",
        display_code="REQ-P01-D-002",
        requirement_revision=1,
        covered=True,
        execution="pass",
    ),
    ValidationGateItem(
        key="durability",
        label="耐久要求",
        requirement_id="req-f001",
        display_code="REQ-P01-F-001",
        requirement_revision=1,
        covered=True,
        execution="pass",
    ),
)

ARTIFACTS = (
    ArtifactGateItem(
        key="test_plan",
        label="试验方案",
        object_type="test_plan",
        object_id="plan-1",
        display_code="TP-P01",
        revision=1,
        status="confirmed",
    ),
    ArtifactGateItem(
        key="design_review",
        label="设计评审清单",
        object_type="design_review",
        object_id="review-1",
        display_code="DR-P01",
        revision=1,
        status="confirmed",
    ),
    ArtifactGateItem(
        key="dfmea",
        label="DFMEA",
        object_type="fmea_document",
        object_id="fmea-1",
        display_code="DFMEA-P01",
        revision=1,
        status="confirmed",
    ),
)

CONSISTENCY = ConsistencyGateItem(
    check_id="check-1",
    display_code="CR-P01-001",
    status="confirmed",
    validity="current",
    blocking_conflicts=(),
    open_high_count=0,
)

COORDINATION = (
    CoordinationRiskGateItem(
        topic_id="topic-1",
        display_code="CT-01",
        metric_run_id="run-1",
        risk_level="high",
        accepted=True,
    ),
)


def _inputs(**overrides):
    values = {
        "requirements": REQUIREMENTS,
        "validation": VALIDATION,
        "artifacts": ARTIFACTS,
        "sample_artifacts": (),
        "consistency": CONSISTENCY,
        "issues": (),
        "coordination": COORDINATION,
        "expected_denominator": 5,
    }
    values.update(overrides)
    return PackageGateInputs(**values)


@pytest.mark.parametrize(
    "status,stale,exists,ready",
    [
        ("confirmed", False, True, True),
        ("draft", False, True, False),
        ("confirmed", True, True, False),
        ("rejected", False, True, False),
        ("confirmed", False, False, False),
    ],
)
def test_engineering_artifacts_have_independent_gate(status, stale, exists, ready):
    item = ArtifactGateItem(
        key="part:p1",
        label="复用决策 P-01",
        object_type="reusable_part_decision",
        object_id="p1",
        revision=2,
        status=status,
        needs_reconfirmation=stale,
        exists=exists,
    )
    result = evaluate_package_gate(_inputs(artifacts=ARTIFACTS + (item,))).to_dict()
    assert result["ready"] is ready
    if not ready:
        assert any(row.get("object_id") == "p1" for row in result["blockers"])


def test_ready_gate_requires_all_five_verified_and_confirmed_artifacts():
    result = evaluate_package_gate(_inputs()).to_dict()

    assert result["status"] == "ready"
    assert result["ready"] is True
    assert result["blockers"] == []
    checks = {check["key"]: check for check in result["checks"]}
    assert set(checks) == {
        "requirements_confirmed",
        "test_plan_confirmed",
        "design_review_confirmed",
        "dfmea_confirmed",
        "coverage_complete",
        "verification_passed",
        "sample_comparison_confirmed",
        "consistency_cleared",
        "issues_cleared",
        "coordination_risk_accepted",
    }
    assert checks["coverage_complete"]["status"] == "pass"
    assert checks["verification_passed"]["status"] == "pass"
    assert checks["coordination_risk_accepted"]["status"] == "pass"


def test_gate_lists_each_blocker_instead_of_stopping_at_first_failure():
    requirements = (
        REQUIREMENTS[0],
        RequirementGateItem(
            requirement_id="req-c002",
            display_code="REQ-P01-C-002",
            revision=1,
            review_status="draft",
            validity="current",
        ),
    )
    validation = (
        VALIDATION[0],
        ValidationGateItem(
            key="gearCount",
            label="档位数",
            requirement_id="req-c001",
            display_code="REQ-P01-C-001",
            requirement_revision=1,
            covered=False,
            execution="not_run",
        ),
        *VALIDATION[2:],
    )
    plan = ArtifactGateItem(
        key="test_plan",
        label="试验方案",
        object_type="test_plan",
        object_id="plan-1",
        display_code="TP-P01",
        revision=1,
        status="draft",
    )
    consistency = ConsistencyGateItem(
        check_id="check-1",
        display_code="CR-P01-001",
        status="draft",
        validity="current",
        blocking_conflicts=(
            ConflictGateItem(
                conflict_id="conflict-1",
                display_code="CF-P01-001",
                severity="blocking",
                status="open",
            ),
        ),
        open_high_count=1,
    )
    issues = (
        IssueGateItem(
            issue_id="issue-1",
            issue_type="contradictory",
            severity="high",
            status="open",
            message="协议条款矛盾",
        ),
    )
    coordination = (
        CoordinationRiskGateItem(
            topic_id="topic-1",
            display_code="CT-01",
            metric_run_id="run-1",
            risk_level="high",
            accepted=False,
        ),
    )

    result = evaluate_package_gate(
        _inputs(
            requirements=requirements,
            validation=validation,
            artifacts=(plan, *ARTIFACTS[1:]),
            consistency=consistency,
            issues=issues,
            coordination=coordination,
        )
    ).to_dict()

    assert result["status"] == "blocked"
    codes = {blocker["code"] for blocker in result["blockers"]}
    assert {
        "REQUIREMENT_NOT_CONFIRMED",
        "COVERAGE_INCOMPLETE",
        "VERIFICATION_NOT_PASSED",
        "ARTIFACT_NOT_CONFIRMED",
        "CONSISTENCY_CHECK_NOT_CONFIRMED",
        "BLOCKING_CONFLICT_OPEN",
        "HIGH_ISSUE_OPEN",
        "COORDINATION_RISK_UNACCEPTED",
    } <= codes
    assert result["summary"]["blocker_count"] == len(result["blockers"])


def test_missing_artifacts_and_sample_comparison_are_reported_explicitly():
    sample = ArtifactGateItem(
        key="sample_comparison",
        label="样件比对 SD-01",
        object_type="sample_comparison",
        object_id=None,
        display_code="SD-01",
        revision=None,
        status=None,
        exists=False,
    )
    result = evaluate_package_gate(
        _inputs(
            artifacts=(
                ArtifactGateItem(
                    key="test_plan",
                    label="试验方案",
                    object_type="test_plan",
                    object_id=None,
                    display_code=None,
                    revision=None,
                    status=None,
                    exists=False,
                ),
                ArtifactGateItem(
                    key="design_review",
                    label="设计评审清单",
                    object_type="design_review",
                    object_id=None,
                    display_code=None,
                    revision=None,
                    status=None,
                    exists=False,
                ),
                ArtifactGateItem(
                    key="dfmea",
                    label="DFMEA",
                    object_type="fmea_document",
                    object_id=None,
                    display_code=None,
                    revision=None,
                    status=None,
                    exists=False,
                ),
            ),
            sample_artifacts=(sample,),
            consistency=ConsistencyGateItem(
                check_id=None,
                display_code=None,
                status=None,
                validity=None,
                blocking_conflicts=(),
                open_high_count=0,
            ),
        )
    ).to_dict()

    codes = {blocker["code"] for blocker in result["blockers"]}
    assert "TEST_PLAN_MISSING" in codes
    assert "DESIGN_REVIEW_MISSING" in codes
    assert "DFMEA_MISSING" in codes
    assert "SAMPLE_COMPARISON_MISSING" in codes
    assert "CONSISTENCY_CHECK_MISSING" in codes
    assert "COORDINATION_RISK_UNACCEPTED" not in codes


def test_unknown_coordination_risk_is_not_treated_as_low():
    coordination = (
        CoordinationRiskGateItem(
            topic_id="topic-1",
            display_code="CT-01",
            metric_run_id=None,
            risk_level=None,
            accepted=False,
        ),
        CoordinationRiskGateItem(
            topic_id="topic-2",
            display_code="CT-02",
            metric_run_id="run-2",
            risk_level="insufficient",
            accepted=False,
        ),
        CoordinationRiskGateItem(
            topic_id="topic-3",
            display_code="CT-03",
            metric_run_id="run-3",
            risk_level="medium",
            accepted=False,
        ),
    )

    result = evaluate_package_gate(_inputs(coordination=coordination)).to_dict()

    codes = {blocker["code"] for blocker in result["blockers"]}
    assert "COORDINATION_METRICS_MISSING" in codes
    assert "COORDINATION_RISK_UNACCEPTED" in codes
    assert result["status"] == "blocked"
    warning_codes = {warning["code"] for warning in result["warnings"]}
    assert "COORDINATION_RISK_UNACCEPTED" not in warning_codes


def test_no_sample_or_coordination_data_is_not_applicable_not_silent_pass():
    result = evaluate_package_gate(
        _inputs(sample_artifacts=(), coordination=())
    ).to_dict()

    checks = {check["key"]: check for check in result["checks"]}
    assert checks["sample_comparison_confirmed"]["status"] == "not_applicable"
    assert checks["coordination_risk_accepted"]["status"] == "not_applicable"
    assert result["status"] == "ready"
    warning_codes = {warning["code"] for warning in result["warnings"]}
    assert "SAMPLE_NOT_PROVIDED" in warning_codes
    assert "COORDINATION_NOT_PROVIDED" in warning_codes
