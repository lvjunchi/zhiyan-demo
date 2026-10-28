from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

RelationStatus = Literal["satisfied", "violated", "invalid", "unsupported"]
ConflictType = Literal[
    "parameter", "version", "reference", "condition", "rule"
]
Severity = Literal["low", "medium", "high", "blocking"]

_OPERATOR_ALIASES = {"≥": ">=", "≤": "<="}
_SUPPORTED_OPERATORS = {">", ">=", "<", "<=", "="}
_NUMERIC_DATA_TYPES = {"numeric", "range"}
_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class RelationEvaluation:
    status: RelationStatus
    reason: str
    operator: str | None
    left_value: float | None
    right_value: float | None


@dataclass(frozen=True)
class RequirementRecord:
    id: str
    display_code: str
    parameter_name: str
    data_type: str
    operator: str
    value_num: float | None
    unit: str
    review_status: str
    validity: str
    current_revision: int
    source_document_id: str | None
    source_excerpt: str


@dataclass(frozen=True)
class RequirementReferenceRecord:
    id: str
    requirement_id: str
    referenced_requirement_id: str
    relation: str


@dataclass(frozen=True)
class ArtifactRecord:
    object_type: str
    object_id: str
    display_code: str
    revision: int
    review_status: str
    reason: str


@dataclass(frozen=True)
class TestCaseRecord:
    __test__ = False

    id: str
    display_code: str
    revision: int
    review_status: str
    validity: str
    minimum_coefficient: float
    load_basis_requirement_id: str | None
    is_static_torsion: bool


@dataclass(frozen=True)
class TestRunRecord:
    __test__ = False

    id: str
    case_id: str
    case_revision: int
    status: str
    result: str | None
    load_basis_numeric: float | None
    backup_coefficient: float | None
    created_at: str


@dataclass(frozen=True)
class ConsistencyInputs:
    requirements: tuple[RequirementRecord, ...] = ()
    references: tuple[RequirementReferenceRecord, ...] = ()
    stale_artifacts: tuple[ArtifactRecord, ...] = ()
    test_cases: tuple[TestCaseRecord, ...] = ()
    latest_runs: tuple[TestRunRecord, ...] = ()


@dataclass(frozen=True)
class ConflictCandidate:
    stable_key: str
    conflict_type: ConflictType
    severity: Severity
    title: str
    detail: str
    object_type: str
    object_id: str
    object_revision: int
    object_review_status: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _format_value(value: float | None, unit: str) -> str:
    if value is None:
        return "缺失"
    suffix = f" {unit}" if unit else ""
    return f"{value:g}{suffix}"


def evaluate_relation(
    *,
    left_value: float | None,
    left_unit: str,
    left_data_type: str,
    relation: str,
    right_value: float | None,
    right_unit: str,
    right_data_type: str,
) -> RelationEvaluation:
    operator = _OPERATOR_ALIASES.get(relation.strip(), relation.strip())
    if operator not in _SUPPORTED_OPERATORS:
        return RelationEvaluation(
            status="unsupported",
            reason=f"不支持的比较运算符：{relation}",
            operator=operator or None,
            left_value=left_value,
            right_value=right_value,
        )
    if (
        left_data_type not in _NUMERIC_DATA_TYPES
        or right_data_type not in _NUMERIC_DATA_TYPES
    ):
        return RelationEvaluation(
            status="unsupported",
            reason="非数值类型需求不能用于自动数值比较",
            operator=operator,
            left_value=left_value,
            right_value=right_value,
        )
    if (
        left_value is None
        or right_value is None
        or not math.isfinite(left_value)
        or not math.isfinite(right_value)
    ):
        return RelationEvaluation(
            status="invalid",
            reason="比较值为空或不是有限数值",
            operator=operator,
            left_value=left_value,
            right_value=right_value,
        )

    left_unit = left_unit.strip()
    right_unit = right_unit.strip()
    if bool(left_unit) != bool(right_unit):
        missing_side = "左侧" if not left_unit else "右侧"
        return RelationEvaluation(
            status="invalid",
            reason=f"单位缺失：{missing_side}未提供单位，不按数值直接比较",
            operator=operator,
            left_value=left_value,
            right_value=right_value,
        )
    if left_unit and right_unit and left_unit != right_unit:
        return RelationEvaluation(
            status="invalid",
            reason=(
                f"单位不一致：左侧 {left_unit}，右侧 {right_unit}，"
                "不按数值直接比较"
            ),
            operator=operator,
            left_value=left_value,
            right_value=right_value,
        )

    if operator == ">=":
        satisfied = left_value >= right_value
    elif operator == ">":
        satisfied = left_value > right_value
    elif operator == "<=":
        satisfied = left_value <= right_value
    elif operator == "<":
        satisfied = left_value < right_value
    else:
        satisfied = left_value == right_value

    unit_text = f" {left_unit}" if left_unit else ""
    reason = (
        f"{left_value:g}{unit_text} {operator} "
        f"{right_value:g}{unit_text} "
        f"{'成立' if satisfied else '不成立'}"
    )
    return RelationEvaluation(
        status="satisfied" if satisfied else "violated",
        reason=reason,
        operator=operator,
        left_value=left_value,
        right_value=right_value,
    )


