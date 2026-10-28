FIXED_PROTOCOL = """3.1 整车配置：6×4 牵引车，整车总质量 49 t；发动机最大扭矩 2600 N·m，最大功率 397 kW / 1900 r/min。
4.2 变速器要求：12 档 AMT，一档速比不低于 14.5，最高档为直接档或超速档；额定输入扭矩不低于发动机最大扭矩；需配置取力器接口。
4.5 安装：总成重量不超过 300 kg，离合器壳接口按主机厂图纸 SX-DRW-0215 执行。
7.1 耐久：台架耐久按双方商定标准执行。"""

DISPLAY_CODE_MAP = {
    "engineMaxTorque": "REQ-P01-B-003",
    "gearboxRatedInputTorque": "REQ-P01-C-002",
    "gearCount": "REQ-P01-C-001",
    "transmissionType": "REQ-P01-C-001-T",
    "pto": "REQ-P01-C-006",
    "assemblyWeight": "REQ-P01-D-002",
    "durability": "REQ-P01-F-001",
}

CONFIRMATION = {
    "actor": "试验工程师甲",
    "role": "试验工程师（演示角色）",
    "decision": "confirmed",
    "comment": "合成数据确认",
}


def _create_project(client, display_code="P01"):
    response = client.post(
        "/api/projects",
        json={
            "display_code": display_code,
            "name": "法士特—陕汽定制项目试点",
            "customer": "陕汽集团",
            "product": "重型商用车变速器",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_and_parse(client, project_id):
    source_response = client.post(
        f"/api/projects/{project_id}/source-documents",
        json={
            "display_code": "DOC-P01-001",
            "doc_type": "protocol",
            "version": "V1",
            "content": FIXED_PROTOCOL,
            "mode": "manual",
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    response = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={"display_code_map": DISPLAY_CODE_MAP},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _requirements(client, project_id):
    response = client.get(f"/api/projects/{project_id}/requirements")
    assert response.status_code == 200, response.text
    return {
        item["parser_key"]: item for item in response.json()
    }


def _run_check(client, project_id):
    response = client.post(
        f"/api/projects/{project_id}/consistency-checks"
    )
    assert response.status_code == 200, response.text
    return response.json()


def _update_requirement(client, requirement, **fields):
    payload = {
        "expected_revision": requirement["current_revision"],
        **fields,
    }
    response = client.patch(
        f"/api/requirements/{requirement['id']}", json=payload
    )
    assert response.status_code == 200, response.text
    return response.json()


def _confirm_check(client, check, decision="confirmed"):
    return client.post(
        f"/api/consistency-checks/{check['id']}/confirmations",
        json={
            **CONFIRMATION,
            "expected_revision": check["revision"],
            "decision": decision,
        },
    )


def _close(client, conflict, **overrides):
    payload = {
        "expected_revision": conflict["revision"],
        "actor": "质量工程师甲",
        "role": "质量工程师（演示角色）",
        "resolution_type": "fixed",
        "note": "已完成修订并复核",
        "evidence": "复核记录 CR-01",
    }
    payload.update(overrides)
    return client.post(
        f"/api/conflicts/{conflict['id']}/close", json=payload
    )


def _generate_plan(client, project_id):
    response = client.post(
        f"/api/projects/{project_id}/test-plan"
    )
    assert response.status_code == 200, response.text
    return response.json()


def _cases_by_code(body):
    return {case["display_code"]: case for case in body["cases"]}


def _confirm_case(client, case):
    response = client.post(
        f"/api/test-cases/{case['id']}/confirmations",
        json={**CONFIRMATION, "expected_revision": case["revision"]},
    )
    assert response.status_code == 201, response.text
    return response.json()["case"]


def _record_run(client, case, **payload):
    body = {
        "expected_revision": case["revision"],
        "actor": "试验工程师甲",
        "role": "试验工程师（演示角色）",
        "conditions": "合成台架工况",
        "evidence": "合成执行记录 RUN-01",
    }
    body.update(payload)
    response = client.post(
        f"/api/test-cases/{case['id']}/runs", json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_check_finds_parameter_conflict_with_unreviewed_status_visible(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    initial = _run_check(design_client, project["id"])

    assert initial["check"]["display_code"] == "CR-P01-001"
    assert initial["check"]["status"] == "draft"
    assert initial["check"]["validity"] == "current"
    assert initial["check"]["mode"] == "rule"
    assert initial["check"]["source_label"] == "一致性规则 V1（演示规则）"
    assert initial["conflicts"] == []
    assert initial["check"]["summary"]["open"] == 0

    requirements = _requirements(design_client, project["id"])
    _update_requirement(
        design_client,
        requirements["engineMaxTorque"],
        value_text="2800",
    )

    current = _requirements(design_client, project["id"])
    assert current["gearboxRatedInputTorque"]["value_text"] == "2800"
    _update_requirement(design_client, current["gearboxRatedInputTorque"], value_text="2600")

    result = _run_check(design_client, project["id"])
    check = result["check"]
    assert check["display_code"] == "CR-P01-002"
    assert check["check_no"] == 2
    assert check["summary"]["by_type"]["parameter"] == 1
    assert check["summary"]["blocking_open"] == 1
    assert check["summary"]["review_pending"] >= 1

    parameter = next(
        item
        for item in result["conflicts"]
        if item["conflict_type"] == "parameter"
    )
    assert parameter["display_code"] == "CF-P01-001"
    assert parameter["severity"] == "blocking"
    assert parameter["status"] == "open"
    assert parameter["detected"] is True
    assert parameter["object_type"] == "requirement"
    assert parameter["object_id"] == requirements[
        "gearboxRatedInputTorque"
    ]["id"]
    assert parameter["object_review_status"] == "draft"
    assert "待审核" in parameter["detail"]
    assert "2600" in parameter["detail"] and "2800" in parameter["detail"]

    citation = next(
        item
        for item in result["conflicts"]
        if item["conflict_type"] == "reference"
    )
    assert citation["object_id"] == requirements["engineMaxTorque"]["id"]
    assert "2600" in citation["detail"]

    duplicate = _run_check(design_client, project["id"])
    assert duplicate["check"]["id"] == check["id"]
    assert [item["id"] for item in duplicate["conflicts"]] == [
        item["id"] for item in result["conflicts"]
    ]

    confirmed = _confirm_check(design_client, check)
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["check"]["status"] == "confirmed"
    assert (
        confirmed.json()["confirmation"]["check_revision"] == 1
    )
    assert _confirm_check(design_client, check).status_code == 409


def test_conflict_close_recheck_reopen_and_stable_identity(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    requirements = _requirements(design_client, project["id"])
    _update_requirement(
        design_client,
        requirements["engineMaxTorque"],
        value_text="2800",
        source_excerpt="发动机最大扭矩 2800 N·m",
    )
    current = _requirements(design_client, project["id"])
    assert current["gearboxRatedInputTorque"]["value_text"] == "2800"
    _update_requirement(design_client, current["gearboxRatedInputTorque"], value_text="2600")

    first = _run_check(design_client, project["id"])
    conflict = next(
        item
        for item in first["conflicts"]
        if item["conflict_type"] == "parameter"
    )

    wrong_revision = _close(
        design_client, {**conflict, "revision": 99}
    )
    assert wrong_revision.status_code == 409

    still_detected = _close(design_client, conflict)
    assert still_detected.status_code == 422
    assert "仍检出" in still_detected.json()["error"]["message"]

    accepted = _close(
        design_client,
        conflict,
        resolution_type="accepted_risk",
        note="演示负责人接受该风险，后续版本处理",
        evidence="风险接受记录 RA-01",
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "closed"
    assert accepted.json()["accepted_risk"] is True
    assert accepted.json()["revision"] == 2

    after_accept = _run_check(design_client, project["id"])
    accepted_again = next(
        item
        for item in after_accept["conflicts"]
        if item["id"] == conflict["id"]
    )
    assert accepted_again["status"] == "closed"
    assert accepted_again["detected"] is True
    assert (
        accepted_again["recheck_status"] == "accepted_risk_present"
    )

    requirements = _requirements(design_client, project["id"])
    _update_requirement(
        design_client,
        requirements["gearboxRatedInputTorque"],
        value_text="2800",
    )
    cleared = _run_check(design_client, project["id"])
    cleared_conflict = next(
        item
        for item in cleared["conflicts"]
        if item["id"] == conflict["id"]
    )
    assert cleared_conflict["status"] == "closed"
    assert cleared_conflict["detected"] is False
    assert cleared_conflict["recheck_status"] == "accepted_risk_cleared"

    requirements = _requirements(design_client, project["id"])
    _update_requirement(
        design_client,
        requirements["gearboxRatedInputTorque"],
        value_text="2600",
    )
    reopened = _run_check(design_client, project["id"])
    reopened_conflict = next(
        item
        for item in reopened["conflicts"]
        if item["conflict_type"] == "parameter"
    )
    assert reopened_conflict["id"] == conflict["id"]
    assert reopened_conflict["display_code"] == conflict["display_code"]
    assert reopened_conflict["status"] == "open"
    assert reopened_conflict["detected"] is True
    assert reopened_conflict["revision"] == 3

    detail = design_client.get(
        f"/api/conflicts/{conflict['id']}"
    )
    assert detail.status_code == 200
    actions = [event["action"] for event in detail.json()["events"]]
    assert "conflict.closed" in actions
    assert "conflict.reopened" in actions

    old_check = design_client.get(
        f"/api/consistency-checks/{first['check']['id']}"
    )
    assert old_check.status_code == 200
    assert old_check.json()["check"]["validity"] == "stale"
    stale_confirm = _confirm_check(
        design_client, first["check"]
    )
    assert stale_confirm.status_code == 409


def test_stale_case_old_load_basis_and_rule_conflicts(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    cases = _cases_by_code(body)
    torque_case = _confirm_case(design_client, cases["TC-007"])
    _record_run(
        design_client,
        torque_case,
        load_basis_numeric=2600,
        backup_coefficient=2.4,
    )

    before_change = _run_check(design_client, project["id"])
    assert before_change["check"]["summary"]["by_type"]["rule"] == 1
    assert before_change["check"]["summary"]["by_type"]["condition"] == 0
    rule = next(
        item
        for item in before_change["conflicts"]
        if item["conflict_type"] == "rule"
    )
    assert "2.5" in rule["detail"]

    requirements = _requirements(design_client, project["id"])
    _update_requirement(
        design_client,
        requirements["engineMaxTorque"],
        value_text="2800",
        source_excerpt="发动机最大扭矩 2800 N·m",
    )
    current = _requirements(design_client, project["id"])
    assert current["gearboxRatedInputTorque"]["value_text"] == "2800"
    _update_requirement(design_client, current["gearboxRatedInputTorque"], value_text="2600")

    after_change = _run_check(design_client, project["id"])
    types = {
        item["conflict_type"] for item in after_change["conflicts"]
    }
    assert {"parameter", "version", "condition", "rule"} <= types
    version = next(
        item
        for item in after_change["conflicts"]
        if item["conflict_type"] == "version"
    )
    assert version["object_type"] == "test_case"
    assert version["object_id"] == torque_case["id"]
    assert version["object_review_status"] == "confirmed"

    condition = next(
        item
        for item in after_change["conflicts"]
        if item["conflict_type"] == "condition"
    )
    assert condition["object_id"] == torque_case["id"]
    assert "2600" in condition["detail"]
    assert "2800" in condition["detail"]

    rejected = _close(
        design_client,
        condition,
        resolution_type="fixed",
        note="直接按修复关闭",
        evidence="无",
    )
    assert rejected.status_code == 422

    accepted = _close(
        design_client,
        condition,
        resolution_type="accepted_risk",
        note="旧工况仅用于历史对比，当前版本重新执行",
        evidence="复测计划 RUN-02",
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["accepted_risk"] is True

    listed = design_client.get(
        f"/api/projects/{project['id']}/conflicts"
    )
    assert listed.status_code == 200
    listed_body = listed.json()
    assert any(item["id"] == condition["id"] for item in listed_body)
    assert any(
        event["action"] == "conflict.closed"
        for item in listed_body
        if item["id"] == condition["id"]
        for event in item["events"]
    )

    checks = design_client.get(
        f"/api/projects/{project['id']}/consistency-checks"
    )
    assert checks.status_code == 200
    assert len(checks.json()) == 2

    latest = design_client.get(
        f"/api/projects/{project['id']}/consistency-checks/latest"
    )
    assert latest.status_code == 200
    assert (
        latest.json()["check"]["id"]
        == after_change["check"]["id"]
    )


def test_consistency_unknown_resources_and_empty_latest(design_client):
    project = _create_project(design_client)

    latest = design_client.get(
        f"/api/projects/{project['id']}/consistency-checks/latest"
    )
    assert latest.status_code == 404

    unknown_project = design_client.post(
        "/api/projects/unknown-project/consistency-checks"
    )
    assert unknown_project.status_code == 404

    unknown_check = design_client.get(
        "/api/consistency-checks/unknown-check"
    )
    assert unknown_check.status_code == 404

    unknown_conflict = design_client.get(
        "/api/conflicts/unknown-conflict"
    )
    assert unknown_conflict.status_code == 404

    close_unknown = design_client.post(
        "/api/conflicts/unknown-conflict/close",
        json={
            "expected_revision": 1,
            "actor": "质量工程师甲",
            "role": "质量工程师（演示角色）",
            "resolution_type": "fixed",
            "note": "不存在",
            "evidence": "无",
        },
    )
    assert close_unknown.status_code == 404
