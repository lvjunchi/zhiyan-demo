from dataclasses import replace

import pytest

from app.domain.spectrum import (
    CandidateBase,
    MatchRequirement,
    _compare,
    recommend_bases,
)

CANDIDATES = [
    CandidateBase(
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
    ),
    CandidateBase(
        id="b2",
        display_code="JX-12B",
        name="JX-12B 12档 AMT",
        transmission_type="AMT",
        gear_count=12,
        rated_input_torque=2800,
        first_gear_ratio=14.8,
        top_gear_type="direct",
        has_pto=True,
        weight_kg=305,
        source="合成型谱库 V1（示意数据）",
    ),
    CandidateBase(
        id="b3",
        display_code="JX-13A",
        name="JX-13A 13档 AMT",
        transmission_type="AMT",
        gear_count=13,
        rated_input_torque=3000,
        first_gear_ratio=15.8,
        top_gear_type="overdrive",
        has_pto=True,
        weight_kg=315,
        source="合成型谱库 V1（示意数据）",
    ),
    CandidateBase(
        id="b4",
        display_code="JX-12C",
        name="JX-12C 12档 MT",
        transmission_type="MT",
        gear_count=12,
        rated_input_torque=2600,
        first_gear_ratio=15.0,
        top_gear_type="direct",
        has_pto=False,
        weight_kg=285,
        source="合成型谱库 V1（示意数据）",
    ),
]

REQUIREMENTS = [
    MatchRequirement(
        key="transmissionType",
        requirement_id="r-type",
        display_code="REQ-P01-C-003",
        revision=1,
        value="AMT",
        unit="",
        operator="text",
    ),
    MatchRequirement(
        key="gearCount",
        requirement_id="r-gear",
        display_code="REQ-P01-C-001",
        revision=1,
        value="12",
        unit="档",
        operator="=",
    ),
    MatchRequirement(
        key="gearboxRatedInputTorque",
        requirement_id="r-torque",
        display_code="REQ-P01-C-002",
        revision=1,
        value="2600",
        unit="N·m",
        operator=">=",
    ),
    MatchRequirement(
        key="firstGearRatio",
        requirement_id="r-ratio",
        display_code="REQ-P01-C-004",
        revision=1,
        value="14.5",
        unit="",
        operator=">=",
    ),
    MatchRequirement(
        key="pto",
        requirement_id="r-pto",
        display_code="REQ-P01-C-006",
        revision=1,
        value="required",
        unit="",
        operator="=",
    ),
    MatchRequirement(
        key="assemblyWeight",
        requirement_id="r-weight",
        display_code="REQ-P01-D-002",
        revision=1,
        value="300",
        unit="kg",
        operator="<=",
    ),
    MatchRequirement(
        key="topGearType",
        requirement_id="r-top",
        display_code="REQ-P01-C-005",
        revision=1,
        value="直接档或超速档",
        unit="",
        operator="text",
    ),
]


def test_recommendation_ranks_hard_constraint_candidates_and_explains_basis():
    result = recommend_bases(CANDIDATES, REQUIREMENTS)

    assert result.candidate_count == 4
    assert result.candidate_shortage is False
    assert [item.base.display_code for item in result.top3] == [
        "JX-12A",
        "JX-12B",
        "JX-12C",
    ]

    top = result.top3[0]
    assert top.base.display_code == "JX-12A"
    assert top.hard_failures == []
    assert "topGearType" in top.missing_items
    pto = next(
        criterion
        for criterion in top.criteria
        if criterion.criterion == "pto"
    )
    assert pto.satisfied is False
    assert pto.score == 0
    assert pto.hard_constraint is False
    top_gear = next(
        criterion
        for criterion in top.criteria
        if criterion.criterion == "topGearType"
    )
    assert top_gear.score is None
    assert "未定型" in top_gear.reason
    assert all(
        criterion.source == "合成型谱库 V1（示意数据）"
        for criterion in top.criteria
    )

    jx12b = next(
        item for item in result.top3 if item.base.display_code == "JX-12B"
    )
    assert "assemblyWeight" in jx12b.hard_failures

    jx12c = next(
        item for item in result.top3 if item.base.display_code == "JX-12C"
    )
    assert "transmissionType" in jx12c.hard_failures

    assert any(
        requirement["display_code"] == "REQ-P01-C-002"
        and requirement["revision"] == 1
        for requirement in result.requirement_versions
    )


def test_candidate_shortage_is_reported_honestly():
    result = recommend_bases(CANDIDATES[:2], REQUIREMENTS)

    assert result.candidate_count == 2
    assert result.candidate_shortage is True
    assert len(result.top3) == 2


def test_missing_optional_requirements_are_excluded_not_fabricated():
    optional_missing = [
        requirement
        for requirement in REQUIREMENTS
        if requirement.key not in {"pto", "assemblyWeight"}
    ]

    result = recommend_bases(CANDIDATES, optional_missing)

    top = result.top3[0]
    assert "pto" in top.missing_items
    assert "assemblyWeight" in top.missing_items
    assert all(
        criterion.score is None
        for criterion in top.criteria
        if criterion.criterion in {"pto", "assemblyWeight"}
    )
    assert result.missing_requirements == []


