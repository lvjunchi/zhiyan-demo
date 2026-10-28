"""Controlled synthetic candidates; the engineering part itself stores versioned choices."""

from __future__ import annotations
import sqlite3
from pydantic import BaseModel, ConfigDict, Field
from . import engineering_versions
from .db import transaction, utc_now
from .errors import DomainValidationError, VersionConflictError


class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=1, max_length=2000)


def candidates(
    connection: sqlite3.Connection, project_id: str, name: str
) -> list[dict[str, object]]:
    requirements = connection.execute(
        "SELECT * FROM requirements WHERE project_id=? ORDER BY id", (project_id,)
    ).fetchall()
    output = []
    for item in connection.execute(
        "SELECT * FROM part_candidates WHERE part_name=? ORDER BY rated_torque_nm,model_code",
        (name,),
    ):
        checks = []
        for row in requirements:
            key = row["parser_key"]
            if key not in ("engineMaxTorque", "gearboxRatedInputTorque", "gearCount"):
                continue
            value = row["value_num"]
            actual = (
                item["max_gears"] if key == "gearCount" else item["rated_torque_nm"]
            )
            valid_unit = row["unit"] in (
                ("档", "") if key == "gearCount" else ("N·m", "Nm", "N*m", "N.m")
            )
            result = (
                "incomplete"
                if value is None or not valid_unit
                else "pass" if actual >= value else "fail"
            )
            checks.append(
                {
                    "requirement_id": row["id"],
                    "revision": row["current_revision"],
                    "display_code": row["display_code"],
                    "parameter": row["parameter_name"],
                    "required": value,
                    "unit": row["unit"],
                    "capacity": actual,
                    "comparison": ">=",
                    "result": result,
                    "review_status": row["review_status"],
                }
            )
        has_torque = any(
            row["parser_key"] in ("engineMaxTorque", "gearboxRatedInputTorque")
            for row in requirements
        )
        has_gears = any(row["parser_key"] == "gearCount" for row in requirements)
        fit = (
            "fail"
            if any(check["result"] == "fail" for check in checks)
            else (
                "incomplete"
                if not has_torque
                or not has_gears
                or any(check["result"] == "incomplete" for check in checks)
                else "pass"
            )
        )
        output.append(
            {
                **dict(item),
                "fit": fit,
                "checks": checks,
                "limitations": "仅核对已登记的扭矩/档数包络；材料、几何接口与制造适用性需工程师另行核对。",
            }
        )
    return output


def list_choices(connection: sqlite3.Connection, project_id: str) -> dict[str, object]:
    records = engineering_versions.list_records(connection, project_id)
    groups = []
    for row in records:
        if row["kind"] != "part" or not row["is_applicable"]:
            continue
        options = candidates(connection, project_id, str(row["part_name"]))
        selected = next(
            (item for item in options if item["model_code"] == row["part_number"]), None
        )
        state = (
            "unselected"
            if selected is None
            else (
                "recheck"
                if row["status"] == "stale" or selected["fit"] != "pass"
                else (
                    "confirmed"
                    if row["review_status"] == "confirmed"
                    else (
                        "rejected"
                        if row["review_status"] == "rejected"
                        else "pending_review"
                    )
                )
            )
        )
        groups.append(
            {
                "record": row,
                "candidates": options,
                "selected_candidate_id": selected["id"] if selected else None,
                "selection_state": state,
                "confirmation_blockers": engineering_versions.confirmation_blockers(
                    connection, row
                )
                + (
                    ["本版已失效，请重新运行变型分析"]
                    if row["status"] != "current"
                    else []
                )
                + (
                    ["选定候选不满足当前约束，请重新选择型号"]
                    if selected and selected["fit"] != "pass"
                    else []
                ),
            }
        )
    counts = {
        key: sum(group["selection_state"] == key for group in groups)
        for key in ("unselected", "pending_review", "confirmed", "rejected", "recheck")
    }
    return {
        "parts": groups,
        "counts": counts,
        "mode": "rule",
        "catalog_source": "合成候选库V1，24个型号；示意图不代表制造图纸",
    }


def select(
    connection: sqlite3.Connection, object_id: str, payload: SelectionRequest
) -> dict[str, object]:
    from .services import _audit_engineering_change
    from .consistency_services import mark_consistency_checks_stale

    with transaction(connection):
        row = engineering_versions.record(connection, "part", object_id)
        if (
            row["revision"] != payload.expected_revision
            or row["status"] != "current"
            or not row["is_applicable"]
        ):
            raise VersionConflictError("工程决策已更新或待复核，请先重新运行变型分析")
        candidate = next(
            (
                item
                for item in candidates(
                    connection, str(row["project_id"]), str(row["part_name"])
                )
                if item["id"] == payload.candidate_id
            ),
            None,
        )
        if candidate is None:
            raise DomainValidationError("候选型号与零件类别不匹配或不存在")
        if candidate["fit"] != "pass":
            raise DomainValidationError(
                "候选不满足当前约束或缺少依据", {"checks": candidate["checks"]}
            )
        if row["part_number"] == candidate["model_code"]:
            return row
        connection.execute(
            "UPDATE reusable_part_decisions SET part_number=?,source=?,reason=?,updated_at=? WHERE id=?",
            (
                candidate["model_code"],
                f"{candidate['source']}；candidate_id={candidate['id']}",
                f"已人工选择候选 {candidate['model_code']}；{payload.comment}；{candidate['limitations']}",
                utc_now(),
                object_id,
            ),
        )
        _audit_engineering_change(
            connection,
            project_id=row["project_id"],
            object_type="reusable_part_decision",
            object_id=object_id,
            object_revision=None,
            action="part_candidate.selected",
            actor=payload.actor,
            role=payload.role,
            comment=payload.comment,
            before=row,
        )
        mark_consistency_checks_stale(
            connection, str(row["project_id"]), "零件候选型号变更，需复检"
        )
        return engineering_versions.record(connection, "part", object_id)


def validate_confirmation(
    connection: sqlite3.Connection, row: dict[str, object]
) -> None:
    if not str(row["part_number"]).startswith("DEMO-"):
        return
    candidate = next(
        (
            item
            for item in candidates(
                connection, str(row["project_id"]), str(row["part_name"])
            )
            if item["model_code"] == row["part_number"]
        ),
        None,
    )
    if not candidate or candidate["fit"] != "pass":
        raise DomainValidationError("选定候选不再满足当前约束，请重新选型")
