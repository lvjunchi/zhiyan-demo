from app.domain.testing import (
    VALIDATION_SCOPE,
    CaseSnapshot,
    RequirementRef,
    RunSnapshot,
    ScopeRequirement,
    build_traceability,
    evaluate_static_torsion,
    is_case_complete,
    is_case_covered,
)


def _scope_requirements():
    return [
        ScopeRequirement(
            key=item.key,
            label=item.label,
            requirement_id=f"req-{item.key}",
            display_code=f"REQ-P01-{item.display_hint}",
            revision=1,
        )
        for item in VALIDATION_SCOPE
    ]


def _ref(key: str, revision: int = 1) -> RequirementRef:
    return RequirementRef(
        requirement_id=f"req-{key}",
        display_code=f"REQ-P01-{key}",
        revision=revision,
    )


def _case(
    display_code: str,
    key: str,
    *,
    revision: int = 1,
    review_status: str = "confirmed",
    validity: str = "current",
    conditions: str = "台架工况：额定输入扭矩",
    load_conditions: str = "按当前需求版本加载",
    acceptance: str = "满足当前需求值",
    ref_revision: int = 1,
    latest_run: RunSnapshot | None = None,
) -> CaseSnapshot:
    return CaseSnapshot(
        id=f"case-{display_code}",
        display_code=display_code,
        title=f"验证 {key}",
        revision=revision,
        review_status=review_status,
        validity=validity,
        conditions_text=conditions,
        load_conditions_text=load_conditions,
        acceptance_criteria=acceptance,
        requirement_refs=(_ref(key, ref_revision),),
        fmea_refs=(),
        latest_run=latest_run,
    )


def _run(
    result: str | None,
    *,
    run_no: int = 1,
    status: str = "completed",
    case_revision: int = 1,
) -> RunSnapshot:
    return RunSnapshot(
        id=f"run-{run_no}-{result}",
        run_no=run_no,
        status=status,
        result=result,
        case_revision=case_revision,
        mode="rule",
        created_at="2026-10-19T00:00:00+00:00",
    )


def test_case_completeness_requires_conditions_and_acceptance():
    complete = _case("TC-001", "gearCount")
    missing_standard = _case("TC-004", "durability", acceptance="")
    missing_conditions = _case("TC-002", "pto", conditions="")

    assert is_case_complete(complete) is True
    assert is_case_complete(missing_standard) is False
    assert is_case_complete(missing_conditions) is False


def test_coverage_requires_confirmed_current_case_with_matching_revision():
    valid = _case("TC-001", "gearCount")
    draft = _case("TC-001", "gearCount", review_status="draft")
    stale = _case("TC-001", "gearCount", validity="stale")
    old_ref = _case("TC-001", "gearCount", ref_revision=0)

    assert is_case_covered(valid) is True
    assert is_case_covered(draft) is False
    assert is_case_covered(stale) is False
    assert is_case_covered(old_ref) is False


def test_scope_denominator_stays_five_when_requirement_is_missing():
    scope = _scope_requirements()
    scope[4] = ScopeRequirement(
        key="durability",
        label="耐久要求",
        requirement_id=None,
        display_code=None,
        revision=None,
    )
    cases = [
        _case("TC-001", item.key)
        for item in VALIDATION_SCOPE
        if item.key != "durability"
    ]

    matrix = build_traceability(scope, cases)

    assert matrix.denominator == 5
    assert matrix.covered_count == 4
    assert matrix.coverage_percentage == 80.0
    durability = next(
        item for item in matrix.items if item.key == "durability"
    )
    assert durability.covered is False
    assert durability.reason == "requirement_missing"


def test_multiple_valid_cases_cover_one_requirement_once():
    cases = [
        _case("TC-001", "gearCount"),
        _case("TC-008", "gearCount"),
    ]

    matrix = build_traceability(_scope_requirements(), cases)

    assert matrix.denominator == 5
    assert matrix.covered_count == 1
    assert matrix.coverage_percentage == 20.0
    gear = next(item for item in matrix.items if item.key == "gearCount")
    assert len(gear.valid_case_ids) == 2


