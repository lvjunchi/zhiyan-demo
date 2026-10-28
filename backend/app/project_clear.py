"""Explicit per-project clear: durable verified backup, retained old DB, atomic activation."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from . import backup_services
from .db import connect, run_migrations, transaction, utc_now
from .errors import DomainValidationError, NotFoundError, VersionConflictError
from .services import _audit

SqlValue = str | int | float | bytes | None
Rows = dict[str, list[dict[str, SqlValue]]]


class ClearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_code: str = Field(min_length=1, max_length=100)
    actor: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)


class ClearPersistenceError(backup_services.PersistenceError):
    status_code = 503


def _partition(
    connection: sqlite3.Connection, project_id: str
) -> tuple[dict[str, SqlValue], Rows, dict[str, set[int]]]:
    project = connection.execute(
        "SELECT * FROM projects WHERE id=?", (project_id,)
    ).fetchone()
    if project is None:
        raise NotFoundError("项目不存在")
    tables = [
        name for kind, name, _ in backup_services._schema(connection) if kind == "table"
    ]
    rows = {
        name: [dict(row) for row in connection.execute(f'SELECT * FROM "{name}"')]
        for name in tables
    }
    removed = {
        name: {i for i, row in enumerate(items) if row.get("project_id") == project_id}
        for name, items in rows.items()
    }
    # Resolve all direct and composite foreign keys, so indirect child records follow their owner.
    changed = True
    while changed:
        changed = False
        for name in tables:
            groups: dict[int, list[sqlite3.Row]] = {}
            for fk in connection.execute(f'PRAGMA foreign_key_list("{name}")'):
                groups.setdefault(fk["id"], []).append(fk)
            for group in groups.values():
                parent = group[0]["table"]
                keys = {
                    tuple(rows[parent][i][fk["to"]] for fk in group)
                    for i in removed[parent]
                }
                for i, row in enumerate(rows[name]):
                    if (
                        i not in removed[name]
                        and tuple(row[fk["from"]] for fk in group) in keys
                    ):
                        removed[name].add(i)
                        changed = True
    return dict(project), rows, removed


def preview(connection: sqlite3.Connection, project_id: str) -> dict[str, object]:
    project, rows, removed = _partition(connection, project_id)
    return {
        "project": {key: project[key] for key in ("id", "display_code", "name")},
        "affected_counts": {
            name: len(indices) for name, indices in removed.items() if indices
        },
        "retained_counts": {
            name: len(items) - len(removed[name]) for name, items in rows.items()
        },
        "expected_state_hash": backup_services.create_backup(connection)["sha256"],
    }


def _persist_backup(base: Path, backup_id: str, snapshot: dict[str, object]) -> Path:
    directory = base.parent / f".{base.name}.clear-backups"
    directory.mkdir(exist_ok=True)
    path = directory / f"{backup_id}.json"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    reread = backup_services.Snapshot.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    backup_services.validate_snapshot(reread)
    if reread.sha256 != snapshot["sha256"]:
        raise OSError("清空前备份回读校验失败")
    return path


def clear(
    connection: sqlite3.Connection, base: Path, project_id: str, payload: ClearRequest
) -> dict[str, object]:
    project, rows, removed = _partition(connection, project_id)
    if payload.confirmation_code != project["display_code"]:
        raise DomainValidationError("项目编号不匹配，未清空数据")
    snapshot = backup_services.create_backup(connection)
    if snapshot["sha256"] != payload.expected_state_hash:
        raise VersionConflictError("预览后数据已变化，请重新预览影响范围再确认")
    backup_id = uuid.uuid4().hex
    directory = base.parent / f".{base.name}.restores"
    target = directory / f"{uuid.uuid4().hex}.db"
    try:
        _persist_backup(base, backup_id, snapshot)
        directory.mkdir(exist_ok=True)
        destination = connect(target)
        try:
            run_migrations(destination)
            destination.execute("PRAGMA foreign_keys=OFF")
            with transaction(destination):
                for name, items in rows.items():
                    if name == "schema_migrations":
                        continue
                    for i, row in enumerate(items):
                        if i in removed[name]:
                            continue
                        if name == "part_candidates":
                            seeded = destination.execute(
                                "SELECT * FROM part_candidates WHERE id=?", (row["id"],)
                            ).fetchone()
                            if seeded is not None:
                                if dict(seeded) != row:
                                    raise DomainValidationError(
                                        "保留的候选库与受控版本不一致，未切换数据"
                                    )
                                continue
                        columns = ",".join(f'"{column}"' for column in row)
                        marks = ",".join("?" for _ in row)
                        destination.execute(
                            f'INSERT INTO "{name}" ({columns}) VALUES ({marks})',
                            tuple(row.values()),
                        )
                destination.execute(
                    "UPDATE projects SET stage='requirement_parsing',updated_at=? WHERE id=?",
                    (utc_now(), project_id),
                )
                _audit(
                    destination,
                    project_id=project_id,
                    object_type="project",
                    object_id=project_id,
                    object_revision=None,
                    action="project.business_cleared",
                    actor=payload.actor,
                    role=payload.role,
                    after={
                        "backup_id": backup_id,
                        "backup_sha256": snapshot["sha256"],
                        "affected_counts": {
                            name: len(indices)
                            for name, indices in removed.items()
                            if indices
                        },
                    },
                )
                if destination.execute("PRAGMA foreign_key_check").fetchone():
                    raise DomainValidationError("清空副本存在引用错误，未切换数据")
            destination.execute("PRAGMA foreign_keys=ON")
            backup_services.validate_snapshot(
                backup_services.Snapshot.model_validate(
                    backup_services.create_backup(destination)
                )
            )
        finally:
            destination.close()
        backup_services._activate_database(base, target)
    except (OSError, sqlite3.DatabaseError) as exc:
        # Retain all original, backup and unsuccessful staging files for diagnosis.
        raise ClearPersistenceError("备份或清空副本写入失败，当前数据未切换") from exc
    return {
        "status": "cleared",
        "original_retained": True,
        "reload_required": True,
        "backup_url": f"/api/system/clear-backups/{backup_id}",
        "backup_sha256": snapshot["sha256"],
        "path": str(target),
    }


def read_backup(base: Path, backup_id: str) -> dict[str, object]:
    if len(backup_id) != 32 or any(c not in "0123456789abcdef" for c in backup_id):
        raise NotFoundError("清空备份不存在")
    path = base.parent / f".{base.name}.clear-backups" / f"{backup_id}.json"
    if not path.is_file():
        raise NotFoundError("清空备份不存在")
    snapshot = backup_services.Snapshot.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    backup_services.validate_snapshot(snapshot)
    return snapshot.model_dump()
