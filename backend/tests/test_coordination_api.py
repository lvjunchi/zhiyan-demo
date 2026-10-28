WINDOW_START = "2026-10-01T00:00:00+00:00"
WINDOW_END = "2026-10-20T00:00:00+00:00"
PARTICIPANTS = ["主机厂", "法士特", "S-02"]


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


def _create_topic(client, project_id, **overrides):
    payload = {
        "name": "样件接口与响应协同",
        "expected_participants": PARTICIPANTS,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
    }
    payload.update(overrides)
    response = client.post(
        f"/api/projects/{project_id}/coordination-topics", json=payload
    )
    return response


def _record(
    client,
    topic_id,
    external_id,
    *,
    record_type="message",
    sender="法士特",
    sent_at,
    reply_to=None,
    summary="合成协同记录",
):
    response = client.post(
        f"/api/coordination-topics/{topic_id}/records",
        json={
            "external_id": external_id,
            "record_type": record_type,
            "sender": sender,
            "content_summary": summary,
            "sent_at": sent_at,
            "reply_to_external_id": reply_to,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_fixture_records(client, topic_id):
    responses = (
        "2026-10-03T01:00:00+00:00",
        "2026-10-03T06:00:00+00:00",
        "2026-10-03T11:00:00+00:00",
    )
    for index, response_time in enumerate(responses, start=1):
        _record(
            client,
            topic_id,
            f"REQ-{index}",
            sender="法士特",
            sent_at=f"2026-10-01T0{index}:00:00+00:00",
        )
        _record(
            client,
            topic_id,
            f"RES-{index}",
            sender="S-02",
            sent_at=response_time,
            reply_to=f"REQ-{index}",
        )
    for index in range(1, 5):
        _record(
            client,
            topic_id,
            f"REOPENED-{index}",
            record_type="reopened",
            sender="法士特",
            sent_at=f"2026-10-08T0{index}:00:00+00:00",
        )


def _metrics(client, topic_id, **payload):
    response = client.post(
        f"/api/coordination-topics/{topic_id}/metrics", json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_fixture_metrics_are_computed_from_timestamped_records_and_recomputed(
    client,
):
    project = _create_project(client)
    topic_response = _create_topic(client, project["id"])
    assert topic_response.status_code == 201, topic_response.text
    topic = topic_response.json()
    assert topic["display_code"] == "CT-01"
    assert topic["mode"] == "manual"
    assert topic["source_label"] == "协同记录（合成数据）"

    _add_fixture_records(client, topic["id"])
    detail = client.get(
        f"/api/coordination-topics/{topic['id']}"
    ).json()
    assert detail["record_count"] == 10

    first = _metrics(
        client, topic["id"], labor_hours=6, hourly_rate=200
    )
    run = first["metric_run"]
    metrics = run["metrics"]
    risk = run["risk"]
    cost = run["cost"]

    assert run["run_no"] == 1
    assert run["rule_label"] == "COORD-DEMO-V1"
    assert run["mode"] == "rule"
    assert run["source_label"] == "COORD-DEMO-V1（演示规则）"
    assert metrics["average_response_hours"] == 52.0
    assert metrics["response_sample_size"] == 3
    assert metrics["response_latencies_hours"] == [48.0, 52.0, 56.0]
    assert metrics["iteration_count"] == 4
    assert metrics["actual_participants"] == ["S-02", "法士特"]
    assert metrics["absent_participants"] == ["主机厂"]
    assert abs(metrics["absence_rate"] - 1 / 3) < 1e-9
    assert metrics["pending_count"] == 0
    assert risk["risk_level"] == "high"
    assert risk["hit_count"] == 3
    assert risk["score"] == 100.0
    assert len(risk["reasons"]) == 3
    assert cost["labor_hours"] == 6.0
    assert cost["hourly_rate"] == 200.0
    assert cost["amount"] == 1200.0
    assert "不由消息条数推算" in cost["basis"]

    latest = client.get(
        f"/api/coordination-topics/{topic['id']}/metrics"
    )
    assert latest.status_code == 200
    assert latest.json()["metric_run"]["id"] == run["id"]

    second = _metrics(
        client, topic["id"], labor_hours=4, hourly_rate=250
    )
    assert second["metric_run"]["run_no"] == 2
    assert second["metric_run"]["cost"]["amount"] == 1000.0
    assert (
        second["metric_run"]["metrics"]["average_response_hours"]
        == 52.0
    )

    refreshed = client.get(
        f"/api/coordination-topics/{topic['id']}"
    ).json()
    assert refreshed["latest_metrics"]["run_no"] == 2

    overview = client.get(
        f"/api/projects/{project['id']}/coordination-overview"
    )
    assert overview.status_code == 200
    body = overview.json()
    assert body["topic_count"] == 1
    assert body["record_count"] == 10
    assert body["metrics_available"] == 1
    assert body["highest_risk"] == "high"


def test_pending_request_is_not_zero_and_missing_metrics_are_insufficient(
    client,
):
    project = _create_project(client)
    topic = _create_topic(client, project["id"]).json()
    _record(
        client,
        topic["id"],
        "REQ-PENDING",
        sender="法士特",
        sent_at="2026-10-10T00:00:00+00:00",
    )

    result = _metrics(client, topic["id"])
    metrics = result["metric_run"]["metrics"]
    risk = result["metric_run"]["risk"]
    cost = result["metric_run"]["cost"]

    assert metrics["average_response_hours"] is None
    assert metrics["response_sample_size"] == 0
    assert metrics["pending_count"] == 1
    assert metrics["pending_requests"][0]["external_id"] == "REQ-PENDING"
    assert metrics["pending_requests"][0]["waiting_hours"] == 240.0
    assert risk["risk_level"] == "insufficient"
    assert risk["score"] is None
    assert cost["amount"] is None
    assert cost["labor_hours"] is None
    assert any("工时" in gap for gap in cost["data_gaps"])


def test_coordination_validation_rejects_bad_window_and_references(client):
    project = _create_project(client)

    duplicate_participants = _create_topic(
        client,
        project["id"],
        expected_participants=["法士特", "法士特"],
    )
    assert duplicate_participants.status_code == 422

    naive_time = _create_topic(
        client,
        project["id"],
        window_start="2026-10-01T00:00:00",
    )
    assert naive_time.status_code == 422

    reversed_window = _create_topic(
        client,
        project["id"],
        window_start=WINDOW_END,
        window_end=WINDOW_START,
    )
    assert reversed_window.status_code == 422

    topic = _create_topic(client, project["id"]).json()
    duplicate_code = _create_topic(
        client, project["id"], display_code="CT-01"
    )
    assert duplicate_code.status_code == 409
    assert duplicate_code.json()["error"]["code"] == "DUPLICATE_DISPLAY_CODE"

    outside = client.post(
        f"/api/coordination-topics/{topic['id']}/records",
        json={
            "external_id": "REQ-OUT",
            "record_type": "message",
            "sender": "法士特",
            "sent_at": "2026-11-01T00:00:00+00:00",
        },
    )
    assert outside.status_code == 422

    orphan = client.post(
        f"/api/coordination-topics/{topic['id']}/records",
        json={
            "external_id": "RES-ORPHAN",
            "record_type": "message",
            "sender": "S-02",
            "sent_at": "2026-10-02T00:00:00+00:00",
            "reply_to_external_id": "MISSING",
        },
    )
    assert orphan.status_code == 422

    request = _record(
        client,
        topic["id"],
        "REQ-1",
        sent_at="2026-10-05T00:00:00+00:00",
    )
    assert request["record_count"] == 1

    early_response = client.post(
        f"/api/coordination-topics/{topic['id']}/records",
        json={
            "external_id": "RES-EARLY",
            "record_type": "message",
            "sender": "S-02",
            "sent_at": "2026-10-04T00:00:00+00:00",
            "reply_to_external_id": "REQ-1",
        },
    )
    assert early_response.status_code == 422

    duplicate_external = client.post(
        f"/api/coordination-topics/{topic['id']}/records",
        json={
            "external_id": "REQ-1",
            "record_type": "message",
            "sender": "法士特",
            "sent_at": "2026-10-06T00:00:00+00:00",
        },
    )
    assert duplicate_external.status_code == 409
    assert duplicate_external.json()["error"]["code"] == "DUPLICATE_RECORD"

    reopened_reply = client.post(
        f"/api/coordination-topics/{topic['id']}/records",
        json={
            "external_id": "REOPENED-1",
            "record_type": "reopened",
            "sender": "法士特",
            "sent_at": "2026-10-06T00:00:00+00:00",
            "reply_to_external_id": "REQ-1",
        },
    )
    assert reopened_reply.status_code == 422

    missing_metrics = client.get(
        f"/api/coordination-topics/{topic['id']}/metrics"
    )
    assert missing_metrics.status_code == 404

    missing_topic = client.get(
        "/api/coordination-topics/unknown-topic"
    )
    assert missing_topic.status_code == 404

    missing_project = client.post(
        "/api/projects/unknown-project/coordination-topics",
        json={
            "name": "不存在",
            "expected_participants": ["法士特"],
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    )
    assert missing_project.status_code == 404
