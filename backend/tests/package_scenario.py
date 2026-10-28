"""Reusable synthetic project factory for M4-02 material package tests."""

CONFIRMATION = {
    "actor": "演示工程师甲",
    "role": "演示角色",
    "decision": "confirmed",
    "comment": "合成演示数据确认",
}

FIXED_PROTOCOL = """3.1 整车配置：6×4 牵引车，整车总质量 49 t；发动机最大扭矩 2600 N·m，最大功率 397 kW / 1900 r/min。
4.2 变速器要求：12 档 AMT，一档速比不低于 14.5，最高档为直接档或超速档；额定输入扭矩不低于发动机最大扭矩；需配置取力器接口。
4.5 安装：总成重量不超过 300 kg，离合器壳接口按主机厂图纸 SX-DRW-0215 执行。
7.1 耐久：台架耐久按双方商定标准执行。"""

DISPLAY_CODE_MAP = {
    "engineMaxTorque": "REQ-P01-B-003",
    "gearboxRatedInputTorque": "REQ-P01-C-002",
    "gearCount": "REQ-P01-C-001",
    "transmissionType": "REQ-P01-C-001-T",
    "pto": "REQ-P01-C-006",
    "assemblyWeight": "REQ-P01-D-002",
    "durability": "REQ-P01-F-001",
}

SAMPLE_DELIVERY = {
    "display_code": "SD-01",
    "supplier": "S-02（合成供应商）",
    "part_display_code": "P-1001",
    "drawing_display_code": "SX-DRW-0215",
    "drawing_revision": "B",
    "delivered_at": "2026-10-19",
    "quantity": 2,
    "notes": "合成样件，仅用于本地演示",
    "drawing_parameters": [
        {
            "parameter_key": "holePosition",
            "parameter_name": "孔位",
            "expected_value": 120.0,
            "tolerance": 0.5,
            "unit": "mm",
            "source_note": "图纸 SX-DRW-0215 第 2 区域标注",
        },
        {
            "parameter_key": "shaftDiameter",
            "parameter_name": "轴径",
            "expected_value": 45.0,
            "tolerance": 0.02,
            "unit": "mm",
            "source_note": "图纸 SX-DRW-0215 第 3 区域标注",
        },
    ],
}

SAMPLE_FILE = b"sample drawing payload: SX-DRW-0215 rev B"


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def create_project(client, display_code="P01"):
    return _ok(
        client.post(
            "/api/projects",
            json={
                "display_code": display_code,
                "name": "法士特—陕汽定制项目试点",
                "customer": "陕汽集团",
                "product": "重型商用车变速器",
            },
        ),
        201,
    )


def create_and_parse(client, project_id):
    source = _ok(
        client.post(
            f"/api/projects/{project_id}/source-documents",
            json={
                "display_code": "DOC-P01-001",
                "doc_type": "protocol",
                "version": "V1",
                "content": FIXED_PROTOCOL,
                "mode": "manual",
            },
        ),
        201,
    )
    parsed = _ok(
        client.post(
            f"/api/source-documents/{source['id']}/parse",
            json={"display_code_map": DISPLAY_CODE_MAP},
        )
    )
    return source, parsed


def _confirm_requirements(client, project_id):
    requirements = _ok(client.get(f"/api/projects/{project_id}/requirements"))
    for requirement in requirements:
        _ok(
            client.post(
                f"/api/requirements/{requirement['id']}/confirmations",
                json={
                    **CONFIRMATION,
                    "expected_revision": requirement["current_revision"],
                },
            ),
            201,
        )
    return requirements


def _close_open_high_issues(client, project_id):
    issues = _ok(client.get(f"/api/projects/{project_id}/issues"))
    closed = []
    for issue in issues:
        if issue["status"] != "open":
            continue
        if issue["severity"] not in ("high", "blocking"):
            continue
        closed.append(
            _ok(
                client.post(
                    f"/api/issues/{issue['id']}/close",
                    json={
                        "expected_status": "open",
                        "actor": "演示负责人",
                        "role": "演示角色",
                        "resolution_type": "manual_supplement",
                        "resolution_note": "合成演示：已按固定协议和补充说明核对",
                        "evidence": "证据：DOC-P01-001 与合成补充说明",
                    },
                )
            )
        )
    return issues, closed


def _confirm_artifact(client, path, revision, **extra):
    return _ok(
        client.post(
            path,
            json={
                **CONFIRMATION,
                "expected_revision": revision,
                **extra,
            },
        ),
        201,
    )


