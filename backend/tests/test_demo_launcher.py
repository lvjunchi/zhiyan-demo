import base64
import hashlib
import json
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import start_demo as launcher


ROOT = Path(__file__).resolve().parents[2]


def config_for(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE projects(id TEXT)")
    return launcher.Config(ROOT, source, tmp_path / "工作副本" / "workspace.db", 0, 0)


def test_preflight_is_read_only_and_refuses_busy_ports(tmp_path):
    config = config_for(tmp_path)
    before = config.source.read_bytes()
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        config = launcher.Config(
            config.root,
            config.source,
            config.workspace,
            occupied.getsockname()[1],
            5181,
        )
        problems = launcher.preflight(config)
    assert any("端口" in item and str(config.backend_port) in item for item in problems)
    assert config.source.read_bytes() == before
    assert not config.workspace.parent.exists()


def test_preflight_detects_incomplete_frontend_install_even_when_vite_exists(tmp_path):
    config = config_for(tmp_path)
    root = tmp_path / "project"
    vite = root / "frontend/node_modules/vite/bin/vite.js"
    vite.parent.mkdir(parents=True)
    vite.write_text("", encoding="utf-8")
    (root / "frontend/index.html").write_text("", encoding="utf-8")
    config = launcher.Config(root, config.source, config.workspace, 8027, 5181)
    assert any("react" in item for item in launcher.preflight(config))


def test_preflight_retains_damaged_workspace_and_broken_restore_pointer(tmp_path):
    config = config_for(tmp_path)
    config.workspace.parent.mkdir()
    config.workspace.write_bytes(b"user data, do not replace")
    assert any("数据库" in item for item in launcher.preflight(config))
    assert config.workspace.read_bytes() == b"user data, do not replace"
    config.workspace.write_bytes(config.source.read_bytes())
    pointer = config.workspace.with_name(".workspace.db.active.json")
    pointer.write_text(json.dumps({"filename": "0" * 32 + ".db"}), encoding="utf-8")
    assert any("恢复" in item for item in launcher.preflight(config))
    assert pointer.exists()


def test_health_requires_real_database_and_schema_not_http_success_only():
    assert launcher.valid_health(
        {
            "status": "ok",
            "database": "connected",
            "schema_version": "018_coordination_progress",
        }
    )
    for value in [
        {},
        {"status": "ok"},
        {"status": "ok", "database": "disconnected", "schema_version": "014"},
        {
            "status": "ok",
            "database": "connected",
            "schema_version": "015_sample_comparison_versions",
        },
        {
            "status": "ok",
            "database": "connected",
            "schema_version": "014_engineering_versions",
        },
        [],
        "ok",
    ]:
        assert not launcher.valid_health(value)


def test_readiness_rejects_early_exit_and_times_out_without_success():
    dead = SimpleNamespace(poll=lambda: 7)
    with pytest.raises(launcher.LauncherError, match="退出"):
        launcher.wait_ready("http://127.0.0.1:1/api/health", dead, 0.15)
    alive = SimpleNamespace(poll=lambda: None)
    with pytest.raises(launcher.LauncherError, match="超时"):
        launcher.wait_ready("http://127.0.0.1:1/api/health", alive, 0.15)


@pytest.fixture
def backup_server():
    raw = b"synthetic snapshot for transport integrity"
    payload = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "database_base64": base64.b64encode(raw).decode(),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", payload
    server.shutdown()
    server.server_close()
    thread.join()


def test_shutdown_snapshot_is_verified_before_reporting_success(
    tmp_path, backup_server
):
    url, payload = backup_server
    saved = launcher.save_shutdown_backup(url, tmp_path)
    assert json.loads(saved.read_text(encoding="utf-8")) == payload
    payload["sha256"] = "f" * 64
    with pytest.raises(launcher.LauncherError, match="备份"):
        launcher.save_shutdown_backup(url, tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == 1
