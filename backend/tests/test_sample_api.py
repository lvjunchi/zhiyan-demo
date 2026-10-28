import hashlib

DELIVERY = {
    "display_code": "SD-01",
    "supplier": "S-02（合成供应商）",
    "part_display_code": "P-1001",
    "drawing_display_code": "SX-DRW-0215",
    "drawing_revision": "B",
    "delivered_at": "2026-10-19",
    "quantity": 2,
    "notes": "合成样件，仅用于本地演示",
    "drawing_parameters": [
        {
            "parameter_key": "holePosition",
            "parameter_name": "孔位",
            "expected_value": 120.0,
            "tolerance": 0.5,
            "unit": "mm",
            "source_note": "图纸 SX-DRW-0215 第 2 区域标注",
        },
        {
            "parameter_key": "shaftDiameter",
            "parameter_name": "轴径",
            "expected_value": 45.0,
            "tolerance": 0.02,
            "unit": "mm",
            "source_note": "图纸 SX-DRW-0215 第 3 区域标注",
        },
    ],
}

VISUAL_FAIL = {
    "mode": "mock",
    "result": "fail",
    "note": "模拟目视检查：孔位与图纸不符（合成数据）",
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


def _create_delivery(client, project_id, **overrides):
    payload = {**DELIVERY, **overrides}
    response = client.post(
        f"/api/projects/{project_id}/sample-deliveries", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client, delivery, content=b"sample drawing payload"):
    return client.put(
        f"/api/sample-deliveries/{delivery['id']}/file",
        params={"file_name": "sample-drawing.txt"},
        content=content,
        headers={"Content-Type": "text/plain"},
    )


def _comparison_payload(**overrides):
    payload = {
        "actor": "质量工程师甲",
        "role": "质量工程师（演示角色）",
        "parameters": [
            {
                "parameter_key": "holePosition",
                "measured_value": 123.5,
                "unit": "mm",
            },
            {
                "parameter_key": "shaftDiameter",
                "measured_value": 45.01,
                "unit": "mm",
            },
        ],
        "visual_check": VISUAL_FAIL,
        "evidence": "合成测量记录 TR-01；模拟视觉记录 VS-01",
    }
    payload.update(overrides)
    return payload


def _compare(client, delivery, **overrides):
    current = client.get(f"/api/sample-deliveries/{delivery['id']}/comparison")
    if current.status_code == 200:
        overrides.setdefault(
            "expected_revision", current.json()["comparison"]["revision"]
        )
    return client.post(
        f"/api/sample-deliveries/{delivery['id']}/comparison",
        json=_comparison_payload(**overrides),
    )


def _confirm_comparison(client, comparison, **overrides):
    payload = {
        "expected_revision": comparison["revision"],
        "actor": "质量工程师甲",
        "role": "质量工程师（演示角色）",
        "decision": "confirmed",
        "comment": "样件比对记录已核对",
    }
    payload.update(overrides)
    return client.post(
        f"/api/sample-comparisons/{comparison['id']}/confirmations",
        json=payload,
    )


def test_sample_delivery_records_structured_drawing_and_real_file(
    design_client,
):
    project = _create_project(design_client)
    delivery = _create_delivery(design_client, project["id"])

    assert delivery["display_code"] == "SD-01"
    assert delivery["mode"] == "manual"
    assert delivery["file_uploaded"] is False
    assert len(delivery["drawing_parameters"]) == 2
    assert delivery["source_label"] == "样件交付记录（合成数据）"

    content = b"sample drawing payload"
    uploaded = _upload(design_client, delivery, content)
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    assert body["file_uploaded"] is True
    assert body["file"]["size_bytes"] == len(content)
    assert body["file"]["content_hash"] == hashlib.sha256(content).hexdigest()

    downloaded = design_client.get(f"/api/sample-deliveries/{delivery['id']}/file")
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["x-content-sha256"] == hashlib.sha256(content).hexdigest()

    duplicate = _upload(design_client, delivery, b"second payload")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "VERSION_CONFLICT"

    duplicate_code = design_client.post(
        f"/api/projects/{project['id']}/sample-deliveries",
        json=DELIVERY,
    )
    assert duplicate_code.status_code == 409
    assert duplicate_code.json()["error"]["code"] == "DUPLICATE_DISPLAY_CODE"

    listed = design_client.get(f"/api/projects/{project['id']}/sample-deliveries")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [delivery["id"]]


def test_file_upload_validates_name_size_and_requires_file_before_compare(
    design_client,
):
    project = _create_project(design_client)
    delivery = _create_delivery(design_client, project["id"])

    without_file = _compare(design_client, delivery)
    assert without_file.status_code == 422
    assert "上传" in without_file.json()["error"]["message"]

    empty = _upload(design_client, delivery, b"")
    assert empty.status_code == 422

    bad_name = design_client.put(
        f"/api/sample-deliveries/{delivery['id']}/file",
        params={"file_name": "../escape.txt"},
        content=b"payload",
        headers={"Content-Type": "text/plain"},
    )
    assert bad_name.status_code == 422

    oversized = _upload(design_client, delivery, b"x" * (8 * 1024 * 1024 + 1))
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "VALIDATION_ERROR"


def test_comparison_creates_traceable_issue_and_revision(design_client):
    project = _create_project(design_client)
    delivery = _create_delivery(design_client, project["id"])
    _upload(design_client, delivery)

    response = _compare(design_client, delivery)

    assert response.status_code == 200, response.text
    body = response.json()
    comparison = body["comparison"]
    assert comparison["display_code"] == "CMP-SD-01"
    assert comparison["revision"] == 1
    assert comparison["status"] == "draft"
    assert comparison["overall_result"] == "fail"
    assert comparison["mode"] == "mock"
    findings = {finding["parameter_key"]: finding for finding in comparison["findings"]}
    assert findings["holePosition"]["result"] == "fail"
    assert findings["holePosition"]["mode"] == "rule"
    assert findings["shaftDiameter"]["result"] == "pass"
    assert findings["visualCheck"]["mode"] == "mock"
    assert findings["visualCheck"]["result"] == "fail"

    issues = body["issues"]
    assert len(issues) == 1
    assert issues[0]["status"] == "open"
    assert issues[0]["issue_type"] == "contradictory"
    assert issues[0]["category"] == "sample"
    assert "孔位" in issues[0]["message"]

    project_issues = design_client.get(f"/api/projects/{project['id']}/issues").json()
    assert any(issue["id"] == issues[0]["id"] for issue in project_issues)

    duplicate = _compare(design_client, delivery)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["comparison"]["revision"] == 1
    assert len(duplicate.json()["issues"]) == 1

    corrected = _compare(
        design_client,
        delivery,
        parameters=[
            {
                "parameter_key": "holePosition",
                "measured_value": 120.2,
                "unit": "mm",
            },
            {
                "parameter_key": "shaftDiameter",
                "measured_value": 45.01,
                "unit": "mm",
            },
        ],
        visual_check={
            "mode": "mock",
            "result": "pass",
            "note": "模拟目视检查：未发现明显不符（合成数据）",
        },
    )
    assert corrected.status_code == 200, corrected.text
    corrected_body = corrected.json()
    assert corrected_body["comparison"]["revision"] == 2
    assert corrected_body["comparison"]["overall_result"] == "pass"
    assert corrected_body["issues"][0]["status"] == "open"

    confirmed = _confirm_comparison(design_client, corrected_body["comparison"])
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["comparison"]["status"] == "confirmed"
    assert confirmed.json()["confirmation"]["comparison_revision"] == 2

    duplicate_confirmation = _confirm_comparison(
        design_client,
        corrected_body["comparison"],
    )
    assert duplicate_confirmation.status_code == 409

    stale_confirmation = _confirm_comparison(
        design_client,
        {**corrected_body["comparison"], "revision": 1},
    )
    assert stale_confirmation.status_code == 409

    close = design_client.post(
        f"/api/issues/{issues[0]['id']}/close",
        json={
            "expected_status": "open",
            "actor": "质量工程师甲",
            "role": "质量工程师（演示角色）",
            "resolution_type": "accepted_risk",
            "resolution_note": "样件复测合格，首批样件按让步接收",
            "evidence": "复测记录 TR-02：孔位 120.2 mm",
        },
    )
    assert close.status_code == 200, close.text
    fetched = design_client.get(
        f"/api/sample-deliveries/{delivery['id']}/comparison"
    ).json()
    assert fetched["issues"][0]["status"] == "closed"


def test_comparison_reports_incomplete_and_invalid_without_issue(
    design_client,
):
    project = _create_project(design_client)
    delivery = _create_delivery(design_client, project["id"])
    _upload(design_client, delivery)

    incomplete = _compare(
        design_client,
        delivery,
        parameters=[
            {
                "parameter_key": "holePosition",
                "measured_value": 120.1,
                "unit": "mm",
            }
        ],
        visual_check={
            "mode": "manual",
            "result": "incomplete",
            "note": "人工目视记录缺失，待补录",
        },
    )
    assert incomplete.status_code == 200, incomplete.text
    assert incomplete.json()["comparison"]["overall_result"] == "incomplete"
    assert incomplete.json()["issues"] == []
    assert incomplete.json()["comparison"]["mode"] == "manual"

    invalid = _compare(
        design_client,
        delivery,
        parameters=[
            {
                "parameter_key": "holePosition",
                "measured_value": 12.01,
                "unit": "cm",
            },
            {
                "parameter_key": "shaftDiameter",
                "measured_value": 45.01,
                "unit": "mm",
            },
        ],
        visual_check={
            "mode": "mock",
            "result": "pass",
            "note": "模拟目视通过",
        },
    )
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["comparison"]["overall_result"] == "invalid"
    findings = {
        finding["parameter_key"]: finding
        for finding in invalid.json()["comparison"]["findings"]
    }
    assert findings["holePosition"]["result"] == "invalid"
    assert "单位" in findings["holePosition"]["reason"]
    assert invalid.json()["issues"] == []

    missing_unit = _compare(
        design_client,
        delivery,
        parameters=[
            {
                "parameter_key": "holePosition",
                "measured_value": 120.1,
                "unit": "",
            },
            {
                "parameter_key": "shaftDiameter",
                "measured_value": 45.01,
                "unit": "mm",
            },
        ],
        visual_check={
            "mode": "mock",
            "result": "pass",
            "note": "模拟目视通过",
        },
    )
    assert missing_unit.status_code == 200, missing_unit.text
    assert missing_unit.json()["comparison"]["overall_result"] == "invalid"
    missing_findings = {
        finding["parameter_key"]: finding
        for finding in missing_unit.json()["comparison"]["findings"]
    }
    assert missing_findings["holePosition"]["result"] == "invalid"
    assert "单位" in missing_findings["holePosition"]["reason"]
    assert missing_unit.json()["issues"] == []


def test_sample_validation_rejects_unknown_parameter_and_bad_tolerance(
    design_client,
):
    project = _create_project(design_client)

    bad_tolerance = design_client.post(
        f"/api/projects/{project['id']}/sample-deliveries",
        json={
            **DELIVERY,
            "drawing_parameters": [
                {
                    "parameter_key": "holePosition",
                    "parameter_name": "孔位",
                    "expected_value": 120.0,
                    "tolerance": -0.1,
                    "unit": "mm",
                }
            ],
        },
    )
    assert bad_tolerance.status_code == 422

    duplicate_keys = design_client.post(
        f"/api/projects/{project['id']}/sample-deliveries",
        json={
            **DELIVERY,
            "drawing_parameters": DELIVERY["drawing_parameters"] * 2,
        },
    )
    assert duplicate_keys.status_code == 422

    delivery = _create_delivery(design_client, project["id"])
    _upload(design_client, delivery)
    unknown = _compare(
        design_client,
        delivery,
        parameters=[
            {
                "parameter_key": "unknownKey",
                "measured_value": 1.0,
                "unit": "mm",
            }
        ],
    )
    assert unknown.status_code == 422
    assert "unknownKey" in unknown.json()["error"]["message"]

    missing_visual = _compare(
        design_client,
        delivery,
        visual_check=None,
    )
    assert missing_visual.status_code == 422

    unknown_delivery = _compare(design_client, {**delivery, "id": "unknown-delivery"})
    assert unknown_delivery.status_code == 404

    unknown_comparison = design_client.get(
        f"/api/sample-deliveries/{delivery['id']}/comparison"
    )
    assert unknown_comparison.status_code == 404


def test_sample_delivery_allocates_stable_codes_and_exposes_detail(
    design_client,
):
    project = _create_project(design_client)
    first = _create_delivery(design_client, project["id"], display_code=None)
    second = _create_delivery(design_client, project["id"], display_code=None)
    assert first["display_code"] == "SD-01"
    assert second["display_code"] == "SD-02"
    assert first["id"] != second["id"]

    detail = design_client.get(f"/api/sample-deliveries/{first['id']}")
    assert detail.status_code == 200
    assert detail.json()["display_code"] == "SD-01"

    missing_file = design_client.get(f"/api/sample-deliveries/{first['id']}/file")
    assert missing_file.status_code == 404

    missing_delivery = design_client.get("/api/sample-deliveries/unknown-delivery")
    assert missing_delivery.status_code == 404

    missing_project = design_client.get(
        "/api/projects/unknown-project/sample-deliveries"
    )
    assert missing_project.status_code == 404


def test_repeated_failure_links_same_open_issue_and_confirm_rejects_unknown(
    design_client,
):
    project = _create_project(design_client)
    delivery = _create_delivery(design_client, project["id"])
    _upload(design_client, delivery)

    first = _compare(design_client, delivery)
    assert first.status_code == 200, first.text
    first_issue_id = first.json()["issues"][0]["id"]

    still_failing = _compare(
        design_client,
        delivery,
        parameters=[
            {
                "parameter_key": "holePosition",
                "measured_value": 124.0,
                "unit": "mm",
            },
            {
                "parameter_key": "shaftDiameter",
                "measured_value": 45.01,
                "unit": "mm",
            },
        ],
    )
    assert still_failing.status_code == 200, still_failing.text
    body = still_failing.json()
    assert body["comparison"]["revision"] == 2
    assert body["comparison"]["overall_result"] == "fail"
    assert [issue["id"] for issue in body["issues"]] == [first_issue_id]
    assert body["issues"][0]["status"] == "open"

    unknown = design_client.post(
        "/api/sample-comparisons/unknown-comparison/confirmations",
        json={
            "expected_revision": 1,
            "actor": "质量工程师甲",
            "role": "质量工程师（演示角色）",
            "decision": "confirmed",
            "comment": "不应写入",
        },
    )
    assert unknown.status_code == 404
