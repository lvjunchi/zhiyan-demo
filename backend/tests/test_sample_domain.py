from app.domain.sample import (
    ParameterMeasurement,
    ParameterSpec,
    combine_results,
    compare_parameter,
    visual_finding,
)


def _spec(
    key="holePosition",
    name="孔位",
    expected=120.0,
    tolerance=0.5,
    unit="mm",
) -> ParameterSpec:
    return ParameterSpec(
        parameter_key=key,
        parameter_name=name,
        expected_value=expected,
        tolerance=tolerance,
        unit=unit,
        source_note="图纸 SX-DRW-0215 标注",
    )


def _measurement(
    key="holePosition", measured=120.5, unit="mm"
) -> ParameterMeasurement:
    return ParameterMeasurement(
        parameter_key=key, measured_value=measured, unit=unit
    )


def test_parameter_comparison_boundary_is_inclusive():
    on_limit = compare_parameter(_spec(), _measurement(measured=120.5))
    above_limit = compare_parameter(
        _spec(), _measurement(measured=120.5001)
    )

    assert on_limit.result == "pass"
    assert above_limit.result == "fail"
    assert "0.5" in above_limit.reason


def test_missing_measurement_is_incomplete_not_zero():
    finding = compare_parameter(
        _spec(),
        ParameterMeasurement(
            parameter_key="holePosition", measured_value=None, unit="mm"
        ),
    )

    assert finding.result == "incomplete"
    assert finding.measured_value is None
    assert finding.reason


def test_unit_mismatch_is_invalid_not_compared_numerically():
    finding = compare_parameter(
        _spec(), _measurement(measured=12.05, unit="cm")
    )

    assert finding.result == "invalid"
    assert "单位" in finding.reason


def test_missing_unit_on_either_side_is_invalid_not_assumed():
    missing_measured = compare_parameter(
        _spec(), _measurement(measured=120.1, unit="")
    )
    missing_spec = compare_parameter(
        _spec(unit=""), _measurement(measured=120.1, unit="mm")
    )
    both_missing = compare_parameter(
        _spec(unit=""), _measurement(measured=120.1, unit="")
    )

    assert missing_measured.result == "invalid"
    assert "单位" in missing_measured.reason
    assert missing_spec.result == "invalid"
    assert "单位" in missing_spec.reason
    assert both_missing.result == "pass"


def test_non_finite_measurement_is_invalid():
    finding = compare_parameter(
        _spec(), _measurement(measured=float("inf"))
    )

    assert finding.result == "invalid"


def test_visual_finding_keeps_explicit_mock_mode():
    finding = visual_finding(
        mode="mock",
        result="fail",
        note="模拟目视：孔位与图纸不符（合成数据）",
    )

    assert finding.mode == "mock"
    assert finding.result == "fail"
    assert finding.parameter_key == "visualCheck"
    assert "模拟" in finding.reason


def test_combine_results_prefers_definite_failure_and_invalid():
    assert combine_results(["pass", "pass"]) == "pass"
    assert combine_results(["pass", "incomplete"]) == "incomplete"
    assert combine_results(["incomplete", "fail"]) == "fail"
    assert combine_results(["fail", "invalid"]) == "invalid"
    assert combine_results([]) == "incomplete"
