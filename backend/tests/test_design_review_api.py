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


def _generate(client, project_id, base="JX-12A"):
    return client.post(
        f"/api/projects/{project_id}/design-review",
        json={"base_display_code": base},
    )


def _requirements(client, project_id):
    response = client.get(f"/api/projects/{project_id}/requirements")
    assert response.status_code == 200, response.text
    return response.json()


def _update_requirement(client, requirement, **changes):
    payload = {"expected_revision": requirement["current_revision"]}
    payload.update(changes)
    response = client.patch(
        f"/api/requirements/{requirement['id']}", json=payload
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_generate_design_review_returns_draft_with_dependencies(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])

    response = _generate(design_client, project["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "rule"
    assert body["review"]["display_code"] == "DR-P01"
    assert body["review"]["revision"] == 1
    assert body["review"]["status"] == "draft"
    assert body["review"]["base_display_code"] == "JX-12A"
    assert len({item["id"] for item in body["items"]}) == len(
        body["items"]
    )
    torque_item = body["items"][0]
    assert torque_item["display_code"] == "DR-01"
    assert torque_item["revision"] == 1
    dependency_codes = {
        dependency["display_code"]
        for dependency in torque_item["dependencies"]
    }
    assert "REQ-P01-C-002" in dependency_codes
    assert "REQ-P01-B-003" in dependency_codes

    fetched = design_client.get(
        f"/api/projects/{project['id']}/design-review"
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["review"]["id"] == body["review"]["id"]
    assert fetched.json()["items"] == body["items"]


def test_design_review_regeneration_is_idempotent(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])

    first = _generate(design_client, project["id"]).json()
    second = _generate(design_client, project["id"]).json()

    assert second["review"]["id"] == first["review"]["id"]
    assert second["review"]["revision"] == 1
    assert [item["id"] for item in second["items"]] == [
        item["id"] for item in first["items"]
    ]
    assert [item["revision"] for item in second["items"]] == [
        item["revision"] for item in first["items"]
    ]


def test_requirement_change_creates_new_review_revision_and_keeps_history(
    design_client, db_path
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    first = _generate(design_client, project["id"]).json()
    gear = next(
        requirement
        for requirement in _requirements(design_client, project["id"])
        if requirement["display_code"] == "REQ-P01-C-001"
    )

    _update_requirement(design_client, gear, value_text="10")
    second = _generate(design_client, project["id"]).json()

    assert second["review"]["id"] == first["review"]["id"]
    assert second["review"]["revision"] == 2
    assert second["review"]["status"] == "draft"
    gear_item = next(
        item for item in second["items"] if item["display_code"] == "DR-02"
    )
    assert gear_item["revision"] == 2

    connection = connect(db_path)
    try:
        history = connection.execute(
            """
            SELECT revision, check_point FROM design_review_item_revisions
            WHERE item_id = ? ORDER BY revision ASC
            """,
            (gear_item["id"],),
        ).fetchall()
    finally:
        connection.close()
    assert [row["revision"] for row in history] == [1, 2]


def test_review_confirmation_is_immutable_and_version_checked(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    generated = _generate(design_client, project["id"]).json()
    review_id = generated["review"]["id"]

    response = design_client.post(
        f"/api/design-reviews/{review_id}/confirmations",
        json={
            "expected_revision": 1,
            "actor": "评审员甲",
            "role": "评审员（演示角色）",
            "decision": "confirmed",
            "comment": "设计评审清单通过",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["review"]["status"] == "confirmed"
    assert body["confirmation"]["review_revision"] == 1
    assert body["confirmation"]["decision"] == "confirmed"
    assert len(body["confirmation"]["item_snapshot"]) == len(
        generated["items"]
    )

    duplicate = design_client.post(
        f"/api/design-reviews/{review_id}/confirmations",
        json={
            "expected_revision": 1,
            "actor": "评审员乙",
            "role": "评审员（演示角色）",
            "decision": "confirmed",
            "comment": "重复确认",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "VERSION_CONFLICT"

    stale = design_client.post(
        f"/api/design-reviews/{review_id}/confirmations",
        json={
            "expected_revision": 99,
            "actor": "评审员乙",
            "role": "评审员（演示角色）",
            "decision": "confirmed",
            "comment": "旧版本",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    fetched = design_client.get(
        f"/api/projects/{project['id']}/design-review"
    ).json()
    assert len(fetched["confirmations"]) == 1
    assert fetched["confirmations"][0]["actor"] == "评审员甲"


def test_review_rejection_sets_status_and_keeps_record(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    review = _generate(design_client, project["id"]).json()["review"]

    response = design_client.post(
        f"/api/design-reviews/{review['id']}/confirmations",
        json={
            "expected_revision": review["revision"],
            "actor": "评审员甲",
            "role": "评审员（演示角色）",
            "decision": "rejected",
            "comment": "缺少取力器布置依据",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["review"]["status"] == "rejected"
    assert response.json()["confirmation"]["comment"] == "缺少取力器布置依据"


def test_review_issue_item_becomes_stale_when_issues_close(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    first = _generate(design_client, project["id"]).json()
    issue_item = next(
        item for item in first["items"] if item["display_code"] == "DR-07"
    )
    assert issue_item["dependencies"]

    issues = design_client.get(
        f"/api/projects/{project['id']}/issues"
    ).json()
    for issue in issues:
        response = design_client.post(
            f"/api/issues/{issue['id']}/close",
            json={
                "expected_status": "open",
                "actor": "工程师甲",
                "role": "设计工程师（演示角色）",
                "resolution_type": "manual_supplement",
                "resolution_note": "补充合成说明",
                "evidence": "合成证据：问题已澄清",
            },
        )
        assert response.status_code == 200, response.text

    second = _generate(design_client, project["id"]).json()

    assert all(item["display_code"] != "DR-07" for item in second["items"])
    assert second["review"]["revision"] == 2


def test_get_missing_design_review_and_dfmea_return_404(design_client):
    project = _create_project(design_client)

    review = design_client.get(
        f"/api/projects/{project['id']}/design-review"
    )
    dfmea = design_client.get(f"/api/projects/{project['id']}/dfmea")

    assert review.status_code == 404
    assert dfmea.status_code == 404
    assert review.json()["error"]["code"] == "NOT_FOUND"
    assert dfmea.json()["error"]["code"] == "NOT_FOUND"