def conflict_key(
    conflict_type: str,
    object_type: str,
    object_id: str,
    discriminator: str = "",
) -> str:
    return f"{conflict_type}:{object_type}:{object_id}:{discriminator}"


def _review_note(review_status: str) -> str:
    labels = {
        "draft": "待审核",
        "pending_review": "审核中",
        "rejected": "已驳回",
        "confirmed": "已确认",
    }
    label = labels.get(review_status, review_status or "无审核状态")
    return f"审核状态：{review_status or '未记录'}（{label}）"


def _parameter_conflicts(
    inputs: ConsistencyInputs,
) -> list[ConflictCandidate]:
    requirements = {item.id: item for item in inputs.requirements}
    conflicts: list[ConflictCandidate] = []
    for reference in inputs.references:
        left = requirements.get(reference.requirement_id)
        right = requirements.get(reference.referenced_requirement_id)
        if left is None or right is None:
            missing = reference.requirement_id if left is None else (
                reference.referenced_requirement_id
            )
            conflicts.append(
                ConflictCandidate(
                    stable_key=conflict_key(
                        "reference", "requirement_reference", reference.id
                    ),
                    conflict_type="reference",
                    severity="medium",
                    title="需求引用对象缺失",
                    detail=f"引用关系 {reference.id} 指向不存在的需求 {missing}",
                    object_type="requirement_reference",
                    object_id=reference.id,
                    object_revision=1,
                    object_review_status="",
                    evidence={"requirement_id": reference.requirement_id},
                )
            )
            continue

        evaluation = evaluate_relation(
            left_value=left.value_num,
            left_unit=left.unit,
            left_data_type=left.data_type,
            relation=reference.relation,
            right_value=right.value_num,
            right_unit=right.unit,
            right_data_type=right.data_type,
        )
        if evaluation.status == "satisfied":
            continue
        severity: Severity
        if evaluation.status == "violated":
            severity = "blocking"
            title = "参数关系冲突"
        elif evaluation.status == "invalid":
            severity = "medium"
            title = "参数关系无法判定"
        else:
            severity = "medium"
            title = "参数关系未自动判定"
        left_text = _format_value(left.value_num, left.unit)
        right_text = _format_value(right.value_num, right.unit)
        conflicts.append(
            ConflictCandidate(
                stable_key=conflict_key(
                    "parameter", "requirement_reference", reference.id
                ),
                conflict_type="parameter",
                severity=severity,
                title=title,
                detail=(
                    f"{left.display_code} {left.parameter_name}（{left_text}）"
                    f" {reference.relation} "
                    f"{right.display_code} {right.parameter_name}"
                    f"（{right_text}）：{evaluation.reason}；"
                    f"{_review_note(left.review_status)}"
                ),
                object_type="requirement",
                object_id=left.id,
                object_revision=left.current_revision,
                object_review_status=left.review_status,
                evidence={
                    "relation": reference.relation,
                    "left_display_code": left.display_code,
                    "left_value": left.value_num,
                    "left_unit": left.unit,
                    "right_display_code": right.display_code,
                    "right_value": right.value_num,
                    "right_unit": right.unit,
                    "evaluation": evaluation.status,
                },
            )
        )
    return conflicts


