import pytest
from app.domain.parser import parse_protocol


@pytest.mark.parametrize(
    "text,key,category",
    [
        ("润滑油采用75W-90齿轮油", "lubricant", "G"),
        ("油品要求采用合成齿轮油", "lubricant", "G"),
        ("换油周期不低于10万km", "oilChangeInterval", "G"),
        ("适用标准为GB/T 6404-2017", "applicableStandards", "H"),
        ("法规要求符合约定的车辆技术规范", "applicableStandards", "H"),
        ("出厂验收需提交参数记录与签字报告", "acceptanceMethod", "I"),
        ("验收方法为台架验证与文件评审", "acceptanceMethod", "I"),
        ("整机噪声不超过80 dB(A)", "noiseLimit", "F"),
    ],
)
def test_extended_protocol_fields_preserve_sources(text, key, category):
    result = parse_protocol("8.1 " + text)
    row = next((row for row in result.requirements if row.key == key), None)
    assert row is not None
    assert (
        row.category == category
        and row.source_location == "8.1"
        and row.source_excerpt == text
    )


def test_maintenance_unit_and_duplicate_extended_fields_are_retained():
    result = parse_protocol("8.1 换油周期不低于10万km；换油周期不低于80000 km。")
    rows = [row for row in result.requirements if row.key == "oilChangeInterval"]
    assert len(rows) == 2
    assert (
        rows[0].value_text == "10"
        and rows[0].unit == "万km"
        and rows[0].operator == ">="
    )
    assert any(issue.issue_type == "contradictory" for issue in result.issues)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("采用12档AMT结构", "AMT"),
        ("变速器为MT型", "MT"),
        ("SMART控制器", None),
        ("ATT自动控制", None),
    ],
)
def test_transmission_tokens_support_chinese_adjacency_without_matching_english_words(
    text, expected
):
    rows = [
        row
        for row in parse_protocol(text).requirements
        if row.key == "transmissionType"
    ]
    assert [row.value_text for row in rows] == ([] if expected is None else [expected])
