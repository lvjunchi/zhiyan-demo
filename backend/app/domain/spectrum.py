from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

CRITICAL_REQUIREMENT_KEYS = (
    "transmissionType",
    "gearCount",
    "gearboxRatedInputTorque",
)
WEIGHTS = {
    "torqueMargin": 0.45,
    "pto": 0.25,
    "weightMargin": 0.20,
    "topGearType": 0.10,
}
WEIGHT_REFERENCE_KG = 250.0


@dataclass(frozen=True)
class CandidateBase:
    id: str
    display_code: str
    name: str
    transmission_type: str
    gear_count: int
    rated_input_torque: float
    first_gear_ratio: float
    top_gear_type: str
    has_pto: bool
    weight_kg: float
    source: str


@dataclass(frozen=True)
class MatchRequirement:
    key: str
    requirement_id: str
    display_code: str
    revision: int
    value: str
    unit: str
    operator: str


@dataclass
class CriterionResult:
    criterion: str
    requirement_value: str | None
    candidate_value: str | None
    weight: float
    score: float | None
    satisfied: bool | None
    hard_constraint: bool
    reason: str
    source: str


@dataclass
class CandidateEvaluation:
    base: CandidateBase
    score: float
    hard_failures: list[str] = field(default_factory=list)
    satisfied_items: list[str] = field(default_factory=list)
    unsatisfied_items: list[str] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    criteria: list[CriterionResult] = field(default_factory=list)


@dataclass
class RecommendationResult:
    top3: list[CandidateEvaluation]
    candidate_count: int
    candidate_shortage: bool
    missing_requirements: list[str]
    requirement_versions: list[dict[str, object]]


def _compare(actual: float, operator: str, expected: float) -> bool:
    if operator in {">=", "≥"}:
        return actual >= expected
    if operator == ">":
        return actual > expected
    if operator in {"<=", "≤"}:
        return actual <= expected
    if operator == "<":
        return actual < expected
    if operator in {"=", "eq"}:
        return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
    return False


