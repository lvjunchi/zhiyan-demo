"""Immutable uploaded source bytes, separate from human-reviewed text."""

from __future__ import annotations

import base64
import binascii
import hashlib
import sqlite3

from .db import utc_now
from .document_text import extract_text
from .errors import DomainValidationError, NotFoundError
from .schemas import SourceOriginal


def store(
    connection: sqlite3.Connection,
    source_id: str,
    original: SourceOriginal,
    reviewed_text: str,
) -> None:
    try:
        content = base64.b64decode(original.data_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise DomainValidationError("原始文件编码损坏") from exc
    if hashlib.sha256(content).hexdigest() != original.sha256:
        raise DomainValidationError("原始文件 SHA-256 不匹配")
    extracted = extract_text(original.filename, content)
    text = str(extracted["content"])
    media_type = {
        "txt": "text/plain; charset=utf-8",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }[str(extracted["format"])]
    connection.execute(
        """INSERT INTO source_document_files
        (source_document_id,filename,media_type,sha256,size_bytes,content,extracted_text_hash,reviewed_text_changed,archived_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            source_id,
            original.filename,
            media_type,
            original.sha256,
            len(content),
            content,
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
            int(text != reviewed_text),
            utc_now(),
        ),
    )


def metadata(
    connection: sqlite3.Connection, source_id: str
) -> dict[str, object] | None:
    row = connection.execute(
        """SELECT source_document_id,filename,media_type,sha256,size_bytes,
        extracted_text_hash,reviewed_text_changed,archived_at FROM source_document_files WHERE source_document_id=?""",
        (source_id,),
    ).fetchone()
    return (
        {**dict(row), "reviewed_text_changed": bool(row["reviewed_text_changed"])}
        if row
        else None
    )


def list_sources(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, object]]:
    if not connection.execute(
        "SELECT 1 FROM projects WHERE id=?", (project_id,)
    ).fetchone():
        raise NotFoundError("项目不存在")
    return [
        {
            **dict(row),
            "original_file": metadata(connection, row["id"]),
            "parse_summary": parse_summary(connection, row["id"], row["parsed_at"]),
        }
        for row in connection.execute(
            "SELECT * FROM source_documents WHERE project_id=? ORDER BY created_at,display_code,version",
            (project_id,),
        )
    ]


def parse_summary(
    connection: sqlite3.Connection, source_id: str, parsed_at: str | None
) -> dict[str, object]:
    requirements = connection.execute(
        """SELECT COUNT(*) AS total,
        COALESCE(SUM(review_status IN ('draft','pending_review')),0) AS pending
        FROM requirements WHERE source_document_id=?""",
        (source_id,),
    ).fetchone()
    issues = connection.execute(
        """SELECT COUNT(*) AS total,
        COALESCE(SUM(status='open'),0) AS open_count FROM issues WHERE source_document_id=?""",
        (source_id,),
    ).fetchone()
    return {
        "status": (
            "pending_parse"
            if parsed_at is None
            else "parsed" if requirements["total"] else "needs_manual_review"
        ),
        "requirement_count": requirements["total"],
        "pending_requirement_count": requirements["pending"],
        "issue_count": issues["total"],
        "open_issue_count": issues["open_count"],
        "closed_issue_count": issues["total"] - issues["open_count"],
    }


def download(connection: sqlite3.Connection, source_id: str) -> tuple[bytes, str, str]:
    row = connection.execute(
        "SELECT * FROM source_document_files WHERE source_document_id=?", (source_id,)
    ).fetchone()
    if not row:
        raise NotFoundError("该文档未归档原始文件；历史正文不能替代原件")
    content = bytes(row["content"])
    if (
        len(content) != row["size_bytes"]
        or hashlib.sha256(content).hexdigest() != row["sha256"]
    ):
        raise DomainValidationError("归档原件完整性校验失败")
    return content, row["filename"], row["media_type"]
