from app.domain.parser import parse_protocol

FIXED_PROTOCOL = """3.1 整车配置：6×4 牵引车，整车总质量 49 t；发动机最大扭矩 2600 N·m，最大功率 397 kW / 1900 r/min。
4.2 变速器要求：12 档 AMT，一档速比不低于 14.5，最高档为直接档或超速档；额定输入扭矩不低于发动机最大扭矩；需配置取力器接口。
4.5 安装：总成重量不超过 300 kg，离合器壳接口按主机厂图纸 SX-DRW-0215 执行。
7.1 耐久：台架耐久按双方商定标准执行。"""


def _by_key(result):
    return {requirement.key: requirement for requirement in result.requirements}


def test_fixed_protocol_extracts_fixed_and_extra_requirements():
    result = parse_protocol(FIXED_PROTOCOL)
    requirements = _by_key(result)

    assert set(requirements) == {
        "vehicleConfig",
        "grossVehicleWeight",
        "engineMaxTorque",
        "engineMaxPower",
        "gearCount",
        "transmissionType",
        "firstGearRatio",
        "topGearType",
        "gearboxRatedInputTorque",
        "pto",
        "assemblyWeight",
        "clutchHousingInterface",
        "durability",
    }

    engine_torque = requirements["engineMaxTorque"]
    assert engine_torque.category == "B"
    assert engine_torque.data_type == "numeric"
    assert engine_torque.operator == "="
    assert engine_torque.value_text == "2600"
    assert engine_torque.unit == "N·m"
    assert engine_torque.source_location == "3.1"
    assert "发动机最大扭矩" in engine_torque.source_excerpt

    rated_torque = requirements["gearboxRatedInputTorque"]
    assert rated_torque.category == "C"
    assert rated_torque.data_type == "numeric"
    assert rated_torque.operator == ">="
    assert rated_torque.value_text == "2600"
    assert rated_torque.unit == "N·m"
    assert rated_torque.reference_key == "engineMaxTorque"
    assert rated_torque.reference_relation == ">="
    assert rated_torque.source_location == "4.2"

    gear_count = requirements["gearCount"]
    assert gear_count.value_text == "12"
    assert gear_count.unit == "档"
    assert gear_count.source_location == "4.2"

    transmission_type = requirements["transmissionType"]
    assert transmission_type.category == "C"
    assert transmission_type.data_type == "text"
    assert transmission_type.value_text == "AMT"
    assert transmission_type.source_location == "4.2"

    first_gear = requirements["firstGearRatio"]
    assert first_gear.operator == ">="
    assert first_gear.value_text == "14.5"
    assert first_gear.unit == ""

    pto = requirements["pto"]
    assert pto.data_type == "boolean"
    assert pto.value_text == "需要"
    assert pto.category == "C"

    weight = requirements["assemblyWeight"]
    assert weight.operator == "<="
    assert weight.value_text == "300"
    assert weight.unit == "kg"
    assert weight.source_location == "4.5"

    power = requirements["engineMaxPower"]
    assert power.value_text == "397"
    assert power.unit == "kW"
    assert power.condition_text == "1900 r/min"

    durability = requirements["durability"]
    assert durability.category == "F"
    assert durability.data_type == "text"
    assert durability.source_location == "7.1"
    assert "双方商定标准" in durability.source_excerpt

    issue_messages = " ".join(issue.message for issue in result.issues)
    assert "最高档" in issue_messages
    assert "耐久" in issue_messages
    assert result.missing_categories == ["E", "G", "H", "I"]


def test_duplicate_contradictory_torque_is_preserved_and_flagged():
    text = """3.1 发动机最大扭矩 2600 N·m。
3.2 发动机最大扭矩 2800 N·m。
4.2 额定输入扭矩不低于发动机最大扭矩。"""

    result = parse_protocol(text)
    torque_values = [
        requirement.value_text
        for requirement in result.requirements
        if requirement.key == "engineMaxTorque"
    ]

    assert torque_values == ["2600", "2800"]
    assert not any(
        requirement.key == "gearboxRatedInputTorque"
        for requirement in result.requirements
    )
    assert any(
        issue.issue_type == "contradictory"
        and "发动机最大扭矩" in issue.message
        for issue in result.issues
    )
    assert any(
        issue.requirement_key == "gearboxRatedInputTorque"
        for issue in result.issues
    )


def test_unrecognized_text_returns_issue_not_fake_requirements():
    text = """这是一份与变速器无关的会议纪要。
本次会议讨论了项目排期。"""

    result = parse_protocol(text)

    assert result.requirements == []
    assert result.missing_categories == list("ABCDEFGHI")
    assert any(issue.issue_type == "unparsed" for issue in result.issues)
    assert all(clause in result.unrecognized_clauses for clause in [
        "这是一份与变速器无关的会议纪要",
        "本次会议讨论了项目排期",
    ])


def test_missing_unit_is_explicit_and_requirement_stays_draft():
    text = "4.5 安装：总成重量不超过 300。"

    result = parse_protocol(text)
    weight = next(
        requirement
        for requirement in result.requirements
        if requirement.key == "assemblyWeight"
    )

    assert weight.value_text == "300"
    assert weight.unit == ""
    assert any(
        issue.issue_type == "missing" and "单位" in issue.message
        for issue in result.issues
    )


def test_temperature_range_is_parsed_as_range_not_single_point():
    text = "5.1 使用环境温度 -40～50 ℃。"

    result = parse_protocol(text)
    temperature = next(
        requirement
        for requirement in result.requirements
        if requirement.key == "operatingTemperature"
    )

    assert temperature.category == "E"
    assert temperature.data_type == "range"
    assert temperature.operator == "range"
    assert temperature.unit == "℃"
    assert "-40" in temperature.value_text
    assert "50" in temperature.value_text
