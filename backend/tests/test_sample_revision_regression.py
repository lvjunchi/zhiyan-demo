import json
import sqlite3

from app.db import connect, run_migrations
from test_sample_api import (
    _create_project,
    _create_delivery,
    _upload,
    _comparison_payload,
)


def sample(client):
    project = _create_project(client)
    delivery = _create_delivery(client, project["id"])
    assert _upload(client, delivery).status_code == 200
    return f"/api/sample-deliveries/{delivery['id']}/comparison"


def test_evidence_edit_creates_new_snapshot_and_preserves_old_content(client):
    endpoint = sample(client)
    payload = _comparison_payload()
    first = client.post(endpoint, json=payload).json()["comparison"]
    response = client.post(
        endpoint,
        json={**payload, "expected_revision": 1, "evidence": "补充测量原始记录 TR-02"},
    )
    assert response.status_code == 200, response.text
    second = response.json()
    assert second["comparison"]["revision"] == 2
    assert second["comparison"]["evidence"] == "补充测量原始记录 TR-02"
    history = {row["revision"]: row["snapshot"] for row in second["versions"]}
    assert history[1]["evidence"] == first["evidence"]
    assert history[2]["evidence"] == second["comparison"]["evidence"]
    assert history[1]["findings"] == first["findings"]
    assert client.get(endpoint).json()["versions"] == second["versions"]


def test_missing_and_old_revision_cannot_replace_new_measurement(client):
    endpoint = sample(client)
    original = _comparison_payload()
    assert client.post(endpoint, json=original).status_code == 200
    changed = {**original, "evidence": "新版测量证据"}
    missing = client.post(endpoint, json=changed)
    assert missing.status_code == 409, missing.text
    updated = client.post(endpoint, json={**changed, "expected_revision": 1})
    assert updated.status_code == 200, updated.text
    stale = client.post(
        endpoint, json={**original, "expected_revision": 1, "evidence": "旧页面提交"}
    )
    assert stale.status_code == 409, stale.text
    assert client.get(endpoint).json()["comparison"]["evidence"] == "新版测量证据"
    assert client.get(endpoint).json()["comparison"]["revision"] == 2


def test_sample_history_migration_retains_current_legacy_row_and_is_immutable(tmp_path):
    # Use the real schema preceding the fix, preserving the one available legacy revision.
    import shutil
    from app.db import MIGRATIONS_DIR

    legacy = tmp_path / "migrations"
    legacy.mkdir()
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name[:3] <= "014":
            shutil.copyfile(path, legacy / path.name)
    connection = connect(tmp_path / "legacy.db")
    try:
        run_migrations(connection, legacy)
        connection.execute(
            "INSERT INTO projects(id,display_code,name,customer,product,created_at,updated_at) VALUES ('p','P01','legacy','c','x','2026-10-22T00:00:00Z','2026-10-22T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO sample_deliveries(id,project_id,display_code,supplier,part_display_code,drawing_display_code,drawing_revision,delivered_at,quantity,created_at,updated_at) VALUES ('s','p','SD-01','s','p','d','A','2026-10-22',1,'now','now')"
        )
        connection.execute(
            "INSERT INTO sample_comparisons(id,project_id,sample_id,display_code,revision,status,mode,overall_result,evidence,created_at,updated_at) VALUES ('c','p','s','CMP-SD-01',7,'draft','manual','incomplete','legacy evidence','now','now')"
        )
        run_migrations(connection)
        rows = connection.execute("SELECT * FROM sample_comparison_versions").fetchall()
        assert len(rows) == 1
        assert rows[0]["revision"] == 7
        assert json.loads(rows[0]["snapshot_json"])["evidence"] == "legacy evidence"
        import pytest

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM sample_comparison_versions")
    finally:
        connection.close()
