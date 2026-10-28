import sqlite3

import pytest

from app import services
from app.db import connect
from test_parse_api import _create_project, _create_source


def setup_rows(client):
    project = _create_project(client)
    source = _create_source(client, project["id"])
    result = client.post(f"/api/source-documents/{source['id']}/parse", json={}).json()
    rows = [
        row
        for row in result["requirements"]
        if row["parser_key"] in ("engineMaxTorque", "gearCount")
    ]
    assert len(rows) == 2
    return project, rows


def items(rows):
    return [
        {"requirement_id": row["id"], "expected_revision": row["current_revision"]}
        for row in rows
    ]


def preview(client, project, rows):
    result = client.post(
        f"/api/projects/{project['id']}/requirements/batch-preview",
        json={"items": items(rows)},
    )
    assert result.status_code == 200, result.text
    return result.json()


def commit(client, project, rows, checked):
    return client.post(
        f"/api/projects/{project['id']}/requirements/batch-confirm",
        json={
            "items": items(rows),
            "expected_preview_hash": checked["preview_hash"],
            "actor": "核对工程师",
            "role": "design_engineer",
            "comment": "逐条核对原文及适用要求",
        },
    )


def test_batch_preview_is_readonly_then_commit_records_each_exact_revision(client):
    project, rows = setup_rows(client)
    before = client.get("/api/system/backup").json()["sha256"]
    checked = preview(client, project, rows)
    assert checked["can_submit"] and checked["selected_count"] == 2
    assert all(row["eligible"] for row in checked["rows"])
    assert client.get("/api/system/backup").json()["sha256"] == before
    result = commit(client, project, rows, checked)
    assert result.status_code == 200, result.text
    assert result.json()["confirmed_count"] == 2
    for row in rows:
        current = client.get(f"/api/requirements/{row['id']}").json()
        assert current["review_status"] == "confirmed"
        events = client.get(f"/api/requirements/{row['id']}/confirmations").json()
        assert (
            len(events) == 1 and events[0]["object_revision"] == row["current_revision"]
        )
        assert events[0]["actor"] == "核对工程师"
    assert commit(client, project, rows, checked).status_code == 409


@pytest.mark.parametrize("change", ["rejected", "revision", "issue"])
def test_batch_refuses_changed_scope_and_never_partially_confirms(
    client, db_path, change
):
    project, rows = setup_rows(client)
    checked = preview(client, project, rows)
    if change == "rejected":
        client.post(
            f"/api/requirements/{rows[1]['id']}/confirmations",
            json={
                "expected_revision": 1,
                "actor": "工程师",
                "role": "design_engineer",
                "decision": "rejected",
                "comment": "需修订",
            },
        )
    elif change == "revision":
        client.patch(
            f"/api/requirements/{rows[1]['id']}",
            json={"expected_revision": 1, "value_text": "14"},
        )
    else:
        connection = connect(db_path)
        connection.execute(
            "UPDATE requirements SET validity='stale' WHERE id=?", (rows[1]["id"],)
        )
        connection.close()
    result = commit(client, project, rows, checked)
    assert result.status_code == 409, result.text
    assert (
        client.get(f"/api/requirements/{rows[0]['id']}").json()["review_status"]
        == "draft"
    )
    assert client.get(f"/api/requirements/{rows[0]['id']}/confirmations").json() == []


def test_batch_blocks_unresolved_clauses_rejected_rows_invalid_units_and_other_projects(
    client, db_path
):
    project, rows = setup_rows(client)
    all_rows = client.get(f"/api/projects/{project['id']}/requirements").json()
    durability = next(row for row in all_rows if row["parser_key"] == "durability")
    checked = preview(client, project, [rows[0], durability])
    assert not checked["can_submit"]
    assert next(
        row for row in checked["rows"] if row["requirement"]["id"] == durability["id"]
    )["reasons"]
    assert commit(client, project, [rows[0], durability], checked).status_code == 422
    assert (
        client.get(f"/api/requirements/{rows[0]['id']}").json()["review_status"]
        == "draft"
    )
    connection = connect(db_path)
    connection.execute(
        "UPDATE requirements SET unit='unknown' WHERE id=?", (rows[0]["id"],)
    )
    connection.close()
    assert not preview(client, project, rows)["can_submit"]
    other = client.post(
        "/api/projects",
        json={
            "display_code": "OTHER",
            "name": "其他",
            "customer": "客户",
            "product": "设备",
        },
    ).json()
    assert (
        client.post(
            f"/api/projects/{other['id']}/requirements/batch-preview",
            json={"items": items(rows)},
        ).status_code
        == 422
    )


def test_batch_rollback_after_second_write_failure(client, monkeypatch):
    project, rows = setup_rows(client)
    checked = preview(client, project, rows)
    calls = 0
    original = services._audit

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("injected batch write failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(services, "_audit", fail_second)
    result = commit(client, project, rows, checked)
    assert result.status_code == 503, result.text
    assert all(
        client.get(f"/api/requirements/{row['id']}").json()["review_status"] == "draft"
        for row in rows
    )
    assert all(
        client.get(f"/api/requirements/{row['id']}/confirmations").json() == []
        for row in rows
    )
