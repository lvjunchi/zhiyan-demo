from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .spectrum import (
    CandidateBase,
    MatchRequirement,
    _compare,
    _to_float,
    _top_gear_value,
)

NEW_PART_METADATA = {
    "取力器接口": {
        "part_display_code": "P-NEW-PTO-01",
        "part_number": "PN-PTO-IF-01",
    },
}


@dataclass(frozen=True)
class BasePart:
    display_code: str
    name: str
    part_number: str
    category: str
    source: str


@dataclass(frozen=True)
class VariantCandidate:
    parameter_key: str
    parameter_name: str
    base_value: str
    requirement_value: str
    variant_type: str
    affected_parts: tuple[str, ...]
    upstream_requirements: tuple[dict[str, object], ...]
    basis: str


@dataclass(frozen=True)
class PartDecision:
    part_display_code: str
    part_name: str
    part_number: str
    classification: str
    reason: str
    source: str
    variant_keys: tuple[str, ...] = ()


@dataclass
class VariantAnalysis:
    variants: list[VariantCandidate] = field(default_factory=list)
    reusable_parts: list[PartDecision] = field(default_factory=list)
    pending_items: list[str] = field(default_factory=list)
    requirement_versions: list[dict[str, object]] = field(
        default_factory=list
    )


# Frozen engineering influence scope, shared by generation and change invalidation.
PARAMETER_PARTS: dict[str, tuple[str, ...]] = {
    "pto": ("取力器接口", "主箱壳体"),
    "gearboxRatedInputTorque": ("输入轴", "一轴齿轮"),
    "gearCount": ("齿轮组", "主箱壳体"),
    "firstGearRatio": ("齿轮组",),
    "assemblyWeight": ("主箱壳体", "离合器壳"),
    "transmissionType": ("换挡执行机构",),
    "topGearType": ("齿轮组",),
}


def _requirement_info(requirement: MatchRequirement) -> dict[str, object]:
    return {
        "requirement_id": requirement.requirement_id,
        "display_code": requirement.display_code,
        "revision": requirement.revision,
        "key": requirement.key,
    }


def _requirement_text(requirement: MatchRequirement) -> str:
    return f"{requirement.operator} {requirement.value} {requirement.unit}".strip()


def _required_boolean(value: str) -> bool:
    return value in {"required", "需要", "true", "yes", "是", "有"}


def _top_gear_label(value: str) -> str:
    return {"direct": "直接档", "overdrive": "超速档"}.get(value, value)


def _part_decisions(
    base_parts: Sequence[BasePart],
    variants: Sequence[VariantCandidate],
) -> list[PartDecision]:
    decisions: dict[str, PartDecision] = {}
    order: list[str] = []
    base_by_name = {part.name: part for part in base_parts}

    for part in base_parts:
        decisions[part.display_code] = PartDecision(
            part_display_code=part.display_code,
            part_name=part.name,
            part_number=part.part_number,
            classification="carryover",
            reason="未被变型点影响",
            source=part.source,
            variant_keys=(),
        )
        order.append(part.display_code)

    for variant in variants:
        for part_name in variant.affected_parts:
            base_part = base_by_name.get(part_name)
            if base_part is not None:
                existing = decisions[base_part.display_code]
                if existing.classification == "carryover":
                    classification = "modify"
                    reason = (
                        f"受变型点 {variant.parameter_name} 影响："
                        f"{variant.basis}"
                    )
                else:
                    classification = existing.classification
                    reason = (
                        f"{existing.reason}；受变型点 "
                        f"{variant.parameter_name} 影响"
                    )
                decisions[base_part.display_code] = PartDecision(
                    part_display_code=base_part.display_code,
                    part_name=base_part.name,
                    part_number=base_part.part_number,
                    classification=classification,
                    reason=reason,
                    source=(
                        f"{base_part.source}；"
                        f"变型点 {variant.parameter_name}"
                    ),
                    variant_keys=existing.variant_keys
                    + (variant.parameter_key,),
                )
                continue

            existing_new = next(
                (
                    decision
                    for decision in decisions.values()
                    if decision.part_name == part_name
                ),
                None,
            )
            if existing_new is not None:
                decisions[existing_new.part_display_code] = PartDecision(
                    part_display_code=existing_new.part_display_code,
                    part_name=existing_new.part_name,
                    part_number=existing_new.part_number,
                    classification="new_design",
                    reason=(
                        f"{existing_new.reason}；变型点 "
                        f"{variant.parameter_name} 需要新增零件"
                    ),
                    source=existing_new.source,
                    variant_keys=existing_new.variant_keys
                    + (variant.parameter_key,),
                )
                continue

            metadata = NEW_PART_METADATA.get(part_name)
            if metadata is None:
                index = len(decisions) + 1
                metadata = {
                    "part_display_code": f"P-NEW-{index:02d}",
                    "part_number": f"PN-NEW-{index:02d}",
                }
            display_code = str(metadata["part_display_code"])
            decisions[display_code] = PartDecision(
                part_display_code=display_code,
                part_name=part_name,
                part_number=str(metadata["part_number"]),
                classification="new_design",
                reason=(
                    f"变型点 {variant.parameter_name} 需要新增零件："
                    f"{variant.basis}"
                ),
                source=f"变型点 {variant.parameter_name}（合成工程判断）",
                variant_keys=(variant.parameter_key,),
            )
            order.append(display_code)

    return [decisions[code] for code in order]


