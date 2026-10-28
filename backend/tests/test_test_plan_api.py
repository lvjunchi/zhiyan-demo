from app.db import connect

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


def _generate_plan(client, project_id):
    response = client.post(f"/api/projects/{project_id}/test-plan")
    assert response.status_code == 200, response.text
    return response.json()


def _cases_by_code(body):
    return {case["display_code"]: case for case in body["cases"]}


def _confirm_case(client, case, decision="confirmed"):
    return client.post(
        f"/api/test-cases/{case['id']}/confirmations",
        json={
            **CONFIRMATION,
            "expected_revision": case["revision"],
            "decision": decision,
        },
    )


def _confirm_plan(client, plan):
    return client.post(
        f"/api/test-plans/{plan['id']}/confirmations",
        json={
            **CONFIRMATION,
            "expected_revision": plan["revision"],
        },
    )


def _confirm_main_cases(client, body):
    confirmed = {}
    for display_code in ("TC-001", "TC-002", "TC-003", "TC-007"):
        case = _cases_by_code(body)[display_code]
        response = _confirm_case(client, case)
        assert response.status_code == 201, response.text
        confirmed[display_code] = response.json()["case"]
    return confirmed


def _matrix(client, project_id):
    response = client.get(
        f"/api/projects/{project_id}/traceability-matrix"
    )
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, case, **payload):
    body = {
        "expected_revision": case["revision"],
        "actor": "试验工程师甲",
        "role": "试验工程师（演示角色）",
        "conditions": "合成台架工况",
        "evidence": "合成执行记录：见试验日志",
    }
    body.update(payload)
    return client.post(f"/api/test-cases/{case['id']}/runs", json=body)


