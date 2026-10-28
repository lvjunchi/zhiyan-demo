import base64
import copy
import hashlib
import sqlite3
import pytest
from pathlib import Path

from app import backup_services
from app.main import create_app
from fastapi.testclient import TestClient
from package_scenario import build_ready_project


def _backup(client):
    response = client.get('/api/system/backup')
    assert response.status_code == 200, response.text
    return response.json()


def _restore(client, backup, state_hash):
    return client.post('/api/system/restore', json={'backup': backup, 'expected_state_hash': state_hash, 'actor': '本地工程师', 'role': 'design_engineer'})


def test_backup_restore_preserves_ids_versions_files_and_survives_restart(design_client, db_path):
    project = build_ready_project(design_client)['project']
    old_requirements = design_client.get(f"/api/projects/{project['id']}/requirements").json()
    backup = _backup(design_client)
    assert backup['format'] == 'zhiyan.sqlite-backup.v1'
    assert backup['counts']['sample_delivery_files'] > 0
    assert hashlib.sha256(base64.b64decode(backup['database_base64'])).hexdigest() == backup['sha256']
    original_bytes = Path(db_path).read_bytes()
    added = design_client.post('/api/projects', json={'display_code': 'EXTRA', 'name': '恢复前新增', 'customer': '合成客户', 'product': '合成设备'})
    assert added.status_code == 201
    current = _backup(design_client)
    preview = design_client.post('/api/system/restore-preview', json={'backup': backup})
    assert preview.status_code == 200, preview.text
    assert preview.json()['counts'] == backup['counts']
    assert len(design_client.get('/api/projects').json()) == 2
    restored = _restore(design_client, backup, current['sha256'])
    assert restored.status_code == 200, restored.text
    assert Path(design_client.app.state.db_path) != db_path
    assert Path(db_path).exists() and original_bytes
    retained = sqlite3.connect(db_path)
    try:
        assert retained.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 2
    finally:
        retained.close()
    assert design_client.get(f"/api/projects/{project['id']}/requirements").json() == old_requirements
    assert len(design_client.get('/api/projects').json()) == 1
    with TestClient(create_app(db_path)) as restarted:
        assert restarted.get('/api/projects').json()[0]['id'] == project['id']
        assert restarted.get(f"/api/projects/{project['id']}/requirements").json() == old_requirements
        assert _backup(restarted)['counts']['sample_delivery_files'] == backup['counts']['sample_delivery_files']


def test_restore_rejects_corrupt_payload_schema_and_intervening_changes(design_client):
    build_ready_project(design_client)
    backup = _backup(design_client)
    corrupt = {**backup, 'sha256': '0' * 64}
    assert _restore(design_client, corrupt, backup['sha256']).status_code == 422
    stage = sqlite3.connect(':memory:'); stage.deserialize(base64.b64decode(backup['database_base64']))
    stage.execute('CREATE TABLE unexpected(data TEXT)'); stage.commit()
    blob = stage.serialize(); stage.close()
    modified = {**backup, 'sha256': hashlib.sha256(blob).hexdigest(), 'database_base64': base64.b64encode(blob).decode()}
    assert _restore(design_client, modified, backup['sha256']).status_code == 422
    design_client.post('/api/projects', json={'display_code': 'EXTRA', 'name': '新项目', 'customer': '合成', 'product': '合成'})
    rejected = _restore(design_client, backup, backup['sha256'])
    assert rejected.status_code == 409, rejected.text
    assert len(design_client.get('/api/projects').json()) == 2


def test_restore_fault_during_activation_leaves_current_data_and_restart_unchanged(design_client, db_path, monkeypatch):
    build_ready_project(design_client)
    backup = _backup(design_client)
    before = design_client.get('/api/projects').json()
    def fail(*args, **kwargs):
        raise OSError('injected disk write failure')
    monkeypatch.setattr(backup_services, '_activate_database', fail)
    response = _restore(design_client, backup, backup['sha256'])
    assert response.status_code == 500, response.text
    assert response.json()['error']['code'] == 'PERSISTENCE_ERROR'
    assert design_client.get('/api/projects').json() == before
    with TestClient(create_app(db_path)) as restarted:
        assert restarted.get('/api/projects').json() == before


def test_restore_rejects_tampered_numeric_data(design_client):
    build_ready_project(design_client)
    backup = _backup(design_client)
    stage = sqlite3.connect(':memory:'); stage.deserialize(base64.b64decode(backup['database_base64']))
    stage.execute("UPDATE requirements SET value_text='Infinity' WHERE parser_key='engineMaxTorque'"); stage.commit()
    blob = stage.serialize(); stage.close()
    corrupt = copy.deepcopy(backup)
    corrupt.update(database_base64=base64.b64encode(blob).decode(), sha256=hashlib.sha256(blob).hexdigest())
    response = _restore(design_client, corrupt, backup['sha256'])
    assert response.status_code == 422, response.text
    assert _backup(design_client)['sha256'] == backup['sha256']


@pytest.mark.parametrize('tamper', [
    "UPDATE sample_delivery_files SET content=X'636f7272757074'",
    "UPDATE source_documents SET original_text='corrupt text'",
    "UPDATE material_packages SET snapshot_json='{}'",
    "UPDATE material_packages SET zip_content=X'636f7272757074'",
])
def test_restore_rejects_corrupted_archived_bytes_even_with_new_image_hash(design_client, tamper):
    project = build_ready_project(design_client)['project']
    package = design_client.post(f"/api/projects/{project['id']}/material-packages", json={'include_originals': True, 'actor': '本地工程师'})
    assert package.status_code == 201, package.text
    backup = _backup(design_client)
    stage = sqlite3.connect(':memory:'); stage.deserialize(base64.b64decode(backup['database_base64']))
    changed = stage.execute(tamper)
    assert changed.rowcount > 0
    stage.commit()
    blob = stage.serialize(); stage.close()
    corrupt = {**backup, 'database_base64': base64.b64encode(blob).decode(), 'sha256': hashlib.sha256(blob).hexdigest()}
    response = _restore(design_client, corrupt, backup['sha256'])
    assert response.status_code == 422, response.text
    assert _backup(design_client)['sha256'] == backup['sha256']
