import base64
import hashlib
import io
import zipfile

import pytest

from app.main import create_app
from fastapi.testclient import TestClient
from package_scenario import build_ready_project
from test_document_text import _pdf


def original(name="protocol.txt", content=None):
    data = content if content is not None else "3.1 发动机最大扭矩 2600 N·m。".encode()
    return {
        "filename": name,
        "data_base64": base64.b64encode(data).decode(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def create(client, project_id, file, version="V1"):
    return client.post(
        f"/api/projects/{project_id}/source-documents",
        json={
            "display_code": "ARCHIVE",
            "doc_type": "protocol",
            "version": version,
            "content": "人工核对正文：发动机最大扭矩 2600 N·m。",
            "mode": "manual",
            "original_file": file,
        },
    )


@pytest.mark.parametrize(
    "name,data",
    [
        ("协议.txt", "发动机最大扭矩 2600 N·m。".encode()),
        ("protocol.pdf", _pdf("engine torque 2600 Nm")),
    ],
    ids=["txt", "pdf"],
)
def test_archived_bytes_download_versions_and_restart(
    design_client, db_path, name, data
):
    project = build_ready_project(design_client)["project"]
    response = create(design_client, project["id"], original(name, data))
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["original_file"]["sha256"] == hashlib.sha256(data).hexdigest()
    assert source["original_file"]["reviewed_text_changed"] is True
    url = f"/api/source-documents/{source['id']}/original"
    assert design_client.get(url).content == data
    assert design_client.get(url).headers["x-content-type-options"] == "nosniff"
    second = create(design_client, project["id"], original(), "V2")
    assert second.status_code == 201
    assert create(design_client, project["id"], original()).status_code == 409
    assert design_client.get(url).content == data
    with TestClient(create_app(db_path)) as restarted:
        sources = restarted.get(
            f"/api/projects/{project['id']}/source-documents"
        ).json()
        assert any(
            item["id"] == source["id"] and item["original_file"]["filename"] == name
            for item in sources
        )
        assert restarted.get(url).content == data


def test_originals_in_frozen_package_and_backup(design_client):
    project = build_ready_project(design_client)["project"]
    data = "发动机最大扭矩 2600 N·m。".encode()
    source = create(design_client, project["id"], original("协议.txt", data)).json()
    result = design_client.post(
        f"/api/projects/{project['id']}/material-packages",
        json={"include_originals": True, "actor": "本地工程师"},
    )
    assert result.status_code == 201, result.text
    download = design_client.get(
        f"/api/material-packages/{result.json()['id']}/download"
    )
    with zipfile.ZipFile(io.BytesIO(download.content)) as zipped:
        assert any(zipped.read(path) == data for path in zipped.namelist())
    assert (
        create(
            design_client, project["id"], original(content=b"revised"), "V2"
        ).status_code
        == 201
    )
    assert (
        design_client.get(
            f"/api/material-packages/{result.json()['id']}/download"
        ).content
        == download.content
    )
    backup = design_client.get("/api/system/backup").json()
    assert backup["counts"]["source_document_files"] == 2
    restored = design_client.post(
        "/api/system/restore",
        json={
            "backup": backup,
            "expected_state_hash": backup["sha256"],
            "actor": "本地工程师",
            "role": "design_engineer",
        },
    )
    assert restored.status_code == 200, restored.text
    assert (
        design_client.get(f"/api/source-documents/{source['id']}/original").content
        == data
    )


@pytest.mark.parametrize(
    "file",
    [
        {**original(), "sha256": "0" * 64},
        {**original(), "data_base64": "invalid!"},
        original("../protocol.txt"),
        original("broken.pdf", b"broken"),
        original("large.txt", b"x" * (8 * 1024 * 1024 + 1)),
    ],
)
def test_invalid_original_rejected_without_source_or_audit(design_client, file):
    project = build_ready_project(design_client)["project"]
    before = design_client.get("/api/system/backup").json()["sha256"]
    response = create(design_client, project["id"], file)
    assert response.status_code == 422, response.text
    assert design_client.get("/api/system/backup").json()["sha256"] == before
