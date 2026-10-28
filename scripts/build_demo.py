"""Build a repeatable local demo database without touching data/zhiyan.db."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

from app import design_services, services  # noqa: E402
from app.db import connect, run_migrations  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import package_scenario  # noqa: E402

DEFAULT_DB = ROOT / "data" / "demo.db"
PROTECTED_DATABASES = {
    (ROOT / "data" / "zhiyan.db").resolve(),
}


def _ok(response: Any, status: int = 200) -> Any:
    if response.status_code != status:
        raise RuntimeError(
            f"{response.request.method} {response.request.url} "
            f"-> {response.status_code}: {response.text}"
        )
    return response.json()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reset_database(db_path: Path) -> None:
    if db_path.resolve() in PROTECTED_DATABASES:
        raise SystemExit(
            f"拒绝重置受保护数据库：{db_path}。演示库请使用 data/demo*.db"
        )
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def _seed_reference_data(db_path: Path) -> dict[str, Any]:
    connection = connect(db_path)
    try:
        run_migrations(connection)
        catalog = services.seed_catalog(connection)
        history = design_services.seed_history(connection)
    finally:
        connection.close()
    return {"catalog": catalog, "history": history}


def _build_playground_project(client: TestClient) -> dict[str, Any]:
    project = _ok(
        client.post(
            "/api/projects",
            json={
                "display_code": "P02",
                "name": "现场演练项目（从需求确认开始）",
                "customer": "陕汽集团",
                "product": "重型商用车变速器",
            },
        ),
        201,
    )
    source = _ok(
        client.post(
            f"/api/projects/{project['id']}/source-documents",
            json={
                "display_code": "DOC-P02-001",
                "doc_type": "protocol",
                "version": "V1",
                "content": package_scenario.FIXED_PROTOCOL,
                "mode": "manual",
            },
        ),
        201,
    )
    display_code_map = {
        key: value.replace("P01", "P02")
        for key, value in package_scenario.DISPLAY_CODE_MAP.items()
    }
    parsed = _ok(
        client.post(
            f"/api/source-documents/{source['id']}/parse",
            json={"display_code_map": display_code_map},
        )
    )
    requirements = _ok(
        client.get(f"/api/projects/{project['id']}/requirements")
    )
    issues = _ok(client.get(f"/api/projects/{project['id']}/issues"))
    return {
        "project": {
            "id": project["id"],
            "display_code": project["display_code"],
            "name": project["name"],
        },
        "source": {
            "id": source["id"],
            "display_code": source["display_code"],
            "content_hash": source["content_hash"],
            "mode": source["mode"],
        },
        "parsed_status": parsed["status"],
        "parsed_at": parsed["parsed_at"],
        "requirement_count": len(requirements),
        "open_issue_count": sum(
            1 for issue in issues if issue["status"] == "open"
        ),
        "missing_categories": parsed["missing_categories"],
        "draft_requirement_codes": [
            item["display_code"] for item in requirements
        ],
    }


def _build_demo_database(
    db_path: Path, export_package: Path | None
) -> dict[str, Any]:
    _seed_reference_data(db_path)
    app = create_app(db_path=str(db_path))
    with TestClient(app) as client:
        scenario = package_scenario.build_ready_project(
            client,
            accept_coordination_risk=True,
            include_sample=True,
            include_coordination=True,
        )
        project_id = scenario["project"]["id"]

        recommendations = _ok(
            client.post(
                f"/api/projects/{project_id}/recommend-bases",
                json={"top_n": 3},
            )
        )
        base_display_code = recommendations["top3"][0]["base"][
            "display_code"
        ]
        variants = _ok(
            client.post(
                f"/api/projects/{project_id}/variant-analysis",
                json={"base_display_code": base_display_code},
            )
        )
        matrix = _ok(
            client.get(
                f"/api/projects/{project_id}/traceability-matrix"
            )
        )
        review_after = _ok(
            client.get(f"/api/projects/{project_id}/design-review")
        )
        fmea_after = _ok(
            client.get(f"/api/projects/{project_id}/dfmea")
        )
        latest_check = _ok(
            client.get(
                f"/api/projects/{project_id}/consistency-checks/latest"
            )
        )
        package = _ok(
            client.post(
                f"/api/projects/{project_id}/material-packages",
                json={
                    "include_originals": False,
                    "actor": "演示负责人",
                },
            ),
            201,
        )
        download = client.get(
            f"/api/material-packages/{package['id']}/download"
        )
        if download.status_code != 200:
            raise RuntimeError(
                f"材料包下载失败：{download.status_code} {download.text}"
            )
        archive_bytes = download.content
        archive_hash = _sha256(archive_bytes)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            archive_entries = sorted(archive.namelist())
            if "manifest.json" not in archive_entries:
                raise RuntimeError("材料包缺少 manifest.json")
            manifest = json.loads(
                archive.read("manifest.json").decode("utf-8")
            )
        if export_package is not None:
            export_package.parent.mkdir(parents=True, exist_ok=True)
            export_package.write_bytes(archive_bytes)

        playground = _build_playground_project(client)

    db_hash = _sha256(db_path.read_bytes())
    run_count = len(scenario["runs"])
    return {
        "database": str(db_path),
        "database_sha256": db_hash,
        "primary_project": {
            "id": project_id,
            "display_code": scenario["project"]["display_code"],
            "name": scenario["project"]["name"],
            "requirement_count": len(scenario["requirements"]),
            "open_high_issues_closed": len(
                scenario["closed_issues"]
            ),
            "recommended_bases": [
                {
                    "display_code": item["base"]["display_code"],
                    "score": item["score"],
                }
                for item in recommendations["top3"]
            ],
            "variant_base": base_display_code,
            "variant_count": len(variants.get("variants", [])),
            "reusable_part_count": len(
                variants.get("reusable_parts", [])
            ),
            "design_review_status": review_after["review"]["status"],
            "dfmea_status": fmea_after["fmea"]["status"],
            "test_cases": len(scenario["cases"]),
            "test_runs": run_count,
            "coverage_percentage": matrix["coverage_percentage"],
            "covered_count": matrix["covered_count"],
            "denominator": matrix["denominator"],
            "sample_comparison_result": scenario["sample"]["comparison"][
                "comparison"
            ]["overall_result"],
            "consistency_check_status": latest_check["check"]["status"],
            "coordination_risk": scenario["coordination"]["metric"][
                "metric_run"
            ]["risk"]["risk_level"],
            "package": {
                "id": package["id"],
                "display_code": package["display_code"],
                "status": package["status"],
                "snapshot_hash": package["snapshot_hash"],
                "blockers": package["gate"]["blockers"],
                "zip_sha256": archive_hash,
                "zip_bytes": len(archive_bytes),
                "zip_entries": archive_entries,
                "manifest_project": manifest.get("project", {}).get(
                    "display_code"
                ),
            },
            "export_package": (
                str(export_package) if export_package is not None else None
            ),
        },
        "playground_project": playground,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="构建本地演示数据库（默认 data/demo.db）"
    )
    parser.add_argument("db_path", nargs="?", default=str(DEFAULT_DB))
    parser.add_argument(
        "--reset",
        action="store_true",
        help="显式删除已存在的目标演示库后重建",
    )
    parser.add_argument(
        "--export-package",
        type=Path,
        help="将 P01 材料包 ZIP 写入指定路径",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if db_path.exists():
        if not args.reset:
            raise SystemExit(
                f"目标数据库已存在：{db_path}。"
                "如需重建演示库，请显式加 --reset。"
            )
        _reset_database(db_path)
    else:
        _reset_database(db_path)

    summary = _build_demo_database(db_path, args.export_package)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
