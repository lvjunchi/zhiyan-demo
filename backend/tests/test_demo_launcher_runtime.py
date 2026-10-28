"""Real local supervisor/SQLite round trip; never uses the daily working database."""

import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


def free_ports():
    with socket.socket() as first, socket.socket() as second:
        first.bind(("127.0.0.1", 0))
        second.bind(("127.0.0.1", 0))
        return first.getsockname()[1], second.getsockname()[1]


def call(url, data=None):
    request = Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
        method="PATCH" if data is not None else "GET",
    )
    with urlopen(request, timeout=3) as response:
        return json.load(response)


def test_actual_launcher_preserves_revision_and_source_across_two_starts(tmp_path):
    source = tmp_path / "中文 空格路径" / "source.db"
    source.parent.mkdir()
    with sqlite3.connect(
        f"{(ROOT / 'data/demo.db').as_uri()}?mode=ro", uri=True
    ) as original:
        with sqlite3.connect(source) as destination:
            original.backup(destination)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    workspace = tmp_path / "日常 副本" / "workspace.db"
    backend_port, frontend_port = free_ports()
    base = f"http://127.0.0.1:{frontend_port}"
    revised = None
    for cycle in range(2):
        with (tmp_path / f"launch-{cycle}.log").open("wb") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / "scripts/start_demo.py"),
                    "--no-browser",
                    "--source",
                    str(source),
                    "--workspace",
                    str(workspace),
                    "--backend-port",
                    str(backend_port),
                    "--frontend-port",
                    str(frontend_port),
                ],
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            try:
                deadline = time.monotonic() + 40
                while True:
                    assert process.poll() is None, (
                        tmp_path / f"launch-{cycle}.log"
                    ).read_text(encoding="utf-8")
                    try:
                        health = call(base + "/api/health")
                        if health["database"] == "connected":
                            break
                    except (OSError, URLError):
                        pass  # Expected while this isolated test server is starting.
                    assert (
                        time.monotonic() < deadline
                    ), "local supervisor startup timed out"
                    time.sleep(0.15)
                project = next(
                    p
                    for p in call(base + "/api/projects")
                    if p["display_code"] == "P01"
                )
                engine = next(
                    r
                    for r in call(base + f"/api/projects/{project['id']}/requirements")
                    if r["parser_key"] == "engineMaxTorque"
                )
                if cycle == 0:
                    revised = call(
                        base + f"/api/requirements/{engine['id']}",
                        {
                            "expected_revision": engine["current_revision"],
                            "value_text": (
                                "2800" if engine["value_text"] != "2800" else "2600"
                            ),
                        },
                    )
                else:
                    assert revised is not None
                    assert engine["id"] == revised["id"]
                    assert engine["current_revision"] == revised["current_revision"]
                    assert engine["value_text"] == revised["value_text"]
                process.stdin.write(b"stop\n")
                process.stdin.flush()
                assert process.wait(timeout=30) == 0, (
                    tmp_path / f"launch-{cycle}.log"
                ).read_text(encoding="utf-8")
            finally:
                if process.poll() is None:
                    process.stdin.write(b"stop\n")
                    process.stdin.flush()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        # Only this test's supervisor and descendants; all data is in tmp_path.
                        if os.name == "nt":
                            subprocess.run(
                                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                check=True,
                                capture_output=True,
                            )
                        else:
                            process.kill()
                        raise AssertionError("test supervisor did not stop")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    assert len(list((workspace.parent / "launcher-backups").glob("*.json"))) == 2
