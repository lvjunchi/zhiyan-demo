import concurrent.futures
import hashlib
import json
import shutil
import threading
import uuid

from app.db import MIGRATIONS_DIR, connect, run_migrations
from app.main import create_app
from fastapi.testclient import TestClient
from package_scenario import build_ready_project


def test_legacy_database_migration_keeps_ids_and_marks_unknown_history(tmp_path):
    old = tmp_path / "legacy-migrations"
    old.mkdir()
    for migration in MIGRATIONS_DIR.glob("*.sql"):
        if migration.name <= "012_design_validity.sql":
            shutil.copyfile(migration, old / migration.name)
    path = tmp_path / "legacy.db"
    connection = connect(path)
    run_migrations(connection, old)
    project_id, source_id = str(uuid.uuid4()), str(uuid.uuid4())
    connection.execute(
        "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)",
        (
            project_id,
            "LEGACY",
            "保留项目",
            "合成",
            "合成",
            "requirement_parsing",
            "2026-10-19T00:00:00+00:00",
            "2026-10-19T00:00:00+00:00",
        ),
    )
    text = "发动机最大扭矩 2600 N·m"
    connection.execute(
        "INSERT INTO source_documents (id,project_id,display_code,doc_type,version,content_hash,original_text,mode,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            source_id,
            project_id,
            "LEGACY-SOURCE",
            "protocol",
            "V1",
            hashlib.sha256(text.encode()).hexdigest(),
            text,
            "manual",
            "2026-10-19T00:00:00+00:00",
        ),
    )
    from app import services

    services.seed_catalog(connection)
    base_id = connection.execute(
        "SELECT id FROM product_bases WHERE display_code='JX-12A'"
    ).fetchone()[0]
    variant_id = str(uuid.uuid4())
    connection.execute(
        "INSERT INTO variant_points (id,project_id,base_id,display_code,parameter_key,parameter_name,variant_type,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            variant_id,
            project_id,
            base_id,
            "V-01",
            "pto",
            "取力器",
            "new_function",
            "2026-10-19T00:00:00+00:00",
            "2026-10-19T00:00:00+00:00",
        ),
    )
    connection.close()
    with TestClient(create_app(path)) as client:
        sources = client.get(f"/api/projects/{project_id}/source-documents").json()
        assert sources[0]["id"] == source_id and sources[0]["original_file"] is None
        history = client.get(f"/api/engineering-records/variant/{variant_id}").json()
        assert history["current"]["revision"] == 1
        assert "migration_note" in history["versions"][0]["snapshot"]
        assert (
            client.post(
                f"/api/engineering-records/variant/{variant_id}/confirmations",
                json={
                    "expected_revision": 1,
                    "actor": "工程师",
                    "role": "design_engineer",
                    "decision": "confirmed",
                },
            ).status_code
            == 422
        )
        backup = client.get("/api/system/backup").json()
        assert (
            client.post(
                "/api/system/restore-preview", json={"backup": backup}
            ).status_code
            == 200
        )
    with TestClient(create_app(path)) as restarted:
        assert restarted.get("/api/projects").json()[0]["id"] == project_id


