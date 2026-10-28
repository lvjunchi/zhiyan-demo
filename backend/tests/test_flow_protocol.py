from pathlib import Path
import pytest
from app.document_text import extract_text
from app.domain.parser import parse_protocol

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("extension", ["docx", "pdf"])
def test_flow_protocol_has_nineteen_requirements_and_explicit_criteria(extension):
    path = ROOT / "演示导入文件/流程演示" / f"01_流程演示协议_V1.{extension}"
    result = parse_protocol(extract_text(path.name, path.read_bytes())["content"])
    assert len(result.requirements) == 19
    assert result.issues == []
    requirements = {row.key: row for row in result.requirements}
    assert "超速档" in requirements["topGearType"].value_text
    assert "直接档" not in requirements["topGearType"].value_text
    assert "DEMO-DUR-001" in requirements["durability"].value_text
    assert "1000" in requirements["durability"].value_text


def test_original_protocol_keeps_its_clarification_scenario():
    path = ROOT / "演示导入文件/综合演示/01_综合技术协议_V1.docx"
    result = parse_protocol(extract_text(path.name, path.read_bytes())["content"])
    assert len(result.requirements) == 19
    assert len(result.issues) == 2
