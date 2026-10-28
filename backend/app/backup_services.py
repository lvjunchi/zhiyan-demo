"""Complete offline SQLite snapshots; restore to a new file without overwriting user data."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .db import connect, run_migrations, transaction, utc_now
from .domain.values import normalize_value
from .errors import ApiError, DomainValidationError, VersionConflictError
from .services import _audit
from .engineering_versions import validate_store

MAX_IMAGE_BYTES = 32 * 1024 * 1024


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["zhiyan.sqlite-backup.v1"]
    schema_version: str = Field(min_length=1, max_length=100)
    created_at: str = Field(min_length=1, max_length=100)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    counts: dict[str, int]
    database_base64: str = Field(max_length=MAX_IMAGE_BYTES * 4 // 3 + 8)


class RestorePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    backup: Snapshot


class RestoreRequest(RestorePreview):
    expected_state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)


class PersistenceError(ApiError):
    code = "PERSISTENCE_ERROR"


def _schema(connection: sqlite3.Connection) -> list[tuple[str, str, str]]:
    return [
        tuple(row)
        for row in connection.execute(
            "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
        )
    ]


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [name for kind, name, _ in _schema(connection) if kind == "table"]
    return {
        name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in tables
    }


def _image(connection: sqlite3.Connection) -> bytes:
    memory = sqlite3.connect(":memory:")
    try:
        connection.backup(memory)
        image = bytearray(memory.serialize())
        # A snapshot contains all committed WAL pages; encode a standalone image.
        image[18:20] = b"\x01\x01"
        return bytes(image)
    finally:
        memory.close()


def create_backup(connection: sqlite3.Connection) -> dict[str, object]:
    image = _image(connection)
    if len(image) > MAX_IMAGE_BYTES:
        raise DomainValidationError(
            "当前数据库超过 32 MiB 备份上限，请使用本地管理工具备份"
        )
    stage = sqlite3.connect(":memory:")
    try:
        stage.deserialize(image)
        return {
            "format": "zhiyan.sqlite-backup.v1",
            "created_at": utc_now(),
            "schema_version": stage.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0],
            "sha256": hashlib.sha256(image).hexdigest(),
            "counts": _counts(stage),
            "database_base64": base64.b64encode(image).decode("ascii"),
        }
    finally:
        stage.close()


def validate_snapshot(
    snapshot: Snapshot,
) -> tuple[bytes, dict[str, int], list[dict[str, str]]]:
    try:
        image = base64.b64decode(snapshot.database_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DomainValidationError("备份编码损坏") from exc
    if len(image) > MAX_IMAGE_BYTES or not image.startswith(b"SQLite format 3\x00"):
        raise DomainValidationError("备份不是受支持的 SQLite 数据快照")
    if hashlib.sha256(image).hexdigest() != snapshot.sha256:
        raise DomainValidationError("备份校验值不匹配，文件可能已损坏")
    stage = sqlite3.connect(":memory:")
    expected = connect(":memory:")
    try:
        version = run_migrations(expected)
        stage.deserialize(image)
        stage.row_factory = sqlite3.Row
        stage.execute("PRAGMA trusted_schema=OFF")
        stage.execute("PRAGMA query_only=ON")
        if version != snapshot.schema_version or _schema(stage) != _schema(expected):
            raise DomainValidationError("备份结构或版本与当前系统不兼容")
        if {
            row[0] for row in stage.execute("SELECT version FROM schema_migrations")
        } != {
            row[0] for row in expected.execute("SELECT version FROM schema_migrations")
        }:
            raise DomainValidationError("备份迁移记录不完整")
        if (
            stage.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or stage.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise DomainValidationError("备份完整性或引用校验失败")
        values = [dict(row) for row in stage.execute("SELECT * FROM requirements")]
        values.extend(
            json.loads(row[0])
            for row in stage.execute("SELECT snapshot_json FROM requirement_revisions")
        )
        for row in values:
            normalized = normalize_value(
                row["data_type"], row["operator"], row["value_text"]
            )
            if normalized.value_num != row["value_num"]:
                raise DomainValidationError("备份数值与规范化数据不一致")
            if normalized.value_num_high != row.get("value_num_high"):
                raise DomainValidationError("备份范围数据不一致")
        cross_project = stage.execute(
            """SELECT 1 FROM requirements r JOIN source_documents s ON s.id=r.source_document_id
            WHERE r.project_id != s.project_id UNION ALL
            SELECT 1 FROM requirement_references x JOIN requirements a ON a.id=x.requirement_id
            JOIN requirements b ON b.id=x.referenced_requirement_id WHERE a.project_id != b.project_id LIMIT 1"""
        ).fetchone()
        if cross_project:
            raise DomainValidationError("备份包含跨项目引用")
        for row in stage.execute(
            "SELECT content,content_hash,size_bytes FROM sample_delivery_files"
        ):
            if (
                len(row["content"]) != row["size_bytes"]
                or hashlib.sha256(row["content"]).hexdigest() != row["content_hash"]
            ):
                raise DomainValidationError("备份样件文件与归档校验值不一致")
        for row in stage.execute(
            "SELECT original_text,content_hash FROM source_documents"
        ):
            if (
                not isinstance(row["original_text"], str)
                or hashlib.sha256(row["original_text"].encode("utf-8")).hexdigest()
                != row["content_hash"]
            ):
                raise DomainValidationError("备份来源正文与归档校验值不一致")
        for row in stage.execute(
            "SELECT content,sha256,size_bytes FROM source_document_files"
        ):
            if (
                len(row["content"]) != row["size_bytes"]
                or hashlib.sha256(row["content"]).hexdigest() != row["sha256"]
            ):
                raise DomainValidationError("备份来源原件与归档校验值不一致")
        for row in stage.execute(
            "SELECT snapshot_json,snapshot_hash,zip_content,zip_hash,zip_size FROM material_packages"
        ):
            if (
                not isinstance(row["snapshot_json"], str)
                or hashlib.sha256(row["snapshot_json"].encode("utf-8")).hexdigest()
                != row["snapshot_hash"]
            ):
                raise DomainValidationError("备份材料快照与归档校验值不一致")
            if (
                len(row["zip_content"]) != row["zip_size"]
                or hashlib.sha256(row["zip_content"]).hexdigest() != row["zip_hash"]
            ):
                raise DomainValidationError("备份材料附件与归档校验值不一致")
        counts = _counts(stage)
        validate_store(stage)
        from .coordination_progress import validate_store as validate_progress

        validate_progress(stage)
        if counts != snapshot.counts:
            raise DomainValidationError("备份清单与数据数量不一致")
        projects = [
            dict(row)
            for row in stage.execute(
                "SELECT id,display_code,name FROM projects ORDER BY display_code"
            )
        ]
        return image, counts, projects
    except (sqlite3.DatabaseError, ValueError, TypeError, IndexError, KeyError) as exc:
        raise DomainValidationError("备份内容不合法，未修改当前数据") from exc
    finally:
        stage.close()
        expected.close()


def _pointer(base: Path) -> Path:
    return base.with_name(f".{base.name}.active.json")


def active_database(base: Path) -> Path:
    pointer = _pointer(base)
    if not pointer.exists():
        return base
    record = json.loads(pointer.read_text(encoding="utf-8"))
    name = record.get("filename", "")
    if not isinstance(name, str) or not re.fullmatch(r"[0-9a-f]{32}\.db", name):
        raise RuntimeError("恢复指针损坏，请检查本地数据配置")
    path = base.parent / f".{base.name}.restores" / name
    if not path.is_file():
        raise RuntimeError("恢复数据文件缺失，未回退或覆盖原始数据库")
    return path


def _activate_database(base: Path, restored: Path) -> None:
    pointer = _pointer(base)
    pending = pointer.with_name(f"{pointer.name}.{uuid.uuid4().hex}.tmp")
    try:
        with pending.open("x", encoding="utf-8") as handle:
            json.dump({"filename": restored.name, "activated_at": utc_now()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, pointer)
    finally:
        pending.unlink(missing_ok=True)


def restore_database(
    connection: sqlite3.Connection, base: Path, payload: RestoreRequest
) -> Path:
    image, _, _ = validate_snapshot(payload.backup)
    if create_backup(connection)["sha256"] != payload.expected_state_hash:
        raise VersionConflictError("校验后数据已发生变化，请重新预览备份再恢复")
    directory = base.parent / f".{base.name}.restores"
    restored = directory / f"{uuid.uuid4().hex}.db"
    try:
        directory.mkdir(exist_ok=True)
        with restored.open("xb") as handle:
            handle.write(image)
            handle.flush()
            os.fsync(handle.fileno())
        restored_connection = connect(restored)
        try:
            with transaction(restored_connection):
                for row in restored_connection.execute(
                    "SELECT id FROM projects"
                ).fetchall():
                    _audit(
                        restored_connection,
                        project_id=row["id"],
                        object_type="system_backup",
                        object_id=payload.backup.sha256,
                        object_revision=None,
                        action="system.backup_restored",
                        actor=payload.actor,
                        role=payload.role,
                        after={"snapshot_sha256": payload.backup.sha256},
                    )
        finally:
            restored_connection.close()
        _activate_database(base, restored)
        return restored
    except (OSError, sqlite3.DatabaseError) as exc:
        # This path was generated here; never remove the base or a user-selected file.
        restored.unlink(missing_ok=True)
        raise PersistenceError("恢复写入失败，当前数据未切换，原数据库仍保留") from exc
