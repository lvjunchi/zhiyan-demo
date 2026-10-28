from contextlib import closing

from app.db import connect
from package_scenario import build_ready_project, CONFIRMATION


def edit_linked_item(client, state):
    project_id = state["project"]["id"]
    plan = client.get(f"/api/projects/{project_id}/test-plan").json()
    case = next(case for case in plan["cases"] if case["fmea_refs"])
    reference = case["fmea_refs"][0]
    response = client.patch(
        f"/api/fmea-items/{reference['fmea_item_id']}",
        json={
            "expected_revision": reference["revision"],
            "actor": "回归工程师",
            "role": "演示角色",
            "action_text": "追加接口疲劳复测措施",
        },
    )
    assert response.status_code == 200, response.text
    return case, response.json()


def confirm_fmea(client, project_id, item):
    scores = client.post(
        f"/api/fmea-items/{item['id']}/confirm-scores",
        json={
            "expected_revision": item["revision"],
            "actor": "回归工程师",
            "role": "演示角色",
        },
    )
    assert scores.status_code == 200, scores.text
    fmea = client.get(f"/api/projects/{project_id}/dfmea").json()["fmea"]
    response = client.post(
        f"/api/fmea-documents/{fmea['id']}/confirmations",
        json={
            **CONFIRMATION,
            "expected_revision": fmea["revision"],
        },
    )
    assert response.status_code == 201, response.text
    return scores.json()


def test_fmea_edit_invalidates_only_linked_cases_and_blocks_package(design_client):
    client = design_client
    state = build_ready_project(client)
    project_id = state["project"]["id"]
    case, item = edit_linked_item(client, state)
    plan = client.get(f"/api/projects/{project_id}/test-plan").json()
    changed = next(row for row in plan["cases"] if row["id"] == case["id"])
    assert changed["validity"] == "stale"
    assert changed["review_status"] == "confirmed"  # 旧审核保留
    assert changed["runs"] == case["runs"]
    assert all(
        row["validity"] == "current"
        for row in plan["cases"]
        if not any(ref["fmea_item_id"] == item["id"] for ref in row["fmea_refs"])
    )
    assert (
        client.get(f"/api/projects/{project_id}/consistency-checks/latest").json()[
            "check"
        ]["validity"]
        == "stale"
    )
    confirm_fmea(client, project_id, item)
    matrix = client.get(f"/api/projects/{project_id}/traceability-matrix").json()
    assert matrix["covered_count"] < 5
    package = client.post(f"/api/projects/{project_id}/material-packages", json={})
    assert package.status_code == 201, package.text
    assert package.json()["status"] == "draft"


def test_fmea_rebase_requires_new_case_review_and_new_execution(design_client):
    client = design_client
    state = build_ready_project(client)
    project_id = state["project"]["id"]
    case, item = edit_linked_item(client, state)
    current_item = confirm_fmea(client, project_id, item)
    revised = client.patch(
        f"/api/test-cases/{case['id']}",
        json={
            "expected_revision": case["revision"],
            "actor": "回归工程师",
            "role": "演示角色",
            "rebase_requirements": True,
            "comment": "核对新 FMEA 措施后重新基线",
        },
    )
    assert revised.status_code == 200, revised.text
    updated = revised.json()
    assert updated["revision"] == case["revision"] + 1
    assert updated["fmea_refs"][0]["revision"] == current_item["revision"]
    assert updated["review_status"] == "draft"
    assert updated["runs"] == case["runs"]
    confirmed = client.post(
        f"/api/test-cases/{case['id']}/confirmations",
        json={
            **CONFIRMATION,
            "expected_revision": updated["revision"],
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    matrix = client.get(f"/api/projects/{project_id}/traceability-matrix").json()
    row = next(row for row in matrix["items"] if case["id"] in row["valid_case_ids"])
    assert row["execution"] == "not_run"
    assert row["covered"] is True


def test_existing_fmea_reference_drift_is_detected_without_rewriting_history(
    design_client, db_path
):
    client = design_client
    state = build_ready_project(client)
    project_id = state["project"]["id"]
    case, item = edit_linked_item(client, state)
    confirm_fmea(client, project_id, item)
    # 模拟升级前已存在的漏标记旧数据；读取应核对实际引用，而非只信缓存状态。
    with closing(connect(db_path)) as connection:
        connection.execute(
            "UPDATE test_cases SET validity='current' WHERE id=?", (case["id"],)
        )
        connection.execute(
            "UPDATE test_case_revisions SET validity='current' WHERE case_id=?",
            (case["id"],),
        )
    plan = client.get(f"/api/projects/{project_id}/test-plan").json()
    current = next(row for row in plan["cases"] if row["id"] == case["id"])
    assert current["coverage_valid"] is False
    run = client.post(
        f"/api/test-cases/{case['id']}/runs",
        json={
            "expected_revision": case["revision"],
            "actor": "回归工程师",
            "role": "演示角色",
            "conditions": "合成工况",
            "evidence": "旧用例不能用于新措施",
            "manual_result": "pass",
        },
    )
    assert run.status_code == 422, run.text
