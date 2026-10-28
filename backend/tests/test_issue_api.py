FIXED_PROTOCOL = """3.1 整车配置：6×4 牵引车，整车总质量 49 t；发动机最大扭矩 2600 N·m，最大功率 397 kW / 1900 r/min。
4.2 变速器要求：12 档 AMT，一档速比不低于 14.5，最高档为直接档或超速档；额定输入扭矩不低于发动机最大扭矩；需配置取力器接口。
4.5 安装：总成重量不超过 300 kg，离合器壳接口按主机厂图纸 SX-DRW-0215 执行。
7.1 耐久：台架耐久按双方商定标准执行。"""

DISPLAY_CODE_MAP = {
    "engineMaxTorque": "REQ-P01-B-003",
    "gearboxRatedInputTorque": "REQ-P01-C-002",
    "gearCount": "REQ-P01-C-001",
    "pto": "REQ-P01-C-006",
    "assemblyWeight": "REQ-P01-D-002",
    "durability": "REQ-P01-F-001",
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


def _create_and_parse(client, project_id, content=FIXED_PROTOCOL):
    source_response = client.post(
        f"/api/projects/{project_id}/source-documents",
        json={
            "display_code": "DOC-P01-001",
            "doc_type": "protocol",
            "version": "V1",
            "content": content,
            "mode": "manual",
        },
    )
    assert source_response.status_code == 201, source_response.text
    source = source_response.json()
    parse_response = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={"display_code_map": DISPLAY_CODE_MAP},
    )
    assert parse_response.status_code == 200, parse_response.text
    return source, parse_response.json()


def _issues(client, project_id):
    response = client.get(f"/api/projects/{project_id}/issues")
    assert response.status_code == 200, response.text
    return response.json()


def _issue_by_key(client, project_id, key):
    return next(
        issue
        for issue in _issues(client, project_id)
        if issue["parser_key"] == key
    )


