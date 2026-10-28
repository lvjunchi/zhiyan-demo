import hashlib
import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import create_app


def _post_project(client: TestClient, **overrides):
    payload = {
        "name": "法士特—陕汽定制项目试点",
        "customer": "陕汽集团",
        "product": "重型商用车变速器",
    }
    payload.update(overrides)
    return client.post("/api/projects", json=payload)


def _create_project(client: TestClient, **overrides):
    response = _post_project(client, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def _post_source(client: TestClient, project_id: str, **overrides):
    payload = {
        "display_code": "DOC-P01-001",
        "doc_type": "protocol",
        "version": "V1",
        "content": "4.2 变速器要求：12 档 AMT；发动机最大扭矩 2600 N·m。",
        "mode": "manual",
    }
    payload.update(overrides)
    return client.post(
        f"/api/projects/{project_id}/source-documents", json=payload
    )


def _create_source(client: TestClient, project_id: str, **overrides):
    response = _post_source(client, project_id, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def _post_requirement(client: TestClient, project_id: str, **overrides):
    payload = {
        "display_code": "REQ-P01-B-003",
        "category": "B",
        "parameter_name": "发动机最大扭矩",
        "data_type": "numeric",
        "operator": "=",
        "value_text": "2600",
        "unit": "N·m",
        "raw_expression": "发动机最大扭矩 2600 N·m",
        "source_location": "§3.1",
        "source_excerpt": "发动机最大扭矩 2600 N·m",
    }
    payload.update(overrides)
    return client.post(
        f"/api/projects/{project_id}/requirements", json=payload
    )


def _create_requirement(client: TestClient, project_id: str, **overrides):
    response = _post_requirement(client, project_id, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


def _seed_project_and_source(client: TestClient):
    project = _create_project(client, display_code="P01")
    source = _create_source(client, project["id"])
    return project, source


def test_project_identity_is_uuid_and_display_code_is_separate(client):
    project = _create_project(client, display_code="P01")

    assert uuid.UUID(project["id"])
    assert project["id"] != project["display_code"]
    assert project["display_code"] == "P01"
    assert project["stage"] == "requirement_parsing"

    second = _create_project(client)
    assert second["display_code"] == "P02"
    assert second["id"] != project["id"]


def test_project_list_and_detail(client):
    project = _create_project(client, display_code="P01")

    listing = client.get("/api/projects")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [project["id"]]

    detail = client.get(f"/api/projects/{project['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == project["id"]


def test_source_document_records_hash_and_mode(client):
    project = _create_project(client, display_code="P01")
    content = "4.2 变速器要求：12 档 AMT。"

    source = _create_source(
        client, project["id"], content=content, mode="manual"
    )

    assert source["content_hash"] == hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()
    assert source["mode"] == "manual"
    assert source["original_text"] == content


def test_requirement_creation_records_revision_one_and_source_evidence(client):
    project, source = _seed_project_and_source(client)

    requirement = _create_requirement(
        client, project["id"], source_document_id=source["id"]
    )

    assert requirement["current_revision"] == 1
    assert requirement["review_status"] == "draft"
    assert requirement["validity"] == "current"
    assert requirement["source_document_id"] == source["id"]
    assert requirement["source_location"] == "§3.1"
    assert requirement["source_excerpt"] == "发动机最大扭矩 2600 N·m"

    revisions = client.get(
        f"/api/requirements/{requirement['id']}/revisions"
    ).json()
    assert len(revisions) == 1
    assert revisions[0]["revision_no"] == 1
    assert revisions[0]["status"] == "current"
    assert revisions[0]["snapshot"]["value_text"] == "2600"

    audits = client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    assert any(
        event["action"] == "requirement.created"
        and event["object_revision"] == 1
        for event in audits
    )


def test_noop_update_does_not_create_revision_or_audit(client):
    project, source = _seed_project_and_source(client)
    requirement = _create_requirement(
        client, project["id"], source_document_id=source["id"]
    )

    response = client.patch(
        f"/api/requirements/{requirement['id']}",
        json={"expected_revision": 1, "value_text": "2600"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["current_revision"] == 1
    assert response.json()["updated_at"] == requirement["updated_at"]
    revisions = client.get(
        f"/api/requirements/{requirement['id']}/revisions"
    ).json()
    assert len(revisions) == 1
    audits = client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    assert not any(
        event["action"] == "requirement.updated" for event in audits
    )


def test_substantive_update_creates_new_revision_and_keeps_old(client):
    project, source = _seed_project_and_source(client)
    requirement = _create_requirement(
        client, project["id"], source_document_id=source["id"]
    )

    response = client.patch(
        f"/api/requirements/{requirement['id']}",
        json={
            "expected_revision": 1,
            "value_text": "2800",
            "raw_expression": "发动机最大扭矩 2800 N·m",
        },
    )

    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["current_revision"] == 2
    assert updated["value_text"] == "2800"
    assert updated["review_status"] == "draft"

    revisions = client.get(
        f"/api/requirements/{requirement['id']}/revisions"
    ).json()
    assert len(revisions) == 2
    first = next(item for item in revisions if item["revision_no"] == 1)
    second = next(item for item in revisions if item["revision_no"] == 2)
    assert first["status"] == "superseded"
    assert first["snapshot"]["value_text"] == "2600"
    assert second["status"] == "current"
    assert second["snapshot"]["value_text"] == "2800"

    audits = client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    updates = [
        event for event in audits if event["action"] == "requirement.updated"
    ]
    assert len(updates) == 1
    assert updates[0]["before"]["value_text"] == "2600"
    assert updates[0]["after"]["value_text"] == "2800"


def test_stale_expected_revision_is_rejected(client):
    project, source = _seed_project_and_source(client)
    requirement = _create_requirement(
        client, project["id"], source_document_id=source["id"]
    )
    first = client.patch(
        f"/api/requirements/{requirement['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    assert first.status_code == 200, first.text

    response = client.patch(
        f"/api/requirements/{requirement['id']}",
        json={"expected_revision": 1, "value_text": "2900"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "VERSION_CONFLICT"
    assert body["error"]["details"]["current_revision"] == 2

    current = client.get(
        f"/api/requirements/{requirement['id']}"
    ).json()
    assert current["value_text"] == "2800"
    assert current["current_revision"] == 2


def test_confirmation_records_identity_and_survives_later_edit(client):
    project, source = _seed_project_and_source(client)
    requirement = _create_requirement(
        client, project["id"], source_document_id=source["id"]
    )

    confirmed = client.post(
        f"/api/requirements/{requirement['id']}/confirmations",
        json={
            "expected_revision": 1,
            "actor": "张工",
            "role": "design_engineer",
            "decision": "confirmed",
            "comment": "已核对来源",
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    assert (
        client.get(f"/api/requirements/{requirement['id']}").json()[
            "review_status"
        ]
        == "confirmed"
    )

    confirmations = client.get(
        f"/api/requirements/{requirement['id']}/confirmations"
    ).json()
    assert len(confirmations) == 1
    record = confirmations[0]
    assert record["actor"] == "张工"
    assert record["role"] == "design_engineer"
    assert record["object_revision"] == 1
    assert record["decision"] == "confirmed"
    assert record["comment"] == "已核对来源"
    assert datetime.fromisoformat(record["created_at"]).tzinfo is not None

    rejected = client.post(
        f"/api/requirements/{requirement['id']}/confirmations",
        json={
            "expected_revision": 1,
            "actor": "李工",
            "role": "reviewer",
            "decision": "rejected",
            "comment": "来源待补",
        },
    )
    assert rejected.status_code == 201, rejected.text
    assert (
        client.get(f"/api/requirements/{requirement['id']}").json()[
            "review_status"
        ]
        == "rejected"
    )
    assert (
        len(
            client.get(
                f"/api/requirements/{requirement['id']}/confirmations"
            ).json()
        )
        == 2
    )

    edited = client.patch(
        f"/api/requirements/{requirement['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    assert edited.status_code == 200, edited.text
    current = edited.json()
    assert current["current_revision"] == 2
    assert current["review_status"] == "draft"

    confirmations_after = client.get(
        f"/api/requirements/{requirement['id']}/confirmations"
    ).json()
    assert len(confirmations_after) == 2
    assert all(item["object_revision"] == 1 for item in confirmations_after)


def test_confirmation_with_stale_revision_is_rejected(client):
    project, source = _seed_project_and_source(client)
    requirement = _create_requirement(
        client, project["id"], source_document_id=source["id"]
    )

    response = client.post(
        f"/api/requirements/{requirement['id']}/confirmations",
        json={
            "expected_revision": 99,
            "actor": "张工",
            "role": "design_engineer",
            "decision": "confirmed",
            "comment": "",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_requirement_cannot_reference_source_from_another_project(client):
    first_project = _create_project(client, display_code="P01")
    second_project = _create_project(client, display_code="P02")
    source = _create_source(client, first_project["id"])

    response = _post_requirement(
        client,
        second_project["id"],
        display_code="REQ-P02-B-001",
        source_document_id=source["id"],
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REFERENCE"
    requirements = client.get(
        f"/api/projects/{second_project['id']}/requirements"
    ).json()
    assert requirements == []


def test_invalid_requirement_input_returns_validation_error(client):
    project, source = _seed_project_and_source(client)

    bad_category = _post_requirement(
        client,
        project["id"],
        category="Z",
        source_document_id=source["id"],
    )
    assert bad_category.status_code == 422
    assert bad_category.json()["error"]["code"] == "VALIDATION_ERROR"

    bad_numeric = _post_requirement(
        client,
        project["id"],
        value_text="abc",
        source_document_id=source["id"],
    )
    assert bad_numeric.status_code == 422
    assert bad_numeric.json()["error"]["code"] == "VALIDATION_ERROR"

    bad_range = _post_requirement(
        client,
        project["id"],
        data_type="range",
        operator="range",
        value_text="50~-40",
        source_document_id=source["id"],
    )
    assert bad_range.status_code == 422
    assert bad_range.json()["error"]["code"] == "VALIDATION_ERROR"


def test_requirement_display_code_auto_generation_avoids_collisions(client):
    project, source = _seed_project_and_source(client)
    explicit = _create_requirement(
        client,
        project["id"],
        display_code="REQ-P01-B-001",
        source_document_id=source["id"],
    )

    generated = _create_requirement(
        client,
        project["id"],
        display_code=None,
        source_document_id=source["id"],
    )

    assert generated["display_code"] == "REQ-P01-B-002"
    assert generated["id"] != explicit["id"]


def test_duplicate_display_code_is_rejected(client):
    project, source = _seed_project_and_source(client)
    _create_requirement(
        client,
        project["id"],
        display_code="REQ-P01-B-003",
        source_document_id=source["id"],
    )

    response = _post_requirement(
        client,
        project["id"],
        display_code="REQ-P01-B-003",
        source_document_id=source["id"],
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_DISPLAY_CODE"


def test_requirements_are_scoped_to_project(client):
    first_project = _create_project(client, display_code="P01")
    second_project = _create_project(client, display_code="P02")
    source = _create_source(client, first_project["id"])
    _create_requirement(
        client, first_project["id"], source_document_id=source["id"]
    )

    first_list = client.get(
        f"/api/projects/{first_project['id']}/requirements"
    ).json()
    second_list = client.get(
        f"/api/projects/{second_project['id']}/requirements"
    ).json()

    assert len(first_list) == 1
    assert second_list == []


def test_health_reports_database_connected(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"


def test_audit_timestamps_include_timezone(client):
    project = _create_project(client, display_code="P01")

    audits = client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()

    assert audits
    assert datetime.fromisoformat(audits[0]["created_at"]).tzinfo is not None


def test_duplicate_source_document_version_is_rejected(client):
    project = _create_project(client, display_code="P01")
    first = _post_source(client, project["id"])
    assert first.status_code == 201, first.text

    duplicate = _post_source(client, project["id"])

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_DISPLAY_CODE"


def test_audit_failure_rolls_back_requirement_creation(app, monkeypatch):
    with TestClient(app) as tolerant_client:
        project = _create_project(tolerant_client, display_code="P01")
        source = _create_source(tolerant_client, project["id"])

        def failing_audit(*args, **kwargs):
            raise RuntimeError("audit failure")

        monkeypatch.setattr("app.services._audit", failing_audit)
        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.post(
                f"/api/projects/{project['id']}/requirements",
                json={
                    "display_code": "REQ-P01-B-003",
                    "category": "B",
                    "parameter_name": "发动机最大扭矩",
                    "data_type": "numeric",
                    "operator": "=",
                    "value_text": "2600",
                    "unit": "N·m",
                    "raw_expression": "发动机最大扭矩 2600 N·m",
                    "source_document_id": source["id"],
                    "source_location": "§3.1",
                    "source_excerpt": "发动机最大扭矩 2600 N·m",
                },
            )

        assert response.status_code == 500
        requirements = tolerant_client.get(
            f"/api/projects/{project['id']}/requirements"
        ).json()
        assert requirements == []
        audits = tolerant_client.get(
            f"/api/projects/{project['id']}/audit-events"
        ).json()
        assert not any(
            event["action"] == "requirement.created" for event in audits
        )


def test_data_survives_app_restart(tmp_path):
    db_path = tmp_path / "persist.db"

    with TestClient(create_app(db_path=str(db_path))) as first_client:
        project = _create_project(first_client, display_code="P01")
        source = _create_source(first_client, project["id"])
        requirement = _create_requirement(
            first_client, project["id"], source_document_id=source["id"]
        )

    with TestClient(create_app(db_path=str(db_path))) as second_client:
        projects = second_client.get("/api/projects").json()
        assert len(projects) == 1
        assert projects[0]["id"] == project["id"]

        fetched = second_client.get(
            f"/api/requirements/{requirement['id']}"
        ).json()
        assert fetched["current_revision"] == 1
        assert fetched["value_text"] == "2600"
