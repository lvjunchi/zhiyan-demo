import json
from pathlib import Path

from app import services
from app.db import connect

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

ROOT = Path(__file__).resolve().parents[2]


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


def test_recommend_bases_returns_top3_with_evidence_and_audit(catalog_client):
    project = _create_project(catalog_client)
    _create_and_parse_source(catalog_client, project["id"])

    response = catalog_client.post(
        f"/api/projects/{project['id']}/recommend-bases",
        json={"top_n": 3},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate_count"] == 4
    assert body["candidate_shortage"] is False
    assert [
        item["base"]["display_code"] for item in body["top3"]
    ] == ["JX-12A", "JX-12B", "JX-12C"]

    top = body["top3"][0]
    assert top["hard_failures"] == []
    pto = next(
        criterion
        for criterion in top["criteria"]
        if criterion["criterion"] == "pto"
    )
    assert pto["satisfied"] is False
    assert pto["score"] == 0
    top_gear = next(
        criterion
        for criterion in top["criteria"]
        if criterion["criterion"] == "topGearType"
    )
    assert top_gear["score"] is None
    assert "未定型" in top_gear["reason"]
    assert all(
        criterion["source"] == "合成型谱库 V1（示意数据）"
        for criterion in top["criteria"]
    )

    jx12b = next(
        item
        for item in body["top3"]
        if item["base"]["display_code"] == "JX-12B"
    )
    assert "assemblyWeight" in jx12b["hard_failures"]

    jx12c = next(
        item
        for item in body["top3"]
        if item["base"]["display_code"] == "JX-12C"
    )
    assert "transmissionType" in jx12c["hard_failures"]

    assert any(
        requirement["display_code"] == "REQ-P01-C-002"
        and requirement["revision"] == 1
        for requirement in body["requirement_versions"]
    )

    audits = catalog_client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    recommendation_events = [
        event
        for event in audits
        if event["action"] == "recommendation.generated"
    ]
    assert len(recommendation_events) == 1
    assert (
        recommendation_events[0]["after"]["top3"][0]["display_code"]
        == "JX-12A"
    )


def test_recommendation_requires_seeded_catalog(client):
    project = _create_project(client)

    response = client.post(
        f"/api/projects/{project['id']}/recommend-bases", json={}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "型谱库为空" in body["error"]["message"]


def test_recommendation_requires_critical_requirements(catalog_client):
    project = _create_project(catalog_client)

    response = catalog_client.post(
        f"/api/projects/{project['id']}/recommend-bases", json={}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    missing = body["error"]["details"]["missing_requirements"]
    assert "gearboxRatedInputTorque" in missing
    assert "gearCount" in missing


def test_catalog_seed_is_idempotent(client, db_path):
    connection = connect(db_path)
    try:
        first = services.seed_catalog(connection)
        second = services.seed_catalog(connection)
        base_count = connection.execute(
            "SELECT COUNT(*) AS count FROM product_bases"
        ).fetchone()["count"]
        part_count = connection.execute(
            "SELECT COUNT(*) AS count FROM base_parts"
        ).fetchone()["count"]
    finally:
        connection.close()

    assert first == {"bases_inserted": 4, "parts_inserted": 7}
    assert second == {"bases_inserted": 0, "parts_inserted": 0}
    assert base_count == 4
    assert part_count == 7


def test_candidate_shortage_is_reported_by_api(client, db_path, tmp_path):
    project = _create_project(client)
    _create_and_parse_source(client, project["id"])

    catalog = json.loads(
        (ROOT / "fixtures" / "product_catalog.json").read_text(
            encoding="utf-8"
        )
    )
    catalog["product_bases"] = catalog["product_bases"][:2]
    catalog["base_parts"] = []
    custom_path = tmp_path / "catalog.json"
    custom_path.write_text(
        json.dumps(catalog, ensure_ascii=False), encoding="utf-8"
    )

    connection = connect(db_path)
    try:
        services.seed_catalog(connection, custom_path)
    finally:
        connection.close()

    response = client.post(
        f"/api/projects/{project['id']}/recommend-bases", json={}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate_count"] == 2
    assert body["candidate_shortage"] is True
    assert len(body["top3"]) == 2
