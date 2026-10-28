"""Project overview API: authoritative read-only aggregation."""

from package_scenario import build_ready_project, create_project


def _overview(client, project_id: str) -> dict:
    response = client.get(f"/api/projects/{project_id}/overview")
    assert response.status_code == 200, response.text
    return response.json()


def test_risk_summary_uses_current_metric_snapshot_and_keeps_full_evidence(
    design_client,
):
    project = create_project(design_client)
    topic_response = design_client.post(
        f"/api/projects/{project['id']}/coordination-topics",
        json={
            "name": "接口交付协同（合成）",
            "expected_participants": ["A", "B"],
            "window_start": "2026-10-01T00:00:00+00:00",
            "window_end": "2026-10-31T00:00:00+00:00",
        },
    )
    assert topic_response.status_code == 201, topic_response.text
    topic_id = topic_response.json()["id"]
    for code, sender, sent_at, reply in [
        ("Q1", "A", "2026-10-01T00:00:00+00:00", None),
        ("R1", "B", "2026-10-03T04:00:00+00:00", "Q1"),
    ]:
        response = design_client.post(
            f"/api/coordination-topics/{topic_id}/records",
            json={
                "external_id": code,
                "record_type": "message",
                "sender": sender,
                "content_summary": "合成接口交付记录",
                "sent_at": sent_at,
                "reply_to_external_id": reply,
            },
        )
        assert response.status_code == 201, response.text
    payload = {
        "participant": "B",
        "milestone": "接口交付",
        "planned_percent": 80,
        "actual_percent": 30,
        "artifact_version": "V1",
        "reported_at": "2026-10-04T00:00:00+00:00",
        "evidence": "合成进度表",
        "expected_revision": 0,
        "actor": "测试工程师",
        "role": "演示角色",
    }
    response = design_client.post(
        f"/api/coordination-topics/{topic_id}/progress", json=payload
    )
    assert response.status_code == 201, response.text
    response = design_client.post(
        f"/api/coordination-topics/{topic_id}/metrics",
        json={"labor_hours": 1, "hourly_rate": 100},
    )
    assert response.status_code == 201, response.text
    audit_url = f"/api/projects/{project['id']}/audit-events"
    before = design_client.get(audit_url).json()
    risk = _overview(design_client, project["id"])["cockpit"]["risk_topics"][0]
    assert risk["headline"] == "最大进度落后 50 个百分点"
    assert risk["progress"]["rows"][0]["actual_percent"] == 30
    assert len(risk["records"]) == 2
    assert risk["metric_details"]["response_sample_size"] == 1
    assert risk["average_response_hours"] == 52
    assert risk["rule_conditions"]
    assert design_client.get(audit_url).json() == before
    changed = design_client.post(
        f"/api/coordination-topics/{topic_id}/progress",
        json={**payload, "actual_percent": 60, "expected_revision": 1},
    )
    assert changed.status_code == 201, changed.text
    stale = _overview(design_client, project["id"])["cockpit"]["risk_topics"][0]
    assert stale["risk_level"] == "insufficient"
    assert stale["headline"] is None
    assert stale["average_response_hours"] is None


