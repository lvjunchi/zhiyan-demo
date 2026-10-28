import hashlib
import io
import json
import zipfile

from package_scenario import (
    SAMPLE_FILE,
    build_ready_project,
    create_and_parse,
    create_project,
)


def _create_package(design_client, project_id, **overrides):
    payload = {"include_originals": False, "actor": "演示用户"}
    payload.update(overrides)
    return design_client.post(
        f"/api/projects/{project_id}/material-packages", json=payload
    )


def _download(design_client, package_id):
    response = design_client.get(f"/api/material-packages/{package_id}/download")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert (
        response.headers["x-content-sha256"]
        == hashlib.sha256(response.content).hexdigest()
    )
    return response


def _archive(response):
    return zipfile.ZipFile(io.BytesIO(response.content))


def _manifest(archive):
    return json.loads(archive.read("manifest.json").decode("utf-8"))


def _assert_manifest_hashes(archive, manifest):
    file_entries = {entry["path"]: entry for entry in manifest["files"]}
    for path, entry in file_entries.items():
        content = archive.read(path)
        assert entry["sha256"] == hashlib.sha256(content).hexdigest()
        assert entry["size_bytes"] == len(content)
    assert "manifest.json" not in file_entries


def test_incomplete_project_exports_draft_with_blockers_but_cannot_be_approved(
    design_client,
):
    project = create_project(design_client)
    create_and_parse(design_client, project["id"])

    response = _create_package(design_client, project["id"])
    assert response.status_code == 201, response.text
    package = response.json()
    assert package["status"] == "draft"
    assert package["gate"]["status"] == "blocked"
    codes = {blocker["code"] for blocker in package["gate"]["blockers"]}
    assert {
        "TEST_PLAN_MISSING",
        "DESIGN_REVIEW_MISSING",
        "DFMEA_MISSING",
        "COVERAGE_INCOMPLETE",
        "CONSISTENCY_CHECK_MISSING",
    } <= codes

    archive = _archive(_download(design_client, package["id"]))
    assert "manifest.json" in archive.namelist()
    assert "report.html" in archive.namelist()
    manifest = _manifest(archive)
    assert manifest["package"]["status"] == "draft"
    assert manifest["gate"]["status"] == "blocked"
    assert manifest["gate"]["blockers"]
    report = archive.read("report.html").decode("utf-8")
    assert "门径评审材料包" in report
    assert "缺口" in report
    assert "未满足" in report
    assert not any(name.startswith("originals/") for name in archive.namelist())

    blocked = design_client.post(
        f"/api/material-packages/{package['id']}/approvals",
        json={
            "expected_snapshot_hash": package["snapshot_hash"],
            "actor": "演示负责人",
            "role": "演示角色",
            "comment": "尝试审批草稿包",
        },
    )
    assert blocked.status_code == 422, blocked.text
    assert "门禁" in blocked.json()["error"]["message"]


