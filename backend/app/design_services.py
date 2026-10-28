from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .db import transaction, utc_now
from .test_dependencies import invalidate_fmea_dependents
from .domain.design import (
    DesignProfile,
    IssueInput,
    RequirementInput,
    VariantInput,
    build_design_review,
    build_dfmea,
)
from .domain.similarity import (
    HistoryProject,
    ProjectProfile,
    find_similar_projects,
)
from .errors import (
    DomainValidationError,
    NotFoundError,
    VersionConflictError,
)
from .schemas import (
    ArtifactConfirmationCreate,
    FmeaItemUpdate,
    FmeaScoreConfirmation,
)
from .services import _audit, _get_project_row, _infer_parser_key

HISTORY_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "history_projects.json"
)

SIMILARITY_KEYS = {
    "transmissionType",
    "gearCount",
    "gearboxRatedInputTorque",
    "engineMaxTorque",
    "pto",
    "assemblyWeight",
}
CRITERIA_NAMES = (
    "transmissionType",
    "gearCount",
    "ratedInputTorque",
    "pto",
    "weightLimit",
)
PTO_REQUIRED_VALUES = {"required", "true", "yes", "是", "有", "需要"}
PTO_NOT_REQUIRED_VALUES = {
    "not_required",
    "false",
    "no",
    "否",
    "无",
    "不需要",
}
EDITABLE_FMEA_FIELDS = (
    "function_text",
    "failure_mode",
    "cause",
    "effect",
    "control",
    "action_text",
    "severity",
    "occurrence",
    "detection",
)


# ---------------------------------------------------------------------------
# O6 similar historical projects
# ---------------------------------------------------------------------------


def seed_history(
    connection: sqlite3.Connection,
    history_path: str | Path | None = None,
) -> dict[str, int]:
    path = Path(history_path) if history_path is not None else HISTORY_PATH
    if not path.exists():
        raise DomainValidationError("历史项目库文件不存在", {"path": str(path)})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainValidationError(
            "历史项目库文件无法读取", {"path": str(path), "error": str(exc)}
        ) from exc

    projects = data.get("history_projects")
    if not isinstance(projects, list):
        raise DomainValidationError("历史项目库缺少 history_projects 列表")

    with transaction(connection):
        inserted = 0
        for item in projects:
            try:
                display_code = str(item["display_code"]).strip()
                transmission_type = str(item["transmission_type"]).strip()
                top_gear_type = str(item["top_gear_type"]).strip()
                gear_count = int(item["gear_count"])
                rated_input_torque = float(item["rated_input_torque"])
                assembly_weight_kg = float(item["assembly_weight_kg"])
                has_pto = bool(item["has_pto"])
                name = str(item["name"]).strip()
                customer = str(item["customer"]).strip()
                source = str(item["source"]).strip()
                notes = str(item.get("notes", "")).strip()
            except (KeyError, TypeError, ValueError) as exc:
                raise DomainValidationError(
                    "历史项目数据不合法", {"item": item, "error": str(exc)}
                ) from exc
            if transmission_type not in {"AMT", "MT", "AT"}:
                raise DomainValidationError(
                    "历史项目换挡方式不合法",
                    {"display_code": display_code, "value": transmission_type},
                )
            if top_gear_type not in {"direct", "overdrive"}:
                raise DomainValidationError(
                    "历史项目最高档形式不合法",
                    {"display_code": display_code, "value": top_gear_type},
                )
            if not display_code or not name or not customer or not source:
                raise DomainValidationError(
                    "历史项目缺少必要字段",
                    {"display_code": display_code},
                )
            existing = connection.execute(
                "SELECT 1 FROM history_projects WHERE display_code = ?",
                (display_code,),
            ).fetchone()
            if existing is not None:
                continue
            connection.execute(
                """
                INSERT INTO history_projects(
                    id, display_code, name, customer, transmission_type,
                    gear_count, rated_input_torque, has_pto,
                    assembly_weight_kg, top_gear_type, notes, source,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    display_code,
                    name,
                    customer,
                    transmission_type,
                    gear_count,
                    rated_input_torque,
                    1 if has_pto else 0,
                    assembly_weight_kg,
                    top_gear_type,
                    notes,
                    source,
                    utc_now(),
                ),
            )
            inserted += 1
        return {"history_projects_inserted": inserted}


def _safe_float(value: str) -> float | None:
    try:
        number = float(value.replace(",", "").replace("，", "").strip())
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return number


def _load_similarity_profile(
    connection: sqlite3.Connection, project_id: str
) -> tuple[ProjectProfile, list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT * FROM requirements
        WHERE project_id = ? AND validity = 'current'
        ORDER BY display_code ASC
        """,
        (project_id,),
    ).fetchall()
    by_key: dict[str, sqlite3.Row] = {}
    duplicates: list[str] = []
    for row in rows:
        key = _infer_parser_key(row)
        if key in by_key:
            duplicates.append(key)
            continue
        by_key[key] = row
    relevant_duplicates = sorted(set(duplicates) & SIMILARITY_KEYS)
    if relevant_duplicates:
        raise DomainValidationError(
            "存在多个同参数需求，请先处理冲突",
            {"duplicate_keys": relevant_duplicates},
        )

    def number(row: sqlite3.Row | None) -> float | None:
        if row is None:
            return None
        return _safe_float(row["value_text"])

    transmission_row = by_key.get("transmissionType")
    transmission_type = (
        transmission_row["value_text"].strip().upper()
        if transmission_row is not None
        else None
    )
    if transmission_type not in {"AMT", "MT", "AT"}:
        transmission_type = None

    torque_row = by_key.get("gearboxRatedInputTorque")
    if torque_row is None:
        torque_row = by_key.get("engineMaxTorque")

    pto_row = by_key.get("pto")
    has_pto: bool | None = None
    if pto_row is not None:
        pto_text = pto_row["value_text"].strip()
        if pto_text.lower() in PTO_REQUIRED_VALUES:
            has_pto = True
        elif pto_text.lower() in PTO_NOT_REQUIRED_VALUES:
            has_pto = False

    gear_count_value = number(by_key.get("gearCount"))
    profile = ProjectProfile(
        transmission_type=transmission_type,
        gear_count=(int(gear_count_value) if gear_count_value is not None else None),
        rated_input_torque=number(torque_row),
        has_pto=has_pto,
        weight_limit_kg=number(by_key.get("assemblyWeight")),
    )
    versions = [
        {
            "key": _infer_parser_key(row),
            "requirement_id": row["id"],
            "display_code": row["display_code"],
            "revision": row["current_revision"],
            "value": row["value_text"],
            "unit": row["unit"],
            "review_status": row["review_status"],
        }
        for row in rows
        if _infer_parser_key(row) in SIMILARITY_KEYS
    ]
    return profile, versions


