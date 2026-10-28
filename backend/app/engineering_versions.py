"""Versioned variant/part records. Called within the enclosing business transaction."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Literal

from .db import transaction, utc_now
from .domain.variant import PARAMETER_PARTS
from .errors import DomainValidationError, NotFoundError, VersionConflictError
from .schemas import ArtifactConfirmationCreate

Kind = Literal["variant", "part"]
TABLES = {"variant": "variant_points", "part": "reusable_part_decisions"}
JSON_FIELDS = {
    "affected_parts",
    "upstream_requirement_ids",
    "variant_keys",
    "dependency_versions",
}
IGNORED = {
    "created_at",
    "updated_at",
    "status",
    "review_status",
    "revision",
    "migration_note",
    "is_applicable",
}


def record(
    connection: sqlite3.Connection, kind: Kind, object_id: str
) -> dict[str, object]:
    row = connection.execute(
        f"SELECT * FROM {TABLES[kind]} WHERE id=?", (object_id,)
    ).fetchone()
    if not row:
        raise NotFoundError("工程对象不存在")
    return {
        key: json.loads(row[key]) if key in JSON_FIELDS else row[key]
        for key in row.keys()
    }


def _dependencies(
    connection: sqlite3.Connection, kind: Kind, row: dict[str, object]
) -> list[dict[str, object]]:
    from .services import _infer_parser_key

    if kind == "variant":
        upstream = row["upstream_requirement_ids"]
        assert isinstance(upstream, list)
        ids = {item["requirement_id"] for item in upstream}
        keys: set[str] = set()
    else:
        ids = (
            {
                row["id"]
                for row in connection.execute(
                    "SELECT id FROM requirements WHERE project_id=? AND parser_key IN ('engineMaxTorque','gearboxRatedInputTorque','gearCount')",
                    (row["project_id"],),
                )
            }
            if str(row["part_number"]).startswith("DEMO-")
            else set()
        )
        keys = {
            key for key, names in PARAMETER_PARTS.items() if row["part_name"] in names
        }
    dependencies = []
    for req in connection.execute(
        "SELECT * FROM requirements WHERE project_id=? ORDER BY id",
        (row["project_id"],),
    ):
        if req["id"] in ids or _infer_parser_key(req) in keys:
            dependencies.append(
                {
                    "object_type": "requirement",
                    "object_id": req["id"],
                    "revision": req["current_revision"],
                }
            )
    if kind == "part":
        variants = row["variant_keys"]
        assert isinstance(variants, list)
        for variant in connection.execute(
            "SELECT id,revision,parameter_key FROM variant_points WHERE project_id=? AND base_id=? AND status='current' ORDER BY id",
            (row["project_id"], row["base_id"]),
        ):
            if variant["parameter_key"] in variants:
                dependencies.append(
                    {
                        "object_type": "variant",
                        "object_id": variant["id"],
                        "revision": variant["revision"],
                    }
                )
    return dependencies


def capture(
    connection: sqlite3.Connection, kind: Kind, object_id: str
) -> tuple[int, bool]:
    row = record(connection, kind, object_id)
    row["dependency_versions"] = _dependencies(connection, kind, row)
    latest = connection.execute(
        "SELECT * FROM engineering_record_versions WHERE object_type=? AND object_id=? ORDER BY revision DESC LIMIT 1",
        (kind, object_id),
    ).fetchone()
    content = {k: v for k, v in row.items() if k not in IGNORED}
    if latest:
        previous = {
            k: v
            for k, v in json.loads(latest["snapshot_json"]).items()
            if k not in IGNORED
        }
        if content == previous and "migration_note" not in json.loads(
            latest["snapshot_json"]
        ):
            return int(row["revision"]), False
    revision = int(latest["revision"]) + 1 if latest else 1
    row.update(revision=revision, review_status="draft")
    connection.execute(
        f"UPDATE {TABLES[kind]} SET revision=?,review_status='draft',dependency_versions=? WHERE id=?",
        (revision, json.dumps(row["dependency_versions"]), object_id),
    )
    connection.execute(
        "INSERT INTO engineering_record_versions VALUES (?,?,?,?,?,?)",
        (
            kind,
            object_id,
            row["project_id"],
            revision,
            json.dumps(row, ensure_ascii=False, sort_keys=True),
            utc_now(),
        ),
    )
    return revision, True


def needs_capture(connection: sqlite3.Connection, kind: Kind, object_id: str) -> bool:
    row = record(connection, kind, object_id)
    latest = connection.execute(
        "SELECT snapshot_json FROM engineering_record_versions WHERE object_type=? AND object_id=? AND revision=?",
        (kind, object_id, row["revision"]),
    ).fetchone()
    return (
        latest is None
        or "migration_note" in json.loads(latest["snapshot_json"])
        or row["dependency_versions"] != _dependencies(connection, kind, row)
    )


def detail(
    connection: sqlite3.Connection, kind: Kind, object_id: str
) -> dict[str, object]:
    current = _display_record(connection, kind, object_id)
    versions = [
        {**dict(row), "snapshot": json.loads(row["snapshot_json"])}
        for row in connection.execute(
            "SELECT * FROM engineering_record_versions WHERE object_type=? AND object_id=? ORDER BY revision",
            (kind, object_id),
        )
    ]
    for version in versions:
        del version["snapshot_json"]
    confirmations = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM engineering_record_confirmations WHERE object_type=? AND object_id=? ORDER BY created_at,id",
            (kind, object_id),
        )
    ]
    return {
        "kind": kind,
        "current": current,
        "versions": versions,
        "confirmations": confirmations,
    }


def _display_record(
    connection: sqlite3.Connection, kind: Kind, object_id: str
) -> dict[str, object]:
    current = record(connection, kind, object_id)
    base = connection.execute(
        "SELECT display_code FROM product_bases WHERE id=?", (current["base_id"],)
    ).fetchone()
    return {
        "kind": kind,
        **current,
        "base_display_code": base["display_code"] if base else None,
    }


def list_records(
    connection: sqlite3.Connection, project_id: str
) -> list[dict[str, object]]:
    if not connection.execute(
        "SELECT 1 FROM projects WHERE id=?", (project_id,)
    ).fetchone():
        raise NotFoundError("项目不存在")
    return [
        _display_record(connection, kind, row["id"])
        for kind, table in TABLES.items()
        for row in connection.execute(
            f"SELECT id FROM {table} WHERE project_id=? ORDER BY created_at,id",
            (project_id,),
        )
    ]


def design_context(
    connection: sqlite3.Connection, project_id: str
) -> dict[str, object]:
    """Read the last actually saved analysis, never pick a catalogue default."""
    if not connection.execute(
        "SELECT 1 FROM projects WHERE id=?", (project_id,)
    ).fetchone():
        raise NotFoundError("项目不存在")
    event = connection.execute(
        "SELECT after_json FROM audit_events WHERE project_id=? AND action='variant_analysis.generated' "
        "ORDER BY created_at DESC,id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    if event is None:
        return {"base_display_code": None, "source": "none"}
    snapshot = json.loads(event["after_json"])
    code = snapshot.get("base_display_code") if isinstance(snapshot, dict) else None
    if (
        not isinstance(code, str)
        or not connection.execute(
            "SELECT 1 FROM product_bases WHERE display_code=?", (code,)
        ).fetchone()
    ):
        raise DomainValidationError("最近变型分析的基型记录无效，请重新核对分析")
    return {"base_display_code": code, "source": "variant_analysis"}


def confirmation_blockers(
    connection: sqlite3.Connection, row: dict[str, object]
) -> list[str]:
    """Use the same upstream checks for approval and for actionable UI guidance."""
    blockers = []
    dependencies = row["dependency_versions"]
    assert isinstance(dependencies, list)
    for dep in dependencies:
        is_requirement = dep["object_type"] == "requirement"
        table = "requirements" if is_requirement else "variant_points"
        upstream = connection.execute(
            f"SELECT * FROM {table} WHERE id=? AND project_id=?",
            (dep["object_id"], row["project_id"]),
        ).fetchone()
        if upstream is None:
            blockers.append(f"引用 {dep['object_id']} V{dep['revision']}：上游不存在")
            continue
        revision = upstream["current_revision" if is_requirement else "revision"]
        validity = upstream["validity" if is_requirement else "status"]
        prefix = f"{upstream['display_code']} {upstream['parameter_name']} V{dep['revision']}"
        if revision != dep["revision"] or validity != "current":
            blockers.append(f"{prefix}：引用版本已失效，请重新运行变型分析")
        elif upstream["review_status"] != "confirmed":
            blockers.append(
                f"{prefix}：上游未确认，请先审核该{'需求' if is_requirement else '变型点'}"
            )
    return blockers


def confirm(
    connection: sqlite3.Connection,
    kind: Kind,
    object_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, object]:
    with transaction(connection):
        return _confirm_in_transaction(connection, kind, object_id, payload)


def _confirm_in_transaction(
    connection: sqlite3.Connection,
    kind: Kind,
    object_id: str,
    payload: ArtifactConfirmationCreate,
) -> dict[str, object]:
    from .services import _audit

    row = record(connection, kind, object_id)
    if row["revision"] != payload.expected_revision or row["status"] != "current":
        raise VersionConflictError("对象版本已变化或已失效，请重新生成并核对当前版本")
    latest = connection.execute(
        "SELECT snapshot_json FROM engineering_record_versions WHERE object_type=? AND object_id=? AND revision=?",
        (kind, object_id, row["revision"]),
    ).fetchone()
    if latest is None or "migration_note" in json.loads(latest["snapshot_json"]):
        raise DomainValidationError(
            "迁移保留的旧记录缺少完整依据，请重新运行分析后再审核"
        )
    if row["review_status"] == payload.decision:
        raise VersionConflictError("该版本已记录相同审核决定，不可覆盖旧记录")
    withdrawing = (
        kind == "part"
        and row["review_status"] == "confirmed"
        and payload.decision == "rejected"
    )
    if kind == "part" and payload.decision == "confirmed":
        from .part_selection import validate_confirmation

        validate_confirmation(connection, row)
    blockers = confirmation_blockers(connection, row)
    if blockers and payload.decision == "confirmed":
        raise DomainValidationError(
            "上游依据尚未确认或版本不再有效，请先复核上游", {"blockers": blockers}
        )
    result = {
        "id": str(uuid.uuid4()),
        "object_type": kind,
        "object_id": object_id,
        "object_revision": payload.expected_revision,
        "actor": payload.actor,
        "role": payload.role,
        "decision": payload.decision,
        "comment": payload.comment,
        "created_at": utc_now(),
    }
    connection.execute(
        "INSERT INTO engineering_record_confirmations VALUES (?,?,?,?,?,?,?,?,?)",
        tuple(result.values()),
    )
    connection.execute(
        f"UPDATE {TABLES[kind]} SET review_status=? WHERE id=?",
        (payload.decision, object_id),
    )
    if withdrawing:
        approval = connection.execute(
            "SELECT id FROM engineering_record_confirmations "
            "WHERE object_type='part' AND object_id=? AND object_revision=? "
            "AND decision='confirmed' ORDER BY created_at DESC,id DESC LIMIT 1",
            (object_id, payload.expected_revision),
        ).fetchone()
        _audit(
            connection,
            project_id=str(row["project_id"]),
            object_type="reusable_part_decision",
            object_id=object_id,
            object_revision=payload.expected_revision,
            action="part.confirmation_withdrawn",
            actor=payload.actor,
            role=payload.role,
            comment=payload.comment.strip(),
            before={"confirmation_id": approval["id"] if approval else None},
            after={"rejection_id": result["id"], "review_status": "rejected"},
        )
        invalidate_dependents(connection, row)
    _audit(
        connection,
        project_id=str(row["project_id"]),
        object_type=(
            "variant_point" if kind == "variant" else "reusable_part_decision"
        ),
        object_id=object_id,
        object_revision=payload.expected_revision,
        action=f"{kind}.reviewed",
        actor=payload.actor,
        role=payload.role,
        decision=payload.decision,
        comment=payload.comment,
    )
    return result


def invalidate_dependents(
    connection: sqlite3.Connection, row: dict[str, object]
) -> None:
    """Use the existing project/base design dependency boundary, in one transaction."""
    from .services import _audit
    from .test_dependencies import invalidate_fmea_dependents

    for table, kind in (
        ("design_reviews", "design_review"),
        ("fmea_documents", "fmea_document"),
    ):
        documents = connection.execute(
            f"SELECT id,revision FROM {table} WHERE project_id=? AND base_id=?",
            (row["project_id"], row["base_id"]),
        ).fetchall()
        for document in documents:
            connection.execute(
                f"UPDATE {table} SET validity='stale',updated_at=? WHERE id=?",
                (utc_now(), document["id"]),
            )
            if table == "fmea_documents":
                connection.execute(
                    "UPDATE fmea_item_revisions SET status='stale' "
                    "WHERE item_id IN (SELECT id FROM fmea_items WHERE fmea_id=?) "
                    "AND revision=(SELECT MAX(r.revision) FROM fmea_item_revisions r "
                    "WHERE r.item_id=fmea_item_revisions.item_id)",
                    (document["id"],),
                )
            _audit(
                connection,
                project_id=str(row["project_id"]),
                object_type=kind,
                object_id=document["id"],
                object_revision=document["revision"],
                action="design.engineering_dependency_stale",
                comment="零件选型确认已撤回，请复核同基型设计依据",
                after={
                    "part_id": row["id"],
                    "revision": row["revision"],
                    "validity": "stale",
                },
            )
    # This also marks the project's consistency report stale. Old executions remain intact.
    invalidate_fmea_dependents(connection, str(row["project_id"]))


def validate_store(connection: sqlite3.Connection) -> None:
    for kind, table in TABLES.items():
        for item in connection.execute(f"SELECT id FROM {table}"):
            row = record(connection, kind, item["id"])
            latest = connection.execute(
                "SELECT * FROM engineering_record_versions WHERE object_type=? AND object_id=? ORDER BY revision DESC LIMIT 1",
                (kind, item["id"]),
            ).fetchone()
            if (
                latest is None
                or latest["revision"] != row["revision"]
                or latest["project_id"] != row["project_id"]
            ):
                raise DomainValidationError("工程记录与独立版本历史不一致")
            snapshot = json.loads(latest["snapshot_json"])
            if not isinstance(snapshot, dict):
                raise DomainValidationError("工程版本快照必须是对象")
            if {k: v for k, v in snapshot.items() if k not in IGNORED} != {
                k: v for k, v in row.items() if k not in IGNORED
            }:
                raise DomainValidationError("工程记录内容与版本快照不一致")
            review = connection.execute(
                "SELECT decision FROM engineering_record_confirmations WHERE object_type=? AND object_id=? AND object_revision=? ORDER BY created_at DESC,id DESC LIMIT 1",
                (kind, item["id"], row["revision"]),
            ).fetchone()
            if (
                review is None and row["review_status"] in ("confirmed", "rejected")
            ) or (review is not None and review["decision"] != row["review_status"]):
                raise DomainValidationError("工程审核状态与该版本的审核留痕不一致")
    for version in connection.execute("SELECT * FROM engineering_record_versions"):
        snapshot = json.loads(version["snapshot_json"])
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("id") != version["object_id"]
            or snapshot.get("project_id") != version["project_id"]
            or snapshot.get("revision") != version["revision"]
        ):
            raise DomainValidationError("工程版本快照的身份或版本不合法")
        dependencies = snapshot.get("dependency_versions", [])
        if not isinstance(dependencies, list) or any(
            not isinstance(dep, dict) for dep in dependencies
        ):
            raise DomainValidationError("工程版本依赖清单不合法")
        for dep in dependencies:
            if dep.get("object_type") == "requirement":
                upstream = connection.execute(
                    "SELECT r.project_id FROM requirement_revisions v JOIN requirements r ON r.id=v.requirement_id WHERE v.requirement_id=? AND v.revision_no=?",
                    (dep.get("object_id"), dep.get("revision")),
                ).fetchone()
            elif dep.get("object_type") == "variant":
                upstream = connection.execute(
                    "SELECT project_id FROM engineering_record_versions WHERE object_type='variant' AND object_id=? AND revision=?",
                    (dep.get("object_id"), dep.get("revision")),
                ).fetchone()
            else:
                upstream = None
            if upstream is None or upstream["project_id"] != version["project_id"]:
                raise DomainValidationError("工程版本包含缺失或跨项目依赖")
