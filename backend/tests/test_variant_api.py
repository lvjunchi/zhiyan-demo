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


def _create_and_parse_source(client, project_id):
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
    parse_response = client.post(
        f"/api/source-documents/{source['id']}/parse",
        json={"display_code_map": DISPLAY_CODE_MAP},
    )
    assert parse_response.status_code == 200, parse_response.text
    return source, parse_response.json()


def _run_variant(client, project_id, base_display_code="JX-12A"):
    return client.post(
        f"/api/projects/{project_id}/variant-analysis",
        json={"base_display_code": base_display_code},
    )


def _rated_torque(parsed):
    return next(
        requirement
        for requirement in parsed["requirements"]
        if requirement["display_code"] == "REQ-P01-C-002"
    )


def test_variant_analysis_creates_pto_variant_and_part_decisions(
    catalog_client,
):
    project = _create_project(catalog_client)
    _, parsed = _create_and_parse_source(catalog_client, project["id"])

    response = _run_variant(catalog_client, project["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["base"]["display_code"] == "JX-12A"
    assert len(body["variants"]) == 1
    pto = body["variants"][0]
    assert pto["display_code"] == "V-01"
    assert pto["parameter_key"] == "pto"
    assert pto["variant_type"] == "new_function"
    assert pto["affected_parts"] == ["取力器接口", "主箱壳体"]
    pto_requirement = next(
        requirement
        for requirement in parsed["requirements"]
        if requirement["display_code"] == "REQ-P01-C-006"
    )
    assert (
        pto["upstream_requirement_ids"][0]["requirement_id"]
        == pto_requirement["id"]
    )
    assert any("最高档" in item for item in body["pending_items"])
    assert body["stale_variants"] == []

    parts = {
        part["part_display_code"]: part
        for part in body["reusable_parts"]
    }
    assert parts["P-NEW-PTO-01"]["classification"] == "new_design"
    assert parts["P-NEW-PTO-01"]["part_name"] == "取力器接口"
    assert parts["P-03"]["classification"] == "modify"
    assert parts["P-01"]["classification"] == "carryover"
    assert parts["P-02"]["classification"] == "carryover"

    audits = catalog_client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    assert any(event["action"] == "variant.created" for event in audits)
    assert any(
        event["action"] == "variant_analysis.generated" for event in audits
    )


def test_variant_analysis_is_idempotent(catalog_client):
    project = _create_project(catalog_client)
    _create_and_parse_source(catalog_client, project["id"])

    first = _run_variant(catalog_client, project["id"]).json()
    second = _run_variant(catalog_client, project["id"]).json()

    assert [variant["id"] for variant in second["variants"]] == [
        variant["id"] for variant in first["variants"]
    ]
    assert [variant["display_code"] for variant in second["variants"]] == [
        "V-01"
    ]
    audits = catalog_client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    assert (
        len(
            [
                event
                for event in audits
                if event["action"] == "variant.created"
            ]
        )
        == 1
    )


def test_torque_increase_adds_second_variant_and_preserves_pto_identity(
    catalog_client,
):
    project = _create_project(catalog_client)
    _, parsed = _create_and_parse_source(catalog_client, project["id"])
    first = _run_variant(catalog_client, project["id"]).json()
    pto_id = first["variants"][0]["id"]

    rated = _rated_torque(parsed)
    patched = catalog_client.patch(
        f"/api/requirements/{rated['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    assert patched.status_code == 200, patched.text

    second = _run_variant(catalog_client, project["id"]).json()

    assert [variant["display_code"] for variant in second["variants"]] == [
        "V-01",
        "V-02",
    ]
    assert second["variants"][0]["id"] == pto_id
    torque = second["variants"][1]
    assert torque["parameter_key"] == "gearboxRatedInputTorque"
    assert torque["variant_type"] == "parameter_adjustment"
    assert torque["base_value"] == "2600 N·m"
    assert torque["requirement_value"] == ">= 2800 N·m"
    assert torque["affected_parts"] == ["输入轴", "一轴齿轮"]

    parts = {
        part["part_display_code"]: part
        for part in second["reusable_parts"]
    }
    assert parts["P-01"]["classification"] == "modify"
    assert parts["P-02"]["classification"] == "modify"
    assert parts["P-03"]["classification"] == "modify"
    assert parts["P-05"]["classification"] == "carryover"


def test_reverting_torque_marks_variant_stale_and_updates_parts(
    catalog_client,
):
    project = _create_project(catalog_client)
    _, parsed = _create_and_parse_source(catalog_client, project["id"])
    _run_variant(catalog_client, project["id"])
    rated = _rated_torque(parsed)

    catalog_client.patch(
        f"/api/requirements/{rated['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    _run_variant(catalog_client, project["id"])

    catalog_client.patch(
        f"/api/requirements/{rated['id']}",
        json={"expected_revision": 2, "value_text": "2600"},
    )
    third = _run_variant(catalog_client, project["id"])

    assert third.status_code == 200, third.text
    body = third.json()
    assert [variant["display_code"] for variant in body["variants"]] == [
        "V-01"
    ]
    assert len(body["stale_variants"]) == 1
    stale = body["stale_variants"][0]
    assert stale["parameter_key"] == "gearboxRatedInputTorque"
    assert stale["status"] == "stale"

    parts = {
        part["part_display_code"]: part
        for part in body["reusable_parts"]
    }
    assert parts["P-01"]["classification"] == "carryover"
    assert parts["P-02"]["classification"] == "carryover"
    assert parts["P-03"]["classification"] == "modify"
    assert parts["P-NEW-PTO-01"]["classification"] == "new_design"


def test_variant_analysis_unknown_base_returns_404(catalog_client):
    project = _create_project(catalog_client)

    response = _run_variant(
        catalog_client, project["id"], base_display_code="JX-999"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
