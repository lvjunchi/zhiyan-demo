"""P0 主线完整验收：导入→确认→设计/试验→冲突→材料包→变更复核。"""

from package_scenario import (
    build_ready_project,
    _build_design_review,
    _build_dfmea,
    _build_engineering,
)

CONFIRMATION = {
    "actor": "演示工程师甲",
    "role": "演示角色",
    "comment": "P0 完整验收确认",
}


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def _requirements(client, project_id):
    return {
        item["display_code"]: item
        for item in _ok(client.get(f"/api/projects/{project_id}/requirements"))
    }


def _matrix(client, project_id):
    return _ok(client.get(f"/api/projects/{project_id}/traceability-matrix"))


def _case(client, project_id, display_code):
    plan = _ok(client.get(f"/api/projects/{project_id}/test-plan"))
    return next(case for case in plan["cases"] if case["display_code"] == display_code)


def _run(client, case, **values):
    payload = {
        "expected_revision": case["revision"],
        "actor": "演示试验工程师",
        "role": "演示角色",
        "conditions": "合成台架工况",
        "evidence": "合成验收执行记录",
        **values,
    }
    if "manual_result" not in payload and "backup_coefficient" not in payload:
        payload["manual_result"] = "pass"
    return client.post(f"/api/test-cases/{case['id']}/runs", json=payload)


def _package(client, project_id):
    return client.post(
        f"/api/projects/{project_id}/material-packages",
        json={"include_originals": False, "actor": "演示负责人"},
    )


