from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

FMEA_SCALE = {
    "min": 1,
    "max": 10,
    "source": "合成 DFMEA 量表 V1（演示规则）",
}
PTO_REQUIRED_VALUES = {"required", "true", "yes", "是", "有", "需要"}


@dataclass(frozen=True)
class RequirementInput:
    requirement_id: str
    display_code: str
    revision: int
    parser_key: str
    parameter_name: str
    value_text: str
    unit: str
    review_status: str
    category: str


@dataclass(frozen=True)
class VariantInput:
    variant_id: str
    display_code: str
    parameter_key: str
    parameter_name: str
    affected_parts: tuple[str, ...]
    basis: str
    revision: int = 1


@dataclass(frozen=True)
class IssueInput:
    issue_id: str
    parser_key: str
    issue_type: str
    message: str
    severity: str


@dataclass(frozen=True)
class DesignProfile:
    project_display_code: str
    base_display_code: str
    base_name: str


@dataclass(frozen=True)
class ReviewItemDraft:
    display_code: str
    check_point: str
    standard_basis: str
    responsible_role: str
    dependencies: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class DesignReviewDraft:
    items: tuple[ReviewItemDraft, ...]
    inputs_snapshot: dict[str, Any]
    missing_inputs: tuple[str, ...]


@dataclass(frozen=True)
class FmeaItemDraft:
    display_code: str
    function_text: str
    failure_mode: str
    cause: str
    effect: str
    control: str
    action_text: str
    dependencies: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class FmeaDraft:
    items: tuple[FmeaItemDraft, ...]
    inputs_snapshot: dict[str, Any]
    missing_inputs: tuple[str, ...]
    scale: dict[str, Any]


def _requirement_dependency(
    requirement: RequirementInput,
) -> dict[str, Any]:
    return {
        "object_type": "requirement",
        "object_id": requirement.requirement_id,
        "display_code": requirement.display_code,
        "revision": requirement.revision,
    }


def _variant_dependency(variant: VariantInput) -> dict[str, Any]:
    return {
        "object_type": "variant_point",
        "object_id": variant.variant_id,
        "display_code": variant.display_code,
        "revision": variant.revision,
    }


def _issue_dependency(issue: IssueInput) -> dict[str, Any]:
    return {
        "object_type": "issue",
        "object_id": issue.issue_id,
        "display_code": issue.parser_key,
        "revision": None,
    }


def _deduplicate(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _requirement_snapshot(
    requirements: Sequence[RequirementInput],
) -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": requirement.requirement_id,
            "display_code": requirement.display_code,
            "revision": requirement.revision,
            "parser_key": requirement.parser_key,
            "parameter_name": requirement.parameter_name,
            "value_text": requirement.value_text,
            "unit": requirement.unit,
            "review_status": requirement.review_status,
            "category": requirement.category,
        }
        for requirement in requirements
    ]


def _variant_snapshot(
    variants: Sequence[VariantInput],
) -> list[dict[str, Any]]:
    return [
        {
            "variant_id": variant.variant_id,
            "revision": variant.revision,
            "display_code": variant.display_code,
            "parameter_key": variant.parameter_key,
            "parameter_name": variant.parameter_name,
            "affected_parts": list(variant.affected_parts),
            "basis": variant.basis,
        }
        for variant in variants
    ]