def _to_float(value: str) -> float | None:
    try:
        number = float(value.replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _top_gear_value(requirement: MatchRequirement) -> tuple[str | None, str]:
    text = requirement.value
    if "或" in text or ("直接档" in text and "超速档" in text):
        return None, "需求未定型（直接档或超速档）"
    if "直接档" in text:
        return "direct", "需求明确为直接档"
    if "超速档" in text:
        return "overdrive", "需求明确为超速档"
    return None, "需求值无法识别"


def _criterion(
    *,
    name: str,
    requirement: MatchRequirement | None,
    candidate_value: str,
    weight: float,
    score: float | None,
    satisfied: bool | None,
    hard_constraint: bool,
    reason: str,
    source: str,
) -> CriterionResult:
    return CriterionResult(
        criterion=name,
        requirement_value=(
            f"{requirement.operator} {requirement.value} {requirement.unit}".strip()
            if requirement
            else None
        ),
        candidate_value=candidate_value,
        weight=weight,
        score=score,
        satisfied=satisfied,
        hard_constraint=hard_constraint,
        reason=reason,
        source=source,
    )


def _evaluate(
    candidate: CandidateBase,
    requirements: dict[str, MatchRequirement],
) -> CandidateEvaluation:
    criteria: list[CriterionResult] = []
    hard_failures: list[str] = []
    satisfied_items: list[str] = []
    unsatisfied_items: list[str] = []
    missing_items: list[str] = []
    source = candidate.source

    def hard(
        name: str,
        requirement: MatchRequirement | None,
        candidate_value: str,
        satisfied: bool | None,
        reason: str,
    ) -> None:
        if requirement is None:
            missing_items.append(name)
            criteria.append(
                _criterion(
                    name=name,
                    requirement=None,
                    candidate_value=candidate_value,
                    weight=0.0,
                    score=None,
                    satisfied=None,
                    hard_constraint=True,
                    reason="需求缺失，无法判定硬约束",
                    source=source,
                )
            )
            return
        criteria.append(
            _criterion(
                name=name,
                requirement=requirement,
                candidate_value=candidate_value,
                weight=0.0,
                score=(
                    None
                    if satisfied is None
                    else 100.0
                    if satisfied
                    else 0.0
                ),
                satisfied=satisfied,
                hard_constraint=True,
                reason=reason,
                source=source,
            )
        )
        if satisfied is False:
            hard_failures.append(name)
        elif satisfied is None:
            missing_items.append(name)

    def soft(
        name: str,
        requirement: MatchRequirement | None,
        candidate_value: str,
        weight: float,
        score: float | None,
        satisfied: bool | None,
        reason: str,
    ) -> None:
        criteria.append(
            _criterion(
                name=name,
                requirement=requirement,
                candidate_value=candidate_value,
                weight=weight,
                score=score,
                satisfied=satisfied,
                hard_constraint=False,
                reason=reason,
                source=source,
            )
        )
        if score is None:
            missing_items.append(name)
        elif satisfied:
            satisfied_items.append(name)
        else:
            unsatisfied_items.append(name)

    transmission = requirements.get("transmissionType")
    hard(
        "transmissionType",
        transmission,
        candidate.transmission_type,
        (
            candidate.transmission_type == transmission.value
            if transmission
            else None
        ),
        (
            f"候选为 {candidate.transmission_type}，需求为 {transmission.value}"
            if transmission
            else ""
        ),
    )

    gear = requirements.get("gearCount")
    gear_expected = _to_float(gear.value) if gear else None
    hard(
        "gearCount",
        gear,
        str(candidate.gear_count),
        (
            gear_expected is not None
            and candidate.gear_count == int(gear_expected)
            if gear
            else None
        ),
        (
            f"候选 {candidate.gear_count} 档，需求 {gear.value} 档"
            if gear
            else ""
        ),
    )

    torque = requirements.get("gearboxRatedInputTorque")
    torque_expected = _to_float(torque.value) if torque else None
    hard(
        "gearboxRatedInputTorque",
        torque,
        f"{candidate.rated_input_torque:g} N·m",
        (
            _compare(
                candidate.rated_input_torque,
                torque.operator,
                torque_expected,
            )
            if torque and torque_expected is not None
            else None
        ),
        (
            f"候选 {candidate.rated_input_torque:g} N·m，"
            f"需求 {torque.operator} {torque.value} N·m"
            if torque and torque_expected is not None
            else "需求值无法解析"
        ),
    )

    ratio = requirements.get("firstGearRatio")
    ratio_expected = _to_float(ratio.value) if ratio else None
    hard(
        "firstGearRatio",
        ratio,
        f"{candidate.first_gear_ratio:g}",
        (
            _compare(
                candidate.first_gear_ratio,
                ratio.operator,
                ratio_expected,
            )
            if ratio and ratio_expected is not None
            else None
        ),
        (
            f"候选一档速比 {candidate.first_gear_ratio:g}，"
            f"需求 {ratio.operator} {ratio.value}"
            if ratio and ratio_expected is not None
            else "需求值无法解析"
        ),
    )

    weight = requirements.get("assemblyWeight")
    weight_expected = _to_float(weight.value) if weight else None
    weight_ok = (
        _compare(candidate.weight_kg, weight.operator, weight_expected)
        if weight and weight_expected is not None
        else None
    )
    hard(
        "assemblyWeight",
        weight,
        f"{candidate.weight_kg:g} kg",
        weight_ok,
        (
            f"候选 {candidate.weight_kg:g} kg，"
            f"需求 {weight.operator} {weight.value} kg"
            if weight and weight_expected is not None
            else "需求值无法解析"
        ),
    )

    torque_score: float | None = None
    if torque and torque_expected and torque_expected > 0:
        if candidate.rated_input_torque >= torque_expected:
            torque_score = max(
                0.0,
                100.0
                - (
                    (candidate.rated_input_torque - torque_expected)
                    / torque_expected
                )
                * 100.0,
            )
        else:
            torque_score = 0.0
    soft(
        "torqueMargin",
        torque,
        f"{candidate.rated_input_torque:g} N·m",
        WEIGHTS["torqueMargin"],
        torque_score,
        (
            candidate.rated_input_torque >= torque_expected
            if torque_expected is not None
            else None
        ),
        "额定输入扭矩相对需求的余量",
    )

    pto = requirements.get("pto")
    pto_required = (
        pto.value in {"required", "需要", "true", "yes", "是", "有"}
        if pto
        else None
    )
    pto_score: float | None = None
    pto_satisfied: bool | None = None
    if pto_required is not None:
        if pto_required:
            pto_satisfied = candidate.has_pto
            pto_score = 100.0 if candidate.has_pto else 0.0
        else:
            pto_satisfied = not candidate.has_pto
            pto_score = 100.0 if not candidate.has_pto else 50.0
    soft(
        "pto",
        pto,
        "有取力器" if candidate.has_pto else "无取力器",
        WEIGHTS["pto"],
        pto_score,
        pto_satisfied,
        (
            "需求要求取力器，候选需新增取力器接口"
            if pto_required
            else "需求未要求取力器"
            if pto_required is False
            else "需求缺失"
        ),
    )

    weight_score: float | None = None
    if weight and weight_expected is not None and weight_expected > 0:
        if candidate.weight_kg > weight_expected:
            weight_score = 0.0
        elif candidate.weight_kg <= WEIGHT_REFERENCE_KG:
            weight_score = 100.0
        else:
            weight_score = max(
                0.0,
                100.0
                - (
                    (candidate.weight_kg - WEIGHT_REFERENCE_KG)
                    / (weight_expected - WEIGHT_REFERENCE_KG)
                )
                * 100.0,
            )
    soft(
        "weightMargin",
        weight,
        f"{candidate.weight_kg:g} kg",
        WEIGHTS["weightMargin"],
        weight_score,
        (
            candidate.weight_kg <= weight_expected
            if weight_expected is not None
            else None
        ),
        "总成重量相对上限的余量",
    )

    top_gear = requirements.get("topGearType")
    top_gear_required: str | None = None
    top_gear_reason = "需求缺失"
    if top_gear:
        top_gear_required, top_gear_reason = _top_gear_value(top_gear)
    if top_gear_required is None:
        top_gear_score = None
        top_gear_satisfied = None
    else:
        top_gear_satisfied = candidate.top_gear_type == top_gear_required
        top_gear_score = 100.0 if top_gear_satisfied else 0.0
    soft(
        "topGearType",
        top_gear,
        candidate.top_gear_type,
        WEIGHTS["topGearType"],
        top_gear_score,
        top_gear_satisfied,
        top_gear_reason,
    )

    applicable = [
        criterion
        for criterion in criteria
        if criterion.weight > 0 and criterion.score is not None
    ]
    weight_sum = sum(criterion.weight for criterion in applicable)
    score = (
        round(
            sum(
                criterion.weight * (criterion.score or 0.0)
                for criterion in applicable
            )
            / weight_sum,
            2,
        )
        if weight_sum
        else 0.0
    )

    return CandidateEvaluation(
        base=candidate,
        score=score,
        hard_failures=hard_failures,
        satisfied_items=satisfied_items,
        unsatisfied_items=unsatisfied_items,
        missing_items=missing_items,
        criteria=criteria,
    )


def recommend_bases(
    candidates: Sequence[CandidateBase],
    requirements: Sequence[MatchRequirement],
    top_n: int = 3,
) -> RecommendationResult:
    """Score controlled candidates against current requirements."""
    if top_n < 1:
        raise ValueError("top_n 必须大于等于 1")

    by_key = {requirement.key: requirement for requirement in requirements}
    missing_requirements = [
        key for key in CRITICAL_REQUIREMENT_KEYS if key not in by_key
    ]
    evaluations = [
        _evaluate(candidate, by_key) for candidate in candidates
    ]
    evaluations.sort(
        key=lambda evaluation: (
            len(evaluation.hard_failures),
            -evaluation.score,
            evaluation.base.display_code,
        )
    )
    return RecommendationResult(
        top3=evaluations[:top_n],
        candidate_count=len(candidates),
        candidate_shortage=len(candidates) < top_n,
        missing_requirements=missing_requirements,
        requirement_versions=[
            {
                "key": requirement.key,
                "requirement_id": requirement.requirement_id,
                "display_code": requirement.display_code,
                "revision": requirement.revision,
                "value": requirement.value,
                "unit": requirement.unit,
            }
            for requirement in requirements
        ],
    )