def compute_variants(
    base: CandidateBase,
    base_parts: Sequence[BasePart],
    requirements: Sequence[MatchRequirement],
) -> VariantAnalysis:
    """Compute variant points and reusable-part decisions."""
    by_key = {requirement.key: requirement for requirement in requirements}
    variants: list[VariantCandidate] = []
    pending: list[str] = []

    pto = by_key.get("pto")
    if pto is None:
        pending.append("缺少取力器要求，无法判断是否需要新增取力器")
    elif _required_boolean(pto.value) and not base.has_pto:
        variants.append(
            VariantCandidate(
                parameter_key="pto",
                parameter_name="取力器接口",
                base_value="无取力器",
                requirement_value="需要取力器",
                variant_type="new_function",
                affected_parts=PARAMETER_PARTS["pto"],
                upstream_requirements=(_requirement_info(pto),),
                basis="基型无取力器，需求要求配置取力器接口",
            )
        )
    elif not _required_boolean(pto.value) and base.has_pto:
        variants.append(
            VariantCandidate(
                parameter_key="pto",
                parameter_name="取力器接口",
                base_value="有取力器",
                requirement_value="不需要取力器",
                variant_type="structural_change",
                affected_parts=("主箱壳体",),
                upstream_requirements=(_requirement_info(pto),),
                basis="基型带取力器，需求未要求取力器，需要封堵或调整接口",
            )
        )

    torque = by_key.get("gearboxRatedInputTorque")
    if torque is None:
        pending.append("缺少变速器最低额定输入扭矩要求")
    else:
        required = _to_float(torque.value)
        if required is None:
            pending.append("变速器最低额定输入扭矩无法解析")
        elif not _compare(
            base.rated_input_torque, torque.operator, required
        ):
            variants.append(
                VariantCandidate(
                    parameter_key="gearboxRatedInputTorque",
                    parameter_name="额定输入扭矩",
                    base_value=f"{base.rated_input_torque:g} N·m",
                    requirement_value=_requirement_text(torque),
                    variant_type="parameter_adjustment",
                    affected_parts=PARAMETER_PARTS["gearboxRatedInputTorque"],
                    upstream_requirements=(_requirement_info(torque),),
                    basis=(
                        "基型额定输入扭矩不满足当前派生要求，"
                        "需要提升轴系与齿轮强度"
                    ),
                )
            )

    gear = by_key.get("gearCount")
    if gear is None:
        pending.append("缺少档位数要求")
    else:
        required = _to_float(gear.value)
        if required is None:
            pending.append("档位数无法解析")
        elif base.gear_count != int(required):
            variants.append(
                VariantCandidate(
                    parameter_key="gearCount",
                    parameter_name="档位数",
                    base_value=f"{base.gear_count} 档",
                    requirement_value=_requirement_text(gear),
                    variant_type="structural_change",
                    affected_parts=PARAMETER_PARTS["gearCount"],
                    upstream_requirements=(_requirement_info(gear),),
                    basis="基型档位数与需求不一致，需要调整齿轮组与壳体",
                )
            )

    ratio = by_key.get("firstGearRatio")
    if ratio is None:
        pending.append("缺少一档速比要求")
    else:
        required = _to_float(ratio.value)
        if required is None:
            pending.append("一档速比无法解析")
        elif not _compare(
            base.first_gear_ratio, ratio.operator, required
        ):
            variants.append(
                VariantCandidate(
                    parameter_key="firstGearRatio",
                    parameter_name="一档速比",
                    base_value=f"{base.first_gear_ratio:g}",
                    requirement_value=_requirement_text(ratio),
                    variant_type="parameter_adjustment",
                    affected_parts=PARAMETER_PARTS["firstGearRatio"],
                    upstream_requirements=(_requirement_info(ratio),),
                    basis="基型一档速比不满足需求，需要调整齿轮组",
                )
            )

    weight = by_key.get("assemblyWeight")
    if weight is None:
        pending.append("缺少总成重量上限要求")
    else:
        required = _to_float(weight.value)
        if required is None:
            pending.append("总成重量上限无法解析")
        elif not _compare(base.weight_kg, weight.operator, required):
            variants.append(
                VariantCandidate(
                    parameter_key="assemblyWeight",
                    parameter_name="总成重量",
                    base_value=f"{base.weight_kg:g} kg",
                    requirement_value=_requirement_text(weight),
                    variant_type="structural_change",
                    affected_parts=PARAMETER_PARTS["assemblyWeight"],
                    upstream_requirements=(_requirement_info(weight),),
                    basis="基型总成重量超过需求上限，需要轻量化或结构变更",
                )
            )

    transmission = by_key.get("transmissionType")
    if transmission is None:
        pending.append("缺少换挡方式要求")
    elif base.transmission_type != transmission.value:
        variants.append(
            VariantCandidate(
                parameter_key="transmissionType",
                parameter_name="换挡方式",
                base_value=base.transmission_type,
                requirement_value=transmission.value,
                variant_type="structural_change",
                affected_parts=PARAMETER_PARTS["transmissionType"],
                upstream_requirements=(_requirement_info(transmission),),
                basis="基型换挡方式与需求不一致，需要更换执行机构",
            )
        )

    top_gear = by_key.get("topGearType")
    if top_gear is None:
        pending.append("缺少最高档形式要求")
    else:
        required, reason = _top_gear_value(top_gear)
        if required is None:
            pending.append(f"最高档形式无法判定：{reason}")
        elif base.top_gear_type != required:
            variants.append(
                VariantCandidate(
                    parameter_key="topGearType",
                    parameter_name="最高档形式",
                    base_value=_top_gear_label(base.top_gear_type),
                    requirement_value=_top_gear_label(required),
                    variant_type="structural_change",
                    affected_parts=PARAMETER_PARTS["topGearType"],
                    upstream_requirements=(_requirement_info(top_gear),),
                    basis="基型最高档形式与需求不一致，需要调整齿轮组",
                )
            )

    return VariantAnalysis(
        variants=variants,
        reusable_parts=_part_decisions(base_parts, variants),
        pending_items=pending,
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
