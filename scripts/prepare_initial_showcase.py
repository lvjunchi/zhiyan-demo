"""Build a full synthetic opening scene, then optionally activate it with a backup."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Protocol
from urllib.parse import urlparse
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app import design_services, services  # noqa: E402
from app.backup_services import Snapshot, validate_snapshot  # noqa: E402
from app.db import connect, utc_now  # noqa: E402
from app.main import create_app  # noqa: E402

SOURCE = ROOT / "演示导入文件/01_重型变速器技术协议_V1.docx"
BUNDLE = ROOT / "演示导入文件/综合演示"
IDENTITY = {"actor": "初始展示准备（合成）", "role": "演示场景准备"}
REVIEW = {
    **IDENTITY,
    "decision": "confirmed",
    "comment": "合成初始展示夹具审核，不代表真实工程签核",
}
MAPPING = {
    "engineMaxTorque": "REQ-P01-B-003",
    "gearboxRatedInputTorque": "REQ-P01-C-002",
    "gearCount": "REQ-P01-C-001",
    "transmissionType": "REQ-P01-C-001-T",
    "pto": "REQ-P01-C-006",
    "assemblyWeight": "REQ-P01-D-002",
    "durability": "REQ-P01-F-001",
}


class Client(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


def call(client: Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    if response.status_code not in (200, 201):
        raise RuntimeError(f"{method} {path}: {response.status_code}: {response.text}")
    return response.json()


def load(name: str) -> dict[str, Any]:
    return json.loads((BUNDLE / name).read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def build(output: Path) -> dict[str, Any]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    database = output / "initial.db"
    with TestClient(create_app(database)) as client:
        connection = connect(database)
        try:
            services.seed_catalog(connection)
            design_services.seed_history(connection)
        finally:
            connection.close()
        project = call(
            client,
            "POST",
            "/api/projects",
            json={
                "display_code": "P01",
                "name": "法士特—陕汽定制项目试点",
                "customer": "陕汽集团",
                "product": "重型商用车变速器 · 合成初始展示",
            },
        )
        pid = project["id"]
        prefix = f"/api/projects/{pid}"
        raw = SOURCE.read_bytes()
        extracted = call(
            client,
            "POST",
            prefix + "/document-imports/extract",
            params={"filename": SOURCE.name},
            content=raw,
        )
        source = call(
            client,
            "POST",
            prefix + "/source-documents",
            json={
                "display_code": "DOC-INITIAL-001",
                "version": "V1",
                "doc_type": "protocol",
                "mode": "manual",
                "content": extracted["content"],
                "import_id": extracted["import_id"],
                "original_file": {
                    "filename": SOURCE.name,
                    "sha256": extracted["sha256"],
                    "data_base64": base64.b64encode(raw).decode(),
                },
            },
        )
        parsed = call(
            client,
            "POST",
            f"/api/source-documents/{source['id']}/parse",
            json={"display_code_map": MAPPING},
        )
        if len(parsed["requirements"]) != 13:
            raise RuntimeError("初版协议不再解析为13条，停止准备，请核对输入版本")
        trial = load("04_试验与评审样例.json")
        sample = load("05_样件与实测样例.json")
        # Clarifications are separate explicit synthetic inputs; the original Word stays unchanged.
        for row in parsed["requirements"]:
            if row["parser_key"] in ("topGearType", "durability"):
                text = (
                    "超速档"
                    if row["parser_key"] == "topGearType"
                    else trial["durability_criteria"]
                )
                call(
                    client,
                    "PATCH",
                    f"/api/requirements/{row['id']}",
                    json={
                        "expected_revision": row["current_revision"],
                        "value_text": text,
                        "source_excerpt": f"初始展示合成澄清单：{text}",
                    },
                )
        for issue in call(client, "GET", prefix + "/issues"):
            if issue["status"] == "open":
                call(
                    client,
                    "POST",
                    f"/api/issues/{issue['id']}/close",
                    json={
                        **IDENTITY,
                        "expected_status": "open",
                        "resolution_type": "manual_supplement",
                        "resolution_note": "初始展示合成CN-01明确超速档，CN-02采用DEMO-DUR-001等效循环1000h无失效",
                        "evidence": "独立样例：02_澄清单与变更说明.txt及04_试验与评审样例.json；非原协议自动给出",
                    },
                )
        requirements = call(client, "GET", prefix + "/requirements")
        items = [
            {"requirement_id": row["id"], "expected_revision": row["current_revision"]}
            for row in requirements
        ]
        preview = call(
            client,
            "POST",
            prefix + "/requirements/batch-preview",
            json={"items": items},
        )
        if not preview["can_submit"]:
            raise RuntimeError(f"初始展示需求仍有阻塞：{preview['rows']}")
        call(
            client,
            "POST",
            prefix + "/requirements/batch-confirm",
            json={
                **IDENTITY,
                "items": items,
                "expected_preview_hash": preview["preview_hash"],
                "comment": REVIEW["comment"],
            },
        )
        call(client, "POST", prefix + "/recommend-bases", json={"top_n": 3})
        engineering = call(
            client,
            "POST",
            prefix + "/variant-analysis",
            json={"base_display_code": "JX-12A"},
        )

        def confirm(path: str, revision: int) -> Any:
            return call(
                client, "POST", path, json={**REVIEW, "expected_revision": revision}
            )

        for row in engineering["variants"]:
            confirm(
                f"/api/engineering-records/variant/{row['id']}/confirmations",
                row["revision"],
            )
        wanted = {
            row["part_name"]: row for row in load("03_零件选型样例.json")["selections"]
        }
        for group in call(client, "GET", prefix + "/part-candidates")["parts"]:
            if group["record"]["part_name"] not in wanted:
                continue
            choice = wanted[group["record"]["part_name"]]
            candidate = next(
                row
                for row in group["candidates"]
                if row["model_code"] == choice["model_code"]
            )
            call(
                client,
                "POST",
                f"/api/engineering-records/part/{group['record']['id']}/selection",
                json={
                    **IDENTITY,
                    "expected_revision": group["record"]["revision"],
                    "candidate_id": candidate["id"],
                    "comment": choice["reason"],
                },
            )
        for row in call(client, "GET", prefix + "/engineering-records"):
            if row["kind"] == "part" and row["is_applicable"]:
                confirm(
                    f"/api/engineering-records/part/{row['id']}/confirmations",
                    row["revision"],
                )
        review = call(
            client,
            "POST",
            prefix + "/design-review",
            json={"base_display_code": "JX-12A"},
        )["review"]
        confirm(f"/api/design-reviews/{review['id']}/confirmations", review["revision"])
        fmea = call(
            client, "POST", prefix + "/dfmea", json={"base_display_code": "JX-12A"}
        )
        for item in fmea["items"]:
            scores = trial["fmea_scores"].get(
                item["display_code"], trial["fmea_scores"]["default"]
            )
            updated = call(
                client,
                "PATCH",
                f"/api/fmea-items/{item['id']}",
                json={**IDENTITY, "expected_revision": item["revision"], **scores},
            )
            call(
                client,
                "POST",
                f"/api/fmea-items/{item['id']}/confirm-scores",
                json={
                    **IDENTITY,
                    "expected_revision": updated["revision"],
                    "comment": trial["fmea_basis"],
                },
            )
        fmea = call(client, "GET", prefix + "/dfmea")["fmea"]
        confirm(f"/api/fmea-documents/{fmea['id']}/confirmations", fmea["revision"])
        plan = call(client, "POST", prefix + "/test-plan")
        confirm(
            f"/api/test-plans/{plan['plan']['id']}/confirmations",
            plan["plan"]["revision"],
        )
        for case in plan["cases"]:
            if case["case_key"] == "durability":
                case = call(
                    client,
                    "PATCH",
                    f"/api/test-cases/{case['id']}",
                    json={
                        **IDENTITY,
                        "expected_revision": case["revision"],
                        "test_conditions": "合成样件/等效台架循环",
                        "load_conditions": "按合成规程DEMO-DUR-001",
                        "acceptance_criteria": trial["durability_criteria"],
                        "comment": "独立合成耐久判据",
                    },
                )
            if not case["complete"]:
                raise RuntimeError(f"用例依据不完整：{case['display_code']}")
            confirm(f"/api/test-cases/{case['id']}/confirmations", case["revision"])
            values = (
                trial["static_torsion"]["initial_pass"]
                if case["case_kind"] == "static_torsion"
                else {"manual_result": "pass"}
            )
            call(
                client,
                "POST",
                f"/api/test-cases/{case['id']}/runs",
                json={
                    **IDENTITY,
                    "expected_revision": case["revision"],
                    "conditions": trial["manual_run"]["conditions"],
                    "evidence": trial["manual_run"]["evidence"],
                    **values,
                },
            )
        delivery = call(
            client, "POST", prefix + "/sample-deliveries", json=sample["delivery"]
        )
        call(
            client,
            "PUT",
            f"/api/sample-deliveries/{delivery['id']}/file",
            params={"file_name": sample["file"]},
            content=(BUNDLE / sample["file"]).read_bytes(),
            headers={"Content-Type": "image/svg+xml"},
        )
        comparison = call(
            client,
            "POST",
            f"/api/sample-deliveries/{delivery['id']}/comparison",
            json={**IDENTITY, **sample["comparison_pass"]},
        )["comparison"]
        confirm(
            f"/api/sample-comparisons/{comparison['id']}/confirmations",
            comparison["revision"],
        )
        topic = call(
            client,
            "POST",
            prefix + "/coordination-topics",
            json={
                "name": "初始展示 · 接口交付协同（合成）",
                "expected_participants": ["主机厂", "法士特", "S-02"],
                "window_start": "2026-10-01T00:00:00+00:00",
                "window_end": "2026-10-20T00:00:00+00:00",
            },
        )
        tp = f"/api/coordination-topics/{topic['id']}"
        for index, end in enumerate(
            (
                "2026-10-03T01:00:00+00:00",
                "2026-10-03T06:00:00+00:00",
                "2026-10-03T11:00:00+00:00",
            ),
            1,
        ):
            for code, sender, stamp, reply in [
                (
                    f"SHOW-REQ-{index}",
                    "法士特",
                    f"2026-10-01T0{index}:00:00+00:00",
                    None,
                ),
                (f"SHOW-RES-{index}", "S-02", end, f"SHOW-REQ-{index}"),
            ]:
                call(
                    client,
                    "POST",
                    tp + "/records",
                    json={
                        "external_id": code,
                        "record_type": "message",
                        "sender": sender,
                        "content_summary": "独立合成展示沟通记录，非协议解析结果",
                        "sent_at": stamp,
                        "reply_to_external_id": reply,
                    },
                )
        for index in range(1, 5):
            call(
                client,
                "POST",
                tp + "/records",
                json={
                    "external_id": f"SHOW-REOPEN-{index}",
                    "record_type": "reopened",
                    "sender": "法士特",
                    "content_summary": "合成议题重开事件",
                    "sent_at": f"2026-10-08T0{index}:00:00+00:00",
                },
            )
        for participant, actual, version in [
            ("主机厂", 90, "V2"),
            ("法士特", 30, "V1"),
            ("S-02", 55, "V1"),
        ]:
            call(
                client,
                "POST",
                tp + "/progress",
                json={
                    **IDENTITY,
                    "participant": participant,
                    "milestone": "接口设计冻结",
                    "planned_percent": 80,
                    "actual_percent": actual,
                    "artifact_version": version,
                    "reported_at": "2026-10-19T08:00:00+00:00",
                    "evidence": "独立合成进度周报；非设备采集或协议推断",
                    "expected_revision": 0,
                },
            )
        metric = call(
            client, "POST", tp + "/metrics", json={"labor_hours": 6, "hourly_rate": 200}
        )["metric_run"]
        check = call(client, "POST", prefix + "/consistency-checks")["check"]
        confirm(
            f"/api/consistency-checks/{check['id']}/confirmations", check["revision"]
        )
        package = call(
            client,
            "POST",
            prefix + "/material-packages",
            json={"include_originals": True, "actor": IDENTITY["actor"]},
        )
        overview = call(client, "GET", prefix + "/overview")
        backup = call(client, "GET", "/api/system/backup")
        validate_snapshot(Snapshot.model_validate(backup))
        write_json(output / "initial-backup.json", backup)
        report = {
            "data_kind": "synthetic",
            "database": str(database),
            "project_id": pid,
            "source_file": str(SOURCE),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "requirements": overview["requirements"]["total"],
            "coverage": overview["traceability"]["coverage_percentage"],
            "passed_requirements": overview["traceability"]["execution_summary"].get(
                "pass", 0
            ),
            "coordination": {
                "latencies": metric["metrics"]["response_latencies_hours"],
                "average_response_hours": metric["metrics"]["average_response_hours"],
                "risk": metric["risk"]["risk_level"],
                "records": 10,
                "progress": 3,
            },
            "package_status": package["status"],
            "separate_inputs": [
                "合成澄清CN-01/CN-02",
                "03_零件选型样例.json",
                "04_试验与评审样例.json",
                "05_样件与实测样例.json",
                "合成沟通与进度周报",
            ],
            "note": "完整初始展示；不改变原协议，不自动接受高风险，不自动批准材料；清空后不自动补回样例",
        }
        write_json(output / "manifest.json", report)
    return report


def activate(
    client: Client, snapshot: dict[str, Any], backup_dir: Path
) -> dict[str, str]:
    validate_snapshot(Snapshot.model_validate(snapshot))
    projects = call(client, "GET", "/api/projects")
    if len(projects) != 1 or projects[0]["display_code"] != "P01":
        raise ValueError("存在其他项目或不是单项目P01，拒绝整体替换")
    old = call(client, "GET", "/api/system/backup")
    _, _, saved_projects = validate_snapshot(Snapshot.model_validate(old))
    if len(saved_projects) != 1 or saved_projects[0]["display_code"] != "P01":
        raise ValueError("实际备份已包含其他项目，拒绝整体替换")
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"before-initial-showcase-{uuid.uuid4().hex}.json"
    write_json(path, old)
    reread = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
    validate_snapshot(reread)
    if reread.sha256 != old["sha256"]:
        raise RuntimeError("备份回读校验失败，未切换")
    preview = call(
        client, "POST", "/api/system/restore-preview", json={"backup": snapshot}
    )
    if preview["expected_state_hash"] != old["sha256"]:
        raise RuntimeError("备份后业务数据有变化，未切换，请重新备份再执行")
    call(
        client,
        "POST",
        "/api/system/restore",
        json={
            **IDENTITY,
            "backup": snapshot,
            "expected_state_hash": preview["expected_state_hash"],
        },
    )
    return {
        "backup": str(path),
        "status": "activated",
        "reload": "required",
        "activated_at": utc_now(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="必须是不存在的独立目录"
    )
    parser.add_argument("--activate-url", help="显式备份后载入运行中的单项目本地系统")
    args = parser.parse_args()
    if args.activate_url:
        parsed = urlparse(args.activate_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
        ):
            parser.error("仅支持本机HTTP服务根地址")
    report = build(args.output_dir)
    if args.activate_url:
        import httpx

        with httpx.Client(
            base_url=args.activate_url, trust_env=False, timeout=60
        ) as client:
            snapshot = json.loads(
                (args.output_dir / "initial-backup.json").read_text(encoding="utf-8")
            )
            result = activate(client, snapshot, ROOT / "data/backups")
            write_json(args.output_dir / "activation.json", result)
            report["activation"] = result
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
