from app.domain.spectrum import CandidateBase, MatchRequirement
from app.domain.variant import BasePart, compute_variants

BASE = CandidateBase(
    id="b1",
    display_code="JX-12A",
    name="JX-12A 12档 AMT",
    transmission_type="AMT",
    gear_count=12,
    rated_input_torque=2600,
    first_gear_ratio=15.5,
    top_gear_type="direct",
    has_pto=False,
    weight_kg=290,
    source="合成型谱库 V1（示意数据）",
)

BASE_PARTS = [
    BasePart("P-01", "输入轴", "PN-INPUT-01", "shaft", "合成 BOM V1（示意数据）"),
    BasePart("P-02", "一轴齿轮", "PN-GEAR-01", "gear", "合成 BOM V1（示意数据）"),
    BasePart("P-03", "主箱壳体", "PN-HOUSING-01", "housing", "合成 BOM V1（示意数据）"),
    BasePart("P-04", "离合器壳", "PN-CLUTCH-01", "housing", "合成 BOM V1（示意数据）"),
    BasePart("P-05", "输出法兰", "PN-FLANGE-01", "flange", "合成 BOM V1（示意数据）"),
    BasePart("P-06", "齿轮组", "PN-GEARSET-01", "gearset", "合成 BOM V1（示意数据）"),
    BasePart("P-07", "换挡执行机构", "PN-ACTUATOR-01", "actuator", "合成 BOM V1（示意数据）"),
]


def _requirement(
    key: str,
    value: str,
    *,
    operator: str = "=",
    unit: str = "",
    requirement_id: str | None = None,
    revision: int = 1,
) -> MatchRequirement:
    return MatchRequirement(
        key=key,
        requirement_id=requirement_id or f"r-{key}",
        display_code=f"REQ-{key}",
        revision=revision,
        value=value,
        unit=unit,
        operator=operator,
    )


REQUIREMENTS = [
    _requirement("transmissionType", "AMT", operator="text"),
    _requirement("gearCount", "12", unit="档"),
    _requirement(
        "gearboxRatedInputTorque",
        "2600",
        operator=">=",
        unit="N·m",
        requirement_id="r-torque",
    ),
    _requirement("firstGearRatio", "14.5", operator=">="),
    _requirement(
        "pto", "required", requirement_id="r-pto"
    ),
    _requirement("assemblyWeight", "300", operator="<=", unit="kg"),
    _requirement("topGearType", "直接档或超速档", operator="text"),
]


def test_fixed_base_produces_pto_variant_and_part_decisions():
    analysis = compute_variants(BASE, BASE_PARTS, REQUIREMENTS)

    assert [variant.parameter_key for variant in analysis.variants] == ["pto"]
    pto = analysis.variants[0]
    assert pto.variant_type == "new_function"
    assert pto.affected_parts == ("取力器接口", "主箱壳体")
    assert pto.upstream_requirements[0]["requirement_id"] == "r-pto"
    assert pto.upstream_requirements[0]["revision"] == 1
    assert "取力器" in pto.basis
    assert any("最高档" in item for item in analysis.pending_items)

    decisions = {
        decision.part_name: decision
        for decision in analysis.reusable_parts
    }
    assert decisions["取力器接口"].classification == "new_design"
    assert decisions["取力器接口"].part_number == "PN-PTO-IF-01"
    assert decisions["主箱壳体"].classification == "modify"
    assert decisions["输入轴"].classification == "carryover"
    assert decisions["一轴齿轮"].classification == "carryover"
    assert decisions["离合器壳"].classification == "carryover"
    assert decisions["输出法兰"].classification == "carryover"
    assert decisions["齿轮组"].classification == "carryover"
    assert decisions["换挡执行机构"].classification == "carryover"
    assert "合成 BOM V1" in decisions["输入轴"].source
    assert "变型点" in decisions["主箱壳体"].source


def test_torque_increase_adds_torque_variant_and_modifies_rotating_parts():
    requirements = [
        _requirement(
            "gearboxRatedInputTorque",
            "2800",
            operator=">=",
            unit="N·m",
            requirement_id="r-torque",
            revision=2,
        )
        if requirement.key == "gearboxRatedInputTorque"
        else requirement
        for requirement in REQUIREMENTS
    ]

    analysis = compute_variants(BASE, BASE_PARTS, requirements)

    assert [variant.parameter_key for variant in analysis.variants] == [
        "pto",
        "gearboxRatedInputTorque",
    ]
    torque = analysis.variants[1]
    assert torque.variant_type == "parameter_adjustment"
    assert torque.base_value == "2600 N·m"
    assert torque.requirement_value == ">= 2800 N·m"
    assert torque.affected_parts == ("输入轴", "一轴齿轮")
    assert torque.upstream_requirements[0]["revision"] == 2

    decisions = {
        decision.part_name: decision
        for decision in analysis.reusable_parts
    }
    assert decisions["输入轴"].classification == "modify"
    assert decisions["一轴齿轮"].classification == "modify"
    assert decisions["主箱壳体"].classification == "modify"
    assert decisions["取力器接口"].classification == "new_design"
    assert decisions["输出法兰"].classification == "carryover"