def test_missing_critical_requirement_is_reported():
    critical_missing = [
        requirement
        for requirement in REQUIREMENTS
        if requirement.key != "gearboxRatedInputTorque"
    ]

    result = recommend_bases(CANDIDATES, critical_missing)

    assert "gearboxRatedInputTorque" in result.missing_requirements


def test_spectrum_comparison_operators_are_strict():
    assert _compare(2600, ">", 2600) is False
    assert _compare(2601, ">", 2600) is True
    assert _compare(2600, "<", 2600) is False
    assert _compare(2599, "<", 2600) is True
    assert _compare(2600, "=", 2600) is True
    assert _compare(2600, "≈", 2600) is False


def test_unambiguous_top_gear_and_optional_pto_are_scored():
    requirements = [
        replace(requirement, value="直接档")
        if requirement.key == "topGearType"
        else replace(requirement, value="not_required")
        if requirement.key == "pto"
        else requirement
        for requirement in REQUIREMENTS
    ]

    result = recommend_bases(CANDIDATES, requirements, top_n=10)
    top = next(
        item for item in result.top3 if item.base.display_code == "JX-12A"
    )

    top_gear = next(
        criterion
        for criterion in top.criteria
        if criterion.criterion == "topGearType"
    )
    assert top_gear.satisfied is True
    assert top_gear.score == 100.0

    pto = next(
        criterion
        for criterion in top.criteria
        if criterion.criterion == "pto"
    )
    assert pto.satisfied is True
    assert pto.score == 100.0

    jx13a = next(
        item for item in result.top3 if item.base.display_code == "JX-13A"
    )
    jx13a_top_gear = next(
        criterion
        for criterion in jx13a.criteria
        if criterion.criterion == "topGearType"
    )
    assert jx13a_top_gear.satisfied is False
    assert jx13a_top_gear.score == 0.0


def test_overdrive_and_unknown_top_gear_are_handled():
    overdrive = [
        replace(requirement, value="超速档")
        if requirement.key == "topGearType"
        else requirement
        for requirement in REQUIREMENTS
    ]
    result = recommend_bases(CANDIDATES, overdrive, top_n=10)
    jx13a = next(
        item for item in result.top3 if item.base.display_code == "JX-13A"
    )
    jx13a_top_gear = next(
        criterion
        for criterion in jx13a.criteria
        if criterion.criterion == "topGearType"
    )
    assert jx13a_top_gear.satisfied is True
    assert jx13a_top_gear.score == 100.0

    unknown = [
        replace(requirement, value="待定")
        if requirement.key == "topGearType"
        else requirement
        for requirement in REQUIREMENTS
    ]
    unknown_result = recommend_bases(CANDIDATES, unknown)
    unknown_top_gear = next(
        criterion
        for criterion in unknown_result.top3[0].criteria
        if criterion.criterion == "topGearType"
    )
    assert unknown_top_gear.score is None
    assert "无法识别" in unknown_top_gear.reason


def test_low_torque_and_light_candidate_branches():
    low_torque = CandidateBase(
        id="b5",
        display_code="JX-12D",
        name="JX-12D 12档 AMT",
        transmission_type="AMT",
        gear_count=12,
        rated_input_torque=2500,
        first_gear_ratio=15.0,
        top_gear_type="direct",
        has_pto=True,
        weight_kg=240,
        source="合成型谱库 V1（示意数据）",
    )

    result = recommend_bases(
        [*CANDIDATES, low_torque], REQUIREMENTS, top_n=10
    )
    evaluation = next(
        item for item in result.top3 if item.base.display_code == "JX-12D"
    )

    assert "gearboxRatedInputTorque" in evaluation.hard_failures
    torque = next(
        criterion
        for criterion in evaluation.criteria
        if criterion.criterion == "torqueMargin"
    )
    weight = next(
        criterion
        for criterion in evaluation.criteria
        if criterion.criterion == "weightMargin"
    )
    assert torque.score == 0.0
    assert weight.score == 100.0


def test_invalid_numeric_requirement_is_missing_not_zero():
    invalid = [
        replace(requirement, value="abc")
        if requirement.key == "gearboxRatedInputTorque"
        else requirement
        for requirement in REQUIREMENTS
    ]

    result = recommend_bases(CANDIDATES, invalid)
    top = result.top3[0]
    assert "gearboxRatedInputTorque" in top.missing_items
    torque = next(
        criterion
        for criterion in top.criteria
        if criterion.criterion == "gearboxRatedInputTorque"
    )
    assert torque.score is None
    assert "无法解析" in torque.reason


def test_top_n_must_be_positive():
    with pytest.raises(ValueError):
        recommend_bases(CANDIDATES, REQUIREMENTS, top_n=0)
