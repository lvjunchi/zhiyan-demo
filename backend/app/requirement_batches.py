"""Preview and atomically confirm an explicit, versioned requirement scope."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import services
from .db import transaction
from .domain.parser import UNITLESS_NUMERIC_KEYS
from .domain.values import normalize_value
from .errors import DomainValidationError, VersionConflictError
from .schemas import ConfirmationCreate

KNOWN_UNITS = {
    "N·m",
    "Nm",
    "N*m",
    "N.m",
    "kg",
    "g",
    "t",
    "kW",
    "W",
    "r/min",
    "rpm",
    "km",
    "万km",
    "h",
    "mm",
    "m",
    "℃",
    "°C",
    "档",
    "dB(A)",
    "dB",
    "s",
    "ms",
    "kN",
    "MPa",
    "bar",
    "V",
    "A",
    "Hz",
    "%",
}


class BatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    requirement_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1)


class BatchPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BatchItem] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique(self):
        if len({item.requirement_id for item in self.items}) != len(self.items):
            raise ValueError("批次包含重复需求，请重新选择")
        return self


class BatchConfirmRequest(BatchPreviewRequest):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_preview_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=1, max_length=2000)


def preview(
    connection: sqlite3.Connection, project_id: str, items: list[BatchItem]
) -> dict[str, object]:
    services.get_project(connection, project_id)
    rows, evidence = [], []
    for item in sorted(items, key=lambda row: row.requirement_id):
        row = services.get_requirement(connection, item.requirement_id)
        if row["project_id"] != project_id:
            raise DomainValidationError("所选需求不属于当前项目")
        reasons = []
        if row["current_revision"] != item.expected_revision:
            reasons.append("版本已变化，请刷新需求列表")
        if row["review_status"] not in {"draft", "pending_review"}:
            reasons.append("仅可批量确认待审核需求；已确认/驳回记录不自动改变")
        if row["validity"] != "current":
            reasons.append("需求待复核，请先核对有效版本")
        try:
            normalized = normalize_value(
                row["data_type"], row["operator"], row["value_text"]
            )
            if (
                normalized.value_num != row["value_num"]
                or normalized.value_num_high != row["value_num_high"]
            ):
                reasons.append("数值与规范化字段不一致")
        except ValueError as exc:
            reasons.append(str(exc))
        if (
            row["data_type"] in {"numeric", "range"}
            and row["parser_key"] not in UNITLESS_NUMERIC_KEYS
            and row["unit"] not in KNOWN_UNITS
        ):
            reasons.append("单位缺失或不在受控单位范围，请修订或逐条核对")
        if (
            not row["source_document_id"]
            or not row["source_excerpt"].strip()
            or not row["source_location"].strip()
        ):
            reasons.append("来源文档、位置或原文摘录不完整")
        issues = [
            dict(issue)
            for issue in connection.execute(
                """SELECT * FROM issues WHERE project_id=? AND status='open'
            AND (requirement_id=? OR (requirement_id IS NULL AND source_document_id=? AND parser_key=? AND parser_key!='')) ORDER BY id""",
                (
                    project_id,
                    item.requirement_id,
                    row["source_document_id"],
                    row["parser_key"],
                ),
            )
        ]
        reasons.extend(
            issue["message"]
            for issue in issues
            if issue["blocking_reason"] or issue["severity"] == "blocking"
        )
        rows.append({"requirement": row, "eligible": not reasons, "reasons": reasons})
        evidence.append(
            {"requested": item.model_dump(), "requirement": row, "issues": issues}
        )
    digest = hashlib.sha256(
        json.dumps(
            {"project_id": project_id, "scope": evidence},
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "project_id": project_id,
        "selected_count": len(items),
        "rows": rows,
        "can_submit": all(row["eligible"] for row in rows),
        "preview_hash": digest,
    }


def confirm(
    connection: sqlite3.Connection, project_id: str, payload: BatchConfirmRequest
) -> dict[str, object]:
    with transaction(connection):
        checked = preview(connection, project_id, payload.items)
        if checked["preview_hash"] != payload.expected_preview_hash:
            raise VersionConflictError(
                "预览后需求版本、审核或问题状态已变化，请重新核对范围"
            )
        if not checked["can_submit"]:
            raise DomainValidationError(
                "批次存在不可确认项，未提交任何审核", {"rows": checked["rows"]}
            )
        events = []
        for item in payload.items:
            events.append(
                services._confirm_requirement_in_transaction(
                    connection,
                    item.requirement_id,
                    ConfirmationCreate(
                        expected_revision=item.expected_revision,
                        actor=payload.actor,
                        role=payload.role,
                        decision="confirmed",
                        comment=payload.comment,
                    ),
                )
            )
        return {
            "project_id": project_id,
            "confirmed_count": len(events),
            "events": events,
        }
