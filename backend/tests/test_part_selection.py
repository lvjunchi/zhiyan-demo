import pytest
from test_engineering_versions import _setup_scenario
from test_variant_api import _run_variant


def selection(client, part, candidate):
    return client.post(
        f"/api/engineering-records/part/{part['id']}/selection",
        json={
            "candidate_id": candidate["id"],
            "expected_revision": part["revision"],
            "actor": "选型工程师",
            "role": "design_engineer",
            "comment": "核对候选参数与约束",
        },
    )


def test_choice_exposes_upstream_blockers_and_rejection_remains_available(
    catalog_client,
):
    client = catalog_client
    project_id, _ = _setup_scenario(client)
    groups = client.get(f"/api/projects/{project_id}/part-candidates").json()["parts"]
    group = next(item for item in groups if item["record"]["part_name"] == "取力器接口")
    candidate = next(item for item in group["candidates"] if item["fit"] == "pass")
    chosen = selection(client, group["record"], candidate).json()
    group = next(
        item
        for item in client.get(f"/api/projects/{project_id}/part-candidates").json()[
            "parts"
        ]
        if item["record"]["id"] == chosen["id"]
    )
    assert any(
        "取力器" in reason and "未确认" in reason
        for reason in group["confirmation_blockers"]
    )
    payload = {
        "expected_revision": chosen["revision"],
        "actor": "工程师",
        "role": "design_engineer",
        "decision": "confirmed",
        "comment": "",
    }
    endpoint = f"/api/engineering-records/part/{chosen['id']}/confirmations"
    assert client.post(endpoint, json=payload).status_code == 422
    rejected = client.post(
        endpoint, json={**payload, "decision": "rejected", "comment": "接口方案需修改"}
    )
    assert rejected.status_code == 201, rejected.text
    detail = client.get(f"/api/engineering-records/part/{chosen['id']}").json()
    assert detail["current"]["review_status"] == "rejected"
    assert detail["confirmations"][-1]["comment"] == "接口方案需修改"


def test_candidate_selection_is_versioned_and_survives_reanalysis(catalog_client):
    client = catalog_client
    project_id, _ = _setup_scenario(client)
    response = client.get(f"/api/projects/{project_id}/part-candidates")
    assert response.status_code == 200, response.text
    data = response.json()
    group = next(
        row for row in data["parts"] if row["record"]["part_name"] == "主箱壳体"
    )
    candidate = next(row for row in group["candidates"] if row["fit"] == "pass")
    chosen = selection(client, group["record"], candidate)
    assert chosen.status_code == 200, chosen.text
    row = chosen.json()
    assert row["revision"] == group["record"]["revision"] + 1
    assert (
        row["review_status"] == "draft"
        and row["part_number"] == candidate["model_code"]
    )
    detail = client.get(f"/api/engineering-records/part/{row['id']}").json()
    assert detail["versions"][-1]["snapshot"]["part_number"] == candidate["model_code"]
    assert selection(client, group["record"], candidate).status_code == 409
    regenerated = _run_variant(client, project_id).json()
    retained = next(
        item for item in regenerated["reusable_parts"] if item["id"] == row["id"]
    )
    assert (
        retained["part_number"] == candidate["model_code"]
        and retained["revision"] == row["revision"]
    )
    backup = client.get("/api/system/backup").json()
    valid = client.post("/api/system/restore-preview", json={"backup": backup})
    assert valid.status_code == 200, valid.text


def test_candidate_rejects_wrong_part_and_hard_failure_without_writing(catalog_client):
    client = catalog_client
    project_id, _ = _setup_scenario(client)
    response = client.get(f"/api/projects/{project_id}/part-candidates")
    assert response.status_code == 200, response.text
    groups = response.json()["parts"]
    group = next(row for row in groups if row["record"]["part_name"] == "主箱壳体")
    wrong = next(row for row in groups if row["record"]["part_name"] == "齿轮组")[
        "candidates"
    ][0]
    low = next(row for row in group["candidates"] if row["fit"] == "fail")
    before = client.get("/api/system/backup").json()["sha256"]
    assert selection(client, group["record"], wrong).status_code == 422
    assert selection(client, group["record"], low).status_code == 422
    assert client.get("/api/system/backup").json()["sha256"] == before


def test_selected_part_needs_reconfirmation_after_requirement_change(catalog_client):
    client = catalog_client
    project_id, result = _setup_scenario(client)
    response = client.get(f"/api/projects/{project_id}/part-candidates")
    assert response.status_code == 200, response.text
    group = next(
        row
        for row in response.json()["parts"]
        if row["record"]["part_name"] == "输入轴"
    )
    candidate = next(
        row for row in group["candidates"] if row["rated_torque_nm"] == 3000
    )
    row = selection(client, group["record"], candidate).json()
    reviewed = client.post(
        f"/api/engineering-records/part/{row['id']}/confirmations",
        json={
            "expected_revision": row["revision"],
            "actor": "工程师",
            "role": "design_engineer",
            "decision": "confirmed",
            "comment": "核对选型",
        },
    )
    assert reviewed.status_code == 201, reviewed.text
    requirements = client.get(f"/api/projects/{project_id}/requirements").json()
    engine = next(
        item for item in requirements if item["parser_key"] == "engineMaxTorque"
    )
    changed = client.patch(
        f"/api/requirements/{engine['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    assert changed.status_code == 200, changed.text
    current = client.get(f"/api/engineering-records/part/{row['id']}").json()
    assert current["current"]["status"] == "stale"
    assert current["confirmations"][0]["object_revision"] == row["revision"]
    rebuilt = _run_variant(client, project_id).json()
    next_row = next(
        item for item in rebuilt["reusable_parts"] if item["id"] == row["id"]
    )
    assert (
        next_row["part_number"] == candidate["model_code"]
        and next_row["revision"] > row["revision"]
    )
    assert next_row["review_status"] == "draft"


def test_pending_durability_does_not_block_unrelated_torque_candidate(catalog_client):
    from test_variant_api import _create_project, _create_and_parse_source, _run_variant

    client = catalog_client
    project = _create_project(client)
    _, parsed = _create_and_parse_source(client, project["id"])
    for req in parsed["requirements"]:
        if req["parser_key"] == "durability":
            continue
        result = client.post(
            f"/api/requirements/{req['id']}/confirmations",
            json={
                "expected_revision": 1,
                "actor": "工程师",
                "role": "design_engineer",
                "decision": "confirmed",
            },
        )
        assert result.status_code == 201, result.text
    _run_variant(client, project["id"])
    group = next(
        row
        for row in client.get(f"/api/projects/{project['id']}/part-candidates").json()[
            "parts"
        ]
        if row["record"]["part_name"] == "输入轴"
    )
    candidate = next(
        row for row in group["candidates"] if row["rated_torque_nm"] == 3000
    )
    selected = selection(client, group["record"], candidate).json()
    reviewed = client.post(
        f"/api/engineering-records/part/{selected['id']}/confirmations",
        json={
            "expected_revision": selected["revision"],
            "actor": "工程师",
            "role": "design_engineer",
            "decision": "confirmed",
            "comment": "扭矩与档数依据均已确认",
        },
    )
    assert reviewed.status_code == 201, reviewed.text
    durability = next(
        row for row in parsed["requirements"] if row["parser_key"] == "durability"
    )
    assert all(
        dep["object_id"] != durability["id"] for dep in selected["dependency_versions"]
    )
