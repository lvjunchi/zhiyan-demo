"""Deterministic local fault injection; not a distributed chaos/resilience certification."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from app import main, testing_services, design_services
from app.db import connect
from package_scenario import build_ready_project


@pytest.mark.parametrize('module,name', [
    (testing_services, 'mark_test_cases_stale_for_requirement'),
    (design_services, 'mark_design_stale_for_requirement'),
])
def test_failure_after_downstream_write_rolls_back_all_tables(design_client, monkeypatch, module, name):
    project_id = build_ready_project(design_client)['project']['id']
    engine = next(r for r in design_client.get(f'/api/projects/{project_id}/requirements').json() if r['parser_key'] == 'engineMaxTorque')
    before = design_client.get('/api/system/backup').json()['sha256']
    original = getattr(module, name)
    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('injected failure after downstream write')
    monkeypatch.setattr(module, name, fail_after_write)
    with pytest.raises(RuntimeError, match='after downstream'):
        design_client.patch(f"/api/requirements/{engine['id']}", json={'expected_revision': 1, 'value_text': '2800'})
    assert design_client.get('/api/system/backup').json()['sha256'] == before


def test_two_concurrent_updates_with_same_revision_have_only_one_winner(design_client):
    project_id = build_ready_project(design_client)['project']['id']
    engine = next(r for r in design_client.get(f'/api/projects/{project_id}/requirements').json() if r['parser_key'] == 'engineMaxTorque')
    def update(value):
        return design_client.patch(f"/api/requirements/{engine['id']}", json={'expected_revision': 1, 'value_text': value})
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(update, ['2700', '2800']))
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(r.json() for r in responses if r.status_code == 200)
    current = design_client.get(f'/api/projects/{project_id}/requirements').json()
    derived = next(r for r in current if r['parser_key'] == 'gearboxRatedInputTorque')
    assert derived['value_text'] == winner['value_text']
    assert derived['current_revision'] == 2


def test_database_lock_returns_explicit_retryable_error_and_no_partial_write(design_client, db_path, monkeypatch):
    project_id = build_ready_project(design_client)['project']['id']
    engine = next(r for r in design_client.get(f'/api/projects/{project_id}/requirements').json() if r['parser_key'] == 'engineMaxTorque')
    before = design_client.get('/api/system/backup').json()['sha256']
    def short_timeout(path):
        connection = connect(path)
        connection.execute('PRAGMA busy_timeout=20')
        return connection
    monkeypatch.setattr(main, 'connect', short_timeout)
    writer = connect(db_path)
    try:
        writer.execute('BEGIN IMMEDIATE')
        response = design_client.patch(f"/api/requirements/{engine['id']}", json={'expected_revision': 1, 'value_text': '2800'})
        assert response.status_code == 503, response.text
        assert response.json()['error']['code'] == 'PERSISTENCE_UNAVAILABLE'
    finally:
        writer.rollback(); writer.close()
    assert design_client.get('/api/system/backup').json()['sha256'] == before
