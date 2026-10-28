import pytest

from app import engineering_versions
from test_engineering_versions import _setup_scenario
from test_part_selection import selection
from test_test_plan_api import _confirm_case, _run


def setup_confirmed(client):
    pid, _ = _setup_scenario(client)
    choices = client.get(f"/api/projects/{pid}/part-candidates").json()["parts"]
    group = next(row for row in choices if row["record"]["part_name"] == "输入轴")
    candidate = next(row for row in group["candidates"] if row["fit"] == "pass")
    part = selection(client, group["record"], candidate).json()
    endpoint = f"/api/engineering-records/part/{part['id']}/confirmations"
    payload = dict(
        expected_revision=part["revision"],
        actor="核对工程师",
        role="design_engineer",
        decision="confirmed",
        comment="",
    )
    confirmed = client.post(endpoint, json=payload)
    assert confirmed.status_code == 201, confirmed.text
    return (
        pid,
        part,
        endpoint,
        {**payload, "decision": "rejected", "comment": "安装接口与实物不符"},
        confirmed.json(),
    )


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_withdrawal_accepts_optional_reason_and_keeps_audit(catalog_client, reason):
    client = catalog_client
    pid, part, endpoint, payload, approval = setup_confirmed(client)
    if reason is None:
        payload.pop("comment")
    else:
        payload["comment"] = reason
    response = client.post(endpoint, json=payload)
    assert response.status_code == 201, response.text
    detail = client.get(f"/api/engineering-records/part/{part['id']}").json()
    assert detail["confirmations"][0] == approval
    assert detail["confirmations"][-1]["comment"] == (reason or "")
    assert detail["current"]["review_status"] == "rejected"
    events = client.get(f"/api/projects/{pid}/audit-events").json()
    withdrawal = next(
        row for row in events if row["action"] == "part.confirmation_withdrawn"
    )
    assert withdrawal["comment"] == ""
    assert withdrawal["before"]["confirmation_id"] == approval["id"]
    assert withdrawal["after"]["rejection_id"] == response.json()["id"]


def test_withdrawal_keeps_approval_and_invalidates_dependents(catalog_client):
    client = catalog_client
    pid, part, endpoint, payload, confirmation = setup_confirmed(client)
    for path in ["design-review", "dfmea"]:
        response = client.post(
            f"/api/projects/{pid}/{path}", json={"base_display_code": "JX-12A"}
        )
        assert response.status_code == 200, response.text
    plan = client.post(f"/api/projects/{pid}/test-plan").json()
    case = next(row for row in plan["cases"] if row["case_key"] == "assemblyWeight")
    assert case["fmea_refs"]
    assert _confirm_case(client, case).status_code == 201
    run = _run(client, case, manual_result="pass")
    assert run.status_code == 200, run.text
    before = client.get(f"/api/engineering-records/part/{part['id']}").json()
    check = client.post(f"/api/projects/{pid}/consistency-checks")
    assert check.status_code in (200, 201), check.text
    response = client.post(endpoint, json=payload)
    assert response.status_code == 201, response.text
    assert (
        client.get(f"/api/projects/{pid}/consistency-checks/latest").json()["check"][
            "validity"
        ]
        == "stale"
    )
    detail = client.get(f"/api/engineering-records/part/{part['id']}").json()
    assert detail["versions"] == before["versions"]
    assert detail["confirmations"][0] == confirmation
    assert len(detail["confirmations"]) == 2
    assert detail["confirmations"][-1]["decision"] == "rejected"
    assert detail["current"]["review_status"] == "rejected"
    assert detail["current"]["revision"] == part["revision"]
    events = client.get(f"/api/projects/{pid}/audit-events").json()
    withdrawn = next(
        row for row in events if row["action"] == "part.confirmation_withdrawn"
    )
    assert withdrawn["before"]["confirmation_id"] == confirmation["id"]
    assert withdrawn["after"]["rejection_id"] == response.json()["id"]
    assert withdrawn["comment"] == payload["comment"]
    for path, key in [("design-review", "review"), ("dfmea", "fmea")]:
        artifact = client.get(f"/api/projects/{pid}/{path}").json()[key]
        assert artifact["validity"] == "stale"
        rebuilt = client.post(
            f"/api/projects/{pid}/{path}", json={"base_display_code": "JX-12A"}
        ).json()[key]
        assert rebuilt["revision"] == artifact["revision"] + 1
        assert rebuilt["status"] == "draft"
    current = client.get(f"/api/projects/{pid}/test-plan").json()
    old_case = next(row for row in current["cases"] if row["id"] == case["id"])
    assert old_case["validity"] == "stale"
    assert old_case["runs"][-1]["id"] == run.json()["run"]["id"]
    assert (
        next(row for row in current["cases"] if row["case_key"] == "gearCount")[
            "validity"
        ]
        == "current"
    )
    saved = client.get("/api/system/backup").json()
    assert client.post(endpoint, json=payload).status_code == 409
    assert client.get("/api/system/backup").json()["sha256"] == saved["sha256"]
    assert (
        client.post("/api/system/restore-preview", json={"backup": saved}).status_code
        == 200
    )


def test_withdrawal_rolls_back_on_propagation_failure(catalog_client, monkeypatch):
    _, _, endpoint, payload, _ = setup_confirmed(catalog_client)
    before = catalog_client.get("/api/system/backup").json()["sha256"]

    def fail(*args, **kwargs):
        raise RuntimeError("injected withdrawal propagation failure")

    monkeypatch.setattr(
        engineering_versions, "invalidate_dependents", fail, raising=False
    )
    with pytest.raises(RuntimeError, match="withdrawal propagation"):
        catalog_client.post(endpoint, json=payload)
    assert catalog_client.get("/api/system/backup").json()["sha256"] == before


def test_withdrawal_propagates_even_if_fmea_document_was_already_stale(catalog_client):
    client = catalog_client
    pid, part, endpoint, payload, _ = setup_confirmed(client)
    response = client.post(
        f"/api/projects/{pid}/dfmea", json={"base_display_code": "JX-12A"}
    )
    assert response.status_code == 200, response.text
    client.post(f"/api/projects/{pid}/test-plan")
    groups = client.get(f"/api/projects/{pid}/part-candidates").json()["parts"]
    other = next(row for row in groups if row["record"]["part_name"] == "齿轮组")
    chosen = selection(
        client,
        other["record"],
        next(row for row in other["candidates"] if row["fit"] == "pass"),
    )
    assert chosen.status_code == 200, chosen.text
    assert (
        client.get(f"/api/projects/{pid}/dfmea").json()["fmea"]["validity"] == "stale"
    )
    assert client.post(endpoint, json=payload).status_code == 201
    cases = client.get(f"/api/projects/{pid}/test-plan").json()["cases"]
    assert all(row["validity"] == "stale" for row in cases if row["fmea_refs"])
    assert all(row["validity"] == "current" for row in cases if not row["fmea_refs"])
