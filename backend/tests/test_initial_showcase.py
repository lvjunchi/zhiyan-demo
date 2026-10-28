from pathlib import Path
import base64
import hashlib
import importlib.util
import json

import pytest
from fastapi.testclient import TestClient
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / "scripts/prepare_initial_showcase.py"
    assert path.is_file(), "missing full initial showcase builder"
    spec = importlib.util.spec_from_file_location("initial_showcase", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_initial_showcase_uses_original_word_and_independent_business_records(tmp_path):
    report = module().build(tmp_path / "initial")
    assert report["requirements"] == 13
    assert report["coverage"] == 100
    assert report["passed_requirements"] == 5
    assert (
        report["source_sha256"]
        == hashlib.sha256(
            (ROOT / "演示导入文件/01_重型变速器技术协议_V1.docx").read_bytes()
        ).hexdigest()
    )
    assert report["coordination"]["latencies"] == [48, 52, 56]
    assert report["coordination"]["average_response_hours"] == 52
    assert report["coordination"]["risk"] == "high"
    assert report["coordination"]["records"] == 10
    assert report["coordination"]["progress"] == 3
    assert report["package_status"] == "draft"
    with TestClient(create_app(report["database"])) as client:
        pid = report["project_id"]
        sources = client.get(f"/api/projects/{pid}/source-documents").json()
        assert len(sources) == 1 and sources[0]["original_file"]["filename"].endswith(
            ".docx"
        )
        requirements = client.get(f"/api/projects/{pid}/requirements").json()
        engine = next(
            row for row in requirements if row["parser_key"] == "engineMaxTorque"
        )
        assert engine["value_text"] == "2600" and engine["current_revision"] == 1
        overview = client.get(f"/api/projects/{pid}/overview").json()
        assert (
            overview["design_review"]["status"]
            == overview["dfmea"]["status"]
            == "confirmed"
        )
        assert overview["samples"]["latest_result"] == "pass"
        assert overview["coordination"]["topic_count"] == 1
        assert (
            overview["package"]["blocker_count"] > 0
        )  # high risk intentionally awaits handling
        backup = client.get("/api/system/backup").json()
        saved = json.loads(
            (tmp_path / "initial/initial-backup.json").read_text(encoding="utf-8")
        )
        assert saved["sha256"] == backup["sha256"]
    marker = tmp_path / "initial/keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        module().build(tmp_path / "initial")
    assert marker.read_text(encoding="utf-8") == "keep"


def test_initial_showcase_can_clear_restart_and_import_comprehensive_word(tmp_path):
    report = module().build(tmp_path / "initial")
    pid = report["project_id"]
    with TestClient(create_app(report["database"])) as client:
        original_ids = {
            row["id"] for row in client.get(f"/api/projects/{pid}/requirements").json()
        }
        response = client.post(f"/api/projects/{pid}/clear-preview")
        assert response.status_code == 200, response.text
        preview = response.json()
        response = client.post(
            f"/api/projects/{pid}/clear",
            json={
                "expected_state_hash": preview["expected_state_hash"],
                "confirmation_code": "P01",
                "actor": "测试工程师",
                "role": "演示角色",
            },
        )
        assert response.status_code == 200, response.text
        assert (
            client.get(f"/api/projects/{pid}/overview").json()["coordination"][
                "topic_count"
            ]
            == 0
        )
        assert client.get(f"/api/projects/{pid}/requirements").json() == []
    with TestClient(create_app(report["database"])) as client:
        assert (
            client.get(f"/api/projects/{pid}/requirements").json() == []
        )  # no automatic reseeding
        path = ROOT / "演示导入文件/综合演示/01_综合技术协议_V1.docx"
        raw = path.read_bytes()
        extract = client.post(
            f"/api/projects/{pid}/document-imports/extract",
            params={"filename": path.name},
            content=raw,
        ).json()
        source = client.post(
            f"/api/projects/{pid}/source-documents",
            json={
                "display_code": "DOC-NEW-001",
                "doc_type": "protocol",
                "version": "V1",
                "mode": "manual",
                "content": extract["content"],
                "import_id": extract["import_id"],
                "original_file": {
                    "filename": path.name,
                    "sha256": extract["sha256"],
                    "data_base64": base64.b64encode(raw).decode(),
                },
            },
        ).json()
        response = client.post(f"/api/source-documents/{source['id']}/parse", json={})
        assert response.status_code == 200, response.text
        rows = client.get(f"/api/projects/{pid}/requirements").json()
        assert len(rows) == 19 and all(row["review_status"] == "draft" for row in rows)
        assert original_ids.isdisjoint(row["id"] for row in rows)
        assert (
            client.get(f"/api/projects/{pid}/overview").json()["coordination"][
                "topic_count"
            ]
            == 0
        )


def test_install_keeps_verified_backup_and_refuses_to_replace_other_projects(
    tmp_path, client
):
    built = module().build(tmp_path / "initial")
    snapshot = json.loads(
        (tmp_path / "initial/initial-backup.json").read_text(encoding="utf-8")
    )
    client.post(
        "/api/projects",
        json={
            "display_code": "P01",
            "name": "用户项目",
            "customer": "客户",
            "product": "产品",
        },
    )
    before = client.get("/api/system/backup").json()
    installed = module().activate(client, snapshot, tmp_path / "backups")
    saved = json.loads(Path(installed["backup"]).read_text(encoding="utf-8"))
    assert saved["sha256"] == before["sha256"]
    assert (
        hashlib.sha256(base64.b64decode(saved["database_base64"])).hexdigest()
        == saved["sha256"]
    )
    assert (
        client.get(f"/api/projects/{built['project_id']}/overview").json()[
            "requirements"
        ]["total"]
        == 13
    )
    client.post(
        "/api/projects",
        json={
            "display_code": "P02",
            "name": "保留项目",
            "customer": "客户",
            "product": "产品",
        },
    )
    before_refused = client.get("/api/system/backup").json()["sha256"]
    with pytest.raises(ValueError, match="其他项目"):
        module().activate(client, snapshot, tmp_path / "backups")
    assert client.get("/api/system/backup").json()["sha256"] == before_refused


def test_launcher_prefers_prepared_initial_source_without_changing_workspace(tmp_path):
    from scripts import start_demo as launcher

    fallback = tmp_path / "data/demo.db"
    fallback.parent.mkdir()
    fallback.write_bytes(b"original fixture")
    assert launcher.default_source(tmp_path) == fallback
    prepared = tmp_path / "data/initial-showcase/initial.db"
    prepared.parent.mkdir()
    prepared.write_bytes(b"prepared scene")
    assert (
        launcher.default_source(tmp_path) == fallback
    )  # partial builds are never selected
    (prepared.parent / "manifest.json").write_text("{}", encoding="utf-8")
    assert launcher.default_source(tmp_path) == prepared
    assert fallback.read_bytes() == b"original fixture"


def test_install_rechecks_project_scope_in_the_actual_backup(tmp_path, client):
    module_under_test = module()
    module_under_test.build(tmp_path / "initial")
    snapshot = json.loads(
        (tmp_path / "initial/initial-backup.json").read_text(encoding="utf-8")
    )
    client.post(
        "/api/projects",
        json={
            "display_code": "P01",
            "name": "项目",
            "customer": "客户",
            "product": "产品",
        },
    )

    class ScopeChangesBeforeBackup:
        def request(self, method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if method == "GET" and path == "/api/projects":
                created = client.post(
                    "/api/projects",
                    json={
                        "display_code": "P02",
                        "name": "新建项目",
                        "customer": "客户",
                        "product": "产品",
                    },
                )
                assert created.status_code == 201
            return response

    with pytest.raises(ValueError, match="其他项目"):
        module_under_test.activate(
            ScopeChangesBeforeBackup(), snapshot, tmp_path / "backups"
        )
    assert {row["display_code"] for row in client.get("/api/projects").json()} == {
        "P01",
        "P02",
    }
