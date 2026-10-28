from app.domain.consistency import (
    ArtifactRecord,
    ConsistencyInputs,
    RequirementRecord,
    RequirementReferenceRecord,
    TestCaseRecord,
    TestRunRecord,
    conflict_key,
    detect_conflicts,
    evaluate_relation,
    summarize_conflicts,
)


def _evaluate(
    left=2600.0,
    relation=">=",
    right=2800.0,
    left_unit="N·m",
    right_unit="N·m",
    left_type="numeric",
    right_type="numeric",
):
    return evaluate_relation(
        left_value=left,
        left_unit=left_unit,
        left_data_type=left_type,
        relation=relation,
        right_value=right,
        right_unit=right_unit,
        right_data_type=right_type,
    )


def _requirement(
    requirement_id,
    display_code,
    parameter_name,
    value,
    *,
    unit="N·m",
    operator="=",
    review_status="confirmed",
    revision=1,
    source_excerpt="",
    source_document_id="doc-1",
    data_type="numeric",
):
    return RequirementRecord(
        id=requirement_id,
        display_code=display_code,
        parameter_name=parameter_name,
        data_type=data_type,
        operator=operator,
        value_num=value,
        unit=unit,
        review_status=review_status,
        validity="current",
        current_revision=revision,
        source_document_id=source_document_id,
        source_excerpt=source_excerpt,
    )


def _reference(reference_id, requirement_id, referenced_id, relation=">="):
    return RequirementReferenceRecord(
        id=reference_id,
        requirement_id=requirement_id,
        referenced_requirement_id=referenced_id,
        relation=relation,
    )


def test_relation_boundaries_use_exact_operators():
    assert _evaluate(2800, ">=", 2800).status == "satisfied"
    assert _evaluate(2799.999, ">=", 2800).status == "violated"
    assert _evaluate(2800, ">", 2800).status == "violated"
    assert _evaluate(2800.001, ">", 2800).status == "satisfied"
    assert _evaluate(2800, "<=", 2800).status == "satisfied"
    assert _evaluate(2800, "<", 2800).status == "violated"
    assert _evaluate(2800, "=", 2800).status == "satisfied"
    assert _evaluate(2800.1, "=", 2800).status == "violated"


def test_relation_accepts_unicode_operator_aliases():
    assert _evaluate(2800, "≥", 2800).status == "satisfied"
    assert _evaluate(2800, "≤", 2800).status == "satisfied"


def test_relation_missing_or_mismatched_unit_is_invalid_not_compared():
    missing = _evaluate(left_unit="", right_unit="N·m")
    mismatched = _evaluate(left_unit="N·m", right_unit="kN·m")

    assert missing.status == "invalid"
    assert "单位" in missing.reason
    assert mismatched.status == "invalid"
    assert "单位" in mismatched.reason


def test_relation_non_finite_or_missing_value_is_invalid():
    assert _evaluate(left=None).status == "invalid"
    assert _evaluate(right=float("nan")).status == "invalid"
    assert _evaluate(left=float("inf")).status == "invalid"


def test_relation_non_numeric_requirement_is_unsupported_not_passed():
    result = _evaluate(left_type="text", left=1.0)

    assert result.status == "unsupported"
    assert "数值" in result.reason


def test_conflict_key_is_stable_and_discriminated():
    first = conflict_key("parameter", "requirement", "req-1", "ref-1")
    second = conflict_key("parameter", "requirement", "req-1", "ref-1")
    other = conflict_key("parameter", "requirement", "req-1", "ref-2")

    assert first == second
    assert first != other
    assert first.startswith("parameter:requirement:req-1:")


def test_relation_conflict_keeps_unreviewed_status_visible():
    inputs = ConsistencyInputs(
        requirements=(
            _requirement(
                "b3",
                "REQ-P01-B-003",
                "发动机最大扭矩",
                2800,
                review_status="draft",
                revision=2,
                source_excerpt="发动机最大扭矩 2800 N·m",
            ),
            _requirement(
                "c2",
                "REQ-P01-C-002",
                "变速器最低额定输入扭矩",
                2600,
                review_status="draft",
                operator=">=",
                source_excerpt="额定输入扭矩不低于 2600 N·m",
            ),
        ),
        references=(_reference("ref-1", "c2", "b3"),),
    )

    conflicts = detect_conflicts(inputs)
    parameter = next(
        item for item in conflicts if item.conflict_type == "parameter"
    )

    assert parameter.severity == "blocking"
    assert parameter.object_id == "c2"
    assert parameter.object_review_status == "draft"
    assert "待审核" in parameter.detail
    assert summarize_conflicts(conflicts)["review_pending"] >= 1


def test_citation_mismatch_is_detected_against_current_value():
    inputs = ConsistencyInputs(
        requirements=(
            _requirement(
                "b3",
                "REQ-P01-B-003",
                "发动机最大扭矩",
                2800,
                revision=2,
                source_excerpt="发动机最大扭矩 2600 N·m",
            ),
        ),
    )

    conflicts = detect_conflicts(inputs)
    citation = next(
        item for item in conflicts if item.conflict_type == "reference"
    )

    assert citation.severity == "high"
    assert "2600" in citation.detail
    assert "2800" in citation.detail


