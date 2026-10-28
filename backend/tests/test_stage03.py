import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import backup_services
from app.main import create_app
from package_scenario import build_ready_project
from test_parse_api import _create_project, _create_source


def preview(client, project_id):
    response = client.post(f"/api/projects/{project_id}/clear-preview")
    assert response.status_code == 200, response.text
    return response.json()


def clear(client, project, checked):
    return client.post(
        f"/api/projects/{project['id']}/clear",
        json={
            "expected_state_hash": checked["expected_state_hash"],
            "confirmation_code": project["display_code"],
            "actor": "本地工程师",
            "role": "design_engineer",
        },
    )


def test_clear_retains_other_project_catalog_sequences_and_verified_backup(
    design_client, db_path
):
    client = design_client
    project = build_ready_project(client)["project"]
    old_project_ids = {
        row["id"]
        for row in client.get(f"/api/projects/{project['id']}/requirements").json()
    }
    other = client.post(
        "/api/projects",
        json={
            "display_code": "OTHER",
            "name": "另一个项目",
            "customer": "客户",
            "product": "设备",
        },
    ).json()
    other_source = _create_source(client, other["id"])
    client.post(f"/api/source-documents/{other_source['id']}/parse", json={})
    other_rows = client.get(f"/api/projects/{other['id']}/requirements").json()
    before = client.get("/api/system/backup").json()
    checked = preview(client, project["id"])
    assert checked["affected_counts"]["requirements"] > 0
    assert client.get("/api/system/backup").json()["sha256"] == before["sha256"]
    response = clear(client, project, checked)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "cleared" and result["original_retained"] is True
    archived = client.get(result["backup_url"])
    assert archived.status_code == 200
    snapshot = archived.json()
    backup_services.validate_snapshot(backup_services.Snapshot.model_validate(snapshot))
    assert snapshot["sha256"] == before["sha256"]
    after = client.get("/api/system/backup").json()
    for table in [
        "product_bases",
        "base_parts",
        "part_candidates",
        "history_projects",
        "sequences",
    ]:
        assert after["counts"][table] == before["counts"][table]
    assert client.get(f"/api/projects/{project['id']}/requirements").json() == []
    assert client.get(f"/api/projects/{project['id']}/source-documents").json() == []
    assert client.get(f"/api/projects/{other['id']}/requirements").json() == other_rows
    assert (
        client.get(f"/api/projects/{project['id']}").json()["stage"]
        == "requirement_parsing"
    )
    assert Path(db_path).exists()
    with TestClient(create_app(db_path)) as restarted:
        assert restarted.get(f"/api/projects/{project['id']}/requirements").json() == []
        source = _create_source(restarted, project["id"])
        parsed = restarted.post(
            f"/api/source-documents/{source['id']}/parse", json={}
        ).json()
        assert not old_project_ids.intersection(r["id"] for r in parsed["requirements"])
        assert all(r["review_status"] == "draft" for r in parsed["requirements"])
        assert parsed["requirements"]


def test_clear_rejects_wrong_confirmation_and_intervening_changes(client):
    project = _create_project(client)
    checked = preview(client, project["id"])
    wrong = client.post(
        f"/api/projects/{project['id']}/clear",
        json={
            "expected_state_hash": checked["expected_state_hash"],
            "confirmation_code": "WRONG",
            "actor": "工程师",
            "role": "design_engineer",
        },
    )
    assert wrong.status_code == 422
    _create_source(client, project["id"])
    assert clear(client, project, checked).status_code == 409
    assert (
        len(client.get(f"/api/projects/{project['id']}/source-documents").json()) == 1
    )


@pytest.mark.parametrize("target", ["backup", "activate"])
def test_clear_persistence_failure_never_switches_or_mutates(
    client, monkeypatch, target
):
    project = _create_project(client)
    _create_source(client, project["id"])
    checked = preview(client, project["id"])
    original_path = client.app.state.db_path

    def fail(*args, **kwargs):
        raise OSError("injected write failure")

    if target == "activate":
        monkeypatch.setattr(backup_services, "_activate_database", fail)
    else:
        from app import project_clear

        monkeypatch.setattr(project_clear, "_persist_backup", fail)
    response = clear(client, project, checked)
    assert response.status_code == 503, response.text
    assert client.app.state.db_path == original_path
    assert (
        client.get("/api/system/backup").json()["sha256"]
        == checked["expected_state_hash"]
    )