def build_design_review(
    profile: DesignProfile,
    requirements: Sequence[RequirementInput],
    variants: Sequence[VariantInput],
    open_issues: Sequence[IssueInput],
) -> DesignReviewDraft:
    by_key = {requirement.parser_key: requirement for requirement in requirements}
    items: list[ReviewItemDraft] = []
    missing_inputs: list[str] = []

    torque_dependencies = tuple(
        _requirement_dependency(by_key[key])
        for key in ("engineMaxTorque", "gearboxRatedInputTorque")
        if key in by_key
    )
    for key in ("engineMaxTorque", "gearboxRatedInputTorque"):
        if key not in by_key:
            missing_inputs.append(key)
    items.append(
        ReviewItemDraft(
            display_code="DR-01",
            check_point="发动机最大扭矩与变速器额定输入扭矩匹配",
            standard_basis=(
                "变速器最低额定输入扭矩 ≥ 发动机最大扭矩；"
                "两条需求必须分别建模并引用当前版本"
            ),
            responsible_role="设计工程师（演示角色）",
            dependencies=torque_dependencies,
        )
    )

    drive_dependencies = tuple(
        _requirement_dependency(by_key[key])
        for key in ("gearCount", "transmissionType")
        if key in by_key
    )
    for key in ("gearCount", "transmissionType"):
        if key not in by_key:
            missing_inputs.append(key)
    items.append(
        ReviewItemDraft(
            display_code="DR-02",
            check_point="档位数、换挡方式与整车配置一致",
            standard_basis=(
                f"以基型 {profile.base_display_code} 为参照，"
                "核对档位数、换挡方式与整车动力配置"
            ),
            responsible_role="设计工程师（演示角色）",
            dependencies=drive_dependencies,
        )
    )

    if "pto" in by_key:
        items.append(
            ReviewItemDraft(
                display_code="DR-03",
                check_point="取力器接口功能与布置可实施",
                standard_basis=(
                    "核对取力器接口位置、齿轮啮合和壳体空间；"
                    "基型无取力器时必须形成变型点"
                ),
                responsible_role="布置工程师（演示角色）",
                dependencies=(_requirement_dependency(by_key["pto"]),),
            )
        )
    else:
        missing_inputs.append("pto")

    if "assemblyWeight" in by_key:
        items.append(
            ReviewItemDraft(
                display_code="DR-04",
                check_point="总成重量满足整车安装上限",
                standard_basis="按总成重量上限核对基础 BOM 与变型件重量",
                responsible_role="总体工程师（演示角色）",
                dependencies=(_requirement_dependency(by_key["assemblyWeight"]),),
            )
        )
    else:
        missing_inputs.append("assemblyWeight")

    ratio_keys = [key for key in ("firstGearRatio", "topGearType") if key in by_key]
    for key in ("firstGearRatio", "topGearType"):
        if key not in by_key:
            missing_inputs.append(key)
    if ratio_keys:
        items.append(
            ReviewItemDraft(
                display_code="DR-05",
                check_point="一档速比与最高档形式满足工况",
                standard_basis=(
                    "核对一档速比、最高档形式与整车爬坡/高速工况；"
                    "最高档未定型时必须保留待澄清问题"
                ),
                responsible_role="设计工程师（演示角色）",
                dependencies=tuple(
                    _requirement_dependency(by_key[key]) for key in ratio_keys
                ),
            )
        )

    if variants:
        items.append(
            ReviewItemDraft(
                display_code="DR-06",
                check_point="变型点与可复用件方案可制造",
                standard_basis=(
                    "逐项核对变型点影响零件，区分沿用、修改和新设计；"
                    "修改件必须有变型依据"
                ),
                responsible_role="工艺工程师（演示角色）",
                dependencies=tuple(
                    _variant_dependency(variant) for variant in variants
                ),
            )
        )

    if open_issues:
        items.append(
            ReviewItemDraft(
                display_code="DR-07",
                check_point="待澄清问题已关闭或明确接受风险",
                standard_basis=(
                    "评审前核对问题状态、证据和处置结论；"
                    "未关闭的阻断问题不得视为已解决"
                ),
                responsible_role="项目经理（演示角色）",
                dependencies=tuple(_issue_dependency(issue) for issue in open_issues),
            )
        )

    unconfirmed = [
        requirement
        for requirement in requirements
        if requirement.review_status != "confirmed"
    ]
    if unconfirmed:
        unconfirmed_text = "、".join(
            f"{requirement.display_code}（{requirement.review_status}）"
            for requirement in unconfirmed
        )
        confirmation_basis = (
            f"仅已确认且 current 的需求可作为设计输入；未确认：" f"{unconfirmed_text}"
        )
    else:
        confirmation_basis = "全部需求均已确认且为 current，可作为设计输入"
    items.append(
        ReviewItemDraft(
            display_code="DR-08",
            check_point="设计输入需求均已确认且版本当前",
            standard_basis=confirmation_basis,
            responsible_role="评审员（演示角色）",
            dependencies=tuple(
                _requirement_dependency(requirement) for requirement in requirements
            ),
        )
    )

    snapshot = {
        "base_display_code": profile.base_display_code,
        "base_name": profile.base_name,
        "requirements": _requirement_snapshot(requirements),
        "variants": _variant_snapshot(variants),
        "open_issues": [
            {
                "issue_id": issue.issue_id,
                "parser_key": issue.parser_key,
                "issue_type": issue.issue_type,
                "message": issue.message,
                "severity": issue.severity,
            }
            for issue in open_issues
        ],
        "unconfirmed_requirements": [
            {
                "requirement_id": requirement.requirement_id,
                "display_code": requirement.display_code,
                "revision": requirement.revision,
                "review_status": requirement.review_status,
            }
            for requirement in unconfirmed
        ],
    }
    return DesignReviewDraft(
        items=tuple(items),
        inputs_snapshot=snapshot,
        missing_inputs=_deduplicate(missing_inputs),
    )


def _pto_required(requirement: RequirementInput) -> bool:
    return requirement.value_text.strip().lower() in PTO_REQUIRED_VALUES or (
        requirement.value_text.strip() in PTO_REQUIRED_VALUES
    )