def test_p0_journey_reaches_ready_and_recovers_after_engine_torque_change(
    design_client,
):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]

    initial_matrix = _matrix(design_client, project_id)
    assert initial_matrix["denominator"] == 5
    assert initial_matrix["covered_count"] == 5
    assert initial_matrix["coverage_percentage"] == 100.0

    first = _package(design_client, project_id)
    assert first.status_code == 201, first.text
    first_package = first.json()
    assert first_package["status"] == "ready_to_submit"
    assert first_package["gate"]["blockers"] == []

    requirements = _requirements(design_client, project_id)
    engine = requirements["REQ-P01-B-003"]
    gearbox = requirements["REQ-P01-C-002"]
    assert engine["value_text"] == "2600"
    assert (
        gearbox["parameter_name"] == "变速器最低额定输入扭矩"
        and gearbox["id"] != engine["id"]
    )

    updated = design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={
            "expected_revision": engine["current_revision"],
            "value_text": "2800",
            "source_excerpt": "发动机最大扭矩 2800 N·m（合成变更记录 CN-01）",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["current_revision"] == 2
    _ok(
        design_client.post(
            f"/api/requirements/{engine['id']}/confirmations",
            json={
                **CONFIRMATION,
                "expected_revision": updated.json()["current_revision"],
                "decision": "confirmed",
            },
        ),
        201,
    )

    stale_matrix = _matrix(design_client, project_id)
    torque = next(
        item
        for item in stale_matrix["items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert stale_matrix["covered_count"] == 4
    assert stale_matrix["coverage_percentage"] == 80.0
    assert torque["covered"] is False
    stale_case = _case(design_client, project_id, "TC-007")
    assert stale_case["validity"] == "stale"

    blocked_run = _run(
        design_client,
        stale_case,
        load_basis_numeric=2600,
        backup_coefficient=2.6,
    )
    assert blocked_run.status_code == 422, blocked_run.text
    assert "失效" in blocked_run.json()["error"]["message"]

    current_requirements = design_client.get(
        f"/api/projects/{project_id}/requirements"
    ).json()
    derived = next(
        r for r in current_requirements if r["parser_key"] == "gearboxRatedInputTorque"
    )
    assert derived["value_text"] == "2800" and derived["current_revision"] == 2
    # A separate erroneous manual override exercises the conflict/repair branch.
    override = design_client.patch(
        f"/api/requirements/{derived['id']}",
        json={"expected_revision": 2, "value_text": "2600"},
    )
    assert override.status_code == 200, override.text
    gearbox = override.json()

    check = _ok(design_client.post(f"/api/projects/{project_id}/consistency-checks"))
    blocking = [
        item
        for item in check["conflicts"]
        if item["severity"] == "blocking" and item["status"] == "open"
    ]
    assert blocking
    _ok(
        design_client.post(
            f"/api/consistency-checks/{check['check']['id']}/confirmations",
            json={
                **CONFIRMATION,
                "expected_revision": check["check"]["revision"],
                "decision": "confirmed",
            },
        ),
        201,
    )

    draft = _package(design_client, project_id)
    assert draft.status_code == 201, draft.text
    draft_package = draft.json()
    assert draft_package["status"] == "draft"
    codes = {blocker["code"] for blocker in draft_package["gate"]["blockers"]}
    assert "BLOCKING_CONFLICT_OPEN" in codes
    assert "COVERAGE_INCOMPLETE" in codes
    assert "VERIFICATION_NOT_PASSED" in codes

    gearbox_update = design_client.patch(
        f"/api/requirements/{gearbox['id']}",
        json={
            "expected_revision": gearbox["current_revision"],
            "value_text": "2800",
        },
    )
    assert gearbox_update.status_code == 200, gearbox_update.text
    assert gearbox_update.json()["current_revision"] == 4
    _ok(
        design_client.post(
            f"/api/requirements/{gearbox['id']}/confirmations",
            json={
                **CONFIRMATION,
                "expected_revision": gearbox_update.json()["current_revision"],
                "decision": "confirmed",
            },
        ),
        201,
    )
    # 新版用例先核对已修订的工程决策和 FMEA，再重新基线及执行。
    _build_engineering(design_client, project_id)
    _build_design_review(design_client, project_id)
    _build_dfmea(design_client, project_id)
    revised_plan = _ok(design_client.post(f"/api/projects/{project_id}/test-plan"))
    assert revised_plan["plan"]["status"] == "draft"
    _ok(
        design_client.post(
            f"/api/test-plans/{revised_plan['plan']['id']}/confirmations",
            json={
                **CONFIRMATION,
                "expected_revision": revised_plan["plan"]["revision"],
                "decision": "confirmed",
            },
        ),
        201,
    )
    rebased = _ok(
        design_client.patch(
            f"/api/test-cases/{stale_case['id']}",
            json={
                "expected_revision": stale_case["revision"],
                "actor": "演示试验工程师",
                "role": "演示角色",
                "rebase_requirements": True,
                "comment": "按 2800 N·m 新版需求重新基线",
            },
        )
    )
    assert rebased["revision"] == 2
    assert rebased["validity"] == "current"
    confirmed_case = _ok(
        design_client.post(
            f"/api/test-cases/{rebased['id']}/confirmations",
            json={
                **CONFIRMATION,
                "expected_revision": rebased["revision"],
                "decision": "confirmed",
            },
        ),
        201,
    )["case"]
    failed = _run(
        design_client,
        confirmed_case,
        load_basis_numeric=2800,
        backup_coefficient=2.4,
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["run"]["result"] == "fail"
    passed = _run(
        design_client,
        confirmed_case,
        load_basis_numeric=2800,
        backup_coefficient=2.5,
    )
    assert passed.status_code == 200, passed.text
    assert passed.json()["run"]["result"] == "pass"

    recovered_matrix = _matrix(design_client, project_id)
    assert recovered_matrix["covered_count"] == 5
    assert recovered_matrix["coverage_percentage"] == 100.0

    recheck = _ok(design_client.post(f"/api/projects/{project_id}/consistency-checks"))
    cleared_blocking = [
        item
        for item in recheck["conflicts"]
        if item["severity"] == "blocking"
        and item["status"] == "open"
        and item["detected"] is False
    ]
    assert cleared_blocking
    closed = _ok(
        design_client.post(
            f"/api/conflicts/{cleared_blocking[0]['id']}/close",
            json={
                "expected_revision": cleared_blocking[0]["revision"],
                "actor": "演示质量工程师",
                "role": "演示角色",
                "resolution_type": "fixed",
                "note": "派生要求已按 2800 N·m 更新并复核",
                "evidence": "REQ-P01-C-002 V2 确认记录；复检未再检出",
            },
        )
    )
    assert closed["status"] == "closed"
    assert closed["resolution_type"] == "fixed"

    final_check = _ok(
        design_client.post(f"/api/projects/{project_id}/consistency-checks")
    )
    assert [
        item
        for item in final_check["conflicts"]
        if item["severity"] == "blocking" and item["status"] == "open"
    ] == []
    _ok(
        design_client.post(
            f"/api/consistency-checks/{final_check['check']['id']}/confirmations",
            json={
                **CONFIRMATION,
                "expected_revision": final_check["check"]["revision"],
                "decision": "confirmed",
            },
        ),
        201,
    )

    recovered = _package(design_client, project_id)
    assert recovered.status_code == 201, recovered.text
    recovered_package = recovered.json()
    assert recovered_package["status"] == "ready_to_submit"
    assert recovered_package["gate"]["blockers"] == []

    approved = _ok(
        design_client.post(
            f"/api/material-packages/{recovered_package['id']}/approvals",
            json={
                "expected_snapshot_hash": recovered_package["snapshot_hash"],
                "actor": "演示负责人",
                "role": "演示角色",
                "comment": "P0 完整验收：人工核对冻结快照后批准",
            },
        ),
        201,
    )
    assert approved["status"] == "human_approved"
    assert approved["frozen_at"] is not None

    package_dir = design_client.get(
        f"/api/material-packages/{recovered_package['id']}/download"
    )
    assert package_dir.status_code == 200
    assert package_dir.headers["content-type"].startswith("application/zip")
