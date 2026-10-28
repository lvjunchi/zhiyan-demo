import pytest
from test_engineering_versions import _setup_scenario


def payload(rows):
    return {
        "actor": "批量演示工程师",
        "role": "design_engineer",
        "items": [
            {
                "kind": row["kind"],
                "object_id": row["id"],
                "expected_revision": row["revision"],
            }
            for row in rows
        ],
    }


def test_batch_confirms_explicit_versions_and_keeps_each_audit(catalog_client):
    client = catalog_client
    pid, _ = _setup_scenario(client)
    rows = client.get(f"/api/projects/{pid}/engineering-records").json()
    variants = [row for row in rows if row["kind"] == "variant"]
    response = client.post(
        f"/api/projects/{pid}/engineering-confirmations", json=payload(variants)
    )
    assert response.status_code == 201, response.text
    assert response.json()["confirmed_count"] == len(variants)
    for row in variants:
        detail = client.get(f"/api/engineering-records/variant/{row['id']}").json()
        assert detail["current"]["review_status"] == "confirmed"
        assert detail["confirmations"][-1]["object_revision"] == row["revision"]
    before = client.get("/api/system/backup").json()["sha256"]
    assert (
        client.post(
            f"/api/projects/{pid}/engineering-confirmations", json=payload(variants)
        ).status_code
        == 409
    )
    assert client.get("/api/system/backup").json()["sha256"] == before


def test_batch_orders_variant_prerequisites_before_selected_part(catalog_client):
    client = catalog_client
    pid, _ = _setup_scenario(client)
    choices = client.get(f"/api/projects/{pid}/part-candidates").json()
    group = next(
        item for item in choices["parts"] if item["record"]["part_name"] == "取力器接口"
    )
    candidate = next(item for item in group["candidates"] if item["fit"] == "pass")
    selected = client.post(
        f"/api/engineering-records/part/{group['record']['id']}/selection",
        json={
            "actor": "批量演示工程师",
            "role": "design_engineer",
            "expected_revision": group["record"]["revision"],
            "candidate_id": candidate["id"],
            "comment": "合成候选依据",
        },
    )
    assert selected.status_code == 200, selected.text
    rows = client.get(f"/api/projects/{pid}/engineering-records").json()
    scope = [next(row for row in rows if row["id"] == group["record"]["id"])] + [
        row for row in rows if row["kind"] == "variant"
    ]
    response = client.post(
        f"/api/projects/{pid}/engineering-confirmations", json=payload(scope)
    )
    assert response.status_code == 201, response.text
    assert response.json()["confirmed_count"] == len(scope)
    assert (
        client.get(f"/api/engineering-records/part/{group['record']['id']}").json()[
            "current"
        ]["review_status"]
        == "confirmed"
    )


def test_batch_confirms_all_original_engineering_decisions_without_selecting_candidates(
    catalog_client,
):
    client = catalog_client
    pid, _ = _setup_scenario(client)
    rows = client.get(f"/api/projects/{pid}/engineering-records").json()
    parts = [row for row in rows if row["kind"] == "part"]
    assert len(parts) >= 7
    original_numbers = {row["id"]: row["part_number"] for row in parts}
    response = client.post(
        f"/api/projects/{pid}/engineering-confirmations",
        json=payload(list(reversed(rows))),
    )
    assert response.status_code == 201, response.text
    assert response.json()["confirmed_count"] == len(rows)
    for row in rows:
        detail = client.get(
            f"/api/engineering-records/{row['kind']}/{row['id']}"
        ).json()
        assert detail["current"]["review_status"] == "confirmed"
        assert detail["confirmations"][-1]["object_revision"] == row["revision"]
    choices = client.get(f"/api/projects/{pid}/part-candidates").json()
    for group in choices["parts"]:
        assert group["record"]["part_number"] == original_numbers[group["record"]["id"]]
        assert group["selected_candidate_id"] is None
        assert group["selection_state"] == "unselected"


@pytest.mark.parametrize(
    "problem", ["revision", "missing_upstream", "cross_project", "duplicate"]
)
def test_batch_failure_never_partially_confirms(catalog_client, problem):
    client = catalog_client
    pid, _ = _setup_scenario(client)
    rows = client.get(f"/api/projects/{pid}/engineering-records").json()
    variants = [row for row in rows if row["kind"] == "variant"]
    body = payload(variants)
    url = f"/api/projects/{pid}/engineering-confirmations"
    if problem == "revision":
        body["items"][-1]["expected_revision"] += 1
    elif problem == "missing_upstream":
        part = next(
            row
            for row in rows
            if row["kind"] == "part"
            and any(
                dep["object_type"] == "variant" for dep in row["dependency_versions"]
            )
        )
        body = payload([part])
    elif problem == "cross_project":
        other = client.post(
            "/api/projects",
            json={
                "display_code": "P-BATCH-OTHER",
                "name": "其他项目",
                "customer": "合成客户",
                "product": "变速器",
            },
        ).json()
        url = f"/api/projects/{other['id']}/engineering-confirmations"
    else:
        body["items"].append(body["items"][0])
    before = client.get("/api/system/backup").json()["sha256"]
    response = client.post(url, json=body)
    assert response.status_code in (409, 422), response.text
    assert client.get("/api/system/backup").json()["sha256"] == before