def test_issue_can_be_closed_with_evidence_and_audited(client):
    project = _create_project(client)
    _create_and_parse(client, project["id"])
    durability = _issue_by_key(client, project["id"], "durability")

    response = client.post(
        f"/api/issues/{durability['id']}/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "manual_supplement",
            "resolution_note": "补充合成耐久标准",
            "evidence": "补充协议 SUP-01：台架耐久按合成标准执行",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "closed"
    assert body["closed_at"] is not None
    assert body["resolution_type"] == "manual_supplement"
    assert body["evidence_text"] == "补充协议 SUP-01：台架耐久按合成标准执行"
    assert body["closed_by"] == "张工"
    assert body["closed_role"] == "design_engineer"
    assert body["close_reason"] == "补充合成耐久标准"

    detail = client.get(f"/api/issues/{durability['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "closed"

    audits = client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    close_events = [
        event
        for event in audits
        if event["action"] == "issue.closed"
        and event["object_id"] == durability["id"]
    ]
    assert len(close_events) == 1
    assert close_events[0]["actor"] == "张工"
    assert close_events[0]["decision"] == "closed"
    assert "SUP-01" in close_events[0]["comment"]


def test_issue_cannot_be_closed_twice_or_without_evidence(client):
    project = _create_project(client)
    _create_and_parse(client, project["id"])
    durability = _issue_by_key(client, project["id"], "durability")

    first = client.post(
        f"/api/issues/{durability['id']}/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "manual_supplement",
            "resolution_note": "补充标准",
            "evidence": "补充协议 SUP-01",
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/issues/{durability['id']}/close",
        json={
            "expected_status": "open",
            "actor": "李工",
            "role": "reviewer",
            "resolution_type": "manual_supplement",
            "resolution_note": "重复关闭",
            "evidence": "重复证据",
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ISSUE_STATE_CONFLICT"

    top_gear = _issue_by_key(client, project["id"], "topGearType")
    no_evidence = client.post(
        f"/api/issues/{top_gear['id']}/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "evidence_added",
            "resolution_note": "补充说明",
            "evidence": "",
        },
    )
    assert no_evidence.status_code == 422
    assert no_evidence.json()["error"]["code"] == "VALIDATION_ERROR"


def test_issue_can_be_reopened_and_reclosed(client):
    project = _create_project(client)
    _create_and_parse(client, project["id"])
    durability = _issue_by_key(client, project["id"], "durability")

    closed = client.post(
        f"/api/issues/{durability['id']}/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "manual_supplement",
            "resolution_note": "补充标准",
            "evidence": "补充协议 SUP-01",
        },
    )
    assert closed.status_code == 200, closed.text

    reopened = client.post(
        f"/api/issues/{durability['id']}/reopen",
        json={
            "expected_status": "closed",
            "actor": "李工",
            "role": "reviewer",
            "reason": "复检发现证据不足",
        },
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"
    assert reopened.json()["closed_at"] is None
    assert reopened.json()["evidence_text"] == ""

    reclosed = client.post(
        f"/api/issues/{durability['id']}/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "manual_supplement",
            "resolution_note": "补充完整证据",
            "evidence": "补充协议 SUP-02",
        },
    )
    assert reclosed.status_code == 200, reclosed.text

    audits = client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    assert (
        len(
            [
                event
                for event in audits
                if event["action"] == "issue.closed"
            ]
        )
        == 2
    )
    assert (
        len(
            [
                event
                for event in audits
                if event["action"] == "issue.reopened"
            ]
        )
        == 1
    )


def test_close_can_link_manual_supplement_requirement(client):
    project = _create_project(client)
    _create_and_parse(client, project["id"])
    durability = _issue_by_key(client, project["id"], "durability")

    requirement = client.post(
        f"/api/projects/{project['id']}/requirements",
        json={
            "display_code": "REQ-P01-F-002",
            "category": "F",
            "parameter_name": "耐久标准",
            "data_type": "text",
            "operator": "text",
            "value_text": "按合成标准 SUP-01 执行",
            "source_location": "人工补录",
            "source_excerpt": "合成补充协议 SUP-01",
        },
    )
    assert requirement.status_code == 201, requirement.text
    requirement_id = requirement.json()["id"]

    response = client.post(
        f"/api/issues/{durability['id']}/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "requirement_clarified",
            "resolution_note": "人工补录耐久标准",
            "evidence": "合成补充协议 SUP-01",
            "linked_requirement_id": requirement_id,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["resolution_requirement_id"] == requirement_id


def test_close_rejects_requirement_from_another_project(client):
    first_project = _create_project(client, display_code="P01")
    second_project = _create_project(client, display_code="P02")
    _create_and_parse(client, first_project["id"])
    durability = _issue_by_key(
        client, first_project["id"], "durability"
    )

    other_requirement = client.post(
        f"/api/projects/{second_project['id']}/requirements",
        json={
            "display_code": "REQ-P02-F-001",
            "category": "F",
            "parameter_name": "耐久标准",
            "data_type": "text",
            "operator": "text",
            "value_text": "另一项目标准",
            "source_location": "人工补录",
            "source_excerpt": "另一项目补充",
        },
    )
    assert other_requirement.status_code == 201, other_requirement.text

    response = client.post(
        f"/api/issues/{durability['id']}/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "requirement_clarified",
            "resolution_note": "跨项目引用",
            "evidence": "另一项目补充",
            "linked_requirement_id": other_requirement.json()["id"],
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REFERENCE"
    still_open = client.get(f"/api/issues/{durability['id']}").json()
    assert still_open["status"] == "open"


def test_unknown_issue_returns_404(client):
    detail = client.get("/api/issues/does-not-exist")
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "NOT_FOUND"

    close = client.post(
        "/api/issues/does-not-exist/close",
        json={
            "expected_status": "open",
            "actor": "张工",
            "role": "design_engineer",
            "resolution_type": "manual_supplement",
            "resolution_note": "补充",
            "evidence": "证据",
        },
    )
    assert close.status_code == 404
