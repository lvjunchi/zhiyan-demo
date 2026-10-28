"""Rehearse public APIs against a NEW isolated DB; never opens the daily workspace."""

from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import connect
from app import services, design_services

BUNDLE = ROOT / "演示导入文件" / "综合演示"
IDENTITY = {"actor": "合成排练工程师", "role": "design_engineer"}
REVIEW = {
    **IDENTITY,
    "decision": "confirmed",
    "comment": "依据配套合成记录核对当前版本",
}


def load(name: str) -> Any:
    return json.loads((BUNDLE / name).read_text(encoding="utf-8"))


def rehearse(output: Path) -> dict[str, Any]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "mode": "isolated synthetic rehearsal",
        "coverage_sequence": [],
        "actions": [],
    }
    database = output / "rehearsal.db"
    app = create_app(database)
    try:
        with TestClient(app) as client:

            def call(method: str, path: str, **kwargs: Any) -> Any:
                response = client.request(method, path, **kwargs)
                report["actions"].append(
                    {"method": method, "path": path, "status": response.status_code}
                )
                if not response.is_success:
                    raise AssertionError(
                        f"{method} {path}: {response.status_code} {response.text[:1500]}"
                    )
                return response.json()

            connection = connect(database)
            try:
                services.seed_catalog(connection)
                design_services.seed_history(connection)
            finally:
                connection.close()
            project = call(
                "POST",
                "/api/projects",
                json={
                    "display_code": "P01",
                    "name": "综合文件排练",
                    "customer": "合成客户",
                    "product": "重型变速器",
                },
            )
            pid = project["id"]
            report["project_id"] = pid
            before = call("GET", f"/api/projects/{pid}/overview")
            assert before["requirements"]["total"] == 0

            def import_file(ext: str, mapping: dict[str, str]) -> dict[str, Any]:
                name = f"01_综合技术协议_V1.{ext}"
                content = (BUNDLE / name).read_bytes()
                extracted = call(
                    "POST",
                    f"/api/projects/{pid}/document-imports/extract",
                    params={"filename": name},
                    content=content,
                )
                source = call(
                    "POST",
                    f"/api/projects/{pid}/source-documents",
                    json={
                        "display_code": f"DOC-COMPREHENSIVE-{ext.upper()}",
                        "version": "V1",
                        "doc_type": "protocol",
                        "mode": "manual",
                        "content": extracted["content"],
                        "import_id": extracted["import_id"],
                        "original_file": {
                            "filename": name,
                            "sha256": extracted["sha256"],
                            "data_base64": base64.b64encode(content).decode(),
                        },
                    },
                )
                return call(
                    "POST",
                    f"/api/source-documents/{source['id']}/parse",
                    json={"display_code_map": mapping},
                )

            parsed = import_file(
                "docx", load("协议正文与编号映射.json")["display_code_map"]
            )
            report["word_requirements"] = len(parsed["requirements"])
            old_ids = {row["id"] for row in parsed["requirements"]}
            assert len({row["category"] for row in parsed["requirements"]}) == 9
            requirements = lambda: call("GET", f"/api/projects/{pid}/requirements")

            def batch(rows: list[dict[str, Any]]) -> None:
                if not rows:
                    return
                items = [
                    {
                        "requirement_id": row["id"],
                        "expected_revision": row["current_revision"],
                    }
                    for row in rows
                ]
                preview = call(
                    "POST",
                    f"/api/projects/{pid}/requirements/batch-preview",
                    json={"items": items},
                )
                assert preview["can_submit"], [
                    (row["requirement"]["display_code"], row["reasons"])
                    for row in preview["rows"]
                    if not row["eligible"]
                ]
                confirmed = call(
                    "POST",
                    f"/api/projects/{pid}/requirements/batch-confirm",
                    json={
                        "items": items,
                        "expected_preview_hash": preview["preview_hash"],
                        **IDENTITY,
                        "comment": "排练工程师已按原文逐条核对本范围",
                    },
                )
                assert confirmed["confirmed_count"] == len(rows)

            all_items = [
                {
                    "requirement_id": row["id"],
                    "expected_revision": row["current_revision"],
                }
                for row in requirements()
            ]
            checked = call(
                "POST",
                f"/api/projects/{pid}/requirements/batch-preview",
                json={"items": all_items},
            )
            assert not checked["can_submit"]
            batch([row["requirement"] for row in checked["rows"] if row["eligible"]])

            def close_issue(issue: dict[str, Any], evidence: str) -> None:
                call(
                    "POST",
                    f"/api/issues/{issue['id']}/close",
                    json={
                        **IDENTITY,
                        "expected_status": "open",
                        "resolution_type": "manual_supplement",
                        "resolution_note": evidence,
                        "evidence": evidence,
                    },
                )

            top = next(
                row for row in requirements() if row["parser_key"] == "topGearType"
            )
            top = call(
                "PATCH",
                f"/api/requirements/{top['id']}",
                json={
                    "expected_revision": top["current_revision"],
                    "value_text": "超速档",
                    "source_excerpt": "合成澄清CN-01：最高档形式为超速档",
                },
            )
            for issue in call("GET", f"/api/projects/{pid}/issues"):
                if issue["status"] == "open" and issue["parser_key"] == "topGearType":
                    close_issue(issue, "合成澄清CN-01已明确超速档并修订当前需求")
            batch([top])
            trial = load("04_试验与评审样例.json")
            choices = load("03_零件选型样例.json")

            def engineering() -> None:
                data = call(
                    "POST",
                    f"/api/projects/{pid}/variant-analysis",
                    json={"base_display_code": "JX-12A"},
                )
                for variant in data["variants"]:
                    if variant["review_status"] != "confirmed":
                        call(
                            "POST",
                            f"/api/engineering-records/variant/{variant['id']}/confirmations",
                            json={**REVIEW, "expected_revision": variant["revision"]},
                        )
                groups = call("GET", f"/api/projects/{pid}/part-candidates")["parts"]
                for group in groups:
                    wanted = next(
                        (
                            row
                            for row in choices["selections"]
                            if row["part_name"] == group["record"]["part_name"]
                        ),
                        None,
                    )
                    if wanted and not group["selected_candidate_id"]:
                        candidate = next(
                            row
                            for row in group["candidates"]
                            if row["model_code"] == wanted["model_code"]
                        )
                        call(
                            "POST",
                            f"/api/engineering-records/part/{group['record']['id']}/selection",
                            json={
                                **IDENTITY,
                                "candidate_id": candidate["id"],
                                "expected_revision": group["record"]["revision"],
                                "comment": wanted["reason"],
                            },
                        )
                for row in call("GET", f"/api/projects/{pid}/engineering-records"):
                    if (
                        row["is_applicable"]
                        and row["kind"] == "part"
                        and row["review_status"] != "confirmed"
                    ):
                        call(
                            "POST",
                            f"/api/engineering-records/part/{row['id']}/confirmations",
                            json={**REVIEW, "expected_revision": row["revision"]},
                        )

            def design() -> None:
                review = call(
                    "POST",
                    f"/api/projects/{pid}/design-review",
                    json={"base_display_code": "JX-12A"},
                )
                if review["review"]["status"] != "confirmed":
                    call(
                        "POST",
                        f"/api/design-reviews/{review['review']['id']}/confirmations",
                        json={
                            **REVIEW,
                            "expected_revision": review["review"]["revision"],
                        },
                    )
                fmea = call(
                    "POST",
                    f"/api/projects/{pid}/dfmea",
                    json={"base_display_code": "JX-12A"},
                )
                for item in fmea["items"]:
                    scores = trial["fmea_scores"].get(
                        item["display_code"], trial["fmea_scores"]["default"]
                    )
                    updated = call(
                        "PATCH",
                        f"/api/fmea-items/{item['id']}",
                        json={
                            **IDENTITY,
                            "expected_revision": item["revision"],
                            **scores,
                        },
                    )
                    call(
                        "POST",
                        f"/api/fmea-items/{item['id']}/confirm-scores",
                        json={
                            **IDENTITY,
                            "expected_revision": updated["revision"],
                            "comment": trial["fmea_basis"],
                        },
                    )
                fmea = call("GET", f"/api/projects/{pid}/dfmea")
                if fmea["fmea"]["status"] != "confirmed":
                    call(
                        "POST",
                        f"/api/fmea-documents/{fmea['fmea']['id']}/confirmations",
                        json={**REVIEW, "expected_revision": fmea["fmea"]["revision"]},
                    )

            def plan_and_confirm() -> dict[str, Any]:
                plan = call("POST", f"/api/projects/{pid}/test-plan")
                if plan["plan"]["status"] != "confirmed":
                    call(
                        "POST",
                        f"/api/test-plans/{plan['plan']['id']}/confirmations",
                        json={**REVIEW, "expected_revision": plan["plan"]["revision"]},
                    )
                for case in plan["cases"]:
                    if case["validity"] == "stale":
                        case = call(
                            "PATCH",
                            f"/api/test-cases/{case['id']}",
                            json={
                                **IDENTITY,
                                "expected_revision": case["revision"],
                                "rebase_requirements": True,
                                "comment": "复核当前需求及DFMEA版本",
                            },
                        )
                    if (
                        case["case_key"] == "durability"
                        and not case["acceptance_criteria"]
                        and next(
                            row
                            for row in requirements()
                            if row["parser_key"] == "durability"
                        )["review_status"]
                        == "confirmed"
                    ):
                        case = call(
                            "PATCH",
                            f"/api/test-cases/{case['id']}",
                            json={
                                **IDENTITY,
                                "expected_revision": case["revision"],
                                "acceptance_criteria": trial["durability_criteria"],
                                "comment": "按独立澄清单补齐可执行判据",
                            },
                        )
                    if (
                        case["complete"]
                        and case["case_key"] != "durability"
                        and case["review_status"] != "confirmed"
                    ):
                        call(
                            "POST",
                            f"/api/test-cases/{case['id']}/confirmations",
                            json={**REVIEW, "expected_revision": case["revision"]},
                        )
                    elif (
                        case["complete"]
                        and case["case_key"] == "durability"
                        and next(
                            row
                            for row in requirements()
                            if row["parser_key"] == "durability"
                        )["review_status"]
                        == "confirmed"
                        and case["review_status"] != "confirmed"
                    ):
                        call(
                            "POST",
                            f"/api/test-cases/{case['id']}/confirmations",
                            json={**REVIEW, "expected_revision": case["revision"]},
                        )
                return call("GET", f"/api/projects/{pid}/test-plan")

            def coverage(expected: int) -> None:
                matrix = call("GET", f"/api/projects/{pid}/traceability-matrix")
                assert matrix["coverage_percentage"] == expected, matrix
                report["coverage_sequence"].append(expected)

            def execute(case: dict[str, Any], load_name: str) -> dict[str, Any]:
                base = {
                    **IDENTITY,
                    "expected_revision": case["revision"],
                    "conditions": trial["manual_run"]["conditions"],
                    "evidence": trial["manual_run"]["evidence"],
                }
                payload = (
                    {**base, **trial["static_torsion"][load_name]}
                    if case["case_kind"] == "static_torsion"
                    else {**base, "manual_result": "pass"}
                )
                return call("POST", f"/api/test-cases/{case['id']}/runs", json=payload)[
                    "run"
                ]

            engineering()
            design()
            plan = plan_and_confirm()
            coverage(80)
            old_runs = []
            for case in plan["cases"]:
                if case["review_status"] == "confirmed":
                    old_runs.append(execute(case, "initial_pass")["id"])
            engine = next(
                row for row in requirements() if row["parser_key"] == "engineMaxTorque"
            )
            call(
                "PATCH",
                f"/api/requirements/{engine['id']}",
                json={
                    "expected_revision": engine["current_revision"],
                    "value_text": "2800",
                    "source_excerpt": "合成变更BG-01：发动机最大扭矩2800 N·m",
                },
            )
            coverage(60)
            batch(
                [
                    row
                    for row in requirements()
                    if row["parser_key"]
                    in ("engineMaxTorque", "gearboxRatedInputTorque")
                ]
            )
            engineering()
            design()
            plan = plan_and_confirm()
            coverage(80)
            static = next(
                row for row in plan["cases"] if row["case_kind"] == "static_torsion"
            )
            assert execute(static, "wrong_load")["result"] != "pass"
            assert execute(static, "new_fail")["result"] == "fail"
            assert execute(static, "new_pass")["result"] == "pass"
            current_runs = {
                run["id"]
                for case in call("GET", f"/api/projects/{pid}/test-plan")["cases"]
                for run in case["runs"]
            }
            report["old_results_retained"] = set(old_runs) <= current_runs
            assert report["old_results_retained"]
            durability = next(
                row for row in requirements() if row["parser_key"] == "durability"
            )
            durability = call(
                "PATCH",
                f"/api/requirements/{durability['id']}",
                json={
                    "expected_revision": durability["current_revision"],
                    "value_text": trial["durability_criteria"],
                    "source_excerpt": trial["durability_criteria"],
                },
            )
            for issue in call("GET", f"/api/projects/{pid}/issues"):
                if issue["status"] == "open" and issue["parser_key"] == "durability":
                    close_issue(
                        issue, "合成CN-02及DEMO-DUR-001：等效台架循环1000h无失效"
                    )
            batch([durability])
            engineering()
            design()
            plan = plan_and_confirm()
            coverage(100)
            for case in plan["cases"]:
                if case["review_status"] == "confirmed":
                    assert execute(case, "new_pass")["result"] == "pass"
            sample = load("05_样件与实测样例.json")
            delivery = call(
                "POST",
                f"/api/projects/{pid}/sample-deliveries",
                json=sample["delivery"],
            )
            call(
                "PUT",
                f"/api/sample-deliveries/{delivery['id']}/file",
                params={"file_name": sample["file"]},
                content=(BUNDLE / sample["file"]).read_bytes(),
                headers={"Content-Type": "image/svg+xml"},
            )
            failed = call(
                "POST",
                f"/api/sample-deliveries/{delivery['id']}/comparison",
                json={**IDENTITY, **sample["comparison_fail"]},
            )
            assert failed["comparison"]["overall_result"] == "fail"
            passed = call(
                "POST",
                f"/api/sample-deliveries/{delivery['id']}/comparison",
                json={
                    **IDENTITY,
                    **sample["comparison_pass"],
                    "expected_revision": failed["comparison"]["revision"],
                },
            )
            assert passed["comparison"]["overall_result"] == "pass"
            for issue in call("GET", f"/api/projects/{pid}/issues"):
                if issue["status"] == "open":
                    close_issue(
                        issue,
                        f"合成复检证据：当前样件比对{passed['comparison']['id']}通过；当前用例已逐项重新执行，历史失败保留",
                    )
            call(
                "POST",
                f"/api/sample-comparisons/{passed['comparison']['id']}/confirmations",
                json={**REVIEW, "expected_revision": passed["comparison"]["revision"]},
            )
            design()
            plan = plan_and_confirm()
            for case in plan["cases"]:
                if case["review_status"] == "confirmed":
                    assert execute(case, "new_pass")["result"] == "pass"
            coord = load("06_协同记录与进度样例.json")
            topic = call(
                "POST", f"/api/projects/{pid}/coordination-topics", json=coord["topic"]
            )
            for record in coord["records"]:
                call(
                    "POST",
                    f"/api/coordination-topics/{topic['id']}/records",
                    json=record,
                )
            for row in coord["progress"]:
                call(
                    "POST",
                    f"/api/coordination-topics/{topic['id']}/progress",
                    json={**IDENTITY, **row, "expected_revision": 0},
                )
            metric = call(
                "POST", f"/api/coordination-topics/{topic['id']}/metrics", json={}
            )["metric_run"]
            assert metric["risk"]["risk_level"] == "high"
            call(
                "POST",
                f"/api/coordination-topics/{topic['id']}/risk-acceptances",
                json={
                    **IDENTITY,
                    "metric_run_id": metric["id"],
                    "note": coord["risk_acceptance_note"],
                },
            )
            check = call("POST", f"/api/projects/{pid}/consistency-checks")
            for conflict in check["conflicts"]:
                if conflict["status"] == "open":
                    assert not conflict["detected"], conflict
                    call(
                        "POST",
                        f"/api/conflicts/{conflict['id']}/close",
                        json={
                            **IDENTITY,
                            "expected_revision": conflict["revision"],
                            "resolution_type": "fixed",
                            "note": "已用当前版本完成复检",
                            "evidence": "当前用例执行与工程审核记录",
                        },
                    )
            check = call("GET", f"/api/projects/{pid}/consistency-checks/latest")
            call(
                "POST",
                f"/api/consistency-checks/{check['check']['id']}/confirmations",
                json={**REVIEW, "expected_revision": check["check"]["revision"]},
            )
            package = call(
                "POST",
                f"/api/projects/{pid}/material-packages",
                json={"include_originals": True, "actor": IDENTITY["actor"]},
            )
            assert package["status"] == "ready_to_submit", package["gate"]
            package = call(
                "POST",
                f"/api/material-packages/{package['id']}/approvals",
                json={
                    **IDENTITY,
                    "expected_snapshot_hash": package["snapshot_hash"],
                    "comment": "合成排练材料当前版本已核对，冻结快照",
                },
            )
            report["package_status"] = package["status"]
            report["package_id"] = package["id"]
            original = client.get(
                f"/api/material-packages/{package['id']}/download"
            ).content
            with zipfile.ZipFile(io.BytesIO(original)) as archive:
                assert archive.testzip() is None
            (output / "approved-material-package.zip").write_bytes(original)
            call(
                "POST",
                f"/api/coordination-topics/{topic['id']}/progress",
                json={
                    **IDENTITY,
                    **coord["progress"][1],
                    "actual_percent": 70,
                    "artifact_version": "V2",
                    "expected_revision": 1,
                },
            )
            report["frozen_export_unchanged"] = (
                client.get(f"/api/material-packages/{package['id']}/download").content
                == original
            )
            assert report["frozen_export_unchanged"]
            before_clear = call("GET", "/api/system/backup")
            (output / "before-clear-backup.json").write_text(
                json.dumps(before_clear, ensure_ascii=False), encoding="utf-8"
            )
            preview = call("POST", f"/api/projects/{pid}/clear-preview")
            cleared = call(
                "POST",
                f"/api/projects/{pid}/clear",
                json={
                    **IDENTITY,
                    "confirmation_code": "P01",
                    "expected_state_hash": preview["expected_state_hash"],
                },
            )
            assert cleared["status"] == "cleared"
            after = call("GET", "/api/system/backup")
            assert after["counts"]["part_candidates"] == 24
            assert requirements() == []
            parsed_pdf = import_file("pdf", {})
            report["pdf_requirements"] = len(parsed_pdf["requirements"])
            report["post_clear_requirement_ids_disjoint"] = old_ids.isdisjoint(
                row["id"] for row in parsed_pdf["requirements"]
            )
            assert report["word_requirements"] == report["pdf_requirements"]
            report["status"] = "passed"
            report["database"] = str(database)
    except BaseException as exc:
        report["status"] = "failed"
        report["failure"] = str(exc)
        raise
    finally:
        (output / "rehearsal-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = rehearse(args.output_dir)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "actions"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