def _citation_conflicts(
    inputs: ConsistencyInputs,
) -> list[ConflictCandidate]:
    conflicts: list[ConflictCandidate] = []
    for requirement in inputs.requirements:
        if (
            requirement.data_type not in _NUMERIC_DATA_TYPES
            or not requirement.source_excerpt
            or requirement.value_num is None
            or not math.isfinite(requirement.value_num)
        ):
            continue
        numbers = [
            float(match)
            for match in _NUMBER_PATTERN.findall(requirement.source_excerpt)
        ]
        if not numbers:
            continue
        if any(abs(number - requirement.value_num) <= 1e-9 for number in numbers):
            continue
        conflicts.append(
            ConflictCandidate(
                stable_key=conflict_key(
                    "reference", "requirement", requirement.id, "citation"
                ),
                conflict_type="reference",
                severity="high",
                title="来源摘录与当前数值不一致",
                detail=(
                    f"{requirement.display_code} 当前值为 "
                    f"{_format_value(requirement.value_num, requirement.unit)}，"
                    f"但来源摘录仍为“{requirement.source_excerpt}”；"
                    f"{_review_note(requirement.review_status)}"
                ),
                object_type="requirement",
                object_id=requirement.id,
                object_revision=requirement.current_revision,
                object_review_status=requirement.review_status,
                evidence={
                    "source_excerpt": requirement.source_excerpt,
                    "numbers_in_excerpt": numbers,
                    "current_value": requirement.value_num,
                    "source_document_id": requirement.source_document_id,
                },
            )
        )
    return conflicts


def _version_conflicts(
    inputs: ConsistencyInputs,
) -> list[ConflictCandidate]:
    conflicts: list[ConflictCandidate] = []
    for artifact in inputs.stale_artifacts:
        conflicts.append(
            ConflictCandidate(
                stable_key=conflict_key(
                    "version", artifact.object_type, artifact.object_id
                ),
                conflict_type="version",
                severity="high",
                title="下游产物引用了过期版本",
                detail=(
                    f"{artifact.display_code}（{artifact.object_type}，"
                    f"版本 {artifact.revision}）已失效：{artifact.reason}；"
                    f"{_review_note(artifact.review_status)}"
                ),
                object_type=artifact.object_type,
                object_id=artifact.object_id,
                object_revision=artifact.revision,
                object_review_status=artifact.review_status,
                evidence={"reason": artifact.reason},
            )
        )

    cases = {item.id: item for item in inputs.test_cases}
    for run in inputs.latest_runs:
        case = cases.get(run.case_id)
        if case is None or run.case_revision == case.revision:
            continue
        conflicts.append(
            ConflictCandidate(
                stable_key=conflict_key("version", "test_run", run.id),
                conflict_type="version",
                severity="high",
                title="执行记录绑定了旧用例版本",
                detail=(
                    f"{case.display_code} 当前用例版本为 {case.revision}，"
                    f"最近执行 {run.id} 绑定版本 {run.case_revision}；"
                    "旧执行不能替代当前版本结论"
                ),
                object_type="test_run",
                object_id=run.id,
                object_revision=run.case_revision,
                object_review_status=case.review_status,
                evidence={
                    "case_id": case.id,
                    "case_display_code": case.display_code,
                    "case_revision": case.revision,
                    "run_case_revision": run.case_revision,
                },
            )
        )
    return conflicts