def test_generate_test_plan_and_cover_four_of_five(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])

    body = _generate_plan(design_client, project["id"])

    assert body["mode"] == "rule"
    assert body["source_label"] == "固定验收集合 V1（演示规则）"
    assert body["plan"]["display_code"] == "TP-P01"
    assert body["plan"]["revision"] == 1
    assert body["plan"]["status"] == "draft"
    cases = _cases_by_code(body)
    assert set(cases) == {"TC-001", "TC-002", "TC-003", "TC-004", "TC-007"}
    assert all(
        len({case["id"] for case in body["cases"]}) == len(body["cases"])
        for _ in [0]
    )
    assert cases["TC-007"]["case_kind"] == "static_torsion"
    assert cases["TC-004"]["acceptance_criteria"] == ""
    assert cases["TC-004"]["complete"] is False
    assert all(
        case["coverage_valid"] is False for case in body["cases"]
    )

    duplicate = _generate_plan(design_client, project["id"])
    assert duplicate["plan"]["id"] == body["plan"]["id"]
    assert duplicate["plan"]["revision"] == 1
    assert [case["id"] for case in duplicate["cases"]] == [
        case["id"] for case in body["cases"]
    ]

    plan_confirmation = _confirm_plan(design_client, body["plan"])
    assert plan_confirmation.status_code == 201, plan_confirmation.text
    assert plan_confirmation.json()["plan"]["status"] == "confirmed"

    rejected = _confirm_case(design_client, cases["TC-004"])
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"

    _confirm_main_cases(design_client, body)

    matrix = _matrix(design_client, project["id"])
    assert matrix["denominator"] == 5
    assert matrix["covered_count"] == 4
    assert matrix["coverage_percentage"] == 80.0
    assert matrix["uncovered"][0]["key"] == "durability"
    assert matrix["execution_summary"]["not_run"] == 5
    torque = next(
        item
        for item in matrix["items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert torque["covered"] is True
    assert torque["execution"] == "not_run"


def test_durability_case_reaches_full_coverage_after_clarification(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    _confirm_main_cases(design_client, body)
    durability = _cases_by_code(body)["TC-004"]

    response = design_client.patch(
        f"/api/test-cases/{durability['id']}",
        json={
            "expected_revision": durability["revision"],
            "actor": "试验工程师甲",
            "role": "试验工程师（演示角色）",
            "acceptance_criteria": (
                "按补充协议 V1：等效台架循环 1000 h 无失效"
            ),
            "comment": "补充耐久判定依据",
        },
    )
    assert response.status_code == 200, response.text
    revised = response.json()
    assert revised["revision"] == 2
    assert revised["review_status"] == "draft"
    assert revised["complete"] is True

    confirmed = _confirm_case(design_client, revised)
    assert confirmed.status_code == 201, confirmed.text
    matrix = _matrix(design_client, project["id"])
    assert matrix["covered_count"] == 5
    assert matrix["coverage_percentage"] == 100.0
    assert matrix["uncovered"] == []


def test_requirement_change_marks_only_referenced_cases_stale(
    design_client, db_path
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    _confirm_main_cases(design_client, body)
    requirements = design_client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    engine = next(
        requirement
        for requirement in requirements
        if requirement["parser_key"] == "engineMaxTorque"
    )

    update = design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={
            "expected_revision": engine["current_revision"],
            "value_text": "2800",
        },
    )
    assert update.status_code == 200, update.text

    refreshed = design_client.get(
        f"/api/projects/{project['id']}/test-plan"
    ).json()
    cases = _cases_by_code(refreshed)
    assert cases["TC-007"]["validity"] == "stale"
    assert cases["TC-001"]["validity"] == "current"
    assert cases["TC-002"]["validity"] == "current"
    assert cases["TC-003"]["validity"] == "current"
    assert cases["TC-004"]["validity"] == "current"

    matrix = _matrix(design_client, project["id"])
    assert matrix["covered_count"] == 3
    assert matrix["coverage_percentage"] == 60.0
    torque = next(
        item
        for item in matrix["items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert torque["covered"] is False
    assert torque["pending_case_ids"] == [cases["TC-007"]["id"]]

    audits = design_client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    stale_events = [
        event for event in audits if event["action"] == "test_case.stale"
    ]
    assert len(stale_events) == 1
    assert stale_events[0]["object_id"] == cases["TC-007"]["id"]

    connection = connect(db_path)
    try:
        row = connection.execute(
            "SELECT validity FROM test_cases WHERE id = ?",
            (cases["TC-007"]["id"],),
        ).fetchone()
    finally:
        connection.close()
    assert row["validity"] == "stale"


def test_tc007_rejects_old_basis_and_computes_pass_fail_from_coefficient(
    design_client, db_path
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    confirmed = _confirm_main_cases(design_client, body)
    torque_case = confirmed["TC-007"]

    initial_pass = _run(
        design_client,
        torque_case,
        load_basis_numeric=2600,
        backup_coefficient=2.6,
    )
    assert initial_pass.status_code == 200, initial_pass.text
    assert initial_pass.json()["run"]["result"] == "pass"
    assert initial_pass.json()["run"]["mode"] == "rule"

    requirements = design_client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    engine = next(
        requirement
        for requirement in requirements
        if requirement["parser_key"] == "engineMaxTorque"
    )
    design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={
            "expected_revision": engine["current_revision"],
            "value_text": "2800",
        },
    )

    stale_run = _run(
        design_client,
        torque_case,
        load_basis_numeric=2600,
        backup_coefficient=2.6,
    )
    assert stale_run.status_code == 422
    assert stale_run.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "失效" in stale_run.json()["error"]["message"]

    rebased = design_client.patch(
        f"/api/test-cases/{torque_case['id']}",
        json={
            "expected_revision": torque_case["revision"],
            "actor": "试验工程师甲",
            "role": "试验工程师（演示角色）",
            "rebase_requirements": True,
            "comment": "按新版需求重新基线",
        },
    )
    assert rebased.status_code == 200, rebased.text
    rebased_case = rebased.json()
    assert rebased_case["revision"] == 2
    assert rebased_case["validity"] == "current"
    assert rebased_case["review_status"] == "draft"
    assert any(
        ref["requirement_id"] == engine["id"] and ref["revision"] == 2
        for ref in rebased_case["requirement_refs"]
    )
    confirmed_case = _confirm_case(design_client, rebased_case).json()["case"]

    matrix = _matrix(design_client, project["id"])
    torque = next(
        item
        for item in matrix["items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert torque["execution"] == "not_run"
    assert matrix["coverage_percentage"] == 80.0

    old_basis = _run(
        design_client,
        confirmed_case,
        load_basis_numeric=2600,
        backup_coefficient=2.6,
    )
    assert old_basis.status_code == 200, old_basis.text
    assert old_basis.json()["run"]["result"] == "invalid"
    assert "加载基准" in old_basis.json()["run"]["reason"]

    failed = _run(
        design_client,
        confirmed_case,
        load_basis_numeric=2800,
        backup_coefficient=2.4,
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["run"]["result"] == "fail"

    matrix = _matrix(design_client, project["id"])
    torque = next(
        item
        for item in matrix["items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert torque["coverage_valid"] is True
    assert torque["execution"] == "fail"
    assert matrix["coverage_percentage"] == 80.0

    passed = _run(
        design_client,
        confirmed_case,
        load_basis_numeric=2800,
        backup_coefficient=2.6,
    )
    assert passed.status_code == 200, passed.text
    assert passed.json()["run"]["result"] == "pass"

    matrix = _matrix(design_client, project["id"])
    torque = next(
        item
        for item in matrix["items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert torque["execution"] == "pass"
    assert matrix["coverage_percentage"] == 80.0

    connection = connect(db_path)
    try:
        runs = connection.execute(
            """
            SELECT case_revision, result FROM test_runs
            WHERE case_id = ? ORDER BY run_no ASC
            """,
            (torque_case["id"],),
        ).fetchall()
    finally:
        connection.close()
    assert [row["case_revision"] for row in runs] == [1, 2, 2, 2]
    assert [row["result"] for row in runs] == [
        "pass",
        "invalid",
        "fail",
        "pass",
    ]


def test_runs_require_complete_input_and_confirmed_current_case(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    cases = _cases_by_code(body)
    torque = cases["TC-007"]

    unconfirmed = _run(
        design_client,
        torque,
        load_basis_numeric=2600,
        backup_coefficient=2.6,
    )
    assert unconfirmed.status_code == 422
    assert "确认" in unconfirmed.json()["error"]["message"]

    confirmed = _confirm_case(design_client, torque).json()["case"]
    incomplete = _run(
        design_client,
        confirmed,
        load_basis_numeric=2600,
    )
    assert incomplete.status_code == 200, incomplete.text
    assert incomplete.json()["run"]["result"] == "incomplete"
    assert incomplete.json()["run"]["reasons"]

    gear = _confirm_case(design_client, cases["TC-001"]).json()["case"]
    manual_missing = _run(design_client, gear)
    assert manual_missing.status_code == 422

    manual = _run(design_client, gear, manual_result="pass")
    assert manual.status_code == 200, manual.text
    assert manual.json()["run"]["result"] == "pass"
    assert manual.json()["run"]["mode"] == "manual"

    stale = _run(
        design_client,
        {**confirmed, "revision": confirmed["revision"] + 1},
        load_basis_numeric=2600,
        backup_coefficient=2.6,
    )
    assert stale.status_code == 409


def test_get_missing_test_plan_returns_404(design_client):
    project = _create_project(design_client)

    plan = design_client.get(f"/api/projects/{project['id']}/test-plan")
    matrix = design_client.get(
        f"/api/projects/{project['id']}/traceability-matrix"
    )

    assert plan.status_code == 404
    assert plan.json()["error"]["code"] == "NOT_FOUND"
    assert matrix.status_code == 200
    assert matrix.json()["covered_count"] == 0
    assert matrix.json()["coverage_percentage"] == 0.0
    assert matrix.json()["denominator"] == 5