def _similar_match_dict(match: Any) -> dict[str, Any]:
    return {
        "history_project_id": match.history_project_id,
        "display_code": match.display_code,
        "name": match.name,
        "customer": match.customer,
        "score": match.score,
        "matched_points": list(match.matched_points),
        "differences": list(match.differences),
        "missing_criteria": list(match.missing_criteria),
        "criteria": [asdict(criterion) for criterion in match.criteria],
        "source": match.source,
        "notes": match.notes,
    }


def find_project_similar_projects(
    connection: sqlite3.Connection,
    project_id: str,
    top_n: int = 3,
) -> dict[str, Any]:
    with transaction(connection):
        _get_project_row(connection, project_id)
        history_rows = connection.execute(
            "SELECT * FROM history_projects ORDER BY display_code ASC"
        ).fetchall()
        if not history_rows:
            raise DomainValidationError(
                "历史项目库为空，请先执行 scripts/seed_history.py"
            )

        profile, versions = _load_similarity_profile(connection, project_id)
        missing_criteria = [
            name
            for name, value in zip(
                CRITERIA_NAMES,
                (
                    profile.transmission_type,
                    profile.gear_count,
                    profile.rated_input_torque,
                    profile.has_pto,
                    profile.weight_limit_kg,
                ),
            )
            if value is None
        ]
        if len(missing_criteria) == len(CRITERIA_NAMES):
            raise DomainValidationError(
                "项目缺少可比对的项目特征",
                {"missing_criteria": missing_criteria},
            )

        history = [
            HistoryProject(
                id=row["id"],
                display_code=row["display_code"],
                name=row["name"],
                customer=row["customer"],
                transmission_type=row["transmission_type"],
                gear_count=int(row["gear_count"]),
                rated_input_torque=float(row["rated_input_torque"]),
                has_pto=bool(row["has_pto"]),
                assembly_weight_kg=float(row["assembly_weight_kg"]),
                top_gear_type=row["top_gear_type"],
                notes=row["notes"],
                source=row["source"],
            )
            for row in history_rows
        ]
        result = find_similar_projects(history, profile, top_n)
        source_labels = sorted({row["source"] for row in history_rows})
        payload = {
            "project_id": project_id,
            "mode": "mock",
            "source_label": "；".join(source_labels),
            "candidate_count": result.candidate_count,
            "top_n": top_n,
            "candidate_shortage": result.candidate_shortage,
            "missing_criteria": list(result.missing_criteria),
            "requirement_versions": versions,
            "matches": [_similar_match_dict(match) for match in result.matches],
        }
        _audit(
            connection,
            project_id=project_id,
            object_type="project",
            object_id=project_id,
            object_revision=None,
            action="similarity.generated",
            actor="rule_engine",
            role="system",
            after={
                "mode": "mock",
                "top_n": top_n,
                "candidate_count": result.candidate_count,
                "missing_criteria": list(result.missing_criteria),
                "matches": [
                    {
                        "display_code": match.display_code,
                        "score": match.score,
                    }
                    for match in result.matches
                ],
            },
        )
        return payload


# ---------------------------------------------------------------------------
# Shared design inputs
# ---------------------------------------------------------------------------


def _get_base_row(
    connection: sqlite3.Connection, base_display_code: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM product_bases WHERE display_code = ?",
        (base_display_code,),
    ).fetchone()
    if row is None:
        raise NotFoundError("基型不存在", {"display_code": base_display_code})
    return row


def _design_profile(project: sqlite3.Row, base: sqlite3.Row) -> DesignProfile:
    return DesignProfile(
        project_display_code=project["display_code"],
        base_display_code=base["display_code"],
        base_name=base["name"],
    )


