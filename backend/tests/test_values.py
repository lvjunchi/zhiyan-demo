import pytest

from app.domain.values import normalize_value


def test_numeric_operator_boundaries_are_distinct():
    assert normalize_value("numeric", ">", "2600").operator == ">"
    assert normalize_value("numeric", ">=", "2600").operator == ">="
    assert normalize_value("numeric", "≥", "2600").operator == ">="
    assert normalize_value("numeric", "<", "2600").operator == "<"
    assert normalize_value("numeric", "<=", "2600").operator == "<="
    assert normalize_value("numeric", "≤", "2600").operator == "<="
    assert normalize_value("numeric", "=", "2600").operator == "="


def test_thousands_separator_and_decimal_are_normalized():
    normalized = normalize_value("numeric", ">=", "2,600.50")

    assert normalized.value_num == 2600.5
    assert normalized.value_text == "2600.5"


def test_invalid_numeric_values_are_rejected():
    for value in ["abc", "", "NaN", "Infinity", "inf"]:
        with pytest.raises(ValueError):
            normalize_value("numeric", ">=", value)


def test_range_keeps_bounds_and_rejects_reversed_range():
    normalized = normalize_value("range", "range", " -40 ～ 50 ")

    assert normalized.value_text == "-40~50"
    assert normalized.value_num == -40
    assert normalized.value_num_high == 50

    with pytest.raises(ValueError):
        normalize_value("range", "range", "50~-40")


def test_boolean_synonyms_are_canonicalized():
    assert normalize_value("boolean", "=", "需要").value_text == "required"
    assert (
        normalize_value("boolean", "=", "不需要").value_text
        == "not_required"
    )
    assert normalize_value("boolean", "=", "是").value_text == "required"
    assert normalize_value("boolean", "=", "否").value_text == "not_required"

    with pytest.raises(ValueError):
        normalize_value("boolean", "=", "maybe")


def test_text_is_trimmed_and_blank_is_rejected():
    normalized = normalize_value(
        "text", "text", "  按双方商定标准执行  "
    )
    assert normalized.value_text == "按双方商定标准执行"

    with pytest.raises(ValueError):
        normalize_value("text", "text", "   ")


def test_unknown_data_type_and_wrong_operator_are_rejected():
    with pytest.raises(ValueError):
        normalize_value("foo", "=", "1")
    with pytest.raises(ValueError):
        normalize_value("numeric", "≈", "1")
    with pytest.raises(ValueError):
        normalize_value("range", "=", "1~2")
    with pytest.raises(ValueError):
        normalize_value("boolean", ">=", "required")
