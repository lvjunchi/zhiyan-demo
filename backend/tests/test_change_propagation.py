import pytest

from app import services
from package_scenario import build_ready_project


def test_engine_change_updates_derived_requirement_and_invalidates_design(design_client):
    project_id = build_ready_project(design_client)["project"]["id"]
    def requirements():
        return {r["parser_key"]: r for r in design_client.get(f"/api/projects/{project_id}/requirements").json()}
    before = requirements()
    engine = before["engineMaxTorque"]
    response = design_client.patch(f"/api/requirements/{engine['id']}", json={"expected_revision": 1, "value_text": "2800"})
    assert response.status_code == 200, response.text
    after = requirements()
    assert after["gearboxRatedInputTorque"]["value_text"] == "2800"
    assert after["gearboxRatedInputTorque"]["current_revision"] == 2
    assert after["gearboxRatedInputTorque"]["review_status"] == "draft"
    assert after["gearCount"] == before["gearCount"]
    for route, key in [("design-review", "review"), ("dfmea", "fmea")]:
        artifact = design_client.get(f"/api/projects/{project_id}/{route}").json()
        assert artifact[key]["validity"] == "stale"
        assert artifact["needs_reconfirmation"] is True
        assert artifact["confirmations"]
    matrix = design_client.get(f"/api/projects/{project_id}/traceability-matrix").json()
    assert matrix["covered_count"] == 4
    audit = design_client.get(f"/api/projects/{project_id}/audit-events").json()
    assert any(e["object_id"] == after["gearboxRatedInputTorque"]["id"] and e["object_revision"] == 2 for e in audit)
    check = design_client.post(f"/api/projects/{project_id}/consistency-checks").json()
    stale_types = {c["object_type"] for c in check["conflicts"] if c["conflict_type"] == "version"}
    assert {"design_review", "fmea_document"} <= stale_types


def test_derived_audit_failure_rolls_back_source_derived_and_design(design_client, monkeypatch):
    project_id = build_ready_project(design_client)["project"]["id"]
    before = design_client.get(f"/api/projects/{project_id}/requirements").json()
    engine = next(r for r in before if r["parser_key"] == "engineMaxTorque")
    derived = next(r for r in before if r["parser_key"] == "gearboxRatedInputTorque")
    original = services._audit
    def fail_derived(*args, **kwargs):
        if kwargs.get("object_id") == derived["id"] and kwargs.get("object_revision") == 2:
            raise RuntimeError("injected derived audit failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(services, "_audit", fail_derived)
    with pytest.raises(RuntimeError, match="injected derived"):
        design_client.patch(f"/api/requirements/{engine['id']}", json={"expected_revision": 1, "value_text": "2800"})
    assert design_client.get(f"/api/projects/{project_id}/requirements").json() == before
    assert design_client.get(f"/api/projects/{project_id}/dfmea").json()["needs_reconfirmation"] is False
