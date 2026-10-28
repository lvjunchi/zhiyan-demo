from test_engineering_versions import _setup_scenario
from test_stage03 import preview, clear


def test_workflow_counts_use_only_current_case_runs_and_show_sample_progress(
    design_client,
):
    from package_scenario import build_ready_project

    data = build_ready_project(design_client)
    project = data["project"]
    response = design_client.get(f"/api/projects/{project['id']}/workflow-summary")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["testing"]["total"] > 0
    assert summary["testing"]["review"]["confirmed"] == summary["testing"]["total"]
    assert summary["samples"]["total"] == 1 and summary["samples"]["confirmed"] == 1
    assert all(step["done"] for step in summary["samples"]["rows"][0]["steps"])
    requirements = design_client.get(
        f"/api/projects/{project['id']}/requirements"
    ).json()
    engine = next(row for row in requirements if row["parser_key"] == "engineMaxTorque")
    response = design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    assert response.status_code == 200, response.text
    changed = design_client.get(
        f"/api/projects/{project['id']}/workflow-summary"
    ).json()
    assert changed["testing"]["stale"] > 0
    assert (
        changed["testing"]["execution"]["pass"]
        < summary["testing"]["execution"]["pass"]
    )
    assert any(
        row["label"] == engine["display_code"]
        and row["before"] == "2600"
        and row["after"] == "2800"
        for row in changed["consistency"]["changes"]
    )


def test_progress_records_compare_participants_and_invalidate_old_metric(client):
    from test_parse_api import _create_project

    project = _create_project(client)
    topic = client.post(
        f"/api/projects/{project['id']}/coordination-topics",
        json={
            "name": "AB设计交付",
            "expected_participants": ["A", "B"],
            "window_start": "2026-10-20T00:00:00+00:00",
            "window_end": "2026-10-23T23:00:00+00:00",
        },
    ).json()
    assert "id" in topic, topic

    def save(participant, actual, revision=0):
        return client.post(
            f"/api/coordination-topics/{topic['id']}/progress",
            json={
                "participant": participant,
                "milestone": "设计冻结",
                "planned_percent": 80,
                "actual_percent": actual,
                "artifact_version": "V2" if participant == "A" else "V1",
                "reported_at": "2026-10-23T08:00:00+00:00",
                "evidence": f"{participant}方合成进度周报",
                "expected_revision": revision,
                "actor": "工程师",
                "role": "design_engineer",
            },
        )

    first = save("A", 90)
    assert first.status_code == 201, first.text
    second = save("B", 30)
    assert second.status_code == 201, second.text
    before = client.get("/api/system/backup").json()["sha256"]
    assessment = client.get(f"/api/coordination-topics/{topic['id']}/progress").json()
    assert assessment["assessment"]["risk_level"] == "high"
    assert {"progress_gap", "schedule_lag", "delivery_version"} <= {
        row["kind"] for row in assessment["assessment"]["alerts"]
    }
    assert client.get("/api/system/backup").json()["sha256"] == before
    metric = client.post(f"/api/coordination-topics/{topic['id']}/metrics", json={})
    assert metric.status_code == 201, metric.text
    assert metric.json()["metric_run"]["risk"]["risk_level"] == "high"
    assert save("B", 50).status_code == 409
    assert save("B", 50, 1).status_code == 201
    updated = client.get(f"/api/coordination-topics/{topic['id']}/metrics").json()
    assert updated["metric_run"]["validity"] == "stale"
    payload = save("C", 10)
    assert payload.status_code == 422


def test_progress_restore_rejects_current_record_without_matching_history(client):
    import base64, hashlib, json, sqlite3
    from test_parse_api import _create_project

    project = _create_project(client)
    topic = client.post(
        f"/api/projects/{project['id']}/coordination-topics",
        json={
            "name": "版本校验",
            "expected_participants": ["A"],
            "window_start": "2026-10-20T00:00:00Z",
            "window_end": "2026-10-24T00:00:00Z",
        },
    ).json()
    payload = {
        "participant": "A",
        "milestone": "冻结",
        "planned_percent": 80,
        "actual_percent": 60,
        "artifact_version": "V1",
        "reported_at": "2026-10-23T08:00:00Z",
        "evidence": "合成周报",
        "expected_revision": 0,
        "actor": "工程师",
        "role": "design_engineer",
    }
    response = client.post(
        f"/api/coordination-topics/{topic['id']}/progress", json=payload
    )
    assert response.status_code == 201, response.text
    before = client.get("/api/system/backup").json()
    valid = client.post("/api/system/restore-preview", json={"backup": before})
    assert valid.status_code == 200, valid.text
    con = sqlite3.connect(":memory:")
    con.deserialize(base64.b64decode(before["database_base64"]))
    con.execute("UPDATE coordination_progress SET revision=2")
    con.commit()
    content = con.serialize()
    con.close()
    damaged = {
        **before,
        "database_base64": base64.b64encode(content).decode(),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    response = client.post("/api/system/restore-preview", json={"backup": damaged})
    assert response.status_code == 422, response.text
    for key, value in [
        ("actual_percent", 101),
        ("participant", "C"),
        ("reported_at", "2026-10-30T00:00:00Z"),
    ]:
        response = client.post(
            f"/api/coordination-topics/{topic['id']}/progress",
            json={**payload, key: value, "expected_revision": 1},
        )
        assert response.status_code == 422, response.text
    assert client.get("/api/system/backup").json()["sha256"] == before["sha256"]


def test_consistency_stale_part_reports_real_engineering_revision(catalog_client):
    from test_engineering_versions import _setup_scenario
    from test_part_selection import selection

    client = catalog_client
    project_id, _ = _setup_scenario(client)
    groups = client.get(f"/api/projects/{project_id}/part-candidates").json()["parts"]
    group = next(row for row in groups if row["record"]["part_name"] == "输入轴")
    candidate = next(
        row for row in group["candidates"] if row["rated_torque_nm"] == 3000
    )
    selected = selection(client, group["record"], candidate).json()
    engine = next(
        row
        for row in client.get(f"/api/projects/{project_id}/requirements").json()
        if row["parser_key"] == "engineMaxTorque"
    )
    changed = client.patch(
        f"/api/requirements/{engine['id']}",
        json={"expected_revision": 1, "value_text": "2800"},
    )
    assert changed.status_code == 200, changed.text
    report = client.post(f"/api/projects/{project_id}/consistency-checks")
    assert report.status_code == 200, report.text
    conflict = next(
        row for row in report.json()["conflicts"] if row["object_id"] == selected["id"]
    )
    assert conflict["object_revision"] == selected["revision"]