def test_overview_trace_links_use_persisted_requirement_versions(design_client):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]
    audit_url = f"/api/projects/{project_id}/audit-events"
    before = design_client.get(audit_url).json()
    data = _overview(design_client, project_id)
    row = next(
        item
        for item in data["cockpit"]["traceability_items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert row["design_items"]
    assert row["design_items"][0]["display_code"] == "DR-01"
    assert row["design_items"][0]["status"] == "confirmed"
    assert row["design_items"][0]["requirement_revision"] == row["requirement_revision"]
    assert row["test_cases"]
    assert any(case["display_code"] == "TC-007" for case in row["test_cases"])
    assert all(case["requirement_refs"] for case in row["test_cases"])
    assert all(case["acceptance_criteria"] for case in row["test_cases"])
    assert design_client.get(audit_url).json() == before

    other = create_project(design_client, "P99")
    assert _overview(design_client, other["id"])["cockpit"]["traceability_items"] == []

    engine = next(
        req
        for req in scenario["requirements"]
        if req["parser_key"] == "engineMaxTorque"
    )
    response = design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    assert response.status_code == 200, response.text
    changed = _overview(design_client, project_id)
    changed_row = next(
        item
        for item in changed["cockpit"]["traceability_items"]
        if item["key"] == "gearboxRatedInputTorque"
    )
    assert changed_row["requirement_revision"] == 2
    assert not changed_row["covered"]
    assert all(
        design["requirement_revision"] == 1 for design in changed_row["design_items"]
    )
    assert all(design["validity"] == "stale" for design in changed_row["design_items"])
    assert all(case["validity"] == "stale" for case in changed_row["test_cases"])
    assert all(
        case["requirement_refs"][0]["revision"] == 1
        for case in changed_row["test_cases"]
    )
    assert any(
        case["runs"] for case in changed_row["test_cases"]
    ), "Historical runs must stay visible"


def test_overview_reports_authoritative_project_state(design_client):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]
    package_response = design_client.post(
        f"/api/projects/{project_id}/material-packages",
        json={"include_originals": False},
    )
    assert package_response.status_code == 201, package_response.text
    variant_response = design_client.post(
        f"/api/projects/{project_id}/variant-analysis",
        json={"base_display_code": "JX-12A"},
    )
    assert variant_response.status_code == 200, variant_response.text

    data = _overview(design_client, project_id)

    assert data["project"]["display_code"] == "P01"
    assert data["requirements"] == {
        "total": 13,
        "confirmed": 13,
        "draft": 0,
        "pending_review": 0,
        "rejected": 0,
        "stale": 0,
    }
    assert data["issues"]["open"] == 1
    assert data["issues"]["closed"] == 1
    assert data["issues"]["open_by_severity"]["medium"] == 1

    assert data["spectrum"] == {
        "variant_points": 1,
        "stale_variant_points": 0,
        "reusable_parts": 8,
    }

    assert data["samples"]["delivery_count"] == 1
    assert data["samples"]["comparison_count"] == 1
    assert data["samples"]["latest_status"] == "confirmed"
    assert data["samples"]["latest_result"] == "pass"

    traceability = data["traceability"]
    assert traceability["denominator"] == 5
    assert traceability["covered_count"] == 5
    assert traceability["coverage_percentage"] == 100.0
    assert traceability["execution_summary"]["pass"] == 5

    assert data["design_review"]["display_code"] == "DR-P01"
    assert data["design_review"]["status"] == "confirmed"
    assert data["design_review"]["revision"] == 1
    assert data["design_review"]["item_count"] > 0

    assert data["dfmea"]["display_code"] == "DFMEA-P01"
    assert data["dfmea"]["status"] == "confirmed"
    assert data["dfmea"]["pending_score_count"] == 0

    assert data["consistency"]["check"]["display_code"] == "CR-P01-001"
    assert data["consistency"]["check"]["status"] == "confirmed"
    assert data["consistency"]["open_conflicts"] == 0
    assert data["consistency"]["blocking_open"] == 0

    assert data["coordination"]["topic_count"] == 1
    assert data["coordination"]["record_count"] > 0
    assert data["coordination"]["metrics_available"] == 1
    assert data["coordination"]["highest_risk"] == "high"
    assert data["coordination"]["high_risk_topics"] == 1

    assert data["package"]["display_code"] == "MP-P01-001"
    assert data["package"]["status"] == "ready_to_submit"
    assert data["package"]["blocker_count"] == 0
    assert data["package"]["warning_count"] == 1
    assert len(data["package"]["snapshot_hash"]) == 64


def test_overview_nulls_artifacts_that_do_not_exist(design_client):
    project = create_project(design_client, "P09")

    data = _overview(design_client, project["id"])

    assert data["requirements"]["total"] == 0
    assert data["issues"]["open"] == 0
    assert data["spectrum"] == {
        "variant_points": 0,
        "stale_variant_points": 0,
        "reusable_parts": 0,
    }
    assert data["samples"]["delivery_count"] == 0
    assert data["samples"]["comparison_count"] == 0
    assert data["samples"]["latest_status"] is None
    assert data["samples"]["latest_result"] is None
    assert data["traceability"] is None
    assert data["design_review"] is None
    assert data["dfmea"] is None
    assert data["consistency"] is None
    assert data["package"] is None
    assert data["coordination"]["topic_count"] == 0
    assert data["coordination"]["highest_risk"] == "insufficient"


def test_overview_unknown_project_returns_404(design_client):
    response = design_client.get("/api/projects/missing-project/overview")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_cockpit_details_are_project_scoped_current_and_read_only(design_client):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]
    other = create_project(design_client, "P10")
    before = design_client.get(f"/api/projects/{project_id}/audit-events").json()
    data = _overview(design_client, project_id)["cockpit"]

    engine = next(
        item for item in data["parameters"] if item["key"] == "engineMaxTorque"
    )
    assert engine["value_text"] == "2600"
    assert engine["revision"] == 1
    assert engine["requirement_id"]
    assert len(data["traceability_items"]) == 5
    assert all(item["execution"] == "pass" for item in data["traceability_items"])
    assert data["resources"]["product_bases"] >= 3
    assert data["resources"]["source_documents"] >= 1
    assert data["risk_topics"][0]["average_response_hours"] == 52
    assert data["risk_topics"][0]["iteration_count"] == 4
    assert data["risk_topics"][0]["absence_rate"] == 1 / 3
    assert data["risk_topics"][0]["risk_level"] == "high"
    assert len(data["recent_activity"]) == min(30, len(before))
    assert len(data["recent_activity"]) > 6
    assert all(item["project_id"] == project_id for item in data["recent_activity"])
    assert data["recent_activity"] == sorted(
        data["recent_activity"],
        key=lambda item: (item["created_at"], item["id"]),
        reverse=True,
    )
    after = design_client.get(f"/api/projects/{project_id}/audit-events").json()
    assert after == before

    empty = _overview(design_client, other["id"])["cockpit"]
    assert empty["parameters"] == []
    assert empty["traceability_items"] == []
    assert empty["risk_topics"] == []
    assert empty["resources"]["source_documents"] == 0
    assert all(item["project_id"] == other["id"] for item in empty["recent_activity"])
