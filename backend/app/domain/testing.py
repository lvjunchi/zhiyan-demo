from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

RunResult = Literal["pass", "fail", "incomplete", "invalid"]


@dataclass(frozen=True)
class ScopeItem:
    key: str
    label: str
    display_hint: str


VALIDATION_SCOPE = (
    ScopeItem("gearboxRatedInputTorque", "变速器最低额定输入扭矩", "C-002"),
    ScopeItem("gearCount", "档位数", "C-001"),
    ScopeItem("pto", "取力器功能", "C-006"),
    ScopeItem("assemblyWeight", "总成重量上限", "D-002"),
    ScopeItem("durability", "耐久要求", "F-001"),
)


@dataclass(frozen=True)
class RequirementRef:
    requirement_id: str
    display_code: str
    revision: int
    current_revision: int = 1


@dataclass(frozen=True)
class RunSnapshot:
    id: str
    run_no: int
    status: str
    result: str | None
    case_revision: int
    mode: str
    created_at: str


@dataclass(frozen=True)
class CaseSnapshot:
    id: str
    display_code: str
    title: str
    revision: int
    review_status: str
    validity: str
    conditions_text: str
    load_conditions_text: str
    acceptance_criteria: str
    requirement_refs: tuple[RequirementRef, ...]
    fmea_refs: tuple[dict[str, object], ...] = ()
    latest_run: RunSnapshot | None = None


@dataclass(frozen=True)
class ScopeRequirement:
    key: str
    label: str
    requirement_id: str | None
    display_code: str | None
    revision: int | None


@dataclass
class RunEvaluation:
    result: RunResult
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TraceabilityItem:
    key: str
    label: str
    requirement_id: str | None
    display_code: str | None
    requirement_revision: int | None
    covered: bool
    valid_case_ids: tuple[str, ...]
    pending_case_ids: tuple[str, ...]
    execution: str
    reason: str | None = None
    latest_runs: tuple[RunSnapshot, ...] = ()


@dataclass(frozen=True)
class Traceability:
    items: tuple[TraceabilityItem, ...]
    denominator: int
    covered_count: int
    coverage_percentage: float
    pending_review: tuple[dict[str, str], ...]
    execution_summary: dict[str, int]

    @property
    def uncovered(self) -> tuple[TraceabilityItem, ...]:
        return tuple(item for item in self.items if not item.covered)


def is_case_complete(case: CaseSnapshot) -> bool:
    return bool(
        case.conditions_text.strip()
        and case.load_conditions_text.strip()
        and case.acceptance_criteria.strip()
        and case.requirement_refs
    )


def is_case_covered(case: CaseSnapshot) -> bool:
    if case.review_status != "confirmed" or case.validity != "current":
        return False
    if not is_case_complete(case):
        return False
    return all(
        reference.revision == reference.current_revision
        for reference in case.requirement_refs
    ) and all(
        ref.get("revision") == ref.get("current_revision")
        and ref.get("current_validity") == "current"
        for ref in case.fmea_refs
    )


def evaluate_static_torsion(
    load_basis: float | None,
    expected_load_basis: float | None,
    backup_coefficient: float | None,
    minimum_coefficient: float = 2.5,
) -> RunEvaluation:
    missing = []
    if load_basis is None:
        missing.append("loadBasis")
    if backup_coefficient is None:
        missing.append("backupCoefficient")
    if missing:
        return RunEvaluation(
            "incomplete",
            ["缺少加载基准或后备系数，不能判定"],
            missing,
        )

    assert load_basis is not None
    assert backup_coefficient is not None
    if not math.isfinite(load_basis) or load_basis <= 0:
        return RunEvaluation("invalid", ["加载基准不是有效的正数"])
    if not math.isfinite(backup_coefficient):
        return RunEvaluation("invalid", ["后备系数不是有限数值"])
    if backup_coefficient < 0:
        return RunEvaluation("invalid", ["后备系数不能为负数"])

    if expected_load_basis is None or not math.isfinite(expected_load_basis):
        return RunEvaluation(
            "invalid",
            ["当前发动机最大扭矩缺失，无法核对加载基准"],
        )
    if not math.isclose(load_basis, expected_load_basis, rel_tol=0.0, abs_tol=1e-9):
        return RunEvaluation(
            "invalid",
            [
                "加载基准与当前需求版本不一致："
                f"记录 {load_basis:g}，当前基准 {expected_load_basis:g}"
            ],
        )

    if backup_coefficient < minimum_coefficient:
        return RunEvaluation(
            "fail",
            [
                f"后备系数 {backup_coefficient:g} < "
                f"{minimum_coefficient:g}，判定失败；"
                "后备系数为无量纲值，不与扭矩直接比较"
            ],
        )
    return RunEvaluation(
        "pass",
        [
            f"后备系数 {backup_coefficient:g} ≥ "
            f"{minimum_coefficient:g}，且加载基准与当前版本一致"
        ],
    )


