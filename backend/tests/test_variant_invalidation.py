import pytest
from app import services
from app.db import connect
from package_scenario import build_ready_project


@pytest.mark.parametrize('key,value,affected', [
    ('engineMaxTorque', '2800', {'输入轴', '一轴齿轮'}),
    ('pto', 'not_required', {'取力器接口', '主箱壳体'}),
])
def test_change_immediately_invalidates_only_related_variant_decisions(design_client, db_path, key, value, affected):
    project_id = build_ready_project(design_client)['project']['id']
    initial = design_client.post(f'/api/projects/{project_id}/variant-analysis', json={'base_display_code': 'JX-12A'}).json()
    requirements = design_client.get(f'/api/projects/{project_id}/requirements').json()
    requirement = next(r for r in requirements if r['parser_key'] == key)
    response = design_client.patch(f"/api/requirements/{requirement['id']}", json={'expected_revision': 1, 'value_text': value})
    assert response.status_code == 200, response.text
    connection = connect(db_path)
    try:
        parts = [dict(r) for r in connection.execute('SELECT * FROM reusable_part_decisions WHERE project_id=?', (project_id,))]
        for part in parts:
            assert part['status'] == ('stale' if part['part_name'] in affected else 'current')
        pto_variant = connection.execute('SELECT * FROM variant_points WHERE id=?', (initial['variants'][0]['id'],)).fetchone()
        assert pto_variant['status'] == ('stale' if key == 'pto' else 'current')
        assert pto_variant['requirement_value'] == initial['variants'][0]['requirement_value']
        assert connection.execute("SELECT rated_input_torque FROM product_bases WHERE display_code='JX-12A'").fetchone()[0] == 2600
    finally:
        connection.close()
    regenerated = design_client.post(f'/api/projects/{project_id}/variant-analysis', json={'base_display_code': 'JX-12A'}).json()
    assert regenerated['variants'] if key == 'engineMaxTorque' else regenerated['stale_variants']


def test_fault_during_part_invalidation_rolls_back_entire_change(design_client, db_path, monkeypatch):
    project_id = build_ready_project(design_client)['project']['id']
    design_client.post(f'/api/projects/{project_id}/variant-analysis', json={'base_display_code': 'JX-12A'})
    before = design_client.get(f'/api/projects/{project_id}/requirements').json()
    engine = next(r for r in before if r['parser_key'] == 'engineMaxTorque')
    original = services._audit
    def fail(*args, **kwargs):
        if kwargs.get('action') == 'part_decision.stale':
            raise RuntimeError('injected part audit failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(services, '_audit', fail)
    with pytest.raises(RuntimeError, match='part audit'):
        design_client.patch(f"/api/requirements/{engine['id']}", json={'expected_revision': 1, 'value_text': '2800'})
    assert design_client.get(f'/api/projects/{project_id}/requirements').json() == before
    connection = connect(db_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM reusable_part_decisions WHERE status='stale'").fetchone()[0] == 0
    finally:
        connection.close()
