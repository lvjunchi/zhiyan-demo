"""Create an explicit-criteria demonstration protocol without overwriting inputs."""

from pathlib import Path
import argparse
from docx import Document

ROOT = Path(__file__).resolve().parents[1]


def create(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    target = output / "01_流程演示协议_V1.docx"
    if target.exists():
        raise FileExistsError("不覆盖已有协议，请另选输出目录")
    doc = Document(ROOT / "演示导入文件/综合演示/01_综合技术协议_V1.docx")
    for paragraph in doc.paragraphs:
        if paragraph.text == "重型变速器综合技术协议":
            paragraph.text = "重型变速器流程演示技术协议"
        elif paragraph.text.startswith("编号 DEMO TX"):
            paragraph.text = "编号 DEMO FLOW 001   版本 V1   日期 2026年10月26日"
        elif "未定事项通过配套澄清单" in paragraph.text:
            paragraph.text = "本协议供智研引擎本地完整流程演示使用，正文条款采用明确的合成判据。全部标准和输入均为合成演示资料；需求仍须人工审核，设计决策、执行记录、实测数据及协同记录分别登记。"
        elif paragraph.text.startswith("3.4 "):
            paragraph.text = "3.4 最高档为超速档。"
        elif paragraph.text.startswith("6.1 "):
            paragraph.text = (
                "6.1 台架耐久按合成规程DEMO-DUR-001执行且等效台架循环1000 h无失效。"
            )
    doc.core_properties.title = "重型变速器流程演示技术协议"
    doc.core_properties.comments = "合成流程演示版；不覆盖原综合协议和澄清演示场景"
    doc.save(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "演示导入文件/流程演示"
    )
    print(create(parser.parse_args().output_dir))
