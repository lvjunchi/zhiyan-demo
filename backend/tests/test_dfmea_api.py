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
        f"/api/projects/{project_id}/dfmea",
        json={"base_display_code": base},
    )


def _get(client, project_id):
    response = client.get(f"/api/projects/{project_id}/dfmea")
    assert response.status_code == 200, response.text
    return response.json()


def _update_item(client, item, **changes):
    payload = {
        "expected_revision": item["revision"],
        "actor": "设计工程师甲",
        "role": "设计工程师（演示角色）",
    }
    payload.update(changes)
    return client.patch(f"/api/fmea-items/{item['id']}", json=payload)


def _confirm_scores(client, item):
    return client.post(
        f"/api/fmea-items/{item['id']}/confirm-scores",
        json={
            "expected_revision": item["revision"],
            "actor": "设计工程师甲",
            "role": "设计工程师（演示角色）",
            "comment": "S/O/D 已按合成量表确认",
        },
    )


def _score_and_confirm_all(client, project_id):
    body = _get(client, project_id)
    for index, item in enumerate(body["items"], start=1):
        updated = _update_item(
            client,
            item,
            severity=(index % 9) + 1,
            occurrence=(index % 8) + 1,
            detection=(index % 7) + 1,
        )
        assert updated.status_code == 200, updated.text
        confirmed = _confirm_scores(client, updated.json())
        assert confirmed.status_code == 200, confirmed.text
    return _get(client, project_id)


