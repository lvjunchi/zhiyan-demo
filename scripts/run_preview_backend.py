"""Run a local preview on an isolated SQLite copy; optionally keep the workspace."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import create_app  # noqa: E402


def prepare_workspace(source: Path, workspace: Path) -> Path:
    source = source.resolve(strict=True)
    workspace = workspace.resolve()
    if source == workspace:
        raise ValueError("preview workspace must differ from source")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if not workspace.exists():
        handle, filename = tempfile.mkstemp(
            prefix="preview-init-", suffix=".db", dir=workspace.parent
        )
        os.close(handle)
        pending = Path(filename)
        try:
            original = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
            destination = sqlite3.connect(pending)
            try:
                original.backup(destination)
            finally:
                destination.close()
                original.close()
            try:
                os.link(
                    pending, workspace
                )  # Atomic creation; never overwrite an existing workspace.
            except FileExistsError:
                pass  # Another launcher completed initialization first; validate that file below.
        finally:
            pending.unlink(missing_ok=True)
    with sqlite3.connect(f"{workspace.as_uri()}?mode=ro", uri=True) as existing:
        if (
            existing.execute("PRAGMA quick_check").fetchone()[0] != "ok"
            or not existing.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1"
            ).fetchone()
        ):
            raise ValueError("preview workspace is invalid; existing data was retained")
    return workspace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data" / "demo.db")
    parser.add_argument("--port", type=int, default=8027)
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Persistent local working copy; omit for isolated temporary tests",
    )
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if args.workspace is not None:
        workspace = prepare_workspace(source, args.workspace)
        print(f"Local preview preserves its working copy at {workspace}", flush=True)
        uvicorn.run(
            create_app(workspace), host="127.0.0.1", port=args.port, log_level="warning"
        )
        return
    with tempfile.TemporaryDirectory(prefix="zhiyan-preview-") as directory:
        preview = Path(directory) / "preview.db"
        source_connection = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
        destination = sqlite3.connect(preview)
        try:
            source_connection.backup(destination)
        finally:
            destination.close()
            source_connection.close()
        print(f"Local preview uses a temporary backup of {source.name}", flush=True)
        uvicorn.run(
            create_app(preview), host="127.0.0.1", port=args.port, log_level="warning"
        )


if __name__ == "__main__":
    main()