def _run_conflicts(
    inputs: ConsistencyInputs,
) -> list[ConflictCandidate]:
    requirements = {item.id: item for item in inputs.requirements}
    cases = {item.id: item for item in inputs.test_cases}
    conflicts: list[ConflictCandidate] = []
    for run in inputs.latest_runs:
        case = cases.get(run.case_id)
        if case is None or not case.is_static_torsion:
            continue
        expected = requirements.get(case.load_basis_requirement_id or "")
        expected_value = expected.value_num if expected is not None else None
        expected_unit = expected.unit if expected is not None else ""

        condition_severity: Severity | None = None
        condition_reason = ""
        if run.load_basis_numeric is None:
            condition_severity = "medium"
            condition_reason = "执行记录缺少加载基准"
        elif not math.isfinite(run.load_basis_numeric):
            condition_severity = "medium"
            condition_reason = "执行加载基准不是有限数值"
        elif expected_value is None or not math.isfinite(expected_value):
            condition_severity = "medium"
            condition_reason = "当前需求缺少可比的加载基准数值"
        elif abs(run.load_basis_numeric - expected_value) > 1e-9:
            condition_severity = "high"
            condition_reason = (
                f"执行加载基准 "
                f"{_format_value(run.load_basis_numeric, expected_unit)} "
                f"与当前需求 "
                f"{_format_value(expected_value, expected_unit)} 不一致"
            )
        if condition_severity is not None:
            conflicts.append(
                ConflictCandidate(
                    stable_key=conflict_key(
                        "condition", "test_case", case.id, "load_basis"
                    ),
                    conflict_type="condition",
                    severity=condition_severity,
                    title="试验工况与当前需求不一致",
                    detail=(
                        f"{case.display_code}（用例版本 {case.revision}）："
                        f"{condition_reason}；{_review_note(case.review_status)}"
                    ),
                    object_type="test_case",
                    object_id=case.id,
                    object_revision=case.revision,
                    object_review_status=case.review_status,
                    evidence={
                        "run_id": run.id,
                        "load_basis_numeric": run.load_basis_numeric,
                        "expected_value": expected_value,
                        "expected_unit": expected_unit,
                    },
                )
            )

        rule_severity: Severity | None = None
        rule_reason = ""
        coefficient = run.backup_coefficient
        if coefficient is None:
            rule_severity = "medium"
            rule_reason = "执行记录缺少无量纲后备系数"
        elif not math.isfinite(coefficient):
            rule_severity = "medium"
            rule_reason = "后备系数不是有限数值"
        elif coefficient + 1e-9 < case.minimum_coefficient:
            rule_severity = "high"
            rule_reason = (
                f"后备系数 {coefficient:g} 低于适用规则要求 "
                f"{case.minimum_coefficient:g}"
            )
        if rule_severity is not None:
            conflicts.append(
                ConflictCandidate(
                    stable_key=conflict_key(
                        "rule", "test_case", case.id, "backup_coefficient"
                    ),
                    conflict_type="rule",
                    severity=rule_severity,
                    title="适用规则冲突",
                    detail=f"{case.display_code}：{rule_reason}",
                    object_type="test_case",
                    object_id=case.id,
                    object_revision=case.revision,
                    object_review_status=case.review_status,
                    evidence={
                        "run_id": run.id,
                        "backup_coefficient": coefficient,
                        "minimum_coefficient": case.minimum_coefficient,
                    },
                )
            )
    return conflicts


def detect_conflicts(
    inputs: ConsistencyInputs,
) -> tuple[ConflictCandidate, ...]:
    conflicts = [
        *_parameter_conflicts(inputs),
        *_citation_conflicts(inputs),
        *_version_conflicts(inputs),
        *_run_conflicts(inputs),
    ]
    return tuple(
        sorted(conflicts, key=lambda item: (item.conflict_type, item.stable_key))
    )


def summarize_conflicts(
    conflicts: tuple[ConflictCandidate, ...] | list[ConflictCandidate],
) -> dict[str, Any]:
    by_type = {
        key: 0
        for key in ("parameter", "version", "reference", "condition", "rule")
    }
    by_severity = {
        key: 0 for key in ("low", "medium", "high", "blocking")
    }
    for item in conflicts:
        by_type[item.conflict_type] = by_type.get(item.conflict_type, 0) + 1
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
    return {
        "total": len(conflicts),
        "by_type": by_type,
        "by_severity": by_severity,
        "blocking": by_severity.get("blocking", 0),
        "review_pending": sum(
            1
            for item in conflicts
            if item.object_review_status in ("draft", "pending_review", "rejected")
        ),
    }