def _load_design_inputs(
    connection: sqlite3.Connection, project_id: str, base_id: str
) -> tuple[
    list[RequirementInput],
    list[VariantInput],
    list[IssueInput],
]:
    requirement_rows = connection.execute(
        """
        SELECT * FROM requirements
        WHERE project_id = ? AND validity = 'current'
        ORDER BY display_code ASC
        """,
        (project_id,),
    ).fetchall()
    requirements = [
        RequirementInput(
            requirement_id=row["id"],
            display_code=row["display_code"],
            revision=row["current_revision"],
            parser_key=_infer_parser_key(row),
            parameter_name=row["parameter_name"],
            value_text=row["value_text"],
            unit=row["unit"],
            review_status=row["review_status"],
            category=row["category"],
        )
        for row in requirement_rows
    ]
    variant_rows = connection.execute(
        """
        SELECT * FROM variant_points
        WHERE project_id = ? AND base_id = ? AND status = 'current'
        ORDER BY display_code ASC
        """,
        (project_id, base_id),
    ).fetchall()
    variants = [
        VariantInput(
            variant_id=row["id"],
            revision=row["revision"],
            display_code=row["display_code"],
            parameter_key=row["parameter_key"],
            parameter_name=row["parameter_name"],
            affected_parts=tuple(json.loads(row["affected_parts"] or "[]")),
            basis=row["basis"],
        )
        for row in variant_rows
    ]
    issue_rows = connection.execute(
        """
        SELECT * FROM issues
        WHERE project_id = ? AND status = 'open'
        ORDER BY created_at ASC, id ASC
        """,
        (project_id,),
    ).fetchall()
    issues = [
        IssueInput(
            issue_id=row["id"],
            parser_key=row["parser_key"],
            issue_type=row["issue_type"],
            message=row["message"],
            severity=row["severity"],
        )
        for row in issue_rows
    ]
    return requirements, variants, issues


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# O7 design review
# ---------------------------------------------------------------------------


def _review_item_content(item: Any) -> dict[str, Any]:
    return {
        "check_point": item.check_point,
        "standard_basis": item.standard_basis,
        "responsible_role": item.responsible_role,
        "dependencies": list(item.dependencies),
    }


