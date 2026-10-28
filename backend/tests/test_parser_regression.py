import pytest

from app.domain.parser import parse_protocol
from app.domain.values import parse_number


@pytest.mark.parametrize(
    "operator,expected",
    [
        ("<", "<"),
        (">", ">"),
        ("=", "="),
        ("<=", "<="),
        (">=", ">="),
        ("≤", "<="),
        ("≥", ">="),
    ],
)
def test_explicit_numeric_operator_is_preserved(operator, expected):
    result = parse_protocol(f"总成重量 {operator} 300 kg")
    assert result.requirements[0].operator == expected


def test_operator_belongs_to_its_own_parameter_in_compound_clause():
    result = parse_protocol("总成重量不超过 300 kg 且一档速比不低于 14.5")
    values = {row.key: row for row in result.requirements}
    assert values["assemblyWeight"].operator == "<="
    assert values["firstGearRatio"].operator == ">="


def test_repeated_parameter_inside_one_clause_is_not_discarded():
    result = parse_protocol("发动机最大扭矩 2600 N·m / 发动机最大扭矩 2800 N·m")
    assert [
        row.value_text for row in result.requirements if row.key == "engineMaxTorque"
    ] == ["2600", "2800"]
    assert any(issue.issue_type == "contradictory" for issue in result.issues)


@pytest.mark.parametrize("text", ["是否需要取力器待定", "取力器另行确认", "取力器可选"])
def test_undecided_pto_is_text_and_blocking_issue(text):
    result = parse_protocol(text)
    pto = next(row for row in result.requirements if row.key == "pto")
    assert pto.data_type == "text"
    assert pto.value_text == text
    assert any(
        issue.requirement_key == "pto" and issue.blocking_reason
        for issue in result.issues
    )


@pytest.mark.parametrize("value", ["2,6,00", "26,00", "1,,000", "1,000,", "1.2,3"])
def test_malformed_thousands_grouping_is_invalid(value):
    with pytest.raises(ValueError):
        parse_number(value)


def test_undecided_validation_requirement_creates_a_gate_blocking_issue(client):
    project = client.post(
        "/api/projects",
        json={
            "display_code": "P01",
            "name": "解析回归",
            "customer": "合成客户",
            "product": "变速器",
        },
    ).json()
    source = client.post(
        f"/api/projects/{project['id']}/source-documents",
        json={
            "display_code": "DOC-UNDECIDED",
            "doc_type": "protocol",
            "version": "V1",
            "content": "取力器是否需要待定",
            "mode": "manual",
        },
    )
    assert source.status_code == 201, source.text
    parsed = client.post(f"/api/source-documents/{source.json()['id']}/parse", json={})
    assert parsed.status_code == 200, parsed.text
    issue = next(row for row in parsed.json()["issues"] if row["parser_key"] == "pto")
    assert issue["status"] == "open"
    assert issue["severity"] in ("high", "blocking")
