from app.domain.testing import (
    CaseSnapshot,
    build_traceability,
    evaluate_static_torsion,
    is_case_complete,
    is_case_covered,
)
from app.domain.testing import VALIDATION_SCOPE, ScopeRequirement

from test_testing_domain import (
    _case,
    _run,
    _scope_requirements,
)

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
    source = client.post(
        f"/api/projects/{project_id}/source-documents",
        json={
            "display_code": "DOC-P01-001",
            "doc_type": "protocol",
            "version": "V1",
            "content": FIXED_PROTOCOL,
            "mode": "manual",
        },
    )
    assert source.status_code == 201, source.text
    parsed = client.post(
        f"/api/source-documents/{source.json()['id']}/parse",
        json={"display_code_map": DISPLAY_CODE_MAP},
    )
    assert parsed.status_code == 200, parsed.text
    return parsed.json()


def _generate_plan(client, project_id):
    response = client.post(f"/api/projects/{project_id}/test-plan")
    assert response.status_code == 200, response.text
    return response.json()


def test_incomplete_case_can_be_rejected_but_not_confirmed(design_client):
    client = design_client
    project = _create_project(client)
    _create_and_parse(client, project["id"])
    plan = _generate_plan(client, project["id"])
    case = next(row for row in plan["cases"] if row["case_key"] == "durability")
    assert case["complete"] is False
    endpoint = f"/api/test-cases/{case['id']}/confirmations"
    payload = {**CONFIRMATION, "expected_revision": case["revision"]}
    assert client.post(endpoint, json=payload).status_code == 422
    rejected = client.post(
        endpoint,
        json={**payload, "decision": "rejected", "comment": "缺少耐久判定标准"},
    )
    assert rejected.status_code == 201, rejected.text
    current = _generate_plan(client, project["id"])
    current_case = next(row for row in current["cases"] if row["id"] == case["id"])
    assert current_case["review_status"] == "rejected"
    assert current_case["coverage_valid"] is False


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
        json={**CONFIRMATION, "expected_revision": plan["revision"]},
    )


def _run_case(client, case, **payload):
    body = {
        "expected_revision": case["revision"],
        "actor": "试验工程师甲",
        "role": "试验工程师（演示角色）",
        "conditions": "合成台架工况",
        "evidence": "合成执行记录：见试验日志",
    }
    body.update(payload)
    return client.post(f"/api/test-cases/{case['id']}/runs", json=body)


def _matrix(client, project_id):
    response = client.get(f"/api/projects/{project_id}/traceability-matrix")
    assert response.status_code == 200, response.text
    return response.json()


def test_case_without_requirement_reference_is_incomplete():
    case = CaseSnapshot(
        id="case-no-ref",
        display_code="TC-010",
        title="缺少需求引用",
        revision=1,
        review_status="confirmed",
        validity="current",
        conditions_text="工况",
        load_conditions_text="加载",
        acceptance_criteria="标准",
        requirement_refs=(),
    )

    assert is_case_complete(case) is False
    assert is_case_covered(case) is False


def test_static_torsion_invalid_inputs_and_missing_expected_basis():
    assert evaluate_static_torsion(-1, 2800, 2.6).result == "invalid"
    assert evaluate_static_torsion(2800, 2800, -0.1).result == "invalid"
    assert evaluate_static_torsion(2800, None, 2.6).result == "invalid"


def test_pending_reason_depends_on_stale_status_and_revision_mismatch():
    stale = _case("TC-001", "gearCount", validity="stale")
    matrix = build_traceability(_scope_requirements(), [stale])
    gear = next(item for item in matrix.items if item.key == "gearCount")
    assert gear.reason == "stale"
    assert matrix.pending_review[0]["reason"] == "stale"

    old_ref = _case("TC-001", "gearCount", ref_revision=0)
    matrix = build_traceability(_scope_requirements(), [old_ref])
    gear = next(item for item in matrix.items if item.key == "gearCount")
    assert gear.reason == "revision_mismatch"


def test_uncovered_scope_without_cases_reports_no_case():
    matrix = build_traceability(_scope_requirements(), [])

    assert matrix.coverage_percentage == 0.0
    assert all(item.reason == "no_case" for item in matrix.items)
    assert matrix.execution_summary["not_run"] == 5


def test_invalid_and_incomplete_runs_are_surfaced():
    invalid = _case(
        "TC-007",
        "gearboxRatedInputTorque",
        latest_run=_run("invalid"),
    )
    incomplete = _case(
        "TC-002",
        "pto",
        latest_run=_run("incomplete"),
    )

    matrix = build_traceability(_scope_requirements(), [invalid, incomplete])

    torque = next(
        item for item in matrix.items if item.key == "gearboxRatedInputTorque"
    )
    pto = next(item for item in matrix.items if item.key == "pto")
    assert torque.execution == "invalid"
    assert pto.execution == "incomplete"
    assert matrix.execution_summary["invalid"] == 1
    assert matrix.execution_summary["incomplete"] == 1