def test_generate_dfmea_returns_draft_with_pending_scores(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])

    response = _generate(design_client, project["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "rule"
    assert body["fmea"]["display_code"] == "DFMEA-P01"
    assert body["fmea"]["revision"] == 1
    assert body["fmea"]["status"] == "draft"
    assert body["fmea"]["scale"]["min"] == 1
    assert body["fmea"]["scale"]["max"] == 10
    assert len(body["items"]) >= 4
    assert len({item["id"] for item in body["items"]}) == len(
        body["items"]
    )
    for item in body["items"]:
        assert item["severity"] is None
        assert item["occurrence"] is None
        assert item["detection"] is None
        assert item["scores_confirmed"] is False
        assert item["rpn"] is None
        assert item["rpn_status"] == "incomplete"

    fetched = _get(design_client, project["id"])
    assert fetched["fmea"]["id"] == body["fmea"]["id"]
    assert fetched["items"] == body["items"]

    audits = design_client.get(
        f"/api/projects/{project['id']}/audit-events"
    ).json()
    events = [
        event for event in audits if event["action"] == "dfmea.generated"
    ]
    assert len(events) == 1


def test_fmea_item_update_versions_item_and_resets_score_confirmation(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    item = _generate(design_client, project["id"]).json()["items"][0]

    response = _update_item(
        design_client,
        item,
        severity=7,
        occurrence=4,
        detection=3,
        cause="额定输入扭矩不足导致输入轴疲劳",
    )

    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["id"] == item["id"]
    assert updated["revision"] == 2
    assert updated["severity"] == 7
    assert updated["occurrence"] == 4
    assert updated["detection"] == 3
    assert updated["scores_confirmed"] is False
    assert updated["rpn"] is None
    assert updated["rpn_status"] == "pending_confirmation"
    assert _get(design_client, project["id"])["fmea"]["revision"] == 2

    noop = _update_item(
        design_client,
        updated,
        severity=7,
        occurrence=4,
        detection=3,
        cause="额定输入扭矩不足导致输入轴疲劳",
    )
    assert noop.status_code == 200, noop.text
    assert noop.json()["revision"] == 2

    stale = _update_item(design_client, item, cause="旧版本修改")
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"


def test_fmea_item_rejects_scores_outside_frozen_scale(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    item = _generate(design_client, project["id"]).json()["items"][0]

    for severity in (0, 11):
        response = _update_item(design_client, item, severity=severity)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_fmea_score_confirmation_computes_rpn_from_confirmed_scores(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    item = _generate(design_client, project["id"]).json()["items"][0]
    updated = _update_item(
        design_client, item, severity=7, occurrence=4, detection=3
    ).json()

    response = _confirm_scores(design_client, updated)

    assert response.status_code == 200, response.text
    confirmed = response.json()
    assert confirmed["revision"] == 3
    assert confirmed["scores_confirmed"] is True
    assert confirmed["rpn"] == 84
    assert confirmed["rpn_status"] == "confirmed"

    repeat = _confirm_scores(design_client, confirmed)
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()["revision"] == 3

    assert _get(design_client, project["id"])["fmea"]["revision"] == 3


def test_dfmea_confirmation_requires_all_scores_and_snapshots_rpn(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    generated = _generate(design_client, project["id"]).json()

    rejected = design_client.post(
        f"/api/fmea-documents/{generated['fmea']['id']}/confirmations",
        json={
            "expected_revision": generated["fmea"]["revision"],
            "actor": "评审员甲",
            "role": "评审员（演示角色）",
            "decision": "confirmed",
            "comment": "尝试确认",
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"
    assert rejected.json()["error"]["details"]["unconfirmed_items"]

    scored = _score_and_confirm_all(design_client, project["id"])

    response = design_client.post(
        f"/api/fmea-documents/{scored['fmea']['id']}/confirmations",
        json={
            "expected_revision": scored["fmea"]["revision"],
            "actor": "评审员甲",
            "role": "评审员（演示角色）",
            "decision": "confirmed",
            "comment": "DFMEA 已按合成量表确认",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["fmea"]["status"] == "confirmed"
    assert body["confirmation"]["fmea_revision"] == scored["fmea"]["revision"]
    snapshot = body["confirmation"]["item_snapshot"]
    assert len(snapshot) == len(scored["items"])
    for item in snapshot:
        assert item["rpn"] == (
            item["severity"] * item["occurrence"] * item["detection"]
        )

    edited = _update_item(
        design_client,
        scored["items"][0],
        cause="复核后发现新的失效原因",
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["scores_confirmed"] is False
    assert edited.json()["rpn"] is None
    current = _get(design_client, project["id"])
    assert current["fmea"]["status"] == "draft"
    assert len(current["confirmations"]) == 1


def test_fmea_item_revision_history_is_preserved(design_client, db_path):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    item = _generate(design_client, project["id"]).json()["items"][0]
    updated = _update_item(
        design_client, item, severity=6, occurrence=5, detection=4
    ).json()
    _confirm_scores(design_client, updated)

    connection = connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT revision, severity, occurrence, detection, scores_confirmed
            FROM fmea_item_revisions
            WHERE item_id = ? ORDER BY revision ASC
            """,
            (item["id"],),
        ).fetchall()
    finally:
        connection.close()

    assert [row["revision"] for row in rows] == [1, 2, 3]
    assert rows[0]["severity"] is None
    assert rows[0]["scores_confirmed"] == 0
    assert rows[1]["severity"] == 6
    assert rows[1]["scores_confirmed"] == 0
    assert rows[2]["scores_confirmed"] == 1


def test_dfmea_regeneration_is_idempotent(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])

    first = _generate(design_client, project["id"]).json()
    second = _generate(design_client, project["id"]).json()

    assert second["fmea"]["id"] == first["fmea"]["id"]
    assert second["fmea"]["revision"] == 1
    assert [item["id"] for item in second["items"]] == [
        item["id"] for item in first["items"]
    ]
    assert [item["revision"] for item in second["items"]] == [
        item["revision"] for item in first["items"]
    ]


def test_dfmea_regeneration_versions_item_when_dependency_changes(
    design_client,
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    first = _generate(design_client, project["id"]).json()
    requirements = design_client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    top_gear = next(
        requirement
        for requirement in requirements
        if requirement["parser_key"] == "topGearType"
    )
    update = design_client.patch(
        f"/api/requirements/{top_gear['id']}",
        json={
            "expected_revision": top_gear["current_revision"],
            "value_text": "直接档",
        },
    )
    assert update.status_code == 200, update.text

    second = _generate(design_client, project["id"]).json()

    assert second["fmea"]["id"] == first["fmea"]["id"]
    assert second["fmea"]["revision"] == 2
    first_top_gear = next(
        item for item in first["items"] if item["display_code"] == "FMEA-06"
    )
    second_top_gear = next(
        item for item in second["items"] if item["display_code"] == "FMEA-06"
    )
    assert second_top_gear["id"] == first_top_gear["id"]
    assert second_top_gear["revision"] == 2
    assert any(
        dependency["revision"] == 2
        for dependency in second_top_gear["dependencies"]
        if dependency["object_type"] == "requirement"
    )


def test_dfmea_optional_item_becomes_stale_when_requirement_changes(
    design_client, db_path
):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    first = _generate(design_client, project["id"]).json()
    assert any(item["display_code"] == "FMEA-02" for item in first["items"])
    requirements = design_client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    pto = next(
        requirement
        for requirement in requirements
        if requirement["parser_key"] == "pto"
    )
    update = design_client.patch(
        f"/api/requirements/{pto['id']}",
        json={
            "expected_revision": pto["current_revision"],
            "value_text": "not_required",
        },
    )
    assert update.status_code == 200, update.text

    second = _generate(design_client, project["id"]).json()

    assert all(item["display_code"] != "FMEA-02" for item in second["items"])
    assert second["fmea"]["revision"] == 2
    connection = connect(db_path)
    try:
        item = connection.execute(
            """
            SELECT i.id FROM fmea_items i
            WHERE i.fmea_id = ? AND i.display_code = 'FMEA-02'
            """,
            (second["fmea"]["id"],),
        ).fetchone()
        latest = connection.execute(
            """
            SELECT revision, status FROM fmea_item_revisions
            WHERE item_id = ? ORDER BY revision DESC LIMIT 1
            """,
            (item["id"],),
        ).fetchone()
    finally:
        connection.close()
    assert latest["revision"] == 2
    assert latest["status"] == "stale"


def test_confirm_scores_requires_complete_scores(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    item = _generate(design_client, project["id"]).json()["items"][0]

    response = _confirm_scores(design_client, item)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]["missing_scores"] == [
        "severity",
        "occurrence",
        "detection",
    ]


def test_confirm_scores_rejects_stale_item_revision(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    item = _generate(design_client, project["id"]).json()["items"][0]
    updated = _update_item(
        design_client, item, severity=5, occurrence=5, detection=5
    ).json()

    response = _confirm_scores(design_client, item)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_dfmea_confirmation_version_and_duplicate_conflicts(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])
    _generate(design_client, project["id"])
    scored = _score_and_confirm_all(design_client, project["id"])
    payload = {
        "expected_revision": scored["fmea"]["revision"],
        "actor": "评审员甲",
        "role": "评审员（演示角色）",
        "decision": "confirmed",
        "comment": "确认",
    }
    first = design_client.post(
        f"/api/fmea-documents/{scored['fmea']['id']}/confirmations",
        json=payload,
    )
    assert first.status_code == 201, first.text

    duplicate = design_client.post(
        f"/api/fmea-documents/{scored['fmea']['id']}/confirmations",
        json=payload,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "VERSION_CONFLICT"

    stale = design_client.post(
        f"/api/fmea-documents/{scored['fmea']['id']}/confirmations",
        json={**payload, "expected_revision": 999},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"


def test_dfmea_and_review_unknown_base_returns_404(design_client):
    project = _create_project(design_client)
    _create_and_parse(design_client, project["id"])

    dfmea = _generate(design_client, project["id"], base="JX-UNKNOWN")
    review = design_client.post(
        f"/api/projects/{project['id']}/design-review",
        json={"base_display_code": "JX-UNKNOWN"},
    )

    assert dfmea.status_code == 404
    assert review.status_code == 404
    assert dfmea.json()["error"]["code"] == "NOT_FOUND"
