FIXED_PROTOCOL = """3.1 整车配置：6×4 牵引车，整车总质量 49 t；发动机最大扭矩 2600 N·m，最大功率 397 kW / 1900 r/min。
4.2 变速器要求：12 档 AMT，一档速比不低于 14.5，最高档为直接档或超速档；额定输入扭矩不低于发动机最大扭矩；需配置取力器接口。
4.5 安装：总成重量不超过 300 kg，离合器壳接口按主机厂图纸 SX-DRW-0215 执行。
7.1 耐久：台架耐久按双方商定标准执行。"""

FIXED_DISPLAY_CODE_MAP = {
    "engineMaxTorque": "REQ-P01-B-003",
    "gearboxRatedInputTorque": "REQ-P01-C-002",
    "gearCount": "REQ-P01-C-001",
    "pto": "REQ-P01-C-006",
    "assemblyWeight": "REQ-P01-D-002",
    "durability": "REQ-P01-F-001",
}


def _create_project(client):
    response = client.post(
        "/api/projects",
        json={
            "display_code": "P01",
            "name": "法士特—陕汽定制项目试点",
            "customer": "陕汽集团",
            "product": "重型商用车变速器",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_source(client, project_id, **overrides):
    payload = {
        "display_code": "DOC-P01-001",
        "doc_type": "protocol",
        "version": "V1",
        "content": FIXED_PROTOCOL,
        "mode": "manual",
    }
    payload.update(overrides)
    response = client.post(
        f"/api/projects/{project_id}/source-documents", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_parse_fixed_protocol_persists_requirements_evidence_and_issues(client):
    project = _create_project(client)
    source = _create_source(client, project["id"])

    response = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={"display_code_map": FIXED_DISPLAY_CODE_MAP},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "rule"
    assert body["status"] == "parsed"
    assert body["already_parsed"] is False
    assert body["parsed_at"] is not None
    assert body["missing_categories"] == ["E", "G", "H", "I"]

    requirements_by_code = {
        requirement["display_code"]: requirement
        for requirement in body["requirements"]
    }
    assert set(FIXED_DISPLAY_CODE_MAP.values()).issubset(
        requirements_by_code
    )

    engine_torque = requirements_by_code["REQ-P01-B-003"]
    assert engine_torque["parser_key"] == "engineMaxTorque"
    assert engine_torque["value_text"] == "2600"
    assert engine_torque["unit"] == "N·m"
    assert engine_torque["source_location"] == "3.1"
    assert "发动机最大扭矩" in engine_torque["source_excerpt"]

    rated_torque = requirements_by_code["REQ-P01-C-002"]
    assert rated_torque["operator"] == ">="
    assert rated_torque["value_text"] == "2600"
    assert rated_torque["parser_key"] == "gearboxRatedInputTorque"
    assert any(
        reference["requirement_id"] == rated_torque["id"]
        and reference["referenced_requirement_id"] == engine_torque["id"]
        and reference["relation"] == ">="
        for reference in body["references"]
    )

    assert requirements_by_code["REQ-P01-C-001"]["value_text"] == "12"
    assert requirements_by_code["REQ-P01-C-006"]["value_text"] == "required"
    assert requirements_by_code["REQ-P01-D-002"]["operator"] == "<="
    assert requirements_by_code["REQ-P01-F-001"]["data_type"] == "text"

    issue_messages = " ".join(issue["message"] for issue in body["issues"])
    assert "最高档" in issue_messages
    assert "耐久" in issue_messages
    assert any(issue["status"] == "open" for issue in body["issues"])

    detail = client.get(
        f"/api/requirements/{rated_torque['id']}"
    ).json()
    assert len(detail["references"]) == 1
    assert (
        detail["references"][0]["referenced_requirement_id"]
        == engine_torque["id"]
    )
    assert detail["references"][0]["relation"] == ">="

    listing = client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    assert set(FIXED_DISPLAY_CODE_MAP.values()).issubset(
        {requirement["display_code"] for requirement in listing}
    )


def test_reparse_is_idempotent_and_does_not_duplicate(client):
    project = _create_project(client)
    source = _create_source(client, project["id"])
    first = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={"display_code_map": FIXED_DISPLAY_CODE_MAP},
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    first_ids = {
        requirement["id"] for requirement in first_body["requirements"]
    }
    first_issue_count = len(first_body["issues"])

    second = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={"display_code_map": FIXED_DISPLAY_CODE_MAP},
    )

    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["already_parsed"] is True
    assert {
        requirement["id"] for requirement in second_body["requirements"]
    } == first_ids
    assert len(second_body["issues"]) == first_issue_count

    listing = client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    assert len(listing) == len(first_ids)


def test_unrecognized_text_returns_manual_review_issue(client):
    project = _create_project(client)
    source = _create_source(
        client,
        project["id"],
        content="这是一份与变速器无关的会议纪要。",
    )

    response = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={"display_code_map": {}},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "needs_manual_review"
    assert body["requirements"] == []
    assert any(
        issue["issue_type"] == "unparsed" for issue in body["issues"]
    )
    assert body["missing_categories"] == list("ABCDEFGHI")


def test_parse_unknown_source_document_returns_404(client):
    response = client.post(
        "/api/source-documents/does-not-exist/parse",
        json={"display_code_map": {}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_duplicate_display_code_map_values_are_rejected(client):
    project = _create_project(client)
    source = _create_source(client, project["id"])

    response = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={
            "display_code_map": {
                "engineMaxTorque": "REQ-P01-B-003",
                "gearCount": "REQ-P01-B-003",
            }
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_display_code_conflict_rolls_back_entire_parse(client):
    project = _create_project(client)
    first_source = _create_source(client, project["id"])
    first = client.post(
        f"/api/source-documents/{first_source['id']}/parse",
        json={"display_code_map": FIXED_DISPLAY_CODE_MAP},
    )
    assert first.status_code == 200, first.text
    first_count = len(
        client.get(
            f"/api/projects/{project['id']}/requirements"
        ).json()
    )

    second_source = _create_source(
        client,
        project["id"],
        display_code="DOC-P01-002",
        version="V2",
    )
    conflict = client.post(
        f"/api/source-documents/{second_source['id']}/parse",
        json={"display_code_map": FIXED_DISPLAY_CODE_MAP},
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE_DISPLAY_CODE"
    second_count = len(
        client.get(
            f"/api/projects/{project['id']}/requirements"
        ).json()
    )
    assert second_count == first_count
