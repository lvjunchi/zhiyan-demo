from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_PATTERN = re.compile(
    r"^\s*(?:§\s*)?(?P<section>\d+(?:\.\d+)+)\s*[、.:：]?\s*(?P<body>.*)$"
)
CLAUSE_SPLIT_PATTERN = re.compile(r"[。；;，]")
NUMERIC_TOKEN = r"(?P<number>-?\d[\d,]*(?:\.\d+)?)"
CONDITION_PATTERN = re.compile(
    r"(?P<condition>\d+(?:\.\d+)?\s*(?:r\s*/\s*min|rpm|转\s*/\s*分))"
)
STANDARD_PATTERN = re.compile(r"(?:GB|QC/T|JB/T|ISO)\s*\d+[-\d]*|DEMO-DUR-\d{3}")
UNITLESS_NUMERIC_KEYS = {"firstGearRatio"}


@dataclass
class ParsedRequirement:
    key: str
    category: str
    parameter_name: str
    data_type: str
    operator: str
    value_text: str
    unit: str
    raw_expression: str
    source_location: str
    source_excerpt: str
    condition_text: str = ""
    reference_key: str | None = None
    reference_relation: str | None = None


@dataclass
class ParsedIssue:
    issue_type: str
    category: str
    message: str
    source_location: str
    source_excerpt: str
    blocking_reason: str
    suggestion: str
    requirement_key: str | None = None


@dataclass
class ParseResult:
    requirements: list[ParsedRequirement] = field(default_factory=list)
    issues: list[ParsedIssue] = field(default_factory=list)
    missing_categories: list[str] = field(default_factory=lambda: list("ABCDEFGHI"))
    unrecognized_clauses: list[str] = field(default_factory=list)
    mode: str = "rule"


@dataclass(frozen=True)
class _Clause:
    section: str
    text: str


def _iter_clauses(text: str) -> list[_Clause]:
    clauses: list[_Clause] = []
    current_section = "未定位"
    current_origin = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        origin = re.fullmatch(
            r"【(?P<origin>PDF 第 \d+ 页|DOCX 段落 \d+|TXT 行 \d+)】", line
        )
        if origin:
            current_origin = origin.group("origin")
            current_section = "未定位"
            continue
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            current_section = section_match.group("section")
            line = section_match.group("body").strip()
        for part in CLAUSE_SPLIT_PATTERN.split(line):
            part = part.strip().strip("：:")
            if part:
                location = (
                    current_origin
                    if current_section == "未定位" and current_origin
                    else current_section
                )
                if current_origin and current_section != "未定位":
                    location = f"{current_origin} · {current_section}"
                clauses.append(_Clause(location, part))
    return clauses


def _operator_for(clause: str, default: str) -> str:
    symbol = re.search(r">=|<=|≥|≤|>|<|=", clause)
    if symbol:
        return {"≥": ">=", "≤": "<="}.get(symbol.group(), symbol.group())
    if re.search(r"不低于|不小于|至少|≥|>=", clause):
        return ">="
    if re.search(r"不超过|不大于|至多|≤|<=", clause):
        return "<="
    if re.search(r"高于|大于", clause):
        return ">"
    if re.search(r"低于|小于", clause):
        return "<"
    return default


def _find_numbers(
    clause: str,
    aliases: tuple[str, ...],
    unit_pattern: str,
    default_operator: str = "=",
) -> list[tuple[str, str, str]]:
    alias_pattern = "|".join(re.escape(alias) for alias in aliases)
    pattern = re.compile(
        rf"(?:{alias_pattern})[^0-9\-]{{0,24}}{NUMERIC_TOKEN}"
        rf"\s*(?P<unit>{unit_pattern})?"
    )
    return [
        (
            match.group("number"),
            match.group("unit") or "",
            _operator_for(match.group(), default_operator),
        )
        for match in pattern.finditer(clause)
    ]


def _make_requirement(
    clause: _Clause,
    *,
    key: str,
    category: str,
    parameter_name: str,
    data_type: str,
    operator: str,
    value_text: str,
    unit: str,
    condition_text: str = "",
    reference_key: str | None = None,
    reference_relation: str | None = None,
) -> ParsedRequirement:
    return ParsedRequirement(
        key=key,
        category=category,
        parameter_name=parameter_name,
        data_type=data_type,
        operator=operator,
        value_text=value_text,
        unit=unit,
        raw_expression=clause.text,
        source_location=clause.section,
        source_excerpt=clause.text,
        condition_text=condition_text,
        reference_key=reference_key,
        reference_relation=reference_relation,
    )