def test_import_attempts_and_source_status_survive_restart_and_preserve_drafts(
    client, db_path
):
    project = _create_project(client)
    endpoint = f"/api/projects/{project['id']}/document-imports"
    failed = client.post(endpoint + "/extract?filename=broken.pdf", content=b"broken")
    assert failed.status_code == 422
    data = "3.1 发动机最大扭矩 2600 N·m。".encode()
    extracted = client.post(endpoint + "/extract?filename=protocol.txt", content=data)
    assert extracted.status_code == 200, extracted.text
    attempt_id = extracted.json()["import_id"]
    attempts = client.get(endpoint).json()
    assert {r["status"] for r in attempts} == {"failed", "awaiting_review"}
    assert next(r for r in attempts if r["status"] == "failed")["error_message"]
    source = _create_source(
        client,
        project["id"],
        content=extracted.json()["content"],
        import_id=attempt_id,
        original_file={
            "filename": "protocol.txt",
            "data_base64": base64.b64encode(data).decode(),
            "sha256": extracted.json()["sha256"],
        },
    )
    assert (
        next(r for r in client.get(endpoint).json() if r["id"] == attempt_id)["status"]
        == "archived"
    )
    parsed = client.post(f"/api/source-documents/{source['id']}/parse", json={}).json()
    listed = client.get(f"/api/projects/{project['id']}/source-documents").json()[0]
    assert listed["parse_summary"]["requirement_count"] == len(parsed["requirements"])
    assert listed["parse_summary"]["pending_requirement_count"] == len(
        parsed["requirements"]
    )
    assert listed["parse_summary"]["open_issue_count"] == len(parsed["issues"])
    assert all(r["review_status"] == "draft" for r in parsed["requirements"])
    with TestClient(create_app(db_path)) as restarted:
        attempts = restarted.get(endpoint).json()
        assert (
            next(r for r in attempts if r["id"] == attempt_id)["status"] == "completed"
        )
        assert len(attempts) == 2
        assert restarted.post(
            f"/api/source-documents/{source['id']}/parse", json={}
        ).json()["already_parsed"]


def test_import_link_rejects_wrong_project_or_mismatched_original(client):
    first = _create_project(client)
    second = client.post(
        "/api/projects",
        json={
            "display_code": "P02",
            "name": "另一项目",
            "customer": "客户",
            "product": "设备",
        },
    ).json()
    data = b"engine torque 2600 Nm"
    extraction = client.post(
        f"/api/projects/{first['id']}/document-imports/extract?filename=protocol.txt",
        content=data,
    )
    assert extraction.status_code == 200, extraction.text
    extracted = extraction.json()
    payload = {
        "display_code": "DOC-X",
        "doc_type": "protocol",
        "version": "V1",
        "content": extracted["content"],
        "import_id": extracted["import_id"],
    }
    for project in [second, first]:
        response = client.post(
            f"/api/projects/{project['id']}/source-documents", json=payload
        )
        assert response.status_code == 422, response.text
        assert (
            client.get(f"/api/projects/{project['id']}/source-documents").json() == []
        )


def test_unarchived_preview_can_be_cancelled_without_removing_history_or_leaking_projects(
    client,
):
    project = _create_project(client)
    endpoint = f"/api/projects/{project['id']}/document-imports"
    result = client.post(
        endpoint + "/extract?filename=protocol.txt",
        content="发动机最大扭矩2600N·m".encode(),
    )
    assert result.status_code == 200
    attempt = result.json()["import_id"]
    wrong = client.post(
        f"/api/projects/unknown/document-imports/{attempt}/discard",
        json={"expected_status": "awaiting_review"},
    )
    assert wrong.status_code == 404
    cancelled = client.post(
        endpoint + f"/{attempt}/discard", json={"expected_status": "awaiting_review"}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert len(client.get(endpoint).json()) == 1
    assert client.get(endpoint).json()[0]["status"] == "cancelled"
    assert (
        client.post(
            endpoint + f"/{attempt}/discard",
            json={"expected_status": "awaiting_review"},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "filename,data,stage",
    [
        ("legacy.doc", b"old Word", "file_check"),
        ("oversize.txt", b"x" * (8 * 1024 * 1024 + 1), "file_check"),
        ("broken.pdf", b"broken", "text_extraction"),
    ],
    ids=["legacy-doc", "oversize", "damaged-pdf"],
)
def test_import_errors_identify_failed_stage_and_are_countable(
    client, filename, data, stage
):
    project = _create_project(client)
    endpoint = f"/api/projects/{project['id']}/document-imports"
    result = client.post(
        endpoint + "/extract", params={"filename": filename}, content=data
    )
    assert result.status_code == 422, result.text
    assert result.json()["error"]["details"]["stage"] == stage
    rows = client.get(endpoint).json()
    assert len(rows) == 1 and rows[0]["status"] == "failed"
    assert rows[0]["stage"] == stage