def _build_engineering(client, project_id):
    engineering = _ok(
        client.post(
            f"/api/projects/{project_id}/variant-analysis",
            json={"base_display_code": "JX-12A"},
        )
    )
    for kind, items in [
        ("variant", engineering["variants"]),
        ("part", engineering["reusable_parts"]),
    ]:
        for item in items:
            if item["review_status"] != "confirmed":
                _confirm_artifact(
                    client,
                    f"/api/engineering-records/{kind}/{item['id']}/confirmations",
                    item["revision"],
                )
    return engineering


def _build_design_review(client, project_id):
    review = _ok(
        client.post(
            f"/api/projects/{project_id}/design-review",
            json={"base_display_code": "JX-12A"},
        )
    )
    confirmed = _confirm_artifact(
        client,
        f"/api/design-reviews/{review['review']['id']}/confirmations",
        review["review"]["revision"],
    )
    return review, confirmed


def _build_dfmea(client, project_id):
    fmea = _ok(
        client.post(
            f"/api/projects/{project_id}/dfmea",
            json={"base_display_code": "JX-12A"},
        )
    )
    for index, item in enumerate(fmea["items"], start=1):
        updated = _ok(
            client.patch(
                f"/api/fmea-items/{item['id']}",
                json={
                    "expected_revision": item["revision"],
                    "actor": CONFIRMATION["actor"],
                    "role": CONFIRMATION["role"],
                    "severity": (index % 9) + 1,
                    "occurrence": (index % 8) + 1,
                    "detection": (index % 7) + 1,
                },
            )
        )
        _ok(
            client.post(
                f"/api/fmea-items/{item['id']}/confirm-scores",
                json={
                    "expected_revision": updated["revision"],
                    "actor": CONFIRMATION["actor"],
                    "role": CONFIRMATION["role"],
                    "comment": "S/O/D 已按合成量表确认",
                },
            )
        )
    current = _ok(client.get(f"/api/projects/{project_id}/dfmea"))
    confirmed = _confirm_artifact(
        client,
        f"/api/fmea-documents/{current['fmea']['id']}/confirmations",
        current["fmea"]["revision"],
    )
    return current, confirmed


def _build_test_plan(client, project_id):
    plan = _ok(client.post(f"/api/projects/{project_id}/test-plan"))
    confirmed_plan = _confirm_artifact(
        client,
        f"/api/test-plans/{plan['plan']['id']}/confirmations",
        plan["plan"]["revision"],
    )
    cases = {case["display_code"]: case for case in plan["cases"]}

    durability = cases["TC-004"]
    revised = _ok(
        client.patch(
            f"/api/test-cases/{durability['id']}",
            json={
                "expected_revision": durability["revision"],
                "actor": CONFIRMATION["actor"],
                "role": CONFIRMATION["role"],
                "acceptance_criteria": ("按补充协议 V1：等效台架循环 1000 h 无失效"),
                "comment": "补充耐久判定依据",
            },
        )
    )
    cases["TC-004"] = revised

    confirmed_cases = {}
    for case in cases.values():
        confirmed_cases[case["display_code"]] = _ok(
            client.post(
                f"/api/test-cases/{case['id']}/confirmations",
                json={
                    **CONFIRMATION,
                    "expected_revision": case["revision"],
                },
            ),
            201,
        )["case"]

    runs = {}
    for display_code, case in confirmed_cases.items():
        payload = {
            "expected_revision": case["revision"],
            "actor": CONFIRMATION["actor"],
            "role": CONFIRMATION["role"],
            "conditions": "合成台架/计算工况",
            "evidence": "合成执行记录：本地演示日志",
        }
        if display_code == "TC-007":
            payload["load_basis_numeric"] = 2600
            payload["backup_coefficient"] = 2.6
        else:
            payload["manual_result"] = "pass"
        runs[display_code] = _ok(
            client.post(f"/api/test-cases/{case['id']}/runs", json=payload)
        )["run"]
    return confirmed_plan, cases, runs


def _build_sample(client, project_id):
    delivery = _ok(
        client.post(
            f"/api/projects/{project_id}/sample-deliveries",
            json=SAMPLE_DELIVERY,
        ),
        201,
    )
    uploaded = _ok(
        client.put(
            f"/api/sample-deliveries/{delivery['id']}/file",
            params={"file_name": "sample-drawing.txt"},
            content=SAMPLE_FILE,
            headers={"Content-Type": "text/plain"},
        )
    )
    comparison = _ok(
        client.post(
            f"/api/sample-deliveries/{delivery['id']}/comparison",
            json={
                "actor": "质量工程师甲",
                "role": "质量工程师（演示角色）",
                "parameters": [
                    {
                        "parameter_key": "holePosition",
                        "measured_value": 120.2,
                        "unit": "mm",
                    },
                    {
                        "parameter_key": "shaftDiameter",
                        "measured_value": 45.01,
                        "unit": "mm",
                    },
                ],
                "visual_check": {
                    "mode": "mock",
                    "result": "pass",
                    "note": "模拟目视检查通过（合成数据）",
                },
                "evidence": "合成测量记录 TR-01；模拟视觉记录 VS-01",
            },
        )
    )
    confirmed = _confirm_artifact(
        client,
        f"/api/sample-comparisons/{comparison['comparison']['id']}/confirmations",
        comparison["comparison"]["revision"],
    )
    return {
        "delivery": delivery,
        "file": uploaded,
        "comparison": comparison,
        "confirmed": confirmed,
    }


