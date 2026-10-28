from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .db import transaction, utc_now
from .test_dependencies import fmea_references, fmea_versions, fmea_dependencies_current
from .domain.testing import (
    VALIDATION_SCOPE,
    CaseSnapshot,
    RequirementRef,
    RunEvaluation,
    RunSnapshot,
    ScopeRequirement,
    build_traceability,
    evaluate_static_torsion,
    is_case_complete,
    is_case_covered,
)
from .errors import (
    DomainValidationError,
    InvalidReferenceError,
    NotFoundError,
    VersionConflictError,
)
from .schemas import (
    ArtifactConfirmationCreate,
    TestCaseUpdate,
    TestRunCreate,
)
from .services import _audit, _get_project_row, _infer_parser_key

TEST_PLAN_SOURCE = "固定验收集合 V1（演示规则）"
VALIDATION_KEYS = {item.key for item in VALIDATION_SCOPE}
CASE_DISPLAY_CODES = {
    "gearboxRatedInputTorque": "TC-007",
    "gearCount": "TC-001",
    "pto": "TC-002",
    "assemblyWeight": "TC-003",
    "durability": "TC-004",
}
CASE_FMEA_CODES = {
    "gearboxRatedInputTorque": "FMEA-01",
    "pto": "FMEA-02",
    "assemblyWeight": "FMEA-05",
}
EDITABLE_CASE_FIELDS = (
    "title",
    "purpose",
    "conditions_text",
    "load_conditions_text",
    "acceptance_criteria",
)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _parse_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _get_plan_row(connection: sqlite3.Connection, plan_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM test_plans WHERE id = ?", (plan_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("试验方案不存在", {"plan_id": plan_id})
    return row


def _get_case_row(connection: sqlite3.Connection, case_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM test_cases WHERE id = ?", (case_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("试验用例不存在", {"case_id": case_id})
    return row


def _current_case_revision(connection: sqlite3.Connection, case_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT * FROM test_case_revisions
        WHERE case_id = ?
        ORDER BY revision DESC LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("试验用例版本不存在", {"case_id": case_id})
    return row


def _current_requirements(
    connection: sqlite3.Connection, project_id: str
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT * FROM requirements
        WHERE project_id = ? AND validity = 'current'
        ORDER BY created_at ASC, display_code ASC
        """,
        (project_id,),
    ).fetchall()


def _scope_requirements(
    connection: sqlite3.Connection, project_id: str
) -> list[ScopeRequirement]:
    by_key: dict[str, sqlite3.Row] = {}
    duplicates: list[str] = []
    for row in _current_requirements(connection, project_id):
        key = _infer_parser_key(row)
        if key not in VALIDATION_KEYS:
            continue
        if key in by_key:
            duplicates.append(key)
            continue
        by_key[key] = row
    if duplicates:
        raise DomainValidationError(
            "固定验收集合存在重复参数，无法确定覆盖对象",
            {"duplicate_keys": sorted(set(duplicates))},
        )
    return [
        ScopeRequirement(
            key=item.key,
            label=item.label,
            requirement_id=(by_key[item.key]["id"] if item.key in by_key else None),
            display_code=(
                by_key[item.key]["display_code"] if item.key in by_key else None
            ),
            revision=(
                by_key[item.key]["current_revision"] if item.key in by_key else None
            ),
        )
        for item in VALIDATION_SCOPE
    ]


def _requirement_ref(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "requirement_id": row["id"],
        "display_code": row["display_code"],
        "revision": row["current_revision"],
    }


def _engine_requirement(
    connection: sqlite3.Connection, project_id: str
) -> sqlite3.Row | None:
    for row in _current_requirements(connection, project_id):
        if _infer_parser_key(row) == "engineMaxTorque":
            return row
    return None


def _fmea_refs_by_code(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT i.id, i.display_code, r.revision
        FROM fmea_items i
        JOIN fmea_documents d ON d.id = i.fmea_id
        JOIN fmea_item_revisions r ON r.item_id = i.id
        WHERE d.project_id = ?
          AND r.revision = (
              SELECT MAX(r2.revision)
              FROM fmea_item_revisions r2
              WHERE r2.item_id = i.id
          )
          AND r.status = 'current'
        """,
        (project_id,),
    ).fetchall()
    return {
        row["display_code"]: [
            {
                "fmea_item_id": row["id"],
                "display_code": row["display_code"],
                "revision": row["revision"],
            }
        ]
        for row in rows
    }


def _durability_acceptance(row: sqlite3.Row) -> str:
    text = f"{row['value_text']} {row['source_excerpt']}"
    if any(marker in text for marker in ("商定", "未明确", "待定", "待澄清", "未确定")):
        return ""
    if not row["value_text"].strip():
        return ""
    return f"满足耐久要求：{row['value_text']}"


def _draft_cases(
    connection: sqlite3.Connection,
    project_id: str,
    by_key: dict[str, sqlite3.Row],
) -> list[dict[str, Any]]:
    engine = _engine_requirement(connection, project_id)
    fmea_refs = _fmea_refs_by_code(connection, project_id)
    drafts: list[dict[str, Any]] = []
    for item in VALIDATION_SCOPE:
        requirement = by_key.get(item.key)
        if requirement is None:
            continue
        display_code = CASE_DISPLAY_CODES[item.key]
        refs = [_requirement_ref(requirement)]
        if item.key == "gearboxRatedInputTorque" and engine is not None:
            refs.append(_requirement_ref(engine))
        case_kind = "manual"
        load_basis_requirement_id = None
        minimum_coefficient = None
        if item.key == "gearboxRatedInputTorque":
            case_kind = "static_torsion"
            minimum_coefficient = 2.5
            load_basis_requirement_id = engine["id"] if engine is not None else None
            title = "静扭强度试验"
            purpose = "验证变速器在额定输入扭矩下的静扭强度能力"
            conditions_text = "台架静扭：按当前发动机最大扭矩加载"
            load_conditions_text = "加载基准 = 当前发动机最大扭矩；记录实际加载值"
            acceptance_criteria = "后备系数 ≥ 2.5（无量纲）；不与扭矩值直接比较"
        elif item.key == "gearCount":
            title = "档位数验证"
            purpose = "核对变速器档位数满足当前需求"
            conditions_text = "台架/静态检查：按当前需求版本核对档位配置"
            load_conditions_text = "不涉及加载"
            acceptance_criteria = f"档位数 = {requirement['value_text']}"
        elif item.key == "pto":
            title = "取力器功能验证"
            purpose = "核对取力器接口与功能满足当前需求"
            conditions_text = "台架：取力器接口与功能检查"
            load_conditions_text = "按取力器额定工况加载"
            acceptance_criteria = (
                "取力器接口可用且功能正常；" f"当前需求为 {requirement['value_text']}"
            )
        elif item.key == "assemblyWeight":
            unit = requirement["unit"]
            suffix = f" {unit}" if unit else ""
            title = "总成重量验证"
            purpose = "核对总成重量满足当前上限"
            conditions_text = "称重：总成装配状态"
            load_conditions_text = "不涉及加载"
            acceptance_criteria = f"总成重量 ≤ {requirement['value_text']}{suffix}"
        else:
            title = "耐久验证"
            purpose = "验证变速器耐久满足明确后的判定标准"
            conditions_text = "台架耐久：按补充协议或确认后的标准执行"
            load_conditions_text = "按补充协议定义的工况与循环"
            acceptance_criteria = _durability_acceptance(requirement)
        drafts.append(
            {
                "display_code": display_code,
                "case_key": item.key,
                "case_kind": case_kind,
                "title": title,
                "purpose": purpose,
                "conditions_text": conditions_text,
                "load_conditions_text": load_conditions_text,
                "acceptance_criteria": acceptance_criteria,
                "load_basis_requirement_id": load_basis_requirement_id,
                "minimum_coefficient": minimum_coefficient,
                "requirement_refs": refs,
                "fmea_refs": fmea_refs.get(CASE_FMEA_CODES.get(item.key, ""), []),
            }
        )
    return drafts


def _insert_case(
    connection: sqlite3.Connection,
    *,
    plan_id: str,
    project_id: str,
    draft: dict[str, Any],
    created_by: str,
) -> str:
    case_id = str(uuid.uuid4())
    now = utc_now()
    connection.execute(
        """
        INSERT INTO test_cases(
            id, plan_id, project_id, display_code, case_key, case_kind,
            revision, review_status, validity, title, purpose,
            conditions_text, load_conditions_text, acceptance_criteria,
            load_basis_requirement_id, minimum_coefficient,
            requirement_refs, fmea_refs, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 1, 'draft', 'current', ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case_id,
            plan_id,
            project_id,
            draft["display_code"],
            draft["case_key"],
            draft["case_kind"],
            draft["title"],
            draft["purpose"],
            draft["conditions_text"],
            draft["load_conditions_text"],
            draft["acceptance_criteria"],
            draft["load_basis_requirement_id"],
            draft["minimum_coefficient"],
            _json_text(draft["requirement_refs"]),
            _json_text(draft["fmea_refs"]),
            now,
            now,
        ),
    )
    connection.execute(
        """
        INSERT INTO test_case_revisions(
            id, case_id, revision, title, purpose, conditions_text,
            load_conditions_text, acceptance_criteria,
            load_basis_requirement_id, minimum_coefficient,
            requirement_refs, fmea_refs, validity, review_status,
            created_at, created_by, change_reason
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'current', 'draft',
                  ?, ?, '生成草案')
        """,
        (
            str(uuid.uuid4()),
            case_id,
            draft["title"],
            draft["purpose"],
            draft["conditions_text"],
            draft["load_conditions_text"],
            draft["acceptance_criteria"],
            draft["load_basis_requirement_id"],
            draft["minimum_coefficient"],
            _json_text(draft["requirement_refs"]),
            _json_text(draft["fmea_refs"]),
            now,
            created_by,
        ),
    )
    return case_id


def _plan_inputs_snapshot(
    requirements: list[sqlite3.Row],
    fmea: dict[str, int],
) -> str:
    snapshot = {
        "fmea_versions": fmea,
        "validation_scope_version": "V1",
        "requirements": [
            {
                "id": row["id"],
                "display_code": row["display_code"],
                "revision": row["current_revision"],
                "parser_key": _infer_parser_key(row),
                "review_status": row["review_status"],
                "value_text": row["value_text"],
                "unit": row["unit"],
            }
            for row in requirements
        ],
    }
    return _json_text(snapshot)


def _plan_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "display_code": row["display_code"],
        "revision": row["revision"],
        "status": row["status"],
        "purpose": row["purpose"],
        "conditions_text": row["conditions_text"],
        "sample_description": row["sample_description"],
        "load_conditions_text": row["load_conditions_text"],
        "acceptance_criteria": row["acceptance_criteria"],
        "source_label": row["source_label"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _plan_confirmation_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    snapshot = _parse_json(data.pop("snapshot_json"), {})
    data["case_snapshot"] = snapshot.get("cases", [])
    return data


def _enrich_requirement_refs(
    connection: sqlite3.Connection, refs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for reference in refs:
        requirement = connection.execute(
            """
            SELECT display_code, current_revision
            FROM requirements WHERE id = ?
            """,
            (reference.get("requirement_id"),),
        ).fetchone()
        item = dict(reference)
        if requirement is not None:
            item["display_code"] = requirement["display_code"]
            item["current_revision"] = requirement["current_revision"]
        else:
            item["current_revision"] = None
        enriched.append(item)
    return enriched


def _run_dict(row: sqlite3.Row) -> dict[str, Any]:
    reasons = _parse_json(row["reasons"], [])
    return {
        "id": row["id"],
        "case_id": row["case_id"],
        "case_revision": row["case_revision"],
        "run_no": row["run_no"],
        "status": row["status"],
        "result": row["result"],
        "mode": row["mode"],
        "conditions_text": row["conditions_text"],
        "evidence": row["evidence"],
        "load_basis_numeric": row["load_basis_numeric"],
        "backup_coefficient": row["backup_coefficient"],
        "manual_result": row["manual_result"],
        "reasons": reasons,
        "reason": "；".join(reasons),
        "measured_values": _parse_json(row["measured_values"], {}),
        "actor": row["actor"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


def _latest_run_row(
    connection: sqlite3.Connection, case_id: str, revision: int
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM test_runs
        WHERE case_id = ? AND case_revision = ?
        ORDER BY run_no DESC LIMIT 1
        """,
        (case_id, revision),
    ).fetchone()


def _case_snapshot(
    connection: sqlite3.Connection, case_row: sqlite3.Row
) -> CaseSnapshot:
    revision_row = _current_case_revision(connection, case_row["id"])
    raw_refs = _parse_json(revision_row["requirement_refs"], [])
    refs = tuple(
        RequirementRef(
            requirement_id=reference["requirement_id"],
            display_code=reference.get("display_code", ""),
            revision=int(reference["revision"]),
            current_revision=(
                int(reference["current_revision"])
                if reference.get("current_revision") is not None
                else 0
            ),
        )
        for reference in refs_with_current(connection, raw_refs)
    )
    latest = _latest_run_row(connection, case_row["id"], revision_row["revision"])
    latest_run = None
    if latest is not None:
        latest_run = RunSnapshot(
            id=latest["id"],
            run_no=latest["run_no"],
            status=latest["status"],
            result=latest["result"],
            case_revision=latest["case_revision"],
            mode=latest["mode"],
            created_at=latest["created_at"],
        )
    return CaseSnapshot(
        id=case_row["id"],
        display_code=case_row["display_code"],
        title=revision_row["title"],
        revision=revision_row["revision"],
        review_status=case_row["review_status"],
        validity=(
            case_row["validity"]
            if fmea_dependencies_current(
                fmea_references(
                    connection,
                    case_row["project_id"],
                    _parse_json(revision_row["fmea_refs"], []),
                )
            )
            else "stale"
        ),
        conditions_text=revision_row["conditions_text"],
        load_conditions_text=revision_row["load_conditions_text"],
        acceptance_criteria=revision_row["acceptance_criteria"],
        requirement_refs=refs,
        fmea_refs=tuple(
            fmea_references(
                connection,
                case_row["project_id"],
                _parse_json(revision_row["fmea_refs"], []),
            )
        ),
        latest_run=latest_run,
    )


def refs_with_current(
    connection: sqlite3.Connection, refs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for reference in refs:
        item = dict(reference)
        row = connection.execute(
            "SELECT current_revision FROM requirements WHERE id = ?",
            (reference.get("requirement_id"),),
        ).fetchone()
        item["current_revision"] = row["current_revision"] if row is not None else None
        result.append(item)
    return result


def _case_dict(connection: sqlite3.Connection, case_row: sqlite3.Row) -> dict[str, Any]:
    revision_row = _current_case_revision(connection, case_row["id"])
    refs = _enrich_requirement_refs(
        connection,
        _parse_json(revision_row["requirement_refs"], []),
    )
    snapshot = _case_snapshot(connection, case_row)
    runs = connection.execute(
        """
        SELECT * FROM test_runs WHERE case_id = ?
        ORDER BY run_no ASC
        """,
        (case_row["id"],),
    ).fetchall()
    return {
        "id": case_row["id"],
        "plan_id": case_row["plan_id"],
        "display_code": case_row["display_code"],
        "case_key": case_row["case_key"],
        "case_kind": case_row["case_kind"],
        "title": revision_row["title"],
        "purpose": revision_row["purpose"],
        "revision": case_row["revision"],
        "review_status": case_row["review_status"],
        "validity": snapshot.validity,
        "conditions_text": revision_row["conditions_text"],
        "load_conditions_text": revision_row["load_conditions_text"],
        "acceptance_criteria": revision_row["acceptance_criteria"],
        "load_basis_requirement_id": revision_row["load_basis_requirement_id"],
        "minimum_coefficient": revision_row["minimum_coefficient"],
        "requirement_refs": refs,
        "fmea_refs": list(snapshot.fmea_refs),
        "complete": is_case_complete(snapshot),
        "coverage_valid": is_case_covered(snapshot),
        "runs": [_run_dict(row) for row in runs],
    }


def _plan_cases(connection: sqlite3.Connection, plan_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT * FROM test_cases WHERE plan_id = ?
        ORDER BY display_code ASC
        """,
        (plan_id,),
    ).fetchall()
    return [_case_dict(connection, row) for row in rows]


def _plan_payload(connection: sqlite3.Connection, plan_id: str) -> dict[str, Any]:
    row = _get_plan_row(connection, plan_id)
    confirmations = connection.execute(
        """
        SELECT * FROM test_plan_confirmations
        WHERE plan_id = ? ORDER BY created_at ASC, id ASC
        """,
        (plan_id,),
    ).fetchall()
    return {
        "mode": "rule",
        "source_label": row["source_label"],
        "needs_reconfirmation": (
            _parse_json(row["inputs_snapshot"], {}).get(
                "fmea_versions", fmea_versions(connection, row["project_id"])
            )
            != fmea_versions(connection, row["project_id"])
            or any(
                case["validity"] == "stale" for case in _plan_cases(connection, plan_id)
            )
        ),
        "plan": _plan_dict(row),
        "cases": _plan_cases(connection, plan_id),
        "confirmations": [_plan_confirmation_dict(item) for item in confirmations],
    }


def generate_test_plan(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    with transaction(connection):
        project = _get_project_row(connection, project_id)
        requirements = _current_requirements(connection, project_id)
        _scope_requirements(connection, project_id)
        by_key: dict[str, sqlite3.Row] = {}
        for row in requirements:
            key = _infer_parser_key(row)
            if key in VALIDATION_KEYS and key not in by_key:
                by_key[key] = row
        snapshot_json = _plan_inputs_snapshot(
            requirements, fmea_versions(connection, project_id)
        )
        existing = connection.execute(
            "SELECT * FROM test_plans WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if existing is not None and (existing["inputs_snapshot"] == snapshot_json):
            return _plan_payload(connection, existing["id"])

        purpose = "按固定验收集合验证定制变速器需求"
        conditions_text = "本地合成台架/计算验证；不驱动真实台架"
        sample_description = f"合成演示样件：{project['product']}（非实物）"
        load_conditions_text = "按各用例定义加载；扭矩类用例以当前发动机最大扭矩为基准"
        acceptance_criteria = "各用例判定标准须完整；TC-007 后备系数 ≥2.5（无量纲）"
        now = utc_now()
        if existing is None:
            plan_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO test_plans(
                    id, project_id, display_code, revision, status,
                    purpose, conditions_text, sample_description,
                    load_conditions_text, acceptance_criteria,
                    inputs_snapshot, source_label, created_at, updated_at
                ) VALUES (?, ?, ?, 1, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    project_id,
                    f"TP-{project['display_code']}",
                    purpose,
                    conditions_text,
                    sample_description,
                    load_conditions_text,
                    acceptance_criteria,
                    snapshot_json,
                    TEST_PLAN_SOURCE,
                    now,
                    now,
                ),
            )
            drafts = _draft_cases(connection, project_id, by_key)
            for draft in drafts:
                _insert_case(
                    connection,
                    plan_id=plan_id,
                    project_id=project_id,
                    draft=draft,
                    created_by="rule_engine",
                )
            _audit(
                connection,
                project_id=project_id,
                object_type="test_plan",
                object_id=plan_id,
                object_revision=1,
                action="test_plan.generated",
                actor="rule_engine",
                role="system",
                after={
                    "display_code": f"TP-{project['display_code']}",
                    "case_count": len(drafts),
                    "validation_scope": list(VALIDATION_KEYS),
                },
            )
            return _plan_payload(connection, plan_id)

        plan_id = existing["id"]
        new_revision = int(existing["revision"]) + 1
        connection.execute(
            """
            UPDATE test_plans SET
                revision = ?, status = 'draft', purpose = ?,
                conditions_text = ?, sample_description = ?,
                load_conditions_text = ?, acceptance_criteria = ?,
                inputs_snapshot = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_revision,
                purpose,
                conditions_text,
                sample_description,
                load_conditions_text,
                acceptance_criteria,
                snapshot_json,
                now,
                plan_id,
            ),
        )
        _audit(
            connection,
            project_id=project_id,
            object_type="test_plan",
            object_id=plan_id,
            object_revision=new_revision,
            action="test_plan.regenerated",
            actor="rule_engine",
            role="system",
            after={
                "case_count": len(_plan_cases(connection, plan_id)),
                "validation_scope": list(VALIDATION_KEYS),
            },
        )
        return _plan_payload(connection, plan_id)


def get_test_plan(connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT id FROM test_plans WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("试验方案不存在", {"project_id": project_id})
    return _plan_payload(connection, row["id"])


def confirm_test_plan(
    connection: sqlite3.Connection,
    plan_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_plan_row(connection, plan_id)
        if payload.expected_revision != row["revision"]:
            raise VersionConflictError(
                "试验方案已被更新，请刷新后重试",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": row["revision"],
                },
            )
        duplicate = connection.execute(
            """
            SELECT id FROM test_plan_confirmations
            WHERE plan_id = ? AND plan_revision = ?
            """,
            (plan_id, row["revision"]),
        ).fetchone()
        if duplicate is not None:
            raise VersionConflictError(
                "该版本试验方案已有确认记录",
                {"plan_revision": row["revision"]},
            )
        status = "confirmed" if payload.decision == "confirmed" else "rejected"
        cases = _plan_cases(connection, plan_id)
        snapshot = {
            "plan_revision": row["revision"],
            "cases": [
                {
                    "id": case["id"],
                    "display_code": case["display_code"],
                    "revision": case["revision"],
                    "review_status": case["review_status"],
                    "validity": case["validity"],
                    "complete": case["complete"],
                }
                for case in cases
            ],
        }
        connection.execute(
            "UPDATE test_plans SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now(), plan_id),
        )
        confirmation_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO test_plan_confirmations(
                id, plan_id, plan_revision, actor, role, decision,
                comment, snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                confirmation_id,
                plan_id,
                row["revision"],
                payload.actor,
                payload.role,
                payload.decision,
                payload.comment,
                _json_text(snapshot),
                utc_now(),
            ),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="test_plan",
            object_id=plan_id,
            object_revision=row["revision"],
            action=f"test_plan.{status}",
            actor=payload.actor,
            role=payload.role,
            decision=payload.decision,
            comment=payload.comment,
            before={"status": row["status"]},
            after={"status": status},
        )
        result = _plan_payload(connection, plan_id)
        confirmation = connection.execute(
            "SELECT * FROM test_plan_confirmations WHERE id = ?",
            (confirmation_id,),
        ).fetchone()
        result["confirmation"] = _plan_confirmation_dict(confirmation)
        return result


def update_test_case(
    connection: sqlite3.Connection,
    case_id: str,
    payload: TestCaseUpdate,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_case_row(connection, case_id)
        if payload.expected_revision != row["revision"]:
            raise VersionConflictError(
                "试验用例已被更新，请刷新后重试",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": row["revision"],
                },
            )
        revision_row = _current_case_revision(connection, case_id)
        updates = payload.model_dump(exclude_unset=True)
        for key in (
            "expected_revision",
            "actor",
            "role",
            "rebase_requirements",
            "comment",
        ):
            updates.pop(key, None)
        candidate = {field: revision_row[field] for field in EDITABLE_CASE_FIELDS}
        for field in EDITABLE_CASE_FIELDS:
            if field in updates:
                candidate[field] = updates[field]
        refs = _parse_json(revision_row["requirement_refs"], [])
        fmea_refs = _parse_json(revision_row["fmea_refs"], [])
        if payload.rebase_requirements:
            fmea_refs = fmea_references(
                connection, row["project_id"], fmea_refs, rebase=True
            )
            for reference in refs:
                requirement = connection.execute(
                    "SELECT * FROM requirements WHERE id = ?",
                    (reference.get("requirement_id"),),
                ).fetchone()
                if (
                    requirement is None
                    or requirement["project_id"] != row["project_id"]
                ):
                    raise InvalidReferenceError(
                        "用例引用的需求不存在或不属于当前项目",
                        {"requirement_id": reference.get("requirement_id")},
                    )
                reference["revision"] = requirement["current_revision"]
                reference["display_code"] = requirement["display_code"]
        changed = (
            any(
                candidate[field] != revision_row[field]
                for field in EDITABLE_CASE_FIELDS
            )
            or _json_text(refs) != revision_row["requirement_refs"]
            or _json_text(fmea_refs) != revision_row["fmea_refs"]
        )
        if not changed:
            return _case_dict(connection, row)

        new_revision = int(row["revision"]) + 1
        now = utc_now()
        connection.execute(
            """
            INSERT INTO test_case_revisions(
                id, case_id, revision, title, purpose, conditions_text,
                load_conditions_text, acceptance_criteria,
                load_basis_requirement_id, minimum_coefficient,
                requirement_refs, fmea_refs, validity, review_status,
                created_at, created_by, change_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'current',
                      'draft', ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                case_id,
                new_revision,
                candidate["title"],
                candidate["purpose"],
                candidate["conditions_text"],
                candidate["load_conditions_text"],
                candidate["acceptance_criteria"],
                revision_row["load_basis_requirement_id"],
                revision_row["minimum_coefficient"],
                _json_text(refs),
                _json_text(fmea_refs),
                now,
                payload.actor,
                payload.comment or "用例修订",
            ),
        )
        connection.execute(
            """
            UPDATE test_cases SET
                title = ?, purpose = ?, conditions_text = ?,
                load_conditions_text = ?, acceptance_criteria = ?,
                requirement_refs = ?, fmea_refs = ?, revision = ?,
                review_status = 'draft', validity = 'current',
                updated_at = ?
            WHERE id = ?
            """,
            (
                candidate["title"],
                candidate["purpose"],
                candidate["conditions_text"],
                candidate["load_conditions_text"],
                candidate["acceptance_criteria"],
                _json_text(refs),
                _json_text(fmea_refs),
                new_revision,
                now,
                case_id,
            ),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="test_case",
            object_id=case_id,
            object_revision=new_revision,
            action="test_case.updated",
            actor=payload.actor,
            role=payload.role,
            comment=payload.comment,
            before={
                "revision": row["revision"],
                "review_status": row["review_status"],
                "validity": row["validity"],
            },
            after={
                "revision": new_revision,
                "review_status": "draft",
                "validity": "current",
            },
        )
        return _case_dict(connection, _get_case_row(connection, case_id))


def _case_missing_criteria(
    revision_row: sqlite3.Row, refs: list[dict[str, Any]]
) -> list[str]:
    missing: list[str] = []
    if not revision_row["conditions_text"].strip():
        missing.append("conditions_text")
    if not revision_row["load_conditions_text"].strip():
        missing.append("load_conditions_text")
    if not revision_row["acceptance_criteria"].strip():
        missing.append("acceptance_criteria")
    if not refs:
        missing.append("requirement_refs")
    return missing


def confirm_test_case(
    connection: sqlite3.Connection,
    case_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_case_row(connection, case_id)
        if payload.expected_revision != row["revision"]:
            raise VersionConflictError(
                "试验用例已被更新，请刷新后重试",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": row["revision"],
                },
            )
        if _case_snapshot(connection, row).validity != "current":
            raise DomainValidationError(
                "用例已失效，请先重新基线",
                {"validity": row["validity"]},
            )
        revision_row = _current_case_revision(connection, case_id)
        refs = _parse_json(revision_row["requirement_refs"], [])
        missing = _case_missing_criteria(revision_row, refs)
        if missing and payload.decision == "confirmed":
            raise DomainValidationError(
                "用例条件或判定标准不完整，不能确认",
                {"missing_fields": missing},
            )
        stale_refs = [
            reference["requirement_id"]
            for reference in refs
            if reference.get("current_revision") is not None
            and reference["revision"] != reference["current_revision"]
        ]
        for reference in refs:
            requirement = connection.execute(
                "SELECT current_revision FROM requirements WHERE id = ?",
                (reference.get("requirement_id"),),
            ).fetchone()
            if requirement is None:
                raise InvalidReferenceError(
                    "用例引用的需求不存在",
                    {"requirement_id": reference.get("requirement_id")},
                )
            if reference["revision"] != requirement["current_revision"]:
                stale_refs.append(reference["requirement_id"])
        if stale_refs:
            raise DomainValidationError(
                "用例引用的需求版本不是当前版本，请先重新基线",
                {"stale_requirement_refs": sorted(set(stale_refs))},
            )
        duplicate = connection.execute(
            """
            SELECT id FROM test_case_confirmations
            WHERE case_id = ? AND case_revision = ?
            """,
            (case_id, row["revision"]),
        ).fetchone()
        if duplicate is not None:
            raise VersionConflictError(
                "该版本试验用例已有确认记录",
                {"case_revision": row["revision"]},
            )
        status = "confirmed" if payload.decision == "confirmed" else "rejected"
        snapshot = {
            "case_revision": row["revision"],
            "title": revision_row["title"],
            "conditions_text": revision_row["conditions_text"],
            "load_conditions_text": revision_row["load_conditions_text"],
            "acceptance_criteria": revision_row["acceptance_criteria"],
            "requirement_refs": refs,
        }
        connection.execute(
            """
            UPDATE test_cases SET review_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, utc_now(), case_id),
        )
        connection.execute(
            """
            UPDATE test_case_revisions SET review_status = ?
            WHERE case_id = ? AND revision = ?
            """,
            (status, case_id, row["revision"]),
        )
        confirmation_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO test_case_confirmations(
                id, case_id, case_revision, actor, role, decision,
                comment, snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                confirmation_id,
                case_id,
                row["revision"],
                payload.actor,
                payload.role,
                payload.decision,
                payload.comment,
                _json_text(snapshot),
                utc_now(),
            ),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="test_case",
            object_id=case_id,
            object_revision=row["revision"],
            action=f"test_case.{status}",
            actor=payload.actor,
            role=payload.role,
            decision=payload.decision,
            comment=payload.comment,
            before={"review_status": row["review_status"]},
            after={"review_status": status},
        )
        confirmation = connection.execute(
            "SELECT * FROM test_case_confirmations WHERE id = ?",
            (confirmation_id,),
        ).fetchone()
        return {
            "case": _case_dict(connection, _get_case_row(connection, case_id)),
            "confirmation": _confirmation_snapshot(confirmation),
        }


def _confirmation_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    snapshot = _parse_json(data.pop("snapshot_json"), {})
    data["snapshot"] = snapshot
    return data


def record_test_run(
    connection: sqlite3.Connection,
    case_id: str,
    payload: TestRunCreate,
) -> dict[str, Any]:
    with transaction(connection):
        row = _get_case_row(connection, case_id)
        if payload.expected_revision != row["revision"]:
            raise VersionConflictError(
                "试验用例已被更新，请刷新后重试",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": row["revision"],
                },
            )
        if row["review_status"] != "confirmed":
            raise DomainValidationError(
                "试验用例尚未确认，不能记录执行",
                {"review_status": row["review_status"]},
            )
        if _case_snapshot(connection, row).validity != "current":
            raise DomainValidationError(
                "试验用例已失效，不能记录新版执行",
                {"validity": row["validity"]},
            )
        revision_row = _current_case_revision(connection, case_id)
        mode = "manual"
        if row["case_kind"] == "static_torsion":
            engine = None
            if revision_row["load_basis_requirement_id"]:
                engine = connection.execute(
                    "SELECT * FROM requirements WHERE id = ?",
                    (revision_row["load_basis_requirement_id"],),
                ).fetchone()
            expected_basis = engine["value_num"] if engine is not None else None
            minimum = revision_row["minimum_coefficient"]
            evaluation = evaluate_static_torsion(
                payload.load_basis_numeric,
                expected_basis,
                payload.backup_coefficient,
                minimum if minimum is not None else 2.5,
            )
            mode = "rule"
        else:
            if payload.manual_result is None:
                raise DomainValidationError(
                    "人工判定用例必须提交结论",
                    {"missing_fields": ["manual_result"]},
                )
            evaluation = RunEvaluation(
                payload.manual_result,
                ["人工记录结论；须由执行人提供可核对证据"],
            )

        run_no = connection.execute(
            """
            SELECT COALESCE(MAX(run_no), 0) + 1 AS next_no
            FROM test_runs WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()["next_no"]
        run_id = str(uuid.uuid4())
        now = utc_now()
        measured_values = {
            "loadBasis": payload.load_basis_numeric,
            "backupCoefficient": payload.backup_coefficient,
        }
        connection.execute(
            """
            INSERT INTO test_runs(
                id, project_id, case_id, case_revision, run_no, status,
                result, mode, conditions_text, evidence,
                load_basis_numeric, backup_coefficient, manual_result,
                reasons, measured_values, actor, role, created_at
            ) VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?)
            """,
            (
                run_id,
                row["project_id"],
                case_id,
                row["revision"],
                run_no,
                evaluation.result,
                mode,
                payload.conditions,
                payload.evidence,
                payload.load_basis_numeric,
                payload.backup_coefficient,
                payload.manual_result,
                _json_text(evaluation.reasons),
                _json_text(measured_values),
                payload.actor,
                payload.role,
                now,
            ),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="test_run",
            object_id=run_id,
            object_revision=row["revision"],
            action="test_run.recorded",
            actor=payload.actor,
            role=payload.role,
            comment=payload.evidence,
            after={
                "case_id": case_id,
                "case_revision": row["revision"],
                "run_no": run_no,
                "result": evaluation.result,
                "mode": mode,
            },
        )
        run_row = connection.execute(
            "SELECT * FROM test_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return {
            "case": _case_dict(connection, _get_case_row(connection, case_id)),
            "run": _run_dict(run_row),
        }


def _matrix_item_dict(item: Any) -> dict[str, Any]:
    return {
        "key": item.key,
        "label": item.label,
        "requirement_id": item.requirement_id,
        "display_code": item.display_code,
        "requirement_revision": item.requirement_revision,
        "covered": item.covered,
        "coverage_valid": item.covered,
        "valid_case_ids": list(item.valid_case_ids),
        "pending_case_ids": list(item.pending_case_ids),
        "execution": item.execution,
        "reason": item.reason,
        "latest_runs": [_run_snapshot_dict(run) for run in item.latest_runs],
    }


def _run_snapshot_dict(run: Any) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_no": run.run_no,
        "status": run.status,
        "result": run.result,
        "case_revision": run.case_revision,
        "mode": run.mode,
        "created_at": run.created_at,
    }


def get_traceability_matrix(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    _get_project_row(connection, project_id)
    scope = _scope_requirements(connection, project_id)
    case_rows = connection.execute(
        """
        SELECT * FROM test_cases WHERE project_id = ?
        ORDER BY display_code ASC
        """,
        (project_id,),
    ).fetchall()
    cases = [_case_snapshot(connection, row) for row in case_rows]
    matrix = build_traceability(scope, cases)
    items = [_matrix_item_dict(item) for item in matrix.items]
    return {
        "mode": "rule",
        "scope_label": TEST_PLAN_SOURCE,
        "denominator": matrix.denominator,
        "covered_count": matrix.covered_count,
        "coverage_percentage": matrix.coverage_percentage,
        "items": items,
        "uncovered": [item for item in items if not item["covered"]],
        "pending_review": [dict(entry) for entry in matrix.pending_review],
        "execution_summary": dict(matrix.execution_summary),
    }


def mark_test_cases_stale_for_requirement(
    connection: sqlite3.Connection,
    requirement_id: str,
    new_revision: int,
) -> None:
    rows = connection.execute(
        "SELECT * FROM test_cases WHERE validity = 'current'"
    ).fetchall()
    for row in rows:
        refs = _parse_json(row["requirement_refs"], [])
        affected = any(
            reference.get("requirement_id") == requirement_id
            and int(reference.get("revision", 0)) != new_revision
            for reference in refs
        )
        if not affected:
            continue
        now = utc_now()
        connection.execute(
            """
            UPDATE test_cases SET validity = 'stale', updated_at = ?
            WHERE id = ?
            """,
            (now, row["id"]),
        )
        connection.execute(
            """
            UPDATE test_case_revisions SET validity = 'stale'
            WHERE case_id = ? AND revision = ?
            """,
            (row["id"], row["revision"]),
        )
        _audit(
            connection,
            project_id=row["project_id"],
            object_type="test_case",
            object_id=row["id"],
            object_revision=row["revision"],
            action="test_case.stale",
            actor="system",
            role="system",
            comment="上游需求版本变化，用例进入待复核",
            before={"validity": "current"},
            after={
                "validity": "stale",
                "requirement_id": requirement_id,
                "requirement_revision": new_revision,
            },
        )