def test_concurrent_edit_and_package_generation_freeze_one_revision_set(design_client):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]
    engine = next(
        row
        for row in design_client.get(f"/api/projects/{project_id}/requirements").json()
        if row["parser_key"] == "engineMaxTorque"
    )
    start = threading.Barrier(2)

    def package():
        start.wait()
        return design_client.post(
            f"/api/projects/{project_id}/material-packages",
            json={"include_originals": True, "actor": "工程师"},
        )

    def edit():
        start.wait()
        return design_client.patch(
            f"/api/requirements/{engine['id']}",
            json={
                "expected_revision": engine["current_revision"],
                "value_text": "2800",
            },
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        package_result, edit_result = [
            task.result(timeout=30)
            for task in [pool.submit(package), pool.submit(edit)]
        ]
    assert package_result.status_code == 201, package_result.text
    assert edit_result.status_code == 200, edit_result.text
    detail = package_result.json()
    rows = {row["parser_key"]: row for row in detail["snapshot"]["requirements"]}
    assert (
        rows["engineMaxTorque"]["value_text"]
        == rows["gearboxRatedInputTorque"]["value_text"]
    )
    assert (
        rows["engineMaxTorque"]["current_revision"]
        == rows["gearboxRatedInputTorque"]["current_revision"]
    )
    assert rows["engineMaxTorque"]["value_text"] in {"2600", "2800"}
    frozen = design_client.get(
        f"/api/material-packages/{detail['id']}/download"
    ).content
    assert hashlib.sha256(frozen).hexdigest() == detail["zip_sha256"]
    assert (
        design_client.get(f"/api/material-packages/{detail['id']}/download").content
        == frozen
    )


def test_legacy_gate_snapshot_cannot_be_approved_as_current_contract(
    design_client, db_path
):
    project_id = build_ready_project(design_client)["project"]["id"]
    package = design_client.post(
        f"/api/projects/{project_id}/material-packages",
        json={"include_originals": False, "actor": "工程师"},
    ).json()
    snapshot = package["snapshot"]
    snapshot["schema_version"] = "O13-legacy"
    text = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
    checksum = hashlib.sha256(text.encode()).hexdigest()
    connection = connect(db_path)
    connection.execute(
        "UPDATE material_packages SET snapshot_json=?,snapshot_hash=? WHERE id=?",
        (text, checksum, package["id"]),
    )
    connection.close()
    result = design_client.post(
        f"/api/material-packages/{package['id']}/approvals",
        json={
            "expected_snapshot_hash": checksum,
            "actor": "工程师",
            "role": "design_engineer",
            "comment": "核对",
        },
    )
    assert result.status_code == 422, result.text
    summary = design_client.get(f"/api/projects/{project_id}/material-packages").json()[
        0
    ]
    assert summary["requires_regeneration"] is True


def test_fixed_five_requirement_coverage_follows_80_60_80_100(design_client, db_path):
    from test_test_plan_api import (
        _create_project,
        _create_and_parse,
        _generate_plan,
        _confirm_main_cases,
        _cases_by_code,
        _confirm_case,
        _matrix,
        _run,
    )

    project_id = _create_project(design_client)["id"]
    _create_and_parse(design_client, project_id)
    plan = _generate_plan(design_client, project_id)
    cases = _confirm_main_cases(design_client, plan)
    torque = cases["TC-007"]
    assert (
        _run(
            design_client, torque, load_basis_numeric=2600, backup_coefficient=2.6
        ).json()["run"]["result"]
        == "pass"
    )
    coverage = [_matrix(design_client, project_id)["coverage_percentage"]]
    engine = next(
        row
        for row in design_client.get(f"/api/projects/{project_id}/requirements").json()
        if row["parser_key"] == "engineMaxTorque"
    )
    assert (
        design_client.patch(
            f"/api/requirements/{engine['id']}",
            json={"expected_revision": 1, "value_text": "2800"},
        ).status_code
        == 200
    )
    coverage.append(_matrix(design_client, project_id)["coverage_percentage"])
    revised = design_client.patch(
        f"/api/test-cases/{torque['id']}",
        json={
            "expected_revision": 1,
            "rebase_requirements": True,
            "actor": "试验工程师",
            "role": "test_engineer",
            "comment": "当前基准 2800",
        },
    ).json()
    current = _confirm_case(design_client, revised).json()["case"]
    coverage.append(_matrix(design_client, project_id)["coverage_percentage"])
    assert (
        _run(
            design_client, current, load_basis_numeric=2600, backup_coefficient=2.6
        ).json()["run"]["result"]
        == "invalid"
    )
    assert (
        _run(
            design_client, current, load_basis_numeric=2800, backup_coefficient=2.4
        ).json()["run"]["result"]
        == "fail"
    )
    assert (
        _run(
            design_client, current, load_basis_numeric=2800, backup_coefficient=2.5
        ).json()["run"]["result"]
        == "pass"
    )
    durability = _cases_by_code(plan)["TC-004"]
    clarified = design_client.patch(
        f"/api/test-cases/{durability['id']}",
        json={
            "expected_revision": 1,
            "actor": "试验工程师",
            "role": "test_engineer",
            "acceptance_criteria": "合成补充标准：等效台架循环 1000 h 无失效",
            "comment": "补充判定依据",
        },
    ).json()
    assert _confirm_case(design_client, clarified).status_code == 201
    coverage.append(_matrix(design_client, project_id)["coverage_percentage"])
    assert coverage == [80.0, 60.0, 80.0, 100.0]
    connection = connect(db_path)
    try:
        assert (
            connection.execute(
                "SELECT rated_input_torque FROM product_bases WHERE display_code='JX-12A'"
            ).fetchone()[0]
            == 2600
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM test_runs WHERE case_id=? AND case_revision=1 AND result='pass'",
                (torque["id"],),
            ).fetchone()[0]
            == 1
        )
    finally:
        connection.close()
