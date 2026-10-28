import base64
import hashlib
import sqlite3
import pytest

from app import services
from app.db import connect
from test_variant_api import _create_project, _create_and_parse_source, _run_variant


def test_manual_requirement_alias_is_retained_as_part_version_dependency(
    catalog_client,
):
    project_id = _create_project(catalog_client)["id"]
    response = catalog_client.post(
        f"/api/projects/{project_id}/requirements",
        json={
            "category": "C",
            "parameter_name": "取力器",
            "data_type": "boolean",
            "operator": "=",
            "value_text": "required",
            "unit": "",
            "raw_expression": "手工录入需取力器接口",
        },
    )
    assert response.status_code == 201, response.text
    requirement = response.json()
    result = _run_variant(catalog_client, project_id).json()
    pto = next(
        part for part in result["reusable_parts"] if part["part_name"] == "取力器接口"
    )
    assert any(
        dep["object_type"] == "requirement"
        and dep["object_id"] == requirement["id"]
        and dep["revision"] == 1
        for dep in pto["dependency_versions"]
    )


def test_restore_rejects_confirmed_engineering_status_without_review_record(
    catalog_client,
):
    _setup_scenario(catalog_client)
    backup = catalog_client.get("/api/system/backup").json()
    connection = sqlite3.connect(":memory:")
    connection.deserialize(base64.b64decode(backup["database_base64"]))
    connection.execute("UPDATE variant_points SET review_status='confirmed'")
    connection.commit()
    data = connection.serialize()
    connection.close()
    damaged = {
        **backup,
        "sha256": hashlib.sha256(data).hexdigest(),
        "database_base64": base64.b64encode(data).decode(),
    }
    response = catalog_client.post(
        "/api/system/restore",
        json={
            "backup": damaged,
            "expected_state_hash": backup["sha256"],
            "actor": "工程师",
            "role": "design_engineer",
        },
    )
    assert response.status_code == 422, response.text
    assert catalog_client.get("/api/system/backup").json()["sha256"] == backup["sha256"]


def _setup_scenario(client):
    project = _create_project(client)
    _, parsed = _create_and_parse_source(client, project["id"])
    for req in parsed["requirements"]:
        response = client.post(
            f"/api/requirements/{req['id']}/confirmations",
            json={
                "expected_revision": 1,
                "actor": "工程师",
                "role": "design_engineer",
                "decision": "confirmed",
            },
        )
        assert response.status_code == 201, response.text
    return project["id"], _run_variant(client, project["id"]).json()


def test_engineering_read_models_identify_bases_without_changing_versions(
    catalog_client,
):
    project_id, first = _setup_scenario(catalog_client)
    second = _run_variant(catalog_client, project_id, "JX-12B")
    assert second.status_code == 200, second.text
    before = catalog_client.get("/api/system/backup").json()["sha256"]
    rows = catalog_client.get(f"/api/projects/{project_id}/engineering-records").json()
    assert {row["base_display_code"] for row in rows} == {"JX-12A", "JX-12B"}
    item = next(row for row in rows if row["id"] == first["variants"][0]["id"])
    detail = catalog_client.get(f"/api/engineering-records/variant/{item['id']}").json()
    assert detail["current"]["base_display_code"] == "JX-12A"
    assert detail["current"]["revision"] == item["revision"]
    assert catalog_client.get("/api/system/backup").json()["sha256"] == before