def test_ready_package_contains_verified_zip_and_stays_frozen_after_edits(
    design_client,
):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]

    response = _create_package(design_client, project_id)
    assert response.status_code == 201, response.text
    package = response.json()
    assert package["status"] == "ready_to_submit"
    assert package["gate"]["status"] == "ready"
    assert package["gate"]["blockers"] == []

    archive_response = _download(design_client, package["id"])
    archive = _archive(archive_response)
    required_files = {
        "manifest.json",
        "report.html",
        "requirements.csv",
        "design_review.csv",
        "dfmea.csv",
        "test_plan.csv",
        "traceability.csv",
        "conflicts.csv",
        "coordination.csv",
        "coordination_records.csv",
        "audit_log.csv",
        "issues.csv",
        "evidence_index.csv",
    }
    assert required_files <= set(archive.namelist())
    manifest = _manifest(archive)
    _assert_manifest_hashes(archive, manifest)

    assert manifest["schema_version"] == "O13-1.2"
    assert manifest["project"]["name"] == "法士特—陕汽定制项目试点"
    assert manifest["package"]["status"] == "ready_to_submit"
    assert manifest["package"]["snapshot_hash"] == package["snapshot_hash"]
    assert manifest["gate"]["status"] == "ready"
    assert manifest["package"]["include_originals"] is False
    requirements = {
        item["display_code"]: item
        for item in manifest["object_versions"]["requirements"]
    }
    assert requirements["REQ-P01-C-002"]["revision"] == 1
    assert requirements["REQ-P01-B-003"]["revision"] == 1
    assert manifest["object_versions"]["test_plan"]["status"] == "confirmed"
    assert manifest["object_versions"]["design_review"]["status"] == ("confirmed")
    assert manifest["object_versions"]["dfmea"]["status"] == "confirmed"
    assert manifest["object_versions"]["consistency_check"]["status"] == ("confirmed")
    assert len(manifest["object_versions"]["test_cases"]) == 5
    assert all(
        case["review_status"] == "confirmed"
        for case in manifest["object_versions"]["test_cases"]
    )
    assert (
        manifest["object_versions"]["coordination_metric_runs"][0]["risk_level"]
        == "high"
    )
    assert (
        manifest["object_versions"]["coordination_metric_runs"][0]["accepted"] is True
    )

    report = archive.read("report.html").decode("utf-8")
    assert '<meta charset="utf-8">' in report
    assert "法士特—陕汽定制项目试点" in report
    assert "门径评审材料包" in report
    assert "追溯矩阵" in report
    assert "变速器最低额定输入扭矩" in report
    assert "5 / 5" in report
    assert "可提交" in report
    assert "http://" not in report
    assert "https://" not in report

    requirements_csv = archive.read("requirements.csv").decode("utf-8-sig")
    assert "REQ-P01-C-002" in requirements_csv
    assert "变速器最低额定输入扭矩" in requirements_csv
    traceability_csv = archive.read("traceability.csv").decode("utf-8-sig")
    assert "gearboxRatedInputTorque" in traceability_csv
    assert "pass" in traceability_csv
    test_plan_csv = archive.read("test_plan.csv").decode("utf-8-sig")
    assert "TC-007" in test_plan_csv
    assert "2800" not in test_plan_csv
    assert "2600" in test_plan_csv
    audit_csv = archive.read("audit_log.csv").decode("utf-8-sig")
    assert "requirement.confirmed" in audit_csv
    assert "material_package" not in audit_csv
    evidence_csv = archive.read("evidence_index.csv").decode("utf-8-sig")
    assert "manifest.json" not in evidence_csv
    assert "report.html" in evidence_csv

    engine = next(
        item
        for item in scenario["requirements"]
        if item["display_code"] == "REQ-P01-B-003"
    )
    update = design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={
            "expected_revision": engine["current_revision"],
            "value_text": "2800",
        },
    )
    assert update.status_code == 200, update.text

    frozen = _download(design_client, package["id"])
    assert frozen.content == archive_response.content
    assert frozen.headers["x-content-sha256"] == package["zip_sha256"]

    approved = design_client.post(
        f"/api/material-packages/{package['id']}/approvals",
        json={
            "expected_snapshot_hash": package["snapshot_hash"],
            "actor": "演示负责人",
            "role": "演示角色",
            "comment": "人工核对冻结材料包后批准",
        },
    )
    assert approved.status_code == 201, approved.text
    approved_body = approved.json()
    assert approved_body["status"] == "human_approved"
    assert approved_body["frozen_at"] is not None
    assert approved_body["approval"]["actor"] == "演示负责人"
    assert approved_body["approval"]["snapshot_hash"] == (package["snapshot_hash"])

    duplicate = design_client.post(
        f"/api/material-packages/{package['id']}/approvals",
        json={
            "expected_snapshot_hash": package["snapshot_hash"],
            "actor": "演示负责人",
            "role": "演示角色",
            "comment": "重复审批",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["error"]["code"] == "PACKAGE_STATE_CONFLICT"

    still_frozen = _download(design_client, package["id"])
    assert still_frozen.content == archive_response.content


def test_originals_are_opt_in_and_approval_requires_the_observed_hash(
    design_client,
):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]

    without_originals = _create_package(design_client, project_id).json()
    without_archive = _archive(_download(design_client, without_originals["id"]))
    assert not any(name.startswith("originals/") for name in without_archive.namelist())

    with_originals = _create_package(design_client, project_id, include_originals=True)
    assert with_originals.status_code == 201, with_originals.text
    package = with_originals.json()
    archive = _archive(_download(design_client, package["id"]))
    names = set(archive.namelist())
    source_name = "originals/source_documents/DOC-P01-001_V1.txt"
    sample_name = "originals/samples/SD-01/sample-drawing.txt"
    assert source_name in names
    assert sample_name in names
    assert archive.read(sample_name) == SAMPLE_FILE
    manifest = _manifest(archive)
    indexed = {entry["path"]: entry for entry in manifest["files"]}
    assert (
        indexed[source_name]["sha256"]
        == hashlib.sha256(archive.read(source_name)).hexdigest()
    )
    assert indexed[sample_name]["sha256"] == hashlib.sha256(SAMPLE_FILE).hexdigest()

    wrong_hash = design_client.post(
        f"/api/material-packages/{package['id']}/approvals",
        json={
            "expected_snapshot_hash": "0" * 64,
            "actor": "演示负责人",
            "role": "演示角色",
            "comment": "旧快照",
        },
    )
    assert wrong_hash.status_code == 409, wrong_hash.text
    assert wrong_hash.json()["error"]["code"] == "VERSION_CONFLICT"

    approved = design_client.post(
        f"/api/material-packages/{package['id']}/approvals",
        json={
            "expected_snapshot_hash": package["snapshot_hash"],
            "actor": "演示负责人",
            "role": "演示角色",
            "comment": "人工核对原件后批准",
        },
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["approval"]["snapshot_hash"] == (package["snapshot_hash"])

    missing = design_client.get("/api/material-packages/unknown-package")
    assert missing.status_code == 404
    missing_download = design_client.get(
        "/api/material-packages/unknown-package/download"
    )
    assert missing_download.status_code == 404


def test_unaccepted_coordination_high_risk_blocks_until_explicit_acceptance(
    design_client,
):
    scenario = build_ready_project(design_client, accept_coordination_risk=False)
    project_id = scenario["project"]["id"]

    blocked = _create_package(design_client, project_id)
    assert blocked.status_code == 201, blocked.text
    blocked_package = blocked.json()
    assert blocked_package["status"] == "draft"
    codes = {blocker["code"] for blocker in blocked_package["gate"]["blockers"]}
    assert "COORDINATION_RISK_UNACCEPTED" in codes

    acceptance = design_client.post(
        (
            "/api/coordination-topics/"
            f"{scenario['coordination']['topic']['id']}/risk-acceptances"
        ),
        json={
            "metric_run_id": scenario["coordination"]["metric"]["metric_run"]["id"],
            "actor": "演示负责人",
            "role": "演示角色",
            "note": "明确接受高风险并保留跟踪理由",
        },
    )
    assert acceptance.status_code == 201, acceptance.text

    accepted = _create_package(design_client, project_id)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["status"] == "ready_to_submit"

    historical = design_client.post(
        (
            "/api/coordination-topics/"
            f"{scenario['coordination']['topic']['id']}/risk-acceptances"
        ),
        json={
            "metric_run_id": "unknown-run",
            "actor": "演示负责人",
            "role": "演示角色",
            "note": "错误的指标版本",
        },
    )
    assert historical.status_code == 422


def test_blocking_conflict_and_stale_case_keep_new_package_in_draft(
    design_client,
):
    scenario = build_ready_project(design_client)
    project_id = scenario["project"]["id"]
    engine = next(
        item
        for item in scenario["requirements"]
        if item["display_code"] == "REQ-P01-B-003"
    )

    update = design_client.patch(
        f"/api/requirements/{engine['id']}",
        json={
            "expected_revision": engine["current_revision"],
            "value_text": "2800",
        },
    )
    assert update.status_code == 200, update.text

    current_requirements = design_client.get(
        f"/api/projects/{project_id}/requirements"
    ).json()
    derived = next(
        r for r in current_requirements if r["parser_key"] == "gearboxRatedInputTorque"
    )
    assert derived["value_text"] == "2800" and derived["current_revision"] == 2
    # A separate erroneous manual override exercises the conflict/repair branch.
    override = design_client.patch(
        f"/api/requirements/{derived['id']}",
        json={"expected_revision": 2, "value_text": "2600"},
    )
    assert override.status_code == 200, override.text

    check = design_client.post(f"/api/projects/{project_id}/consistency-checks")
    assert check.status_code == 200, check.text
    check_body = check.json()
    blocking = [
        conflict
        for conflict in check_body["conflicts"]
        if conflict["severity"] == "blocking" and conflict["status"] == "open"
    ]
    assert blocking
    confirmed = design_client.post(
        ("/api/consistency-checks/" f"{check_body['check']['id']}/confirmations"),
        json={
            "expected_revision": check_body["check"]["revision"],
            "actor": "演示工程师甲",
            "role": "演示角色",
            "decision": "confirmed",
            "comment": "确认变更后的冲突仍待处理",
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    response = _create_package(design_client, project_id)
    assert response.status_code == 201, response.text
    package = response.json()
    assert package["status"] == "draft"
    codes = {blocker["code"] for blocker in package["gate"]["blockers"]}
    assert "BLOCKING_CONFLICT_OPEN" in codes
    assert "COVERAGE_INCOMPLETE" in codes
    assert "VERIFICATION_NOT_PASSED" in codes

    archive = _archive(_download(design_client, package["id"]))
    manifest = _manifest(archive)
    assert manifest["gate"]["status"] == "blocked"
    assert manifest["object_versions"]["test_plan"]["status"] == "confirmed"
    test_case_codes = {
        case["display_code"]: case for case in manifest["object_versions"]["test_cases"]
    }
    assert test_case_codes["TC-007"]["validity"] == "stale"
    conflicts_csv = archive.read("conflicts.csv").decode("utf-8-sig")
    assert blocking[0]["display_code"] in conflicts_csv
    assert "blocking" in conflicts_csv
