from app import design_services
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


def test_similar_projects_returns_explained_top3_and_audit(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])

    response = design_client.post(
        f"/api/projects/{project['id']}/similar-projects",
        json={"top_n": 3},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "mock"
    assert body["source_label"] == "合成历史项目库 V1（示意数据）"
    assert body["candidate_count"] == 5
    assert body["candidate_shortage"] is False
    assert [
        match["display_code"] for match in body["matches"]
    ] == ["HX-2023-01", "HX-2023-02", "HX-2022-05"]
    best = body["matches"][0]
    assert best["score"] == 100.0
    assert best["matched_points"]
    assert best["source"] == "合成历史项目库 V1（示意数据）"
    assert all(
        criterion["project_value"] is not None
        for criterion in best["criteria"]
    )
    assert any(
        requirement["display_code"] == "REQ-P01-C-002"
        for requirement in body["requirement_versions"]
    )

    audits = design_client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    events = [
        event
        for event in audits
        if event["action"] == "similarity.generated"
    ]
    assert len(events) == 1
    assert events[0]["after"]["matches"][0]["display_code"] == "HX-2023-01"


def test_similar_projects_requires_seeded_history(client):
    project = _create_project(client)
    _create_and_parse(client, project["id"])

    response = client.post(
        f"/api/projects/{project['id']}/similar-projects", json={}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "历史项目库为空" in body["error"]["message"]


def test_similar_projects_requires_at_least_one_project_criterion(
    design_client,
):
    project = _create_project(design_client)

    response = design_client.post(
        f"/api/projects/{project['id']}/similar-projects", json={}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "缺少可比对的项目特征" in body["error"]["message"]
    assert "transmissionType" in body["error"]["details"]["missing_criteria"]


def test_similar_projects_excludes_missing_criteria_from_score(
    design_client,
):
    project = _create_project(design_client)
    for display_code, name, value in [
        ("REQ-P01-C-001", "档位数", "12"),
        ("REQ-P01-C-001-T", "换挡方式", "AMT"),
    ]:
        response = design_client.post(
            f"/api/projects/{project['id']}/requirements",
            json={
                "display_code": display_code,
                "category": "C",
                "parameter_name": name,
                "data_type": "text",
                "operator": "=",
                "value_text": value,
                "unit": "",
            },
        )
        assert response.status_code == 201, response.text

    response = design_client.post(
        f"/api/projects/{project['id']}/similar-projects", json={}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "ratedInputTorque" in body["missing_criteria"]
    assert "pto" in body["missing_criteria"]
    best = body["matches"][0]
    assert best["display_code"] == "HX-2023-01"
    assert best["score"] == 100.0
    assert best["missing_criteria"] == body["missing_criteria"]


def test_history_seed_is_idempotent(client, db_path):
    connection = connect(db_path)
    try:
        first = design_services.seed_history(connection)
        second = design_services.seed_history(connection)
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM history_projects"
        ).fetchone()["count"]
    finally:
        connection.close()

    assert first == {"history_projects_inserted": 5}
    assert second == {"history_projects_inserted": 0}
    assert count == 5


def test_similarity_rejects_duplicate_parameter_requirements(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    duplicate = design_client.post(
        f"/api/projects/{project['id']}/requirements",
        json={
            "display_code": "REQ-P01-C-001-DUP",
            "category": "C",
            "parameter_name": "档位数",
            "data_type": "text",
            "operator": "=",
            "value_text": "10",
            "unit": "",
        },
    )
    assert duplicate.status_code == 201, duplicate.text

    response = design_client.post(
        f"/api/projects/{project['id']}/similar-projects", json={}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "gearCount" in response.json()["error"]["details"]["duplicate_keys"]
