from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

SIMILARITY_WEIGHTS = {
    "transmissionType": 0.25,
    "gearCount": 0.25,
    "ratedInputTorque": 0.20,
    "pto": 0.15,
    "weightLimit": 0.15,
}
CRITERIA_ORDER = (
    "transmissionType",
    "gearCount",
    "ratedInputTorque",
    "pto",
    "weightLimit",
)


@dataclass(frozen=True)
class HistoryProject:
    id: str
    display_code: str
    name: str
    customer: str
    transmission_type: str
    gear_count: int
    rated_input_torque: float
    has_pto: bool
    assembly_weight_kg: float
    top_gear_type: str
    notes: str
    source: str


@dataclass(frozen=True)
class ProjectProfile:
    transmission_type: str | None
    gear_count: int | None
    rated_input_torque: float | None
    has_pto: bool | None
    weight_limit_kg: float | None
    requirement_versions: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class SimilarityCriterion:
    criterion: str
    project_value: str | None
    history_value: str
    weight: float
    score: float | None
    matched: bool | None
    reason: str


@dataclass(frozen=True)
class SimilarProject:
    history_project_id: str
    display_code: str
    name: str
    customer: str
    score: float
    matched_points: tuple[str, ...]
    differences: tuple[str, ...]
    missing_criteria: tuple[str, ...]
    criteria: tuple[SimilarityCriterion, ...]
    source: str
    notes: str


@dataclass(frozen=True)
class SimilarityResult:
    matches: tuple[SimilarProject, ...]
    candidate_count: int
    candidate_shortage: bool
    missing_criteria: tuple[str, ...]
    applicable_criteria_count: int


def _criterion(
    name: str,
    project_value: str | None,
    history_value: str,
    score: float | None,
    matched: bool | None,
    reason: str,
) -> SimilarityCriterion:
    return SimilarityCriterion(
        criterion=name,
        project_value=project_value,
        history_value=history_value,
        weight=SIMILARITY_WEIGHTS[name],
        score=score,
        matched=matched,
        reason=reason,
    )