def test_version_condition_and_rule_conflicts_are_separate():
    engine = _requirement(
        "b3",
        "REQ-P01-B-003",
        "发动机最大扭矩",
        2800,
        revision=2,
        source_excerpt="发动机最大扭矩 2800 N·m",
    )
    case = TestCaseRecord(
        id="tc7",
        display_code="TC-007",
        revision=2,
        review_status="draft",
        validity="current",
        minimum_coefficient=2.5,
        load_basis_requirement_id="b3",
        is_static_torsion=True,
    )
    run = TestRunRecord(
        id="run-1",
        case_id="tc7",
        case_revision=1,
        status="completed",
        result="fail",
        load_basis_numeric=2600,
        backup_coefficient=2.4,
        created_at="2026-10-19T00:00:00+00:00",
    )
    stale = ArtifactRecord(
        object_type="test_case",
        object_id="tc-old",
        display_code="TC-004",
        revision=1,
        review_status="draft",
        reason="引用的需求版本已更新",
    )
    inputs = ConsistencyInputs(
        requirements=(engine,),
        stale_artifacts=(stale,),
        test_cases=(case,),
        latest_runs=(run,),
    )

    conflicts = detect_conflicts(inputs)
    types = [item.conflict_type for item in conflicts]

    assert "version" in types
    assert "condition" in types
    assert "rule" in types
    version_run = next(
        item
        for item in conflicts
        if item.conflict_type == "version"
        and item.object_type == "test_run"
    )
    assert version_run.object_id == "run-1"
    condition = next(
        item for item in conflicts if item.conflict_type == "condition"
    )
    assert "2600" in condition.detail and "2800" in condition.detail
    rule = next(item for item in conflicts if item.conflict_type == "rule")
    assert "2.5" in rule.detail


def test_missing_reference_and_invalid_relation_are_reported():
    inputs = ConsistencyInputs(
        requirements=(
            _requirement(
                "b3",
                "REQ-P01-B-003",
                "发动机最大扭矩",
                2800,
                source_excerpt="发动机最大扭矩 2800 N·m",
            ),
            _requirement(
                "c2",
                "REQ-P01-C-002",
                "变速器最低额定输入扭矩",
                2600,
                unit="",
                operator=">=",
                source_excerpt="额定输入扭矩不低于 2600",
            ),
            _requirement(
                "t1",
                "REQ-P01-C-099",
                "文本要求",
                1.0,
                data_type="text",
                source_excerpt="文本要求",
            ),
        ),
        references=(
            _reference("ref-invalid", "c2", "b3"),
            _reference("ref-text", "t1", "b3"),
            _reference("ref-missing", "c2", "missing"),
        ),
    )

    conflicts = detect_conflicts(inputs)
    titles = {item.title for item in conflicts}

    assert "参数关系无法判定" in titles
    assert "参数关系未自动判定" in titles
    assert "需求引用对象缺失" in titles


def test_run_checks_skip_non_static_and_handle_missing_values():
    static_case = TestCaseRecord(
        id="tc7",
        display_code="TC-007",
        revision=1,
        review_status="draft",
        validity="current",
        minimum_coefficient=2.5,
        load_basis_requirement_id=None,
        is_static_torsion=True,
    )
    manual_case = TestCaseRecord(
        id="tc1",
        display_code="TC-001",
        revision=1,
        review_status="confirmed",
        validity="current",
        minimum_coefficient=2.5,
        load_basis_requirement_id=None,
        is_static_torsion=False,
    )
    inputs = ConsistencyInputs(
        test_cases=(static_case, manual_case),
        latest_runs=(
            TestRunRecord(
                id="run-empty",
                case_id="tc7",
                case_revision=1,
                status="completed",
                result="incomplete",
                load_basis_numeric=None,
                backup_coefficient=None,
                created_at="2026-10-19T00:00:00+00:00",
            ),
            TestRunRecord(
                id="run-infinite",
                case_id="tc7",
                case_revision=1,
                status="completed",
                result="invalid",
                load_basis_numeric=float("inf"),
                backup_coefficient=float("nan"),
                created_at="2026-10-19T00:00:01+00:00",
            ),
            TestRunRecord(
                id="run-manual",
                case_id="tc1",
                case_revision=1,
                status="completed",
                result="pass",
                load_basis_numeric=None,
                backup_coefficient=None,
                created_at="2026-10-19T00:00:02+00:00",
            ),
        ),
    )

    conflicts = detect_conflicts(inputs)
    condition = [
        item for item in conflicts if item.conflict_type == "condition"
    ]
    rule = [item for item in conflicts if item.conflict_type == "rule"]

    assert len(condition) == 2
    assert len(rule) == 2
    assert all(item.object_id == "tc7" for item in condition + rule)


def test_summary_counts_blocking_and_pending_review():
    inputs = ConsistencyInputs(
        requirements=(
            _requirement(
                "b3",
                "REQ-P01-B-003",
                "发动机最大扭矩",
                2800,
                revision=2,
                source_excerpt="发动机最大扭矩 2800 N·m",
            ),
            _requirement(
                "c2",
                "REQ-P01-C-002",
                "变速器最低额定输入扭矩",
                2600,
                review_status="draft",
                operator=">=",
                source_excerpt="额定输入扭矩不低于 2600 N·m",
            ),
        ),
        references=(_reference("ref-1", "c2", "b3"),),
    )
    conflicts = detect_conflicts(inputs)
    summary = summarize_conflicts(conflicts)

    assert summary["total"] == len(conflicts)
    assert summary["by_type"]["parameter"] == 1
    assert summary["blocking"] == 1
    assert summary["review_pending"] == 1
