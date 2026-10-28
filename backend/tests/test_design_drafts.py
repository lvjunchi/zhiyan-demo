from app.domain.design import (
    FMEA_SCALE,
    DesignProfile,
    IssueInput,
    RequirementInput,
    VariantInput,
    build_design_review,
    build_dfmea,
)


def _requirement(
    parser_key: str,
    display_code: str,
    value_text: str,
    *,
    unit: str = "",
    revision: int = 1,
    review_status: str = "confirmed",
) -> RequirementInput:
    return RequirementInput(
        requirement_id=f"req-{parser_key}",
        display_code=display_code,
        revision=revision,
        parser_key=parser_key,
        parameter_name=display_code,
        value_text=value_text,
        unit=unit,
        review_status=review_status,
        category="C",
    )


def _requirements() -> list[RequirementInput]:
    return [
        _requirement("engineMaxTorque", "REQ-P01-B-003", "2600", unit="N·m"),
        _requirement(
            "gearboxRatedInputTorque",
            "REQ-P01-C-002",
            "2600",
            unit="N·m",
        ),
        _requirement("gearCount", "REQ-P01-C-001", "12"),
        _requirement("transmissionType", "REQ-P01-C-001-T", "AMT"),
        _requirement("pto", "REQ-P01-C-006", "required"),
        _requirement(
            "assemblyWeight",
            "REQ-P01-D-002",
            "300",
            unit="kg",
        ),
    ]


def _profile() -> DesignProfile:
    return DesignProfile(
        project_display_code="P01",
        base_display_code="JX-12A",
        base_name="12 档 AMT 基型",
    )


def test_review_draft_has_independent_items_and_requirement_versions():
    variant = VariantInput(
        variant_id="variant-1",
        display_code="V-01",
        parameter_key="pto",
        parameter_name="取力器功能",
        affected_parts=("主箱壳体",),
        basis="基型无取力器，需求需要取力器",
    )
    issue = IssueInput(
        issue_id="issue-1",
        parser_key="durability",
        issue_type="ambiguous",
        message="耐久标准未明确",
        severity="medium",
    )

    draft = build_design_review(
        _profile(),
        _requirements(),
        [variant],
        [issue],
    )

    codes = [item.display_code for item in draft.items]
    assert codes[0] == "DR-01"
    assert len(codes) == len(set(codes))
    assert len(codes) >= 7

    torque = draft.items[0]
    assert "额定输入扭矩" in torque.check_point
    assert torque.responsible_role.endswith("（演示角色）")
    dependency_text = " ".join(
        dependency["display_code"] for dependency in torque.dependencies
    )
    assert "REQ-P01-C-002" in dependency_text
    assert "REQ-P01-B-003" in dependency_text
    assert all(
        dependency["revision"] == 1
        for dependency in torque.dependencies
        if dependency["object_type"] == "requirement"
    )

    manufacturing = next(
        item for item in draft.items if item.display_code == "DR-06"
    )
    assert manufacturing.dependencies[0]["display_code"] == "V-01"

    issue_item = next(
        item for item in draft.items if item.display_code == "DR-07"
    )
    assert issue_item.dependencies[0]["object_type"] == "issue"
    assert issue_item.dependencies[0]["object_id"] == "issue-1"


def test_review_draft_omits_pto_item_without_pto_requirement():
    requirements = [
        requirement
        for requirement in _requirements()
        if requirement.parser_key != "pto"
    ]

    draft = build_design_review(_profile(), requirements, [], [])

    assert all(item.display_code != "DR-03" for item in draft.items)
    assert "pto" in draft.missing_inputs


def test_review_draft_flags_unconfirmed_requirements():
    requirements = _requirements()
    requirements[2] = _requirement(
        "gearCount",
        "REQ-P01-C-001",
        "12",
        review_status="draft",
    )

    draft = build_design_review(_profile(), requirements, [], [])

    confirmation_item = next(
        item for item in draft.items if item.display_code == "DR-08"
    )
    assert "REQ-P01-C-001" in confirmation_item.standard_basis
    assert "draft" in draft.inputs_snapshot["unconfirmed_requirements"][0]["review_status"]


def test_dfmea_draft_has_null_scores_and_frozen_scale():
    draft = build_dfmea(_profile(), _requirements(), [])

    torque = draft.items[0]
    assert torque.display_code == "FMEA-01"
    assert "扭矩" in torque.function_text
    assert torque.failure_mode
    assert torque.cause
    assert torque.effect
    assert torque.control
    assert torque.action_text
    assert FMEA_SCALE["min"] == 1
    assert FMEA_SCALE["max"] == 10
    assert "合成" in FMEA_SCALE["source"]
    assert draft.scale == FMEA_SCALE
    assert len({item.display_code for item in draft.items}) == len(draft.items)


def test_dfmea_draft_adds_pto_and_housing_items_from_inputs():
    variant = VariantInput(
        variant_id="variant-1",
        display_code="V-01",
        parameter_key="pto",
        parameter_name="取力器功能",
        affected_parts=("主箱壳体", "取力器接口"),
        basis="新增取力器接口",
    )

    draft = build_dfmea(_profile(), _requirements(), [variant])

    codes = {item.display_code for item in draft.items}
    assert "FMEA-02" in codes
    assert "FMEA-03" in codes
    housing = next(
        item for item in draft.items if item.display_code == "FMEA-03"
    )
    assert "壳体" in housing.failure_mode or "壳体" in housing.cause
    assert any(
        dependency["display_code"] == "V-01"
        for dependency in housing.dependencies
    )


def test_dfmea_draft_omits_optional_items_without_matching_inputs():
    requirements = [
        requirement
        for requirement in _requirements()
        if requirement.parser_key not in {"pto", "assemblyWeight"}
    ]
    requirements = [
        requirement
        for requirement in requirements
        if requirement.parser_key != "transmissionType"
    ]

    draft = build_dfmea(_profile(), requirements, [])

    codes = {item.display_code for item in draft.items}
    assert "FMEA-02" not in codes
    assert "FMEA-04" not in codes
    assert "FMEA-05" not in codes