def _evaluate(
    history: HistoryProject, profile: ProjectProfile
) -> SimilarProject:
    criteria: list[SimilarityCriterion] = []

    if profile.transmission_type is None:
        criteria.append(
            _criterion(
                "transmissionType",
                None,
                history.transmission_type,
                None,
                None,
                "项目缺少换挡方式需求，无法比对",
            )
        )
    else:
        same = history.transmission_type == profile.transmission_type
        criteria.append(
            _criterion(
                "transmissionType",
                profile.transmission_type,
                history.transmission_type,
                1.0 if same else 0.0,
                same,
                (
                    f"换挡方式一致（{history.transmission_type}）"
                    if same
                    else (
                        f"换挡方式不同：历史项目 {history.transmission_type}，"
                        f"当前需求 {profile.transmission_type}"
                    )
                ),
            )
        )

    if profile.gear_count is None:
        criteria.append(
            _criterion(
                "gearCount",
                None,
                str(history.gear_count),
                None,
                None,
                "项目缺少档位数需求，无法比对",
            )
        )
    else:
        difference = abs(history.gear_count - profile.gear_count)
        if difference == 0:
            score = 1.0
        elif difference == 1:
            score = 0.5
        else:
            score = 0.0
        criteria.append(
            _criterion(
                "gearCount",
                str(profile.gear_count),
                str(history.gear_count),
                score,
                difference == 0,
                (
                    f"档位数一致（{history.gear_count} 档）"
                    if difference == 0
                    else (
                        f"档位数相差 {difference} 档：历史项目 "
                        f"{history.gear_count} 档，当前需求 "
                        f"{profile.gear_count} 档"
                    )
                ),
            )
        )

    if profile.rated_input_torque is None:
        criteria.append(
            _criterion(
                "ratedInputTorque",
                None,
                f"{history.rated_input_torque:g} N·m",
                None,
                None,
                "项目缺少额定输入扭矩需求，无法比对",
            )
        )
    else:
        ratio = (
            history.rated_input_torque / profile.rated_input_torque
            if profile.rated_input_torque
            else 0.0
        )
        if ratio >= 1.0:
            score = 1.0
        elif ratio >= 0.9:
            score = 0.5
        else:
            score = 0.0
        criteria.append(
            _criterion(
                "ratedInputTorque",
                f"{profile.rated_input_torque:g} N·m",
                f"{history.rated_input_torque:g} N·m",
                score,
                ratio >= 1.0,
                (
                    f"历史项目扭矩覆盖当前需求（{history.rated_input_torque:g}"
                    f" ≥ {profile.rated_input_torque:g} N·m）"
                    if ratio >= 1.0
                    else (
                        f"历史项目扭矩偏低：{history.rated_input_torque:g} "
                        f"N·m，当前需求 {profile.rated_input_torque:g} N·m"
                    )
                ),
            )
        )

    if profile.has_pto is None:
        criteria.append(
            _criterion(
                "pto",
                None,
                "有取力器" if history.has_pto else "无取力器",
                None,
                None,
                "项目缺少取力器需求，无法比对",
            )
        )
    else:
        same = history.has_pto == profile.has_pto
        criteria.append(
            _criterion(
                "pto",
                "需要取力器" if profile.has_pto else "不需要取力器",
                "有取力器" if history.has_pto else "无取力器",
                1.0 if same else 0.0,
                same,
                (
                    "取力器需求一致"
                    if same
                    else "取力器配置不同：历史项目"
                    f"{'有' if history.has_pto else '无'}取力器，当前需求"
                    f"{'需要' if profile.has_pto else '不需要'}"
                ),
            )
        )

    if profile.weight_limit_kg is None:
        criteria.append(
            _criterion(
                "weightLimit",
                None,
                f"{history.assembly_weight_kg:g} kg",
                None,
                None,
                "项目缺少总成重量上限，无法比对",
            )
        )
    else:
        limit = profile.weight_limit_kg
        if history.assembly_weight_kg <= limit:
            score = 1.0
            matched = True
            reason = (
                f"历史项目重量满足当前上限（{history.assembly_weight_kg:g}"
                f" ≤ {limit:g} kg）"
            )
        elif limit > 0 and history.assembly_weight_kg <= limit * 1.05:
            score = 0.5
            matched = False
            reason = (
                f"历史项目重量超出上限但仍在 5% 容差内"
                f"（{history.assembly_weight_kg:g} kg > {limit:g} kg）"
            )
        else:
            score = 0.0
            matched = False
            reason = (
                f"历史项目重量超出当前上限"
                f"（{history.assembly_weight_kg:g} kg > {limit:g} kg）"
            )
        criteria.append(
            _criterion(
                "weightLimit",
                f"{limit:g} kg",
                f"{history.assembly_weight_kg:g} kg",
                score,
                matched,
                reason,
            )
        )

    applicable = [
        criterion for criterion in criteria if criterion.score is not None
    ]
    weight_sum = sum(criterion.weight for criterion in applicable)
    score = (
        round(
            sum(
                criterion.weight * (criterion.score or 0.0)
                for criterion in applicable
            )
            / weight_sum
            * 100.0,
            2,
        )
        if weight_sum
        else 0.0
    )
    matched_points = tuple(
        criterion.reason
        for criterion in applicable
        if criterion.score == 1.0
    )
    differences = tuple(
        criterion.reason
        for criterion in applicable
        if criterion.score != 1.0
    )
    missing_criteria = tuple(
        criterion.criterion
        for criterion in criteria
        if criterion.score is None
    )
    return SimilarProject(
        history_project_id=history.id,
        display_code=history.display_code,
        name=history.name,
        customer=history.customer,
        score=score,
        matched_points=matched_points,
        differences=differences,
        missing_criteria=missing_criteria,
        criteria=tuple(criteria),
        source=history.source,
        notes=history.notes,
    )


def find_similar_projects(
    history_projects: Sequence[HistoryProject],
    profile: ProjectProfile,
    top_n: int = 3,
) -> SimilarityResult:
    if top_n < 1:
        raise ValueError("top_n 必须大于等于 1")
    evaluated = [
        _evaluate(history_project, profile)
        for history_project in history_projects
    ]
    evaluated.sort(key=lambda match: (-match.score, match.display_code))
    missing_criteria = tuple(
        name
        for name in CRITERIA_ORDER
        if getattr(profile, _profile_attribute(name)) is None
    )
    return SimilarityResult(
        matches=tuple(evaluated[:top_n]),
        candidate_count=len(history_projects),
        candidate_shortage=len(history_projects) < top_n,
        missing_criteria=missing_criteria,
        applicable_criteria_count=len(CRITERIA_ORDER)
        - len(missing_criteria),
    )


def _profile_attribute(criterion: str) -> str:
    return {
        "transmissionType": "transmission_type",
        "gearCount": "gear_count",
        "ratedInputTorque": "rated_input_torque",
        "pto": "has_pto",
        "weightLimit": "weight_limit_kg",
    }[criterion]
