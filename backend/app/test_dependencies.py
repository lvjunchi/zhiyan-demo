"""Resolve persisted FMEA references and propagate changes inside the caller transaction."""

from __future__ import annotations

import json
import sqlite3

from .db import utc_now
from .errors import InvalidReferenceError


def fmea_references(
    connection: sqlite3.Connection,
    project_id: str,
    references: list[dict[str, object]],
    *,
    rebase: bool = False,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for reference in references:
        row = connection.execute(
            """SELECT r.revision, r.status, r.dependencies
               FROM fmea_item_revisions r JOIN fmea_items i ON i.id=r.item_id
               JOIN fmea_documents d ON d.id=i.fmea_id
               WHERE i.id=? AND d.project_id=? ORDER BY r.revision DESC LIMIT 1""",
            (reference.get("fmea_item_id"), project_id),
        ).fetchone()
        current = row["revision"] if row is not None else None
        valid = row is not None and row["status"] == "current"
        if row is not None:
            for dependency in json.loads(row["dependencies"]):
                kind = dependency.get("object_type")
                if kind == "requirement":
                    upstream = connection.execute(
                        "SELECT current_revision AS revision, validity AS validity FROM requirements WHERE id=? AND project_id=?",
                        (dependency.get("object_id"), project_id),
                    ).fetchone()
                elif kind == "variant_point":
                    upstream = connection.execute(
                        "SELECT revision, status AS validity FROM variant_points WHERE id=? AND project_id=?",
                        (dependency.get("object_id"), project_id),
                    ).fetchone()
                else:
                    upstream = None
                valid = (
                    valid
                    and upstream is not None
                    and upstream["revision"] == dependency.get("revision")
                    and upstream["validity"] == "current"
                )
        if rebase:
            if not valid:
                raise InvalidReferenceError(
                    "FMEA 引用缺失或已失效，请先修订 FMEA", reference
                )
            result.append({**reference, "revision": current})
        else:
            result.append(
                {
                    **reference,
                    "current_revision": current,
                    "current_validity": "current" if valid else "stale",
                }
            )
    return result


def fmea_versions(connection: sqlite3.Connection, project_id: str) -> dict[str, int]:
    return {
        row["item_id"]: row["revision"]
        for row in connection.execute(
            """SELECT r.item_id, MAX(r.revision) AS revision FROM fmea_item_revisions r
           JOIN fmea_items i ON i.id=r.item_id JOIN fmea_documents d ON d.id=i.fmea_id
           WHERE d.project_id=? GROUP BY r.item_id ORDER BY r.item_id""",
            (project_id,),
        )
    }


def fmea_dependencies_current(references: list[dict[str, object]]) -> bool:
    return all(
        ref.get("revision") == ref.get("current_revision")
        and ref.get("current_validity") == "current"
        for ref in references
    )


def invalidate_fmea_dependents(connection: sqlite3.Connection, project_id: str) -> None:
    from .services import _audit
    from .consistency_services import mark_consistency_checks_stale

    rows = connection.execute(
        "SELECT * FROM test_cases WHERE project_id=? AND validity='current'",
        (project_id,),
    ).fetchall()
    for row in rows:
        refs = fmea_references(connection, project_id, json.loads(row["fmea_refs"]))
        if fmea_dependencies_current(refs):
            continue
        connection.execute(
            "UPDATE test_cases SET validity='stale',updated_at=? WHERE id=?",
            (utc_now(), row["id"]),
        )
        connection.execute(
            "UPDATE test_case_revisions SET validity='stale' WHERE case_id=? AND revision=?",
            (row["id"], row["revision"]),
        )
        _audit(
            connection,
            project_id=project_id,
            object_type="test_case",
            object_id=row["id"],
            object_revision=row["revision"],
            action="test_case.stale",
            actor="system",
            role="system",
            comment="FMEA 引用版本变化，用例需重新基线及确认",
            before={"validity": "current"},
            after={"validity": "stale", "fmea_refs": refs},
        )
    mark_consistency_checks_stale(
        connection, project_id, "FMEA 内容或评分版本变化，请重新检查"
    )
