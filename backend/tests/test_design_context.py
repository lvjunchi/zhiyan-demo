from test_engineering_versions import _setup_scenario
from test_variant_api import _run_variant


def test_design_context_uses_latest_persisted_analysis_without_writes(catalog_client):
    client = catalog_client
    pid, _ = _setup_scenario(client)
    assert _run_variant(client, pid, "JX-12B").status_code == 200
    before = client.get("/api/system/backup").json()["sha256"]
    response = client.get(f"/api/projects/{pid}/design-context")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "base_display_code": "JX-12B",
        "source": "variant_analysis",
    }
    assert client.get("/api/system/backup").json()["sha256"] == before
    assert client.get("/api/projects/missing/design-context").status_code == 404