def _pending_reason(case: CaseSnapshot) -> str:
    if case.validity != "current":
        return "stale"
    if case.review_status != "confirmed":
        return case.review_status
    if not is_case_complete(case):
        return "criteria_incomplete"
    if any(
        reference.revision != reference.current_revision
        for reference in case.requirement_refs
    ):
        return "revision_mismatch"
    return "not_eligible"


def _case_references(
    case: CaseSnapshot, scope_requirement: ScopeRequirement
) -> list[RequirementRef]:
    if scope_requirement.requirement_id is None:
        return []
    return [
        reference
        for reference in case.requirement_refs
        if reference.requirement_id == scope_requirement.requirement_id
    ]


def _execution_for(
    valid_cases: list[CaseSnapshot],
) -> tuple[str, tuple[RunSnapshot, ...]]:
    if not valid_cases:
        return "not_run", ()
    latest_runs = tuple(
        case.latest_run for case in valid_cases if case.latest_run is not None
    )
    results = [
        run.result
        for run in latest_runs
        if run.status == "completed" and run.result is not None
    ]
    if "fail" in results:
        return "fail", latest_runs
    if "invalid" in results:
        return "invalid", latest_runs
    if "incomplete" in results:
        return "incomplete", latest_runs
    if any(run.status == "running" for run in latest_runs):
        return "running", latest_runs
    if len(latest_runs) < len(valid_cases):
        return "not_run", latest_runs
    if all(run.status == "completed" and run.result == "pass" for run in latest_runs):
        return "pass", latest_runs
    return "not_run", latest_runs


def build_traceability(
    scope_requirements: list[ScopeRequirement] | tuple[ScopeRequirement, ...],
    cases: list[CaseSnapshot] | tuple[CaseSnapshot, ...],
) -> Traceability:
    items: list[TraceabilityItem] = []
    pending_review: list[dict[str, str]] = []
    execution_summary = {
        "pass": 0,
        "fail": 0,
        "incomplete": 0,
        "invalid": 0,
        "running": 0,
        "not_run": 0,
    }

    for scope_requirement in scope_requirements:
        valid_cases: list[CaseSnapshot] = []
        pending_cases: list[CaseSnapshot] = []
        if scope_requirement.requirement_id is not None:
            for case in cases:
                references = _case_references(case, scope_requirement)
                if not references:
                    continue
                matches_current = any(
                    reference.revision == scope_requirement.revision
                    and reference.current_revision == scope_requirement.revision
                    for reference in references
                )
                if is_case_covered(case) and matches_current:
                    valid_cases.append(case)
                elif case not in pending_cases:
                    pending_cases.append(case)

        for case in pending_cases:
            pending_review.append(
                {
                    "case_id": case.id,
                    "display_code": case.display_code,
                    "requirement_key": scope_requirement.key,
                    "reason": _pending_reason(case),
                }
            )

        execution, latest_runs = _execution_for(valid_cases)
        execution_summary[execution] += 1

        if scope_requirement.requirement_id is None:
            reason = "requirement_missing"
        elif valid_cases:
            reason = None
        elif pending_cases:
            reason = _pending_reason(pending_cases[0])
        else:
            reason = "no_case"

        items.append(
            TraceabilityItem(
                key=scope_requirement.key,
                label=scope_requirement.label,
                requirement_id=scope_requirement.requirement_id,
                display_code=scope_requirement.display_code,
                requirement_revision=scope_requirement.revision,
                covered=bool(valid_cases),
                valid_case_ids=tuple(case.id for case in valid_cases),
                pending_case_ids=tuple(case.id for case in pending_cases),
                execution=execution,
                reason=reason,
                latest_runs=latest_runs,
            )
        )

    denominator = len(VALIDATION_SCOPE)
    covered_count = sum(1 for item in items if item.covered)
    percentage = round(covered_count / denominator * 100, 1)
    return Traceability(
        items=tuple(items),
        denominator=denominator,
        covered_count=covered_count,
        coverage_percentage=percentage,
        pending_review=tuple(pending_review),
        execution_summary=execution_summary,
    )