def build_dfmea(
    profile: DesignProfile,
    requirements: Sequence[RequirementInput],
    variants: Sequence[VariantInput],
) -> FmeaDraft:
    by_key = {requirement.parser_key: requirement for requirement in requirements}
    items: list[FmeaItemDraft] = []
    missing_inputs: list[str] = []

    torque_dependencies = tuple(
        _requirement_dependency(by_key[key])
        for key in ("engineMaxTorque", "gearboxRatedInputTorque")
        if key in by_key
    )
    for key in ("engineMaxTorque", "gearboxRatedInputTorque"):
        if key not in by_key:
            missing_inputs.append(key)
    rated = by_key.get("gearboxRatedInputTorque")
    items.append(
        FmeaItemDraft(
            display_code="FMEA-01",
            function_text="传递发动机最大扭矩并承受静扭与疲劳载荷",
            failure_mode="输入轴或齿轮过载、疲劳断裂",
            cause=(
                f"额定输入扭矩低于发动机最大扭矩（{rated.display_code}）"
                if rated
                else "额定输入扭矩要求缺失"
            ),
            effect="动力中断、总成损坏、整车停驶",
            control="额定输入扭矩校核、静扭强度试验（TC-007）",
            action_text=(
                f"按 {rated.display_code} 提升额定输入扭矩并复算传动件"
                if rated
                else "补录额定输入扭矩要求后复算传动件"
            ),
            dependencies=torque_dependencies,
        )
    )

    pto = by_key.get("pto")
    if pto is not None and _pto_required(pto):
        pto_variant = next(
            (variant for variant in variants if variant.parameter_key == "pto"),
            None,
        )
        dependencies: list[dict[str, Any]] = [_requirement_dependency(pto)]
        if pto_variant is not None:
            dependencies.append(_variant_dependency(pto_variant))
        items.append(
            FmeaItemDraft(
                display_code="FMEA-02",
                function_text="提供取力器动力输出接口",
                failure_mode="取力器接口渗漏或齿轮啮合异常",
                cause="新增接口与基型主箱壳体不匹配",
                effect="取力功能失效、润滑油泄漏",
                control="接口尺寸链校核、合成样件比对",
                action_text=(
                    f"按 {pto_variant.display_code} 完成壳体改型与接口验证"
                    if pto_variant
                    else "确认取力器接口方案并补充合成样件比对"
                ),
                dependencies=tuple(dependencies),
            )
        )

    housing_variants = [
        variant
        for variant in variants
        if any("壳体" in part for part in variant.affected_parts)
    ]
    if housing_variants:
        items.append(
            FmeaItemDraft(
                display_code="FMEA-03",
                function_text="主箱壳体承载与密封",
                failure_mode="壳体强度不足或结合面渗漏",
                cause="变型导致壳体局部结构修改",
                effect="总成渗漏、结构失效",
                control="有限元与密封校核（演示规则）",
                action_text=(
                    "按 "
                    + "、".join(variant.display_code for variant in housing_variants)
                    + " 完成壳体改型验证"
                ),
                dependencies=tuple(
                    _variant_dependency(variant) for variant in housing_variants
                ),
            )
        )

    transmission = by_key.get("transmissionType")
    if transmission is not None and transmission.value_text.strip().upper() == "AMT":
        items.append(
            FmeaItemDraft(
                display_code="FMEA-04",
                function_text="AMT 换挡执行与扭矩传递",
                failure_mode="换挡执行机构卡滞或挡位丢失",
                cause="控制策略与执行机构匹配不足",
                effect="换挡失败、动力中断",
                control="台架换挡循环与故障注入（合成）",
                action_text="确认换挡执行机构选型并补充台架用例",
                dependencies=(_requirement_dependency(transmission),),
            )
        )

    weight = by_key.get("assemblyWeight")
    if weight is not None:
        items.append(
            FmeaItemDraft(
                display_code="FMEA-05",
                function_text="总成重量满足整车安装上限",
                failure_mode="总成超重导致安装或承载问题",
                cause="变型件重量增加",
                effect="整车布置超限",
                control="重量清单核算",
                action_text=f"按 {weight.display_code} 控制重量并复称",
                dependencies=(_requirement_dependency(weight),),
            )
        )

    top_gear_variants = [
        variant for variant in variants if variant.parameter_key == "topGearType"
    ]
    top_gear = by_key.get("topGearType")
    if top_gear is not None or top_gear_variants:
        dependencies = []
        if top_gear is not None:
            dependencies.append(_requirement_dependency(top_gear))
        dependencies.extend(
            _variant_dependency(variant) for variant in top_gear_variants
        )
        items.append(
            FmeaItemDraft(
                display_code="FMEA-06",
                function_text="最高档动力传递",
                failure_mode="最高档齿轮或轴承异常磨损",
                cause="最高档形式变更或未定型",
                effect="高速工况噪声或损坏",
                control="齿轮强度与 NVH 校核（演示规则）",
                action_text="确认最高档形式并完成对应校核",
                dependencies=tuple(dependencies),
            )
        )

    snapshot = {
        "base_display_code": profile.base_display_code,
        "base_name": profile.base_name,
        "requirements": _requirement_snapshot(requirements),
        "variants": _variant_snapshot(variants),
        "scale": dict(FMEA_SCALE),
    }
    return FmeaDraft(
        items=tuple(items),
        inputs_snapshot=snapshot,
        missing_inputs=_deduplicate(missing_inputs),
        scale=dict(FMEA_SCALE),
    )