def test_plan_regeneration_and_confirmation_version_conflicts(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    first_plan = body["plan"]
    first_case_ids = [case["id"] for case in body["cases"]]
    confirmed = _confirm_plan(design_client, first_plan)
    assert confirmed.status_code == 201, confirmed.text

    duplicate = _confirm_plan(design_client, first_plan)
    assert duplicate.status_code == 409

    requirements = design_client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    gear = next(
        requirement
        for requirement in requirements
        if requirement["parser_key"] == "gearCount"
    )
    update = design_client.patch(
        f"/api/requirements/{gear['id']}",
        json={
            "expected_revision": gear["current_revision"],
            "value_text": "10",
        },
    )
    assert update.status_code == 200, update.text

    regenerated = _generate_plan(design_client, project["id"])
    assert regenerated["plan"]["id"] == first_plan["id"]
    assert regenerated["plan"]["revision"] == 2
    assert regenerated["plan"]["status"] == "draft"
    assert [case["id"] for case in regenerated["cases"]] == first_case_ids
    assert _cases_by_code(regenerated)["TC-001"]["validity"] == "stale"

    stale_confirmation = _confirm_plan(design_client, {**first_plan, "revision": 1})
    assert stale_confirmation.status_code == 409
    assert stale_confirmation.json()["error"]["code"] == "VERSION_CONFLICT"

    second = _confirm_plan(design_client, {**first_plan, "revision": 2})
    assert second.status_code == 201, second.text
    fetched = design_client.get(f"/api/projects/{project['id']}/test-plan").json()
    assert [
        confirmation["plan_revision"] for confirmation in fetched["confirmations"]
    ] == [1, 2]
    assert fetched["confirmations"][0]["case_snapshot"][0]["revision"] == 1


def test_case_update_noop_rejection_and_version_conflicts(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    cases = _cases_by_code(body)
    gear = cases["TC-001"]

    noop = design_client.patch(
        f"/api/test-cases/{gear['id']}",
        json={
            "expected_revision": gear["revision"],
            "actor": "试验工程师甲",
            "role": "试验工程师（演示角色）",
        },
    )
    assert noop.status_code == 200, noop.text
    assert noop.json()["revision"] == gear["revision"]

    stale = design_client.patch(
        f"/api/test-cases/{gear['id']}",
        json={
            "expected_revision": 99,
            "actor": "试验工程师甲",
            "role": "试验工程师（演示角色）",
            "title": "旧版本修改",
        },
    )
    assert stale.status_code == 409

    confirmed = _confirm_case(design_client, gear)
    assert confirmed.status_code == 201, confirmed.text
    duplicate = _confirm_case(design_client, gear)
    assert duplicate.status_code == 409

    rejected = _confirm_case(design_client, cases["TC-002"], decision="rejected")
    assert rejected.status_code == 201, rejected.text
    assert rejected.json()["case"]["review_status"] == "rejected"

    unknown = design_client.patch(
        "/api/test-cases/unknown-case",
        json={
            "expected_revision": 1,
            "actor": "试验工程师甲",
            "role": "试验工程师（演示角色）",
        },
    )
    assert unknown.status_code == 404


def test_latest_failure_is_not_masked_by_earlier_pass(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    body = _generate_plan(design_client, project["id"])
    gear = _confirm_case(design_client, _cases_by_code(body)["TC-001"]).json()["case"]

    passed = _run_case(design_client, gear, manual_result="pass")
    failed = _run_case(design_client, gear, manual_result="fail")
    assert passed.status_code == 200, passed.text
    assert failed.status_code == 200, failed.text

    matrix = _matrix(design_client, project["id"])
    gear_item = next(item for item in matrix["items"] if item["key"] == "gearCount")
    assert gear_item["execution"] == "fail"
    assert matrix["execution_summary"]["fail"] == 1

    fetched = design_client.get(f"/api/projects/{project['id']}/test-plan").json()
    runs = _cases_by_code(fetched)["TC-001"]["runs"]
    assert [run["result"] for run in runs] == ["pass", "fail"]


def test_matrix_without_plan_still_uses_fixed_denominator(design_client):
    project = _create_project(design_client)

    matrix = _matrix(design_client, project["id"])

    assert matrix["denominator"] == 5
    assert matrix["covered_count"] == 0
    assert matrix["coverage_percentage"] == 0.0
    assert all(item["reason"] == "requirement_missing" for item in matrix["items"])


def test_duplicate_validation_parameter_blocks_plan_generation(
    design_client,
):
    project = _create_project(design_client)
    for display_code, value in [
        ("REQ-P01-C-001", "12"),
        ("REQ-P01-C-001-DUP", "10"),
    ]:
        response = design_client.post(
            f"/api/projects/{project['id']}/requirements",
            json={
                "display_code": display_code,
                "category": "C",
                "parameter_name": "档位数",
                "data_type": "text",
                "operator": "=",
                "value_text": value,
                "unit": "",
            },
        )
        assert response.status_code == 201, response.text

    response = design_client.post(f"/api/projects/{project['id']}/test-plan")

    assert response.status_code == 422
    assert "gearCount" in response.json()["error"]["details"]["duplicate_keys"]
