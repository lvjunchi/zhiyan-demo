from app.db import connect
from package_scenario import build_ready_project, create_project
import subprocess
import sys


def workspace(client, project_id):
    response = client.get(f"/api/projects/{project_id}/workspace")
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_workspace_does_not_invent_completed_stages(design_client, db_path):
    project = create_project(design_client, "EMPTY")
    connection = connect(db_path)
    before = list(connection.iterdump())
    data = workspace(design_client, project["id"])
    assert [s["key"] for s in data["stages"]] == [
        "parsing",
        "requirements",
        "bases",
        "design",
        "testing",
        "samples",
        "consistency",
        "coordination",
        "packages",
    ]
    assert all(s["state"] == "empty" for s in data["stages"])
    assert data["changes"] == []
    assert list(connection.iterdump()) == before
    connection.close()


def test_change_workspace_uses_persisted_versions_and_keeps_history(design_client):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]
    requirements = design_client.get(f"/api/projects/{project_id}/requirements").json()
    engine = next(r for r in requirements if r["parser_key"] == "engineMaxTorque")
    before_runs = design_client.get(f"/api/projects/{project_id}/test-plan").json()
    changed = design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={
            "expected_revision": engine["current_revision"],
            "value_text": "2800",
        },
    )
    assert changed.status_code == 200, changed.text
    data = workspace(design_client, project_id)
    change = next(c for c in data["changes"] if c["requirement_id"] == engine["id"])
    assert change["before"]["value_text"] == "2600"
    assert change["after"]["value_text"] == "2800"
    assert change["to_revision"] == change["from_revision"] + 1
    impact = change["impacts"]
    derived = next(i for i in impact if i["display_code"] == "REQ-P01-C-002")
    assert derived["object_id"] != engine["id"]
    assert derived["review_status"] == "draft"
    case = next(i for i in impact if i["display_code"] == "TC-007")
    assert case["validity"] == "stale"
    assert case["review_status"] == "confirmed"
    assert case["references"] and any(
        r["referenced_revision"] < r["current_revision"] for r in case["references"]
    )
    assert any(i["object_type"] == "design_review" for i in impact)
    stages = {s["key"]: s for s in data["stages"]}
    assert stages["requirements"]["pending_count"] >= 2
    assert stages["testing"]["stale_count"] >= 1
    assert stages["testing"]["state"] == "attention"
    after_runs = design_client.get(f"/api/projects/{project_id}/test-plan").json()
    assert before_runs["cases"][0]["runs"] == after_runs["cases"][0]["runs"]
    other = create_project(design_client, "OTHER")
    assert workspace(design_client, other["id"])["changes"] == []
    assert design_client.get("/api/projects/missing/workspace").status_code == 404


def test_process_abrupt_exit_rolls_back_uncommitted_local_transaction(
    design_client, db_path
):
    project = create_project(design_client, "ABORT")
    connection = connect(db_path)
    before = list(connection.iterdump())
    connection.close()
    # A separate child owns only this pytest temporary database. No user process is killed.
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os, sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.execute('BEGIN IMMEDIATE')
c.execute("UPDATE projects SET name='UNCOMMITTED' WHERE id=?", (sys.argv[2],))
c.execute("UPDATE sequences SET next_value=next_value+10")
os._exit(73)
""",
            str(db_path),
            project["id"],
        ],
        check=False,
    )
    assert child.returncode == 73
    restarted = connect(db_path)
    assert list(restarted.iterdump()) == before
    restarted.close()
    assert workspace(design_client, project["id"])["changes"] == []
