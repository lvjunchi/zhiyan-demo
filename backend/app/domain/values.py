from __future__ import annotations

import math
import re
from dataclasses import dataclass

NUMERIC_OPERATORS = {">", ">=", "≥", "<", "<=", "≤", "="}
OPERATOR_CANONICAL = {
    ">": ">",
    ">=": ">=",
    "≥": ">=",
    "<": "<",
    "<=": "<=",
    "≤": "<=",
    "=": "=",
}
BOOLEAN_MAP = {
    "required": "required",
    "not_required": "not_required",
    "true": "required",
    "false": "not_required",
    "yes": "required",
    "no": "not_required",
    "是": "required",
    "否": "not_required",
    "需要": "required",
    "不需要": "not_required",
    "有": "required",
    "无": "not_required",
}

_RANGE_PATTERN = re.compile(
    r"\s*(-?\d+(?:\.\d+)?)\s*(?:～|~|至)\s*(-?\d+(?:\.\d+)?)\s*"
)


@dataclass(frozen=True)
class NormalizedValue:
    operator: str
    value_text: str
    value_num: float | None
    value_num_high: float | None


def parse_number(text: str) -> float:
    grouped = text.strip().replace("，", ",")
    if "," in grouped and not re.fullmatch(
        r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", grouped
    ):
        raise ValueError("千位分隔符格式无效")
    cleaned = grouped.replace(",", "")
    if not cleaned:
        raise ValueError("数值不能为空")
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise ValueError(f"无法解析数值：{text!r}") from exc
    if not math.isfinite(value):
        raise ValueError("数值必须是有限数")
    return value


def format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return format(value, ".15g")


def parse_range(text: str) -> tuple[float, float]:
    match = _RANGE_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError("范围格式应为“下限～上限”，例如 -40～50")
    low = float(match.group(1))
    high = float(match.group(2))
    if not (math.isfinite(low) and math.isfinite(high)):
        raise ValueError("范围必须是有限数")
    return low, high


def normalize_value(data_type: str, operator: str, value_text: str) -> NormalizedValue:
    if data_type == "numeric":
        if operator not in NUMERIC_OPERATORS:
            raise ValueError("数值需求必须使用 >、>=、≥、<、<=、≤ 或 =")
        number = parse_number(value_text)
        return NormalizedValue(
            operator=OPERATOR_CANONICAL[operator],
            value_text=format_number(number),
            value_num=number,
            value_num_high=None,
        )
    if data_type == "range":
        if operator != "range":
            raise ValueError("范围需求必须使用 operator=range")
        low, high = parse_range(value_text)
        if low > high:
            raise ValueError("范围下限不能大于上限")
        return NormalizedValue(
            operator="range",
            value_text=f"{format_number(low)}~{format_number(high)}",
            value_num=low,
            value_num_high=high,
        )
    if data_type == "boolean":
        if operator != "=":
            raise ValueError("布尔需求必须使用 operator='='")
        canonical = BOOLEAN_MAP.get(value_text.strip())
        if canonical is None:
            raise ValueError(
                "布尔值必须为 required/not_required/true/false/yes/no/是/否/需要/不需要"
            )
        return NormalizedValue(
            operator="=",
            value_text=canonical,
            value_num=None,
            value_num_high=None,
        )
    if data_type == "text":
        text = value_text.strip()
        if not text:
            raise ValueError("文本需求不能为空")
        return NormalizedValue(
            operator="text",
            value_text=text,
            value_num=None,
            value_num_high=None,
        )
    raise ValueError(f"未知数据类型：{data_type}")
