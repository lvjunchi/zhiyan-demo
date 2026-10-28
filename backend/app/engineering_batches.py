"""Confirm an explicit engineering scope atomically using individual review rules."""

from __future__ import annotations

import sqlite3
from pydantic import BaseModel, ConfigDict, Field, model_validator
from . import engineering_versions
from .db import transaction
from .errors import DomainValidationError, VersionConflictError
from .schemas import ArtifactConfirmationCreate


class BatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: engineering_versions.Kind
    object_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1)


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    items: list[BatchItem] = Field(min_length=1, max_length=100)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_items(self):
        if len({(item.kind, item.object_id) for item in self.items}) != len(self.items):
            raise ValueError("批量范围包含重复对象")
        return self


def confirm(
    connection: sqlite3.Connection, project_id: str, payload: BatchRequest
) -> dict[str, int]:
    with transaction(connection):
        # Variants precede parts in the same transaction, never partially committed.
        for item in sorted(payload.items, key=lambda value: value.kind != "variant"):
            row = engineering_versions.record(connection, item.kind, item.object_id)
            if row["project_id"] != project_id or not row["is_applicable"]:
                raise DomainValidationError("确认范围包含其他项目或已不适用的工程对象")
            if row["review_status"] not in ("draft", "pending_review"):
                raise VersionConflictError("确认范围已有审核决定，请重新读取并核对范围")
            # Review the generated engineering decision just as a single review does.
            # Explicit candidate selections are validated by _confirm_in_transaction.
            engineering_versions._confirm_in_transaction(
                connection,
                item.kind,
                item.object_id,
                ArtifactConfirmationCreate(
                    expected_revision=item.expected_revision,
                    actor=payload.actor,
                    role=payload.role,
                    decision="confirmed",
                    comment="批量核对工程版本后确认",
                ),
            )
    return {"confirmed_count": len(payload.items)}