def test_base_with_pto_and_sufficient_torque_has_no_matching_variants():
    base = CandidateBase(
        id="b2",
        display_code="JX-12B",
        name="JX-12B 12档 AMT",
        transmission_type="AMT",
        gear_count=12,
        rated_input_torque=2800,
        first_gear_ratio=15.5,
        top_gear_type="direct",
        has_pto=True,
        weight_kg=290,
        source="合成型谱库 V1（示意数据）",
    )

    analysis = compute_variants(base, BASE_PARTS, REQUIREMENTS)

    assert analysis.variants == []
    assert any("最高档" in item for item in analysis.pending_items)
    decisions = {
        decision.part_name: decision
        for decision in analysis.reusable_parts
    }
    assert decisions["输入轴"].classification == "carryover"
    assert decisions["主箱壳体"].classification == "carryover"


def test_all_missing_requirements_produce_pending_items_not_variants():
    analysis = compute_variants(BASE, BASE_PARTS, [])

    assert analysis.variants == []
    assert len(analysis.pending_items) == 7


def test_multiple_variant_branches_and_shared_part_decisions():
    base = CandidateBase(
        id="b9",
        display_code="JX-9",
        name="JX-9 13档 MT",
        transmission_type="MT",
        gear_count=13,
        rated_input_torque=2500,
        first_gear_ratio=14.0,
        top_gear_type="overdrive",
        has_pto=True,
        weight_kg=320,
        source="合成型谱库 V1（示意数据）",
    )
    requirements = [
        _requirement("transmissionType", "AMT", operator="text"),
        _requirement("gearCount", "12", unit="档"),
        _requirement(
            "gearboxRatedInputTorque", "2600", operator=">=", unit="N·m"
        ),
        _requirement("firstGearRatio", "15", operator=">="),
        _requirement("pto", "not_required"),
        _requirement("assemblyWeight", "300", operator="<=", unit="kg"),
        _requirement("topGearType", "直接档", operator="text"),
    ]

    analysis = compute_variants(base, BASE_PARTS, requirements)

    assert [variant.parameter_key for variant in analysis.variants] == [
        "pto",
        "gearboxRatedInputTorque",
        "gearCount",
        "firstGearRatio",
        "assemblyWeight",
        "transmissionType",
        "topGearType",
    ]
    assert analysis.pending_items == []
    assert analysis.variants[0].variant_type == "structural_change"
    assert analysis.variants[0].affected_parts == ("主箱壳体",)
    top_gear = analysis.variants[-1]
    assert top_gear.parameter_name == "最高档形式"
    assert top_gear.base_value == "超速档"
    assert top_gear.requirement_value == "直接档"

    decisions = {
        decision.part_name: decision
        for decision in analysis.reusable_parts
    }
    assert "取力器接口" not in decisions
    assert decisions["主箱壳体"].classification == "modify"
    assert "取力器接口" in decisions["主箱壳体"].reason
    assert "总成重量" in decisions["主箱壳体"].reason
    assert decisions["输入轴"].classification == "modify"
    assert decisions["一轴齿轮"].classification == "modify"
    assert decisions["齿轮组"].classification == "modify"
    assert decisions["离合器壳"].classification == "modify"
    assert decisions["换挡执行机构"].classification == "modify"


def test_part_decisions_have_stable_identity_and_no_duplicates():
    requirements = [
        _requirement(
            "gearboxRatedInputTorque",
            "2800",
            operator=">=",
            unit="N·m",
            requirement_id="r-torque",
            revision=2,
        )
        if requirement.key == "gearboxRatedInputTorque"
        else requirement
        for requirement in REQUIREMENTS
    ]

    analysis = compute_variants(BASE, BASE_PARTS, requirements)
    codes = [decision.part_display_code for decision in analysis.reusable_parts]

    assert len(codes) == len(set(codes))
    assert set(codes) == {
        "P-01",
        "P-02",
        "P-03",
        "P-04",
        "P-05",
        "P-06",
        "P-07",
        "P-NEW-PTO-01",
    }
