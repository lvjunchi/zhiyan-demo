from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

ComparisonResult = Literal["pass", "fail", "incomplete", "invalid"]
_RESULT_PRECEDENCE = ("invalid", "fail", "incomplete", "pass")


@dataclass(frozen=True)
class ParameterSpec:
    parameter_key: str
    parameter_name: str
    expected_value: float
    tolerance: float
    unit: str
    source_note: str


@dataclass(frozen=True)
class ParameterMeasurement:
    parameter_key: str
    measured_value: float | None
    unit: str


@dataclass(frozen=True)
class Finding:
    parameter_key: str
    parameter_name: str
    mode: str
    expected_value: float | None
    measured_value: float | None
    tolerance: float | None
    unit: str
    result: ComparisonResult
    reason: str
    source_note: str


def compare_parameter(
    spec: ParameterSpec, measurement: ParameterMeasurement
) -> Finding:
    common = {
        "parameter_key": spec.parameter_key,
        "parameter_name": spec.parameter_name,
        "mode": "rule",
        "expected_value": spec.expected_value,
        "tolerance": spec.tolerance,
        "unit": spec.unit,
        "source_note": spec.source_note,
    }
    measured = measurement.measured_value
    if measured is None:
        return Finding(
            **common,
            measured_value=None,
            result="incomplete",
            reason="未提供实测值，证据不足，不能判定合格",
        )
    if not math.isfinite(measured):
        return Finding(
            **common,
            measured_value=None,
            result="invalid",
            reason="实测值不是有限数值",
        )
    if not math.isfinite(spec.expected_value):
        return Finding(
            **common,
            measured_value=measured,
            result="invalid",
            reason="图纸标注值不是有限数值",
        )
    if not math.isfinite(spec.tolerance) or spec.tolerance < 0:
        return Finding(
            **common,
            measured_value=measured,
            result="invalid",
            reason="公差缺失或为负数",
        )
    if bool(measurement.unit) != bool(spec.unit):
        missing_side = "实测" if not measurement.unit else "图纸"
        return Finding(
            **common,
            measured_value=measured,
            result="invalid",
            reason=f"单位缺失：{missing_side}未提供单位；不按数值直接比较",
        )
    if measurement.unit and spec.unit and measurement.unit != spec.unit:
        return Finding(
            **common,
            measured_value=measured,
            result="invalid",
            reason=(
                f"单位不一致：实测 {measurement.unit}，"
                f"图纸 {spec.unit}；不按数值直接比较"
            ),
        )

    deviation = abs(measured - spec.expected_value)
    if deviation <= spec.tolerance + 1e-9:
        return Finding(
            **common,
            measured_value=measured,
            result="pass",
            reason=(
                f"偏差 {deviation:g} {spec.unit} ≤ "
                f"公差 {spec.tolerance:g} {spec.unit}"
            ),
        )
    return Finding(
        **common,
        measured_value=measured,
        result="fail",
        reason=(
            f"偏差 {deviation:g} {spec.unit} > "
            f"公差 {spec.tolerance:g} {spec.unit}"
        ),
    )


def visual_finding(
    mode: Literal["mock", "manual"], result: ComparisonResult, note: str
) -> Finding:
    label = "模拟目视" if mode == "mock" else "人工目视"
    return Finding(
        parameter_key="visualCheck",
        parameter_name="目视检查",
        mode=mode,
        expected_value=None,
        measured_value=None,
        tolerance=None,
        unit="",
        result=result,
        reason=f"{label}结论：{note}",
        source_note=note,
    )


def combine_results(
    results: list[ComparisonResult] | tuple[ComparisonResult, ...],
) -> ComparisonResult:
    if not results:
        return "incomplete"
    for candidate in _RESULT_PRECEDENCE:
        if candidate in results:
            return candidate
    return "incomplete"
