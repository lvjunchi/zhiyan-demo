from pathlib import Path
import json
import re
import pytest
from app.document_text import extract_text
from app.domain.parser import parse_protocol

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "演示导入文件" / "综合演示"


def test_word_pdf_bundle_has_equivalent_nine_category_requirements():
    results = []
    for suffix in ("docx", "pdf"):
        path = BUNDLE / f"01_综合技术协议_V1.{suffix}"
        assert path.is_file(), str(path)
        extracted = extract_text(path.name, path.read_bytes())
        result = parse_protocol(extracted["content"])
        assert result.missing_categories == []
        assert {issue.requirement_key for issue in result.issues} == {
            "topGearType",
            "durability",
        }
        assert all(
            row.source_location != "未定位" and row.source_excerpt
            for row in result.requirements
        )
        results.append(
            sorted(
                (
                    row.key,
                    re.sub(r"\s+", "", row.value_text),
                    re.sub(r"\s+", "", row.unit),
                )
                for row in result.requirements
            )
        )
    assert results[0] == results[1]


def test_independent_fixture_inputs_are_explicit_and_not_implicit_execution_results():
    sample = json.loads((BUNDLE / "05_样件与实测样例.json").read_text(encoding="utf-8"))
    assert sample["mode"] == "manual" and sample["data_kind"] == "synthetic"
    assert (
        sample["comparison_pass"]["parameters"][0]["measured_value"]
        != sample["comparison_fail"]["parameters"][0]["measured_value"]
    )
    tests = json.loads((BUNDLE / "04_试验与评审样例.json").read_text(encoding="utf-8"))
    assert tests["static_torsion"]["wrong_load"]["load_basis_numeric"] == 2600
    assert tests["static_torsion"]["new_fail"]["backup_coefficient"] == 2.4
    assert tests["static_torsion"]["new_pass"]["load_basis_numeric"] == 2800
    assert tests["static_torsion"]["new_pass"]["backup_coefficient"] >= 2.5
    progress = json.loads(
        (BUNDLE / "06_协同记录与进度样例.json").read_text(encoding="utf-8")
    )
    assert (
        progress["progress"][0]["actual_percent"]
        > progress["progress"][1]["actual_percent"]
    )


def test_retired_review_item_is_history_not_a_current_version_conflict(catalog_client):
    from test_engineering_versions import _setup_scenario

    project_id, _ = _setup_scenario(catalog_client)
    initial = catalog_client.post(
        f"/api/projects/{project_id}/design-review",
        json={"base_display_code": "JX-12A"},
    ).json()
    assert any(item["display_code"] == "DR-07" for item in initial["items"])
    for issue in catalog_client.get(f"/api/projects/{project_id}/issues").json():
        if issue["status"] == "open":
            closed = catalog_client.post(
                f"/api/issues/{issue['id']}/close",
                json={
                    "actor": "工程师",
                    "role": "design_engineer",
                    "expected_status": "open",
                    "resolution_type": "manual_supplement",
                    "resolution_note": "合成确认记录",
                    "evidence": "合成CN补充记录",
                },
            )
            assert closed.status_code == 200, closed.text
    refreshed = catalog_client.post(
        f"/api/projects/{project_id}/design-review",
        json={"base_display_code": "JX-12A"},
    ).json()
    assert not any(item["display_code"] == "DR-07" for item in refreshed["items"])
    check = catalog_client.post(f"/api/projects/{project_id}/consistency-checks").json()
    assert not any(
        row["object_type"] == "design_review_item" for row in check["conflicts"]
    )