def detail(client, kind, item):
    response = client.get(f"/api/engineering-records/{kind}/{item['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, kind, item, rev=1):
    return client.post(
        f"/api/engineering-records/{kind}/{item['id']}/confirmations",
        json={
            "expected_revision": rev,
            "actor": "工程师",
            "role": "design_engineer",
            "decision": "confirmed",
            "comment": "已核对版本依据",
        },
    )


def test_immutable_revisions_approvals_and_independent_unaffected_parts(
    catalog_client, db_path
):
    project_id, initial = _setup_scenario(catalog_client)
    variant = initial["variants"][0]
    assert variant["revision"] == 1 and variant["review_status"] == "draft"
    assert confirm(catalog_client, "variant", variant).status_code == 201
    parts = initial["reusable_parts"]
    pto = next(p for p in parts if p["part_name"] == "取力器接口")
    unrelated = next(p for p in parts if p["part_name"] == "输入轴")
    assert confirm(catalog_client, "part", pto).status_code == 201
    frozen = detail(catalog_client, "variant", variant)["versions"][0]
    requirements = catalog_client.get(f"/api/projects/{project_id}/requirements").json()
    req = next(r for r in requirements if r["parser_key"] == "pto")
    changed = catalog_client.patch(
        f"/api/requirements/{req['id']}",
        json={"expected_revision": 1, "value_text": "not_required"},
    )
    assert changed.status_code == 200
    assert detail(catalog_client, "variant", variant)["current"]["status"] == "stale"
    assert confirm(catalog_client, "variant", variant).status_code == 409
    _run_variant(catalog_client, project_id)
    removed = detail(catalog_client, "part", pto)
    assert removed["current"]["status"] == "stale"
    assert removed["versions"][0]["snapshot"]["classification"] == "new_design"
    restored_req = catalog_client.patch(
        f"/api/requirements/{req['id']}",
        json={"expected_revision": 2, "value_text": "required"},
    ).json()
    assert restored_req["current_revision"] == 3
    _run_variant(catalog_client, project_id)
    current = detail(catalog_client, "variant", variant)
    assert (
        current["current"]["revision"] == 2
        and current["current"]["review_status"] == "draft"
    )
    assert current["versions"][0] == frozen
    assert current["confirmations"][0]["object_revision"] == 1
    assert confirm(catalog_client, "variant", variant, 1).status_code == 409
    assert detail(catalog_client, "part", unrelated)["current"]["revision"] == 1
    connection = connect(db_path)
    try:
        with pytest.raises(Exception, match="immutable"):
            connection.execute(
                "UPDATE engineering_record_versions SET snapshot_json='{}'"
            )
    finally:
        connection.close()


def test_idempotent_analysis_and_downstream_revision_references(catalog_client):
    project_id, initial = _setup_scenario(catalog_client)
    rerun = _run_variant(catalog_client, project_id).json()
    assert [(p["id"], p["revision"]) for p in rerun["reusable_parts"]] == [
        (p["id"], p["revision"]) for p in initial["reusable_parts"]
    ]
    assert (
        len(detail(catalog_client, "variant", initial["variants"][0])["versions"]) == 1
    )
    review = catalog_client.post(
        f"/api/projects/{project_id}/design-review",
        json={"base_display_code": "JX-12A"},
    ).json()
    variant_dependencies = [
        d
        for row in review["items"]
        for d in row["dependencies"]
        if d["object_type"] == "variant_point"
    ]
    assert variant_dependencies and all(
        d["revision"] == 1 for d in variant_dependencies
    )


def test_version_write_fault_rolls_back_analysis(catalog_client, monkeypatch):
    project_id, initial = _setup_scenario(catalog_client)
    from app import engineering_versions

    before = catalog_client.get("/api/system/backup").json()["sha256"]
    original = engineering_versions.capture

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected version write failure")

    monkeypatch.setattr(engineering_versions, "capture", fail)
    reqs = catalog_client.get(f"/api/projects/{project_id}/requirements").json()
    req = next(r for r in reqs if r["parser_key"] == "pto")
    # A fresh base creates new records, forcing the version write inside analysis.
    with pytest.raises(RuntimeError, match="version write"):
        _run_variant(catalog_client, project_id, "JX-12B")
    assert catalog_client.get("/api/system/backup").json()["sha256"] == before


def test_restore_rejects_engineering_revision_without_matching_history(catalog_client):
    _setup_scenario(catalog_client)
    backup = catalog_client.get("/api/system/backup").json()
    connection = sqlite3.connect(":memory:")
    connection.deserialize(base64.b64decode(backup["database_base64"]))
    connection.execute("UPDATE variant_points SET revision=99")
    connection.commit()
    data = connection.serialize()
    connection.close()
    damaged = {
        **backup,
        "sha256": hashlib.sha256(data).hexdigest(),
        "database_base64": base64.b64encode(data).decode(),
    }
    response = catalog_client.post(
        "/api/system/restore",
        json={
            "backup": damaged,
            "expected_state_hash": backup["sha256"],
            "actor": "工程师",
            "role": "design_engineer",
        },
    )
    assert response.status_code == 422, response.text
    assert catalog_client.get("/api/system/backup").json()["sha256"] == backup["sha256"]


def test_unreviewed_or_stale_engineering_decision_blocks_ready_package(design_client):
    from package_scenario import build_ready_project

    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]
    records = design_client.get(
        f"/api/projects/{project_id}/engineering-records"
    ).json()
    part = next(row for row in records if row["kind"] == "part")
    rejected = design_client.post(
        f"/api/engineering-records/part/{part['id']}/confirmations",
        json={
            "expected_revision": part["revision"],
            "actor": "工程师",
            "role": "design_engineer",
            "decision": "rejected",
            "comment": "撤回确认：选型接口需重新核对",
        },
    )
    assert rejected.status_code == 201
    package = design_client.post(
        f"/api/projects/{project_id}/material-packages",
        json={"include_originals": False, "actor": "工程师"},
    ).json()
    assert package["status"] == "draft"
    assert any(
        item.get("object_id") == part["id"] for item in package["gate"]["blockers"]
    )


def test_restore_rejects_malformed_engineering_snapshot_without_server_error(
    catalog_client,
):
    _setup_scenario(catalog_client)
    backup = catalog_client.get("/api/system/backup").json()
    connection = sqlite3.connect(":memory:")
    connection.deserialize(base64.b64decode(backup["database_base64"]))
    trigger = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name='engineering_record_versions_immutable_update'"
    ).fetchone()[0]
    connection.execute("DROP TRIGGER engineering_record_versions_immutable_update")
    connection.execute("UPDATE engineering_record_versions SET snapshot_json='[]'")
    connection.execute(trigger)
    connection.commit()
    data = connection.serialize()
    connection.close()
    damaged = {
        **backup,
        "sha256": hashlib.sha256(data).hexdigest(),
        "database_base64": base64.b64encode(data).decode(),
    }
    response = catalog_client.post(
        "/api/system/restore",
        json={
            "backup": damaged,
            "expected_state_hash": backup["sha256"],
            "actor": "工程师",
            "role": "design_engineer",
        },
    )
    assert response.status_code == 422, response.text
    assert catalog_client.get("/api/system/backup").json()["sha256"] == backup["sha256"]