def test_pending_case_is_listed_but_does_not_count_as_coverage():
    cases = [
        _case("TC-004", "durability", review_status="draft"),
    ]

    matrix = build_traceability(_scope_requirements(), cases)

    durability = next(
        item for item in matrix.items if item.key == "durability"
    )
    assert durability.covered is False
    assert list(durability.pending_case_ids) == ["case-TC-004"]
    assert matrix.pending_review[0]["reason"] == "draft"


def test_coverage_is_independent_from_execution_and_latest_failure_wins():
    passing = _case(
        "TC-007",
        "gearboxRatedInputTorque",
        latest_run=_run("pass"),
    )
    failing = _case(
        "TC-007",
        "gearboxRatedInputTorque",
        latest_run=_run("fail", run_no=2),
    )
    cases = [
        passing,
        _case("TC-001", "gearCount"),
        _case("TC-002", "pto"),
        _case("TC-003", "assemblyWeight"),
    ]

    matrix = build_traceability(_scope_requirements(), cases)
    assert matrix.covered_count == 4
    assert matrix.coverage_percentage == 80.0
    torque = next(
        item
        for item in matrix.items
        if item.key == "gearboxRatedInputTorque"
    )
    assert torque.execution == "pass"

    failing_matrix = build_traceability(
        _scope_requirements(),
        [
            failing,
            _case("TC-001", "gearCount"),
            _case("TC-002", "pto"),
            _case("TC-003", "assemblyWeight"),
        ],
    )
    failing_torque = next(
        item
        for item in failing_matrix.items
        if item.key == "gearboxRatedInputTorque"
    )
    assert failing_matrix.coverage_percentage == 80.0
    assert failing_torque.execution == "fail"


def test_one_failing_case_prevents_requirement_pass_conclusion():
    passing = _case(
        "TC-007", "gearboxRatedInputTorque", latest_run=_run("pass")
    )
    failing = _case(
        "TC-009",
        "gearboxRatedInputTorque",
        latest_run=_run("fail", run_no=3),
    )

    matrix = build_traceability(_scope_requirements(), [passing, failing])

    torque = next(
        item
        for item in matrix.items
        if item.key == "gearboxRatedInputTorque"
    )
    assert torque.execution == "fail"


def test_static_torsion_uses_load_basis_and_dimensionless_coefficient():
    assert evaluate_static_torsion(2800, 2800, 2.6).result == "pass"
    assert evaluate_static_torsion(2800, 2800, 2.5).result == "pass"

    failed = evaluate_static_torsion(2800, 2800, 2.4)
    assert failed.result == "fail"
    assert "2.5" in " ".join(failed.reasons)

    old_basis = evaluate_static_torsion(2600, 2800, 2.6)
    assert old_basis.result == "invalid"
    assert old_basis.reasons

    missing = evaluate_static_torsion(2800, 2800, None)
    assert missing.result == "incomplete"
    assert missing.missing_fields == ["backupCoefficient"]

    missing_basis = evaluate_static_torsion(None, 2800, 2.6)
    assert missing_basis.result == "incomplete"
    assert missing_basis.missing_fields == ["loadBasis"]

    non_finite = evaluate_static_torsion(2800, 2800, float("nan"))
    assert non_finite.result == "invalid"


def test_execution_summary_counts_each_scope_requirement_once():
    cases = [
        _case("TC-001", "gearCount", latest_run=_run("pass")),
        _case("TC-002", "pto"),
        _case(
            "TC-003",
            "assemblyWeight",
            latest_run=_run(None, status="running"),
        ),
        _case(
            "TC-007",
            "gearboxRatedInputTorque",
            latest_run=_run("fail"),
        ),
    ]

    matrix = build_traceability(_scope_requirements(), cases)

    assert matrix.execution_summary == {
        "pass": 1,
        "fail": 1,
        "incomplete": 0,
        "invalid": 0,
        "running": 1,
        "not_run": 2,
    }