def _issue(
    clause: _Clause,
    *,
    issue_type: str,
    category: str,
    message: str,
    blocking_reason: str,
    suggestion: str,
    requirement_key: str | None = None,
) -> ParsedIssue:
    return ParsedIssue(
        issue_type=issue_type,
        category=category,
        message=message,
        source_location=clause.section,
        source_excerpt=clause.text,
        blocking_reason=blocking_reason,
        suggestion=suggestion,
        requirement_key=requirement_key,
    )


def _parse_clause(
    clause: _Clause,
) -> tuple[list[ParsedRequirement], list[ParsedIssue]]:
    requirements: list[ParsedRequirement] = []
    issues: list[ParsedIssue] = []

    def add(requirement: ParsedRequirement) -> None:
        requirements.append(requirement)

    text = clause.text

    if "额定输入扭矩" in text and re.search(
        r"(?:不低于|不小于|≥|>=)\s*发动机最大扭矩", text
    ):
        add(
            _make_requirement(
                clause,
                key="gearboxRatedInputTorque",
                category="C",
                parameter_name="变速器最低额定输入扭矩",
                data_type="numeric",
                operator=">=",
                value_text="",
                unit="N·m",
                reference_key="engineMaxTorque",
                reference_relation=">=",
            )
        )

    engine_torque = _find_numbers(
        text,
        ("发动机最大扭矩", "最大扭矩"),
        r"N\s*[·.＊*]?\s*m|Nm|牛米|牛·米",
        default_operator="=",
    )
    for number, unit, operator in engine_torque:
        add(
            _make_requirement(
                clause,
                key="engineMaxTorque",
                category="B",
                parameter_name="发动机最大扭矩",
                data_type="numeric",
                operator=operator,
                value_text=number,
                unit="N·m" if unit else "",
            )
        )

    engine_power = _find_numbers(
        text,
        ("最大功率", "额定功率"),
        r"kW|千瓦",
        default_operator="=",
    )
    for number, unit, operator in engine_power:
        condition = CONDITION_PATTERN.search(text)
        add(
            _make_requirement(
                clause,
                key="engineMaxPower",
                category="B",
                parameter_name="发动机最大功率",
                data_type="numeric",
                operator=operator,
                value_text=number,
                unit="kW" if unit else "",
                condition_text=condition.group("condition") if condition else "",
            )
        )

    gvw = _find_numbers(
        text,
        ("整车总质量", "总质量"),
        r"t|吨|kg|千克",
        default_operator="=",
    )
    for number, unit, operator in gvw:
        add(
            _make_requirement(
                clause,
                key="grossVehicleWeight",
                category="B",
                parameter_name="整车总质量",
                data_type="numeric",
                operator=operator,
                value_text=number,
                unit=unit,
            )
        )

    gear_count = re.search(r"(?P<number>\d+)\s*档(?!\s*速比)", text)
    if gear_count is not None:
        add(
            _make_requirement(
                clause,
                key="gearCount",
                category="C",
                parameter_name="档位数",
                data_type="numeric",
                operator="=",
                value_text=gear_count.group("number"),
                unit="档",
            )
        )

    transmission_type = re.search(r"(?<![A-Za-z])(?P<type>AMT|MT|AT)(?![A-Za-z])", text)
    if transmission_type is not None:
        add(
            _make_requirement(
                clause,
                key="transmissionType",
                category="C",
                parameter_name="换挡方式",
                data_type="text",
                operator="text",
                value_text=transmission_type.group("type"),
                unit="",
            )
        )

    first_gear = _find_numbers(
        text,
        ("一档速比", "1档速比", "一挡速比", "1挡速比"),
        "",
        default_operator=">=",
    )
    for number, _, operator in first_gear:
        add(
            _make_requirement(
                clause,
                key="firstGearRatio",
                category="C",
                parameter_name="一档速比",
                data_type="numeric",
                operator=operator,
                value_text=number,
                unit="",
            )
        )

    if "最高档" in text:
        add(
            _make_requirement(
                clause,
                key="topGearType",
                category="C",
                parameter_name="最高档形式",
                data_type="text",
                operator="text",
                value_text=text,
                unit="",
            )
        )
        if "或" in text:
            issues.append(
                _issue(
                    clause,
                    issue_type="ambiguous",
                    category="C",
                    message=f"最高档类型未定型：{text}",
                    blocking_reason="无法确定最高档为直接档还是超速档",
                    suggestion="请主机厂明确最高档形式",
                    requirement_key="topGearType",
                )
            )

    if "取力器" in text:
        undecided = bool(re.search(r"是否|待定|待确认|另行确认|可选|待澄清", text))
        if undecided:
            pto_value = text
            issues.append(
                _issue(
                    clause,
                    issue_type="ambiguous",
                    category="C",
                    message="取力器需求尚未明确",
                    blocking_reason="不能将未定条款判为需要或不需要",
                    suggestion="请明确取力器是否需要并修订需求",
                    requirement_key="pto",
                )
            )
        elif re.search(r"无需|不需要|不配置|无取力器", text):
            pto_value = "不需要"
        else:
            pto_value = "需要"
        add(
            _make_requirement(
                clause,
                key="pto",
                category="C",
                parameter_name="取力器",
                data_type="text" if undecided else "boolean",
                operator="text" if undecided else "=",
                value_text=pto_value,
                unit="",
            )
        )

    weight = _find_numbers(
        text,
        ("总成重量", "重量"),
        r"kg|千克|公斤",
        default_operator="<=",
    )
    for number, unit, operator in weight:
        add(
            _make_requirement(
                clause,
                key="assemblyWeight",
                category="D",
                parameter_name="总成重量上限",
                data_type="numeric",
                operator=operator,
                value_text=number,
                unit=unit,
            )
        )

    if "离合器壳接口" in text:
        add(
            _make_requirement(
                clause,
                key="clutchHousingInterface",
                category="D",
                parameter_name="离合器壳接口",
                data_type="text",
                operator="text",
                value_text=text,
                unit="",
            )
        )

    if "耐久" in text:
        add(
            _make_requirement(
                clause,
                key="durability",
                category="F",
                parameter_name="耐久要求",
                data_type="text",
                operator="text",
                value_text=text,
                unit="",
            )
        )
        if STANDARD_PATTERN.search(text) is None:
            issues.append(
                _issue(
                    clause,
                    issue_type="missing",
                    category="F",
                    message=f"耐久判定标准未明确：{text}",
                    blocking_reason="缺少可执行的耐久判定标准",
                    suggestion="请补充耐久试验标准编号或明确判定准则",
                    requirement_key="durability",
                )
            )

    if any(vehicle in text for vehicle in ("牵引车", "载货车", "自卸车", "专用车")):
        add(
            _make_requirement(
                clause,
                key="vehicleConfig",
                category="A",
                parameter_name="整车配置",
                data_type="text",
                operator="text",
                value_text=text,
                unit="",
            )
        )

    if "环境温度" in text or "工作温度" in text:
        temperature = re.search(
            r"(?P<low>-?\d+(?:\.\d+)?)\s*(?:～|~|至|-)\s*"
            r"(?P<high>-?\d+(?:\.\d+)?)\s*℃",
            text,
        )
        if temperature is not None:
            add(
                _make_requirement(
                    clause,
                    key="operatingTemperature",
                    category="E",
                    parameter_name="使用环境温度",
                    data_type="range",
                    operator="range",
                    value_text=(
                        f"{temperature.group('low')}～" f"{temperature.group('high')}"
                    ),
                    unit="℃",
                )
            )

    for number, unit, operator in _find_numbers(
        text, ("换油周期", "维护里程"), r"万\s*km|km|公里", default_operator=">="
    ):
        add(
            _make_requirement(
                clause,
                key="oilChangeInterval",
                category="G",
                parameter_name="换油周期",
                data_type="numeric",
                operator=operator,
                value_text=number,
                unit=re.sub(r"\s+", "", unit),
            )
        )
    for number, unit, operator in _find_numbers(
        text, ("整机噪声", "噪声限值", "噪声"), r"dB\(A\)|dB", default_operator="<="
    ):
        add(
            _make_requirement(
                clause,
                key="noiseLimit",
                category="F",
                parameter_name="噪声限值",
                data_type="numeric",
                operator=operator,
                value_text=number,
                unit=unit,
            )
        )
    for aliases, key, category, name in (
        (("润滑油", "油品要求"), "lubricant", "G", "润滑油要求"),
        (
            ("适用标准", "执行标准", "法规要求"),
            "applicableStandards",
            "H",
            "适用标准与法规",
        ),
        (
            ("出厂验收", "验收方法", "验收要求"),
            "acceptanceMethod",
            "I",
            "试验与验收方法",
        ),
    ):
        if any(alias in text for alias in aliases):
            add(
                _make_requirement(
                    clause,
                    key=key,
                    category=category,
                    parameter_name=name,
                    data_type="text",
                    operator="text",
                    value_text=text,
                    unit="",
                )
            )

    return requirements, issues