def _current_review_items(
    connection: sqlite3.Connection, review_id: str
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT i.id, i.display_code, r.*
        FROM design_review_items i
        JOIN design_review_item_revisions r ON r.item_id = i.id
        WHERE i.review_id = ?
          AND r.revision = (
              SELECT MAX(r2.revision)
              FROM design_review_item_revisions r2
              WHERE r2.item_id = i.id
          )
          AND r.status = 'current'
        ORDER BY i.display_code ASC
        """,
        (review_id,),
    ).fetchall()


def _review_item_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["dependencies"] = json.loads(data["dependencies"] or "[]")
    return data


def _review_confirmation_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    snapshot = json.loads(data.pop("snapshot_json"))
    data["item_snapshot"] = snapshot.get("items", [])
    return data


def _design_review_payload(
    connection: sqlite3.Connection, review_id: str
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT r.*, b.display_code AS base_display_code
        FROM design_reviews r
        LEFT JOIN product_bases b ON b.id = r.base_id
        WHERE r.id = ?
        """,
        (review_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("设计评审不存在", {"review_id": review_id})
    snapshot = json.loads(row["inputs_snapshot"] or "{}")
    items = [
        _review_item_dict(item) for item in _current_review_items(connection, review_id)
    ]
    confirmations = [
        _review_confirmation_dict(confirmation)
        for confirmation in connection.execute(
            """
            SELECT * FROM design_review_confirmations
            WHERE review_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (review_id,),
        ).fetchall()
    ]
    review = {
        "id": row["id"],
        "project_id": row["project_id"],
        "display_code": row["display_code"],
        "base_display_code": row["base_display_code"],
        "revision": row["revision"],
        "status": row["status"],
        "validity": row["validity"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    return {
        "review": review,
        "items": items,
        "inputs_snapshot": snapshot,
        "missing_inputs": snapshot.get("missing_inputs", []),
        "confirmations": confirmations,
        "needs_reconfirmation": row["validity"] == "stale"
        or (
            bool(confirmations)
            and confirmations[-1]["review_revision"] < row["revision"]
        ),
        "mode": "rule",
    }


def _store_review_snapshot(
    snapshot: dict[str, Any], missing_inputs: tuple[str, ...]
) -> str:
    stored = dict(snapshot)
    stored["missing_inputs"] = list(missing_inputs)
    return _json_text(stored)


def generate_design_review(
    connection: sqlite3.Connection,
    project_id: str,
    base_display_code: str,
) -> dict[str, Any]:
    with transaction(connection):
        project = _get_project_row(connection, project_id)
        base = _get_base_row(connection, base_display_code)
        requirements, variants, issues = _load_design_inputs(
            connection, project_id, base["id"]
        )
        draft = build_design_review(
            _design_profile(project, base), requirements, variants, issues
        )
        snapshot_json = _store_review_snapshot(
            draft.inputs_snapshot, draft.missing_inputs
        )
        existing = connection.execute(
            "SELECT * FROM design_reviews WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if existing is None:
            review_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO design_reviews(
                    id, project_id, display_code, base_id, revision,
                    status, inputs_snapshot, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 'draft', ?, ?, ?)
                """,
                (
                    review_id,
                    project_id,
                    f"DR-{project['display_code']}",
                    base["id"],
                    snapshot_json,
                    now,
                    now,
                ),
            )
            for item in draft.items:
                item_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO design_review_items(
                        id, review_id, display_code, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (item_id, review_id, item.display_code, now),
                )
                connection.execute(
                    """
                    INSERT INTO design_review_item_revisions(
                        id, item_id, revision, check_point, standard_basis,
                        responsible_role, dependencies, status, created_at
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, 'current', ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        item_id,
                        item.check_point,
                        item.standard_basis,
                        item.responsible_role,
                        _json_text(list(item.dependencies)),
                        now,
                    ),
                )
            _audit(
                connection,
                project_id=project_id,
                object_type="design_review",
                object_id=review_id,
                object_revision=1,
                action="design_review.generated",
                actor="rule_engine",
                role="system",
                after={
                    "display_code": f"DR-{project['display_code']}",
                    "base_display_code": base_display_code,
                    "item_count": len(draft.items),
                    "missing_inputs": list(draft.missing_inputs),
                },
            )
            return _design_review_payload(connection, review_id)

        review_id = existing["id"]
        if (
            existing["base_id"] == base["id"]
            and existing["inputs_snapshot"] == snapshot_json
            and existing["validity"] == "current"
        ):
            return _design_review_payload(connection, review_id)

        new_revision = int(existing["revision"]) + 1
        connection.execute(
            """
            UPDATE design_reviews SET
                base_id = ?, revision = ?, status = 'draft', validity = 'current',
                inputs_snapshot = ?, updated_at = ?
            WHERE id = ?
            """,
            (base["id"], new_revision, snapshot_json, utc_now(), review_id),
        )
        existing_items = {
            row["display_code"]: row
            for row in connection.execute(
                "SELECT * FROM design_review_items WHERE review_id = ?",
                (review_id,),
            ).fetchall()
        }
        drafted_codes = {item.display_code for item in draft.items}
        for item in draft.items:
            item_row = existing_items.get(item.display_code)
            content = _review_item_content(item)
            if item_row is None:
                item_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO design_review_items(
                        id, review_id, display_code, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (item_id, review_id, item.display_code, utc_now()),
                )
                current = None
            else:
                item_id = item_row["id"]
                current = connection.execute(
                    """
                    SELECT * FROM design_review_item_revisions
                    WHERE item_id = ?
                    ORDER BY revision DESC LIMIT 1
                    """,
                    (item_id,),
                ).fetchone()
            changed = (
                current is None
                or current["status"] != "current"
                or any(
                    current[field] != value
                    for field, value in (
                        ("check_point", content["check_point"]),
                        ("standard_basis", content["standard_basis"]),
                        (
                            "responsible_role",
                            content["responsible_role"],
                        ),
                        (
                            "dependencies",
                            _json_text(content["dependencies"]),
                        ),
                    )
                )
            )
            if not changed:
                continue
            next_revision = 1 if current is None else int(current["revision"]) + 1
            connection.execute(
                """
                INSERT INTO design_review_item_revisions(
                    id, item_id, revision, check_point, standard_basis,
                    responsible_role, dependencies, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'current', ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_id,
                    next_revision,
                    content["check_point"],
                    content["standard_basis"],
                    content["responsible_role"],
                    _json_text(content["dependencies"]),
                    utc_now(),
                ),
            )
        for display_code, item_row in existing_items.items():
            if display_code in drafted_codes:
                continue
            current = connection.execute(
                """
                SELECT * FROM design_review_item_revisions
                WHERE item_id = ?
                ORDER BY revision DESC LIMIT 1
                """,
                (item_row["id"],),
            ).fetchone()
            if current is None or current["status"] == "stale":
                continue
            connection.execute(
                """
                INSERT INTO design_review_item_revisions(
                    id, item_id, revision, check_point, standard_basis,
                    responsible_role, dependencies, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'stale', ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_row["id"],
                    int(current["revision"]) + 1,
                    current["check_point"],
                    current["standard_basis"],
                    current["responsible_role"],
                    current["dependencies"],
                    utc_now(),
                ),
            )
        _audit(
            connection,
            project_id=project_id,
            object_type="design_review",
            object_id=review_id,
            object_revision=new_revision,
            action="design_review.regenerated",
            actor="rule_engine",
            role="system",
            after={
                "base_display_code": base_display_code,
                "item_count": len(draft.items),
                "missing_inputs": list(draft.missing_inputs),
            },
        )
        return _design_review_payload(connection, review_id)


def get_design_review(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT id FROM design_reviews WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("设计评审不存在", {"project_id": project_id})
    return _design_review_payload(connection, row["id"])


def confirm_design_review(
    connection: sqlite3.Connection,
    review_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, Any]:
    with transaction(connection):
        review = connection.execute(
            "SELECT * FROM design_reviews WHERE id = ?", (review_id,)
        ).fetchone()
        if review is None:
            raise NotFoundError("设计评审不存在", {"review_id": review_id})
        if review["validity"] == "stale":
            raise DomainValidationError("设计评审已失效，请重新生成并复核")
        if payload.expected_revision != review["revision"]:
            raise VersionConflictError(
                "设计评审版本已变化，无法确认",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": review["revision"],
                },
            )
        duplicate = connection.execute(
            """
            SELECT 1 FROM design_review_confirmations
            WHERE review_id = ? AND review_revision = ?
            """,
            (review_id, review["revision"]),
        ).fetchone()
        if duplicate is not None:
            raise VersionConflictError(
                "该设计评审版本已有确认记录",
                {"review_revision": review["revision"]},
            )
        items = _current_review_items(connection, review_id)
        if payload.decision == "confirmed" and not items:
            raise DomainValidationError("设计评审没有可确认的检查项")
        snapshot = {
            "review_revision": review["revision"],
            "items": [
                {
                    "item_id": item["id"],
                    "display_code": item["display_code"],
                    "revision": item["revision"],
                    "check_point": item["check_point"],
                }
                for item in items
            ],
        }
        confirmation_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO design_review_confirmations(
                id, review_id, review_revision, actor, role, decision,
                comment, snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                confirmation_id,
                review_id,
                review["revision"],
                payload.actor,
                payload.role,
                payload.decision,
                payload.comment,
                _json_text(snapshot),
                utc_now(),
            ),
        )
        connection.execute(
            """
            UPDATE design_reviews SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (payload.decision, utc_now(), review_id),
        )
        _audit(
            connection,
            project_id=review["project_id"],
            object_type="design_review",
            object_id=review_id,
            object_revision=review["revision"],
            action=f"design_review.{payload.decision}",
            actor=payload.actor,
            role=payload.role,
            decision=payload.decision,
            comment=payload.comment,
            after=snapshot,
        )
        result = _design_review_payload(connection, review_id)
        result["confirmation"] = _review_confirmation_dict(
            connection.execute(
                "SELECT * FROM design_review_confirmations WHERE id = ?",
                (confirmation_id,),
            ).fetchone()
        )
        return result


# ---------------------------------------------------------------------------
# O8 DFMEA
# ---------------------------------------------------------------------------


def _fmea_item_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["dependencies"] = json.loads(data["dependencies"] or "[]")
    data["scores_confirmed"] = bool(data["scores_confirmed"])
    values = (data["severity"], data["occurrence"], data["detection"])
    if all(value is not None for value in values):
        if data["scores_confirmed"]:
            data["rpn"] = (
                int(data["severity"]) * int(data["occurrence"]) * int(data["detection"])
            )
            data["rpn_status"] = "confirmed"
        else:
            data["rpn"] = None
            data["rpn_status"] = "pending_confirmation"
    else:
        data["rpn"] = None
        data["rpn_status"] = "incomplete"
    return data


def _current_fmea_items(
    connection: sqlite3.Connection, fmea_id: str
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT i.id, i.display_code, r.*
        FROM fmea_items i
        JOIN fmea_item_revisions r ON r.item_id = i.id
        WHERE i.fmea_id = ?
          AND r.revision = (
              SELECT MAX(r2.revision)
              FROM fmea_item_revisions r2
              WHERE r2.item_id = i.id
          )
          AND r.status = 'current'
        ORDER BY i.display_code ASC
        """,
        (fmea_id,),
    ).fetchall()


def _fmea_confirmation_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    snapshot = json.loads(data.pop("snapshot_json"))
    data["item_snapshot"] = snapshot.get("items", [])
    return data


def _fmea_payload(connection: sqlite3.Connection, fmea_id: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT f.*, b.display_code AS base_display_code
        FROM fmea_documents f
        LEFT JOIN product_bases b ON b.id = f.base_id
        WHERE f.id = ?
        """,
        (fmea_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("DFMEA 不存在", {"fmea_id": fmea_id})
    snapshot = json.loads(row["inputs_snapshot"] or "{}")
    items = [_fmea_item_dict(item) for item in _current_fmea_items(connection, fmea_id)]
    confirmations = [
        _fmea_confirmation_dict(confirmation)
        for confirmation in connection.execute(
            """
            SELECT * FROM fmea_confirmations
            WHERE fmea_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (fmea_id,),
        ).fetchall()
    ]
    fmea = {
        "id": row["id"],
        "project_id": row["project_id"],
        "display_code": row["display_code"],
        "base_display_code": row["base_display_code"],
        "revision": row["revision"],
        "status": row["status"],
        "validity": row["validity"],
        "scale": snapshot.get("scale", {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    return {
        "fmea": fmea,
        "items": items,
        "inputs_snapshot": snapshot,
        "missing_inputs": snapshot.get("missing_inputs", []),
        "confirmations": confirmations,
        "needs_reconfirmation": row["validity"] == "stale"
        or (
            bool(confirmations) and confirmations[-1]["fmea_revision"] < row["revision"]
        ),
        "mode": "rule",
    }


def _store_fmea_snapshot(
    snapshot: dict[str, Any], missing_inputs: tuple[str, ...]
) -> str:
    stored = dict(snapshot)
    stored["missing_inputs"] = list(missing_inputs)
    return _json_text(stored)


def _fmea_item_content(item: Any) -> dict[str, Any]:
    return {
        "function_text": item.function_text,
        "failure_mode": item.failure_mode,
        "cause": item.cause,
        "effect": item.effect,
        "control": item.control,
        "action_text": item.action_text,
        "dependencies": list(item.dependencies),
    }


def _insert_fmea_item(
    connection: sqlite3.Connection,
    fmea_id: str,
    item: Any,
    *,
    revision: int,
    severity: int | None = None,
    occurrence: int | None = None,
    detection: int | None = None,
) -> str:
    item_id = str(uuid.uuid4())
    content = _fmea_item_content(item)
    now = utc_now()
    connection.execute(
        """
        INSERT INTO fmea_items(
            id, fmea_id, display_code, created_at
        ) VALUES (?, ?, ?, ?)
        """,
        (item_id, fmea_id, item.display_code, now),
    )
    connection.execute(
        """
        INSERT INTO fmea_item_revisions(
            id, item_id, revision, function_text, failure_mode,
            cause, effect, control, action_text, severity,
            occurrence, detection, scores_confirmed, dependencies,
            status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                  'current', ?)
        """,
        (
            str(uuid.uuid4()),
            item_id,
            revision,
            content["function_text"],
            content["failure_mode"],
            content["cause"],
            content["effect"],
            content["control"],
            content["action_text"],
            severity,
            occurrence,
            detection,
            _json_text(content["dependencies"]),
            now,
        ),
    )
    return item_id


def generate_dfmea(
    connection: sqlite3.Connection,
    project_id: str,
    base_display_code: str,
) -> dict[str, Any]:
    with transaction(connection):
        project = _get_project_row(connection, project_id)
        base = _get_base_row(connection, base_display_code)
        requirements, variants, _ = _load_design_inputs(
            connection, project_id, base["id"]
        )
        draft = build_dfmea(_design_profile(project, base), requirements, variants)
        snapshot_json = _store_fmea_snapshot(
            draft.inputs_snapshot, draft.missing_inputs
        )
        existing = connection.execute(
            "SELECT * FROM fmea_documents WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if existing is None:
            fmea_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO fmea_documents(
                    id, project_id, display_code, base_id, revision,
                    status, inputs_snapshot, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 'draft', ?, ?, ?)
                """,
                (
                    fmea_id,
                    project_id,
                    f"DFMEA-{project['display_code']}",
                    base["id"],
                    snapshot_json,
                    now,
                    now,
                ),
            )
            for item in draft.items:
                _insert_fmea_item(connection, fmea_id, item, revision=1)
            _audit(
                connection,
                project_id=project_id,
                object_type="fmea_document",
                object_id=fmea_id,
                object_revision=1,
                action="dfmea.generated",
                actor="rule_engine",
                role="system",
                after={
                    "display_code": f"DFMEA-{project['display_code']}",
                    "base_display_code": base_display_code,
                    "item_count": len(draft.items),
                    "missing_inputs": list(draft.missing_inputs),
                },
            )
            return _fmea_payload(connection, fmea_id)

        fmea_id = existing["id"]
        if (
            existing["base_id"] == base["id"]
            and existing["inputs_snapshot"] == snapshot_json
            and existing["validity"] == "current"
        ):
            return _fmea_payload(connection, fmea_id)

        new_revision = int(existing["revision"]) + 1
        connection.execute(
            """
            UPDATE fmea_documents SET
                base_id = ?, revision = ?, status = 'draft', validity = 'current',
                inputs_snapshot = ?, updated_at = ?
            WHERE id = ?
            """,
            (base["id"], new_revision, snapshot_json, utc_now(), fmea_id),
        )
        existing_items = {
            row["display_code"]: row
            for row in connection.execute(
                "SELECT * FROM fmea_items WHERE fmea_id = ?",
                (fmea_id,),
            ).fetchall()
        }
        drafted_codes = {item.display_code for item in draft.items}
        for item in draft.items:
            item_row = existing_items.get(item.display_code)
            content = _fmea_item_content(item)
            if item_row is None:
                _insert_fmea_item(connection, fmea_id, item, revision=1)
                continue
            item_id = item_row["id"]
            current = connection.execute(
                """
                SELECT * FROM fmea_item_revisions
                WHERE item_id = ?
                ORDER BY revision DESC LIMIT 1
                """,
                (item_id,),
            ).fetchone()
            changed = (
                current is None
                or current["status"] != "current"
                or any(
                    current[field] != value
                    for field, value in (
                        ("function_text", content["function_text"]),
                        ("failure_mode", content["failure_mode"]),
                        ("cause", content["cause"]),
                        ("effect", content["effect"]),
                        ("control", content["control"]),
                        (
                            "action_text",
                            content["action_text"],
                        ),
                        (
                            "dependencies",
                            _json_text(content["dependencies"]),
                        ),
                    )
                )
            )
            if not changed:
                continue
            next_revision = 1 if current is None else int(current["revision"]) + 1
            connection.execute(
                """
                INSERT INTO fmea_item_revisions(
                    id, item_id, revision, function_text, failure_mode,
                    cause, effect, control, action_text, severity,
                    occurrence, detection, scores_confirmed,
                    dependencies, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                          'current', ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_id,
                    next_revision,
                    content["function_text"],
                    content["failure_mode"],
                    content["cause"],
                    content["effect"],
                    content["control"],
                    content["action_text"],
                    current["severity"] if current else None,
                    current["occurrence"] if current else None,
                    current["detection"] if current else None,
                    _json_text(content["dependencies"]),
                    utc_now(),
                ),
            )
        for display_code, item_row in existing_items.items():
            if display_code in drafted_codes:
                continue
            current = connection.execute(
                """
                SELECT * FROM fmea_item_revisions
                WHERE item_id = ?
                ORDER BY revision DESC LIMIT 1
                """,
                (item_row["id"],),
            ).fetchone()
            if current is None or current["status"] == "stale":
                continue
            connection.execute(
                """
                INSERT INTO fmea_item_revisions(
                    id, item_id, revision, function_text, failure_mode,
                    cause, effect, control, action_text, severity,
                    occurrence, detection, scores_confirmed,
                    dependencies, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                          'stale', ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_row["id"],
                    int(current["revision"]) + 1,
                    current["function_text"],
                    current["failure_mode"],
                    current["cause"],
                    current["effect"],
                    current["control"],
                    current["action_text"],
                    current["severity"],
                    current["occurrence"],
                    current["detection"],
                    current["dependencies"],
                    utc_now(),
                ),
            )
        _audit(
            connection,
            project_id=project_id,
            object_type="fmea_document",
            object_id=fmea_id,
            object_revision=new_revision,
            action="dfmea.regenerated",
            actor="rule_engine",
            role="system",
            after={
                "base_display_code": base_display_code,
                "item_count": len(draft.items),
                "missing_inputs": list(draft.missing_inputs),
            },
        )
        invalidate_fmea_dependents(connection, project_id)
        return _fmea_payload(connection, fmea_id)


def get_dfmea(connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT id FROM fmea_documents WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("DFMEA 不存在", {"project_id": project_id})
    return _fmea_payload(connection, row["id"])


def _get_fmea_item_current(
    connection: sqlite3.Connection, item_id: str
) -> tuple[sqlite3.Row, sqlite3.Row]:
    item = connection.execute(
        "SELECT * FROM fmea_items WHERE id = ?", (item_id,)
    ).fetchone()
    if item is None:
        raise NotFoundError("DFMEA 条目不存在", {"item_id": item_id})
    current = connection.execute(
        """
        SELECT * FROM fmea_item_revisions
        WHERE item_id = ?
        ORDER BY revision DESC LIMIT 1
        """,
        (item_id,),
    ).fetchone()
    if current is None:
        raise NotFoundError("DFMEA 条目没有版本", {"item_id": item_id})
    if current["status"] != "current":
        raise DomainValidationError(
            "DFMEA 条目已失效，不能编辑",
            {"item_id": item_id, "revision": current["revision"]},
        )
    return item, current


def _fmea_item_response(connection: sqlite3.Connection, item_id: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT i.id, i.display_code, r.*
        FROM fmea_items i
        JOIN fmea_item_revisions r ON r.item_id = i.id
        WHERE i.id = ?
          AND r.revision = (
              SELECT MAX(r2.revision)
              FROM fmea_item_revisions r2
              WHERE r2.item_id = i.id
          )
        """,
        (item_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("DFMEA 条目不存在", {"item_id": item_id})
    return _fmea_item_dict(row)


def _bump_fmea_document(connection: sqlite3.Connection, fmea_id: str) -> int:
    row = connection.execute(
        "SELECT revision FROM fmea_documents WHERE id = ?", (fmea_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("DFMEA 不存在", {"fmea_id": fmea_id})
    new_revision = int(row["revision"]) + 1
    connection.execute(
        """
        UPDATE fmea_documents
        SET revision = ?, status = 'draft', updated_at = ?
        WHERE id = ?
        """,
        (new_revision, utc_now(), fmea_id),
    )
    invalidate_fmea_dependents(connection, _fmea_project_id(connection, fmea_id))
    return new_revision


def _fmea_project_id(connection: sqlite3.Connection, fmea_id: str) -> str:
    row = connection.execute(
        "SELECT project_id FROM fmea_documents WHERE id = ?", (fmea_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("DFMEA 不存在", {"fmea_id": fmea_id})
    return str(row["project_id"])


def update_fmea_item(
    connection: sqlite3.Connection,
    item_id: str,
    payload: FmeaItemUpdate,
) -> dict[str, Any]:
    with transaction(connection):
        item, current = _get_fmea_item_current(connection, item_id)
        if payload.expected_revision != current["revision"]:
            raise VersionConflictError(
                "DFMEA 条目版本已变化，无法保存",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": current["revision"],
                },
            )
        provided = payload.model_fields_set
        changes: dict[str, Any] = {}
        for field in EDITABLE_FMEA_FIELDS:
            if field not in provided:
                continue
            value = getattr(payload, field)
            if value is not None and value != current[field]:
                changes[field] = value
        if not changes:
            return _fmea_item_response(connection, item_id)

        values = {field: current[field] for field in EDITABLE_FMEA_FIELDS}
        values.update(changes)
        next_revision = int(current["revision"]) + 1
        connection.execute(
            """
            INSERT INTO fmea_item_revisions(
                id, item_id, revision, function_text, failure_mode,
                cause, effect, control, action_text, severity,
                occurrence, detection, scores_confirmed, dependencies,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                      'current', ?)
            """,
            (
                str(uuid.uuid4()),
                item_id,
                next_revision,
                values["function_text"],
                values["failure_mode"],
                values["cause"],
                values["effect"],
                values["control"],
                values["action_text"],
                values["severity"],
                values["occurrence"],
                values["detection"],
                current["dependencies"],
                utc_now(),
            ),
        )
        document_revision = _bump_fmea_document(connection, item["fmea_id"])
        project_id = _fmea_project_id(connection, item["fmea_id"])
        _audit(
            connection,
            project_id=project_id,
            object_type="fmea_item",
            object_id=item_id,
            object_revision=next_revision,
            action="fmea_item.updated",
            actor=payload.actor,
            role=payload.role,
            before=dict(current),
            after=values,
        )
        _audit(
            connection,
            project_id=project_id,
            object_type="fmea_document",
            object_id=item["fmea_id"],
            object_revision=document_revision,
            action="fmea_document.reopened_for_edit",
            actor=payload.actor,
            role=payload.role,
            after={"item_id": item_id, "item_revision": next_revision},
        )
        return _fmea_item_response(connection, item_id)


def confirm_fmea_item_scores(
    connection: sqlite3.Connection,
    item_id: str,
    payload: FmeaScoreConfirmation,
) -> dict[str, Any]:
    with transaction(connection):
        item, current = _get_fmea_item_current(connection, item_id)
        if payload.expected_revision != current["revision"]:
            raise VersionConflictError(
                "DFMEA 条目版本已变化，无法确认评分",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": current["revision"],
                },
            )
        missing = [
            field
            for field in ("severity", "occurrence", "detection")
            if current[field] is None
        ]
        if missing:
            raise DomainValidationError(
                "S/O/D 评分不完整，无法确认",
                {"item_id": item_id, "missing_scores": missing},
            )
        if current["scores_confirmed"]:
            return _fmea_item_response(connection, item_id)

        next_revision = int(current["revision"]) + 1
        connection.execute(
            """
            INSERT INTO fmea_item_revisions(
                id, item_id, revision, function_text, failure_mode,
                cause, effect, control, action_text, severity,
                occurrence, detection, scores_confirmed, dependencies,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?,
                      'current', ?)
            """,
            (
                str(uuid.uuid4()),
                item_id,
                next_revision,
                current["function_text"],
                current["failure_mode"],
                current["cause"],
                current["effect"],
                current["control"],
                current["action_text"],
                current["severity"],
                current["occurrence"],
                current["detection"],
                current["dependencies"],
                utc_now(),
            ),
        )
        document_revision = _bump_fmea_document(connection, item["fmea_id"])
        project_id = _fmea_project_id(connection, item["fmea_id"])
        _audit(
            connection,
            project_id=project_id,
            object_type="fmea_item",
            object_id=item_id,
            object_revision=next_revision,
            action="fmea_item.scores_confirmed",
            actor=payload.actor,
            role=payload.role,
            decision="confirmed",
            comment=payload.comment,
            after={
                "severity": current["severity"],
                "occurrence": current["occurrence"],
                "detection": current["detection"],
                "rpn": (
                    current["severity"] * current["occurrence"] * current["detection"]
                ),
            },
        )
        _audit(
            connection,
            project_id=project_id,
            object_type="fmea_document",
            object_id=item["fmea_id"],
            object_revision=document_revision,
            action="fmea_document.reopened_for_score_confirmation",
            actor=payload.actor,
            role=payload.role,
            after={"item_id": item_id, "item_revision": next_revision},
        )
        return _fmea_item_response(connection, item_id)


def confirm_dfmea(
    connection: sqlite3.Connection,
    fmea_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, Any]:
    with transaction(connection):
        document = connection.execute(
            "SELECT * FROM fmea_documents WHERE id = ?", (fmea_id,)
        ).fetchone()
        if document is None:
            raise NotFoundError("DFMEA 不存在", {"fmea_id": fmea_id})
        if document["validity"] == "stale":
            raise DomainValidationError("DFMEA 已失效，请重新生成并复核")
        if payload.expected_revision != document["revision"]:
            raise VersionConflictError(
                "DFMEA 版本已变化，无法确认",
                {
                    "expected_revision": payload.expected_revision,
                    "current_revision": document["revision"],
                },
            )
        duplicate = connection.execute(
            """
            SELECT 1 FROM fmea_confirmations
            WHERE fmea_id = ? AND fmea_revision = ?
            """,
            (fmea_id, document["revision"]),
        ).fetchone()
        if duplicate is not None:
            raise VersionConflictError(
                "该 DFMEA 版本已有确认记录",
                {"fmea_revision": document["revision"]},
            )
        items = [
            _fmea_item_dict(row) for row in _current_fmea_items(connection, fmea_id)
        ]
        if payload.decision == "confirmed":
            unconfirmed = [
                {
                    "item_id": item["id"],
                    "display_code": item["display_code"],
                    "reason": (
                        "S/O/D 不完整"
                        if item["rpn_status"] == "incomplete"
                        else "评分未确认"
                    ),
                }
                for item in items
                if not item["scores_confirmed"]
            ]
            if unconfirmed:
                raise DomainValidationError(
                    "存在未确认的 DFMEA 评分",
                    {"unconfirmed_items": unconfirmed},
                )
        snapshot = {
            "fmea_revision": document["revision"],
            "items": [
                {
                    "item_id": item["id"],
                    "display_code": item["display_code"],
                    "revision": item["revision"],
                    "severity": item["severity"],
                    "occurrence": item["occurrence"],
                    "detection": item["detection"],
                    "rpn": item["rpn"],
                }
                for item in items
            ],
        }
        confirmation_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO fmea_confirmations(
                id, fmea_id, fmea_revision, actor, role, decision,
                comment, snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                confirmation_id,
                fmea_id,
                document["revision"],
                payload.actor,
                payload.role,
                payload.decision,
                payload.comment,
                _json_text(snapshot),
                utc_now(),
            ),
        )
        connection.execute(
            """
            UPDATE fmea_documents SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (payload.decision, utc_now(), fmea_id),
        )
        _audit(
            connection,
            project_id=document["project_id"],
            object_type="fmea_document",
            object_id=fmea_id,
            object_revision=document["revision"],
            action=f"dfmea.{payload.decision}",
            actor=payload.actor,
            role=payload.role,
            decision=payload.decision,
            comment=payload.comment,
            after=snapshot,
        )
        result = _fmea_payload(connection, fmea_id)
        result["confirmation"] = _fmea_confirmation_dict(
            connection.execute(
                "SELECT * FROM fmea_confirmations WHERE id = ?",
                (confirmation_id,),
            ).fetchone()
        )
        return result


def mark_design_stale_for_requirement(
    connection: sqlite3.Connection, project_id: str, requirement_id: str
) -> None:
    """Invalidate dependent documents inside the caller's change transaction."""
    for table, object_type in (
        ("design_reviews", "design_review"),
        ("fmea_documents", "fmea_document"),
    ):
        rows = connection.execute(
            f"SELECT * FROM {table} WHERE project_id = ? AND validity = 'current'",
            (project_id,),
        ).fetchall()
        for row in rows:
            snapshot = json.loads(row["inputs_snapshot"])
            if not any(
                item.get("requirement_id") == requirement_id
                for item in snapshot.get("requirements", [])
            ):
                continue
            connection.execute(
                f"UPDATE {table} SET validity = 'stale', updated_at = ? WHERE id = ?",
                (utc_now(), row["id"]),
            )
            _audit(
                connection,
                project_id=project_id,
                object_type=object_type,
                object_id=row["id"],
                object_revision=row["revision"],
                action=f"{object_type}.stale",
                after={"requirement_id": requirement_id, "validity": "stale"},
            )