def _build_consistency(client, project_id):
    check = _ok(client.post(f"/api/projects/{project_id}/consistency-checks"))
    confirmed = _confirm_artifact(
        client,
        f"/api/consistency-checks/{check['check']['id']}/confirmations",
        check["check"]["revision"],
    )
    return check, confirmed


def _build_coordination(client, project_id, accept_risk):
    topic = _ok(
        client.post(
            f"/api/projects/{project_id}/coordination-topics",
            json={
                "name": "样件接口与响应协同",
                "expected_participants": ["主机厂", "法士特", "S-02"],
                "window_start": "2026-10-01T00:00:00+00:00",
                "window_end": "2026-10-20T00:00:00+00:00",
            },
        ),
        201,
    )
    records = []
    responses = (
        "2026-10-03T01:00:00+00:00",
        "2026-10-03T06:00:00+00:00",
        "2026-10-03T11:00:00+00:00",
    )
    for index, response_time in enumerate(responses, start=1):
        for external_id, sender, sent_at, reply_to in (
            (
                f"REQ-{index}",
                "法士特",
                f"2026-10-01T0{index}:00:00+00:00",
                None,
            ),
            (f"RES-{index}", "S-02", response_time, f"REQ-{index}"),
        ):
            records.append(
                _ok(
                    client.post(
                        f"/api/coordination-topics/{topic['id']}/records",
                        json={
                            "external_id": external_id,
                            "record_type": "message",
                            "sender": sender,
                            "content_summary": "合成协同记录",
                            "sent_at": sent_at,
                            "reply_to_external_id": reply_to,
                        },
                    ),
                    201,
                )
            )
    for index in range(1, 5):
        records.append(
            _ok(
                client.post(
                    f"/api/coordination-topics/{topic['id']}/records",
                    json={
                        "external_id": f"REOPENED-{index}",
                        "record_type": "reopened",
                        "sender": "法士特",
                        "content_summary": "合成重新打开记录",
                        "sent_at": f"2026-10-08T0{index}:00:00+00:00",
                    },
                ),
                201,
            )
        )
    metric = _ok(
        client.post(
            f"/api/coordination-topics/{topic['id']}/metrics",
            json={"labor_hours": 6, "hourly_rate": 200},
        ),
        201,
    )
    acceptance = None
    if accept_risk:
        acceptance = _ok(
            client.post(
                f"/api/coordination-topics/{topic['id']}/risk-acceptances",
                json={
                    "metric_run_id": metric["metric_run"]["id"],
                    "actor": "演示负责人",
                    "role": "演示角色",
                    "note": "合成演示：接受供应商响应滞后风险，持续跟踪",
                },
            ),
            201,
        )
    return {
        "topic": topic,
        "records": records,
        "metric": metric,
        "acceptance": acceptance,
    }


def build_ready_project(
    client,
    *,
    accept_coordination_risk=True,
    include_sample=True,
    include_coordination=True,
):
    project = create_project(client)
    source, parsed = create_and_parse(client, project["id"])
    requirements = _confirm_requirements(client, project["id"])
    issues, closed_issues = _close_open_high_issues(client, project["id"])
    _build_engineering(client, project["id"])
    review, review_confirmation = _build_design_review(client, project["id"])
    fmea, fmea_confirmation = _build_dfmea(client, project["id"])
    plan, cases, runs = _build_test_plan(client, project["id"])
    sample = _build_sample(client, project["id"]) if include_sample else None
    consistency = _build_consistency(client, project["id"])
    coordination = (
        _build_coordination(client, project["id"], accept_risk=accept_coordination_risk)
        if include_coordination
        else None
    )
    return {
        "project": project,
        "source": source,
        "parsed": parsed,
        "requirements": requirements,
        "issues": issues,
        "closed_issues": closed_issues,
        "design_review": review,
        "design_review_confirmation": review_confirmation,
        "fmea": fmea,
        "fmea_confirmation": fmea_confirmation,
        "test_plan": plan,
        "cases": cases,
        "runs": runs,
        "sample": sample,
        "consistency": consistency,
        "coordination": coordination,
    }