def _resolve_references(
    requirements: list[ParsedRequirement],
    issues: list[ParsedIssue],
) -> None:
    engine_torques = [
        requirement
        for requirement in requirements
        if requirement.key == "engineMaxTorque"
    ]
    unique_torques = {
        (requirement.value_text, requirement.unit)
        for requirement in engine_torques
        if requirement.value_text
    }
    derived = [
        requirement
        for requirement in requirements
        if requirement.key == "gearboxRatedInputTorque"
    ]
    if not derived:
        return

    if len(unique_torques) == 1:
        value_text, unit = next(iter(unique_torques))
        for requirement in derived:
            requirement.value_text = value_text
            if unit:
                requirement.unit = unit
        return

    for requirement in derived:
        requirements.remove(requirement)
        if len(unique_torques) > 1:
            issues.append(
                ParsedIssue(
                    issue_type="contradictory",
                    category="C",
                    message=(
                        "发动机最大扭矩存在多个不一致值，"
                        "无法解析变速器最低额定输入扭矩"
                    ),
                    source_location=requirement.source_location,
                    source_excerpt=requirement.source_excerpt,
                    blocking_reason="派生要求依赖的上游参数不唯一",
                    suggestion="请人工确认唯一发动机最大扭矩后重新解析",
                    requirement_key="gearboxRatedInputTorque",
                )
            )
        else:
            issues.append(
                ParsedIssue(
                    issue_type="missing",
                    category="C",
                    message=("未找到发动机最大扭矩，" "无法解析变速器最低额定输入扭矩"),
                    source_location=requirement.source_location,
                    source_excerpt=requirement.source_excerpt,
                    blocking_reason="派生要求缺少可解析的上游参数",
                    suggestion="请补充发动机最大扭矩或人工建立派生关系",
                    requirement_key="gearboxRatedInputTorque",
                )
            )


