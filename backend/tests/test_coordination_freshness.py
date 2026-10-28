from package_scenario import build_ready_project


def add_record(client, topic):
    response = client.post(
        f"/api/coordination-topics/{topic['id']}/records",
        json={
            "external_id": "new-reopen",
            "record_type": "reopened",
            "sender": "S-02",
            "sent_at": topic["window_end"],
            "content_summary": "风险接受后再次重开议题",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_new_record_makes_metrics_stale_and_old_acceptance_cannot_open_gate(
    design_client,
):
    client = design_client
    state = build_ready_project(client)
    pid = state["project"]["id"]
    topic = state["coordination"]["topic"]
    before = client.get(f"/api/coordination-topics/{topic['id']}").json()
    after = add_record(client, topic)
    assert after["latest_metrics"]["validity"] == "stale"
    assert after["latest_metrics"]["id"] == before["latest_metrics"]["id"]
    assert after["latest_metrics"]["metrics"] == before["latest_metrics"]["metrics"]
    assert after["risk_acceptances"] == before["risk_acceptances"]
    overview = client.get(f"/api/projects/{pid}/coordination-overview").json()
    assert overview["metrics_available"] == 0
    assert overview["highest_risk"] == "insufficient"
    package = client.post(f"/api/projects/{pid}/material-packages", json={}).json()
    assert package["status"] == "draft"
    assert any(
        row["code"] == "COORDINATION_METRICS_STALE"
        for row in package["gate"]["blockers"]
    )


def test_recalculation_needs_a_new_explicit_acceptance(design_client):
    client = design_client
    state = build_ready_project(client)
    pid = state["project"]["id"]
    topic = state["coordination"]["topic"]
    after = add_record(client, topic)
    payload = {
        "metric_run_id": after["latest_metrics"]["id"],
        "actor": "负责人",
        "role": "演示角色",
        "note": "核对风险",
    }
    stale_acceptance = client.post(
        f"/api/coordination-topics/{topic['id']}/risk-acceptances", json=payload
    )
    assert stale_acceptance.status_code == 422, stale_acceptance.text
    calculated = client.post(
        f"/api/coordination-topics/{topic['id']}/metrics",
        json={"labor_hours": 6, "hourly_rate": 200},
    )
    assert calculated.status_code == 201, calculated.text
    metric = calculated.json()["metric_run"]
    assert metric["validity"] == "current"
    assert len(metric["inputs_sha256"]) == 64
    assert metric["metrics"]["iteration_count"] == 5
    package = client.post(f"/api/projects/{pid}/material-packages", json={}).json()
    assert package["status"] == "draft"
    accepted = client.post(
        f"/api/coordination-topics/{topic['id']}/risk-acceptances",
        json={**payload, "metric_run_id": metric["id"]},
    )
    assert accepted.status_code == 201, accepted.text
    assert (
        client.post(f"/api/projects/{pid}/material-packages", json={}).json()["status"]
        == "ready_to_submit"
    )
