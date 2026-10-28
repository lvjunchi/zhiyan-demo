"""Versioned participant progress; no inference from message content."""

from __future__ import annotations
import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .db import transaction, utc_now
from .domain.progress import ProgressRecord, evaluate_progress
from .errors import DomainValidationError, VersionConflictError


class ProgressRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )
    participant: str = Field(min_length=1, max_length=200)
    milestone: str = Field(min_length=1, max_length=200)
    planned_percent: float = Field(ge=0, le=100)
    actual_percent: float = Field(ge=0, le=100)
    artifact_version: str = Field(min_length=1, max_length=100)
    reported_at: datetime
    evidence: str = Field(min_length=1, max_length=2000)
    expected_revision: int = Field(ge=0)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)

    @field_validator("reported_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("进度时间必须带时区")
        return value.astimezone(timezone.utc)


def inputs(connection: sqlite3.Connection, topic_id: str) -> list[dict[str, object]]:
    return [
        json.loads(row["snapshot_json"])
        for row in connection.execute(
            "SELECT snapshot_json FROM coordination_progress WHERE topic_id=? ORDER BY participant,milestone,id",
            (topic_id,),
        )
    ]


def detail(connection: sqlite3.Connection, topic_id: str) -> dict[str, object]:
    from .coordination_services import _topic_row

    topic = _topic_row(connection, topic_id)
    rows = inputs(connection, topic_id)
    return {
        "topic_id": topic_id,
        "rows": rows,
        "assessment": evaluate_progress(
            [
                ProgressRecord(
                    **{key: row[key] for key in ProgressRecord.__dataclass_fields__}
                )
                for row in rows
            ],
            tuple(json.loads(topic["expected_participants"])),
        ),
    }


def save(
    connection: sqlite3.Connection, topic_id: str, payload: ProgressRequest
) -> dict[str, object]:
    from .coordination_services import _topic_row
    from .services import _audit

    with transaction(connection):
        topic = _topic_row(connection, topic_id)
        if payload.participant not in json.loads(topic["expected_participants"]):
            raise DomainValidationError("进度参与方不属于该议题")
        if (
            not datetime.fromisoformat(topic["window_start"])
            <= payload.reported_at
            <= datetime.fromisoformat(topic["window_end"])
        ):
            raise DomainValidationError("进度时间必须位于议题统计窗口内")
        row = connection.execute(
            "SELECT * FROM coordination_progress WHERE topic_id=? AND participant=? AND milestone=?",
            (topic_id, payload.participant, payload.milestone),
        ).fetchone()
        revision = row["revision"] if row else 0
        if revision != payload.expected_revision:
            raise VersionConflictError("进度已更新，请重新读取当前版本")
        before = json.loads(row["snapshot_json"]) if row else None
        if before and payload.reported_at < datetime.fromisoformat(
            before["reported_at"]
        ):
            raise DomainValidationError(
                "新进度不能早于当前记录时间；旧记录保留在历史版本"
            )
        identity = row["id"] if row else str(uuid.uuid4())
        snapshot = {
            "id": identity,
            "revision": revision + 1,
            "participant": payload.participant,
            "milestone": payload.milestone,
            "planned_percent": payload.planned_percent,
            "actual_percent": payload.actual_percent,
            "artifact_version": payload.artifact_version,
            "reported_at": payload.reported_at.isoformat(),
            "evidence": payload.evidence,
        }
        encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        if row:
            connection.execute(
                "UPDATE coordination_progress SET revision=?,snapshot_json=? WHERE id=?",
                (revision + 1, encoded, identity),
            )
        else:
            connection.execute(
                "INSERT INTO coordination_progress VALUES (?,?,?,?,?,?)",
                (
                    identity,
                    topic_id,
                    payload.participant,
                    payload.milestone,
                    1,
                    encoded,
                ),
            )
        connection.execute(
            "INSERT INTO coordination_progress_revisions VALUES (?,?,?,?)",
            (identity, revision + 1, encoded, utc_now()),
        )
        _audit(
            connection,
            project_id=topic["project_id"],
            object_type="coordination_progress",
            object_id=identity,
            object_revision=revision + 1,
            action="coordination.progress.saved",
            actor=payload.actor,
            role=payload.role,
            before=before,
            after=snapshot,
        )
        return detail(connection, topic_id)


def validate_store(connection: sqlite3.Connection) -> None:
    for row in connection.execute("SELECT * FROM coordination_progress"):
        snapshot = json.loads(row["snapshot_json"])
        versions = connection.execute(
            "SELECT * FROM coordination_progress_revisions WHERE progress_id=? ORDER BY revision",
            (row["id"],),
        ).fetchall()
        if [item["revision"] for item in versions] != list(
            range(1, row["revision"] + 1)
        ) or versions[-1]["snapshot_json"] != row["snapshot_json"]:
            raise DomainValidationError("协同进度当前记录与版本历史不一致")
        topic = connection.execute(
            "SELECT * FROM coordination_topics WHERE id=?", (row["topic_id"],)
        ).fetchone()
        previous_time = None
        for version in versions:
            snapshot = json.loads(version["snapshot_json"])
            if (
                not isinstance(snapshot, dict)
                or snapshot.get("id") != row["id"]
                or snapshot.get("revision") != version["revision"]
                or snapshot.get("participant") != row["participant"]
                or snapshot.get("milestone") != row["milestone"]
            ):
                raise DomainValidationError("协同进度版本身份不一致")
            fields = {
                key: value
                for key, value in snapshot.items()
                if key not in ("id", "revision")
            }
            checked = ProgressRequest.model_validate(
                {
                    **fields,
                    "expected_revision": version["revision"] - 1,
                    "actor": "备份校验",
                    "role": "validator",
                }
            )
            if (
                not topic
                or checked.participant not in json.loads(topic["expected_participants"])
                or not datetime.fromisoformat(topic["window_start"])
                <= checked.reported_at
                <= datetime.fromisoformat(topic["window_end"])
                or (previous_time is not None and checked.reported_at < previous_time)
            ):
                raise DomainValidationError("协同进度版本参与方或时间不合法")
            previous_time = checked.reported_at