def _add_duplicate_issues(
    requirements: list[ParsedRequirement],
    issues: list[ParsedIssue],
) -> None:
    grouped: dict[str, list[ParsedRequirement]] = {}
    for requirement in requirements:
        grouped.setdefault(requirement.key, []).append(requirement)

    for key, group in grouped.items():
        if len(group) < 2:
            continue
        values = {
            (
                requirement.value_text,
                requirement.unit,
                requirement.operator,
            )
            for requirement in group
        }
        if len(values) < 2:
            continue
        issues.append(
            ParsedIssue(
                issue_type="contradictory",
                category=group[0].category,
                message=(
                    f"{group[0].parameter_name}存在多个不一致值："
                    + "；".join(
                        f"{requirement.value_text} {requirement.unit}".strip()
                        for requirement in group
                    )
                ),
                source_location="、".join(
                    requirement.source_location for requirement in group
                ),
                source_excerpt="；".join(
                    requirement.source_excerpt for requirement in group
                ),
                blocking_reason="同一参数存在不同取值，无法确定唯一事实",
                suggestion="请人工确认唯一有效值并修订来源条款",
                requirement_key=key,
            )
        )


def parse_protocol(text: str) -> ParseResult:
    """Parse protocol text into structured requirements and open issues.

    The parser is deterministic and rule-based. It preserves every matched
    clause, records section-level evidence, flags contradictions and missing
    information, and never fabricates requirements for unrecognized text.
    """
    clauses = _iter_clauses(text)
    requirements: list[ParsedRequirement] = []
    issues: list[ParsedIssue] = []
    unrecognized: list[str] = []

    for clause in clauses:
        matched, clause_issues = _parse_clause(clause)
        if matched:
            requirements.extend(matched)
        else:
            unrecognized.append(clause.text)
        issues.extend(clause_issues)

    _resolve_references(requirements, issues)
    _add_duplicate_issues(requirements, issues)

    for requirement in requirements:
        if (
            requirement.data_type == "numeric"
            and not requirement.unit
            and requirement.key not in UNITLESS_NUMERIC_KEYS
        ):
            issues.append(
                ParsedIssue(
                    issue_type="missing",
                    category=requirement.category,
                    message=(f"{requirement.parameter_name}的单位缺失或无法识别"),
                    source_location=requirement.source_location,
                    source_excerpt=requirement.source_excerpt,
                    blocking_reason="无法确认数值单位",
                    suggestion="请补充可识别的单位，例如 kg、N·m、kW",
                    requirement_key=requirement.key,
                )
            )

    if not requirements:
        issues.append(
            ParsedIssue(
                issue_type="unparsed",
                category="",
                message="未识别到可结构化的需求条款，请人工检查或补录",
                source_location="未定位",
                source_excerpt="；".join(unrecognized)[:500],
                blocking_reason="规则解析未能识别任何需求",
                suggestion="请人工补录结构化需求，或提供更清晰的协议文本",
            )
        )

    present_categories = {
        requirement.category for requirement in requirements if requirement.category
    }
    missing_categories = [
        category for category in "ABCDEFGHI" if category not in present_categories
    ]

    return ParseResult(
        requirements=requirements,
        issues=issues,
        missing_categories=missing_categories,
        unrecognized_clauses=unrecognized,
    )
