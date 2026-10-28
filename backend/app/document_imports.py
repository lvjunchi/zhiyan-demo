"""Persist actual file extraction attempts; never treat parsing as requirement approval."""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from pathlib import PurePath
from typing import Literal
from pydantic import BaseModel, ConfigDict

from .db import transaction, utc_now
from .document_text import MAX_FILE_BYTES, extract_text
from .errors import DomainValidationError, NotFoundError, VersionConflictError
from .schemas import SourceOriginal


class DiscardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_status: Literal["awaiting_review"]


def discard(
    connection: sqlite3.Connection, project_id: str, attempt_id: str
) -> dict[str, object]:
    with transaction(connection):
        row = connection.execute(
            "SELECT * FROM document_imports WHERE id=? AND project_id=?",
            (attempt_id, project_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("导入记录不存在")
        if row["status"] != "awaiting_review" or row["source_document_id"] is not None:
            raise VersionConflictError("导入状态已变化，请刷新记录后重试")
        connection.execute(
            "UPDATE document_imports SET status='cancelled',stage='cancelled',updated_at=? WHERE id=?",
            (utc_now(), attempt_id),
        )
        return dict(
            connection.execute(
                "SELECT * FROM document_imports WHERE id=?", (attempt_id,)
            ).fetchone()
        )


def list_imports(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, object]]:
    if not connection.execute(
        "SELECT 1 FROM projects WHERE id=?", (project_id,)
    ).fetchone():
        raise NotFoundError("项目不存在")
    return [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM document_imports WHERE project_id=? ORDER BY created_at DESC,id",
            (project_id,),
        )
    ]


def extract(
    connection: sqlite3.Connection, project_id: str, filename: str, data: bytes
) -> dict[str, object]:
    list_imports(connection, project_id)
    if (
        not filename.strip()
        or len(filename) > 255
        or any(c in filename for c in "/\\:\x00\r\n")
    ):
        raise DomainValidationError("文件名不可包含路径或控制字符")
    attempt_id, now = str(uuid.uuid4()), utc_now()
    result, failure = None, None
    try:
        result = extract_text(filename, data)
    except DomainValidationError as exc:
        failure = exc
    failed_stage = (
        "file_check"
        if len(data) > MAX_FILE_BYTES
        or PurePath(filename).suffix.lower() not in {".docx", ".pdf", ".txt"}
        or not data
        else "text_extraction"
    )
    with transaction(connection):
        connection.execute(
            """INSERT INTO document_imports
            (id,project_id,filename,sha256,size_bytes,status,stage,error_message,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                attempt_id,
                project_id,
                PurePath(filename).name,
                hashlib.sha256(data).hexdigest(),
                len(data),
                "failed" if failure else "awaiting_review",
                failed_stage if failure else "review_text",
                str(failure.message) if failure else "",
                now,
                now,
            ),
        )
    if failure:
        failure.details = {
            **failure.details,
            "stage": failed_stage,
            "import_id": attempt_id,
        }
        raise failure
    return {**result, "import_id": attempt_id}


def link(
    connection: sqlite3.Connection,
    project_id: str,
    source_id: str,
    import_id: str,
    original: SourceOriginal | None,
) -> None:
    row = connection.execute(
        "SELECT * FROM document_imports WHERE id=? AND project_id=?",
        (import_id, project_id),
    ).fetchone()
    if (
        row is None
        or row["status"] != "awaiting_review"
        or original is None
        or original.sha256 != row["sha256"]
        or original.filename != row["filename"]
    ):
        raise DomainValidationError(
            "导入记录与当前项目、文件或状态不匹配，请重新选择文件"
        )
    connection.execute(
        "UPDATE document_imports SET source_document_id=?,status='archived',stage='requirement_parse',updated_at=? WHERE id=?",
        (source_id, utc_now(), import_id),
    )


def mark_parse(connection: sqlite3.Connection, source_id: str, error: str = "") -> None:
    connection.execute(
        "UPDATE document_imports SET status=?,stage=?,error_message=?,updated_at=? WHERE source_document_id=? AND (status != ? OR error_message != ?)",
        (
            "failed" if error else "completed",
            "requirement_parse" if error else "saved",
            error,
            utc_now(),
            source_id,
            "failed" if error else "completed",
            error,
        ),
    )
