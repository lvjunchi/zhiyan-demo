"""Start both local services without replacing data or stopping foreign processes."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
LATEST_SCHEMA = sorted((ROOT / "backend/app/migrations").glob("*.sql"))[-1].stem
LOCAL_HTTP = build_opener(ProxyHandler({}))


def default_source(root: Path) -> Path:
    prepared = root / "data/initial-showcase/initial.db"
    ready = prepared.is_file() and (prepared.parent / "manifest.json").is_file()
    return prepared if ready else root / "data/demo.db"


class LauncherError(RuntimeError):
    """Actionable startup/shutdown error; diagnostics are kept in local logs."""


class RunningProcess(Protocol):
    def poll(self) -> int | None: ...


@dataclass(frozen=True)
class Config:
    root: Path
    source: Path
    workspace: Path
    backend_port: int = 8027
    frontend_port: int = 5181

    @property
    def backend_url(self) -> str:
        return f"http://127.0.0.1:{self.backend_port}"

    @property
    def frontend_url(self) -> str:
        return f"http://127.0.0.1:{self.frontend_port}"


def check_database(path: Path) -> None:
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as database:
        if database.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise LauncherError("数据库完整性检查未通过")
        if not database.execute(
            "SELECT 1 FROM sqlite_master WHERE name='projects'"
        ).fetchone():
            raise LauncherError("数据库缺少项目表")


def preflight(config: Config) -> list[str]:
    problems: list[str] = []
    missing = [
        name
        for name in ("fastapi", "uvicorn", "pydantic", "pypdf")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        problems.append(
            f"Python 依赖缺失：{', '.join(missing)}。请按 README 安装 backend/requirements-dev.txt。"
        )
    if shutil.which("node") is None:
        problems.append("未找到 Node.js，请安装 README 中已验证的运行环境。")
    if not (config.root / "frontend/node_modules/vite/bin/vite.js").is_file():
        problems.append("前端依赖缺失，请先在 frontend 目录执行 npm ci。")
    for package in ("react", "react-dom", "@vitejs/plugin-react"):
        if not (
            config.root / "frontend/node_modules" / package / "package.json"
        ).is_file():
            problems.append(
                f"前端依赖 {package} 不完整，请在 frontend 目录执行 npm ci。"
            )
    if not (config.root / "frontend/index.html").is_file():
        problems.append("前端入口缺失，请检查项目文件。")
    if config.source.resolve() == config.workspace.resolve():
        problems.append("工作副本不能使用原始数据库路径。")
    for label, path in (("源数据库", config.source), ("工作数据库", config.workspace)):
        if label == "工作数据库" and not path.exists():
            continue
        try:
            check_database(path)
        except (OSError, sqlite3.DatabaseError, LauncherError) as exc:
            problems.append(f"{label}检查失败，未替换数据：{exc}")
    pointer = config.workspace.with_name(f".{config.workspace.name}.active.json")
    if pointer.exists() and not missing:
        sys.path.insert(0, str(config.root / "backend"))
        try:
            from app.backup_services import active_database

            check_database(active_database(config.workspace))
        except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError) as exc:
            problems.append(f"恢复数据检查失败，未回退或覆盖现有数据：{exc}")
    if config.backend_port == config.frontend_port:
        problems.append("前后端端口不能相同。")
    for port in (config.backend_port, config.frontend_port):
        if not 1 <= port <= 65535:
            problems.append(f"端口 {port} 不合法，应为 1–65535。")
            continue
        with socket.socket() as probe:
            try:
                if os.name == "nt":
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                probe.bind(("127.0.0.1", port))
            except OSError:
                problems.append(
                    f"端口 {port} 已占用或不可用。若系统已启动，请直接访问原页面；本工具不会结束已有进程。"
                )
    return problems


def valid_health(value: object) -> bool:
    return (
        isinstance(value, dict)
        and value.get("status") == "ok"
        and value.get("database") == "connected"
        and value.get("schema_version") == LATEST_SCHEMA
    )


def read_json(url: str, timeout: float = 2) -> object:
    with LOCAL_HTTP.open(url, timeout=timeout) as response:
        return json.load(response)


def wait_ready(url: str, process: RunningProcess, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = "尚未响应"
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise LauncherError(f"服务启动期间退出（退出码 {code}），请查看启动日志。")
        try:
            if valid_health(
                read_json(url, timeout=min(1.0, max(0.05, deadline - time.monotonic())))
            ):
                return
            last_error = "数据库连接或迁移版本未就绪"
        except (OSError, URLError, ValueError) as exc:
            last_error = str(exc)
        time.sleep(min(0.15, max(0, deadline - time.monotonic())))
    raise LauncherError(f"等待服务就绪超时：{url}；{last_error}")


def save_shutdown_backup(url: str, directory: Path) -> Path:
    try:
        data = read_json(url + "/api/system/backup", timeout=15)
        if not isinstance(data, dict) or not isinstance(
            data.get("database_base64"), str
        ):
            raise ValueError("快照结构不合法")
        raw = base64.b64decode(data["database_base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != data.get("sha256"):
            raise ValueError("快照校验不一致")
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = directory / f"stop-{stamp}-{uuid.uuid4().hex[:8]}.json"
        with path.open("x", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        return path
    except (OSError, URLError, ValueError, binascii.Error) as exc:
        raise LauncherError(f"退出前备份失败，服务暂不停止：{exc}") from exc


def stop_owned(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGTERM)
    except OSError as exc:
        print(
            f"服务无可用控制台信号，将停止本次子进程 {process.pid}：{exc}", flush=True
        )
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)


def run(config: Config, no_browser: bool, timeout: float) -> int:
    runtime = config.root / ".runtime"
    runtime.mkdir(exist_ok=True)
    stamp = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    children: list[subprocess.Popen[bytes]] = []
    backend: subprocess.Popen[bytes] | None = None
    backend_ready = False
    exit_code = 0
    stop_requested = threading.Event()

    def read_commands() -> None:
        try:
            for line in sys.stdin:
                if line.strip().lower() == "stop":
                    stop_requested.set()
        except OSError as exc:
            print(f"当前输入不可用，可使用 Ctrl+C 停止：{exc}", flush=True)

    threading.Thread(target=read_commands, daemon=True).start()
    with ExitStack() as logs:

        def launch(
            name: str, command: list[str], cwd: Path, env: dict[str, str]
        ) -> subprocess.Popen[bytes]:
            log = runtime / f"{stamp}-{name}.log"
            output = logs.enter_context(log.open("wb"))
            options = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                **options,
            )
            children.append(process)
            print(f"{name} 日志：{log}", flush=True)
            return process

        try:
            environment = {
                **os.environ,
                "PYTHONUTF8": "1",
                "PYTHONUNBUFFERED": "1",
                "CI": "1",
            }
            print("[1/3] 正在启动数据服务，保留已有工作副本…", flush=True)
            backend = launch(
                "backend",
                [
                    sys.executable,
                    str(config.root / "scripts/run_preview_backend.py"),
                    "--source",
                    str(config.source),
                    "--workspace",
                    str(config.workspace),
                    "--port",
                    str(config.backend_port),
                ],
                config.root,
                environment,
            )
            wait_ready(config.backend_url + "/api/health", backend, timeout)
            backend_ready = True
            print("[2/3] 数据库已连接，正在启动工作台…", flush=True)
            frontend = launch(
                "frontend",
                [
                    str(shutil.which("node")),
                    str(config.root / "frontend/node_modules/vite/bin/vite.js"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(config.frontend_port),
                    "--strictPort",
                ],
                config.root / "frontend",
                {**environment, "ZHIYAN_API_TARGET": config.backend_url},
            )
            wait_ready(config.frontend_url + "/api/health", frontend, timeout)
            print(
                f"[3/3] 系统就绪：{config.frontend_url}/\n工作副本：{config.workspace}\n保持此窗口运行；输入 stop 回车或按 Ctrl+C，会先备份再停止本次启动的服务。",
                flush=True,
            )
            if not no_browser:
                if not webbrowser.open(config.frontend_url):
                    print("未能自动打开浏览器，请使用上方地址访问。", flush=True)
            while not stop_requested.is_set():
                for child in children:
                    code = child.poll()
                    if code is not None:
                        raise LauncherError(
                            f"运行中的服务意外退出（退出码 {code}）。请查看 {runtime} 日志。"
                        )
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n正在准备停止…", flush=True)
        except (LauncherError, OSError) as exc:
            print(f"启动/运行失败：{exc}", file=sys.stderr, flush=True)
            exit_code = 1
        finally:
            # Preserve the owned backend when backup fails. Retry only after a new explicit Ctrl+C.
            while backend_ready and backend is not None and backend.poll() is None:
                try:
                    backup = save_shutdown_backup(
                        config.backend_url, config.workspace.parent / "launcher-backups"
                    )
                    print(f"退出前备份已校验保存：{backup}", flush=True)
                    break
                except LauncherError as exc:
                    print(
                        f"{exc}\n工作副本保留在 {config.workspace}。修复连接/空间后按 Ctrl+C 重试停止。",
                        file=sys.stderr,
                        flush=True,
                    )
                    stop_requested.clear()
                    try:
                        while not stop_requested.wait(0.5):
                            if backend.poll() is not None:
                                break
                    except KeyboardInterrupt:
                        pass  # Explicit retry; never stop children as a consequence of backup failure.
            for child in reversed(children):
                stop_owned(child)
    print("本次服务已停止，工作副本与备份均保留。", flush=True)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="只读检查，不创建工作副本或启动服务"
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--source", type=Path, default=default_source(ROOT))
    parser.add_argument(
        "--workspace", type=Path, default=ROOT / "data/local-preview/workspace.db"
    )
    parser.add_argument("--backend-port", type=int, default=8027)
    parser.add_argument("--frontend-port", type=int, default=5181)
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 180:
        parser.error("--timeout 须在 1–180 秒内")
    config = Config(
        ROOT,
        args.source.resolve(),
        args.workspace.resolve(),
        args.backend_port,
        args.frontend_port,
    )
    print("智研引擎 · 本地运行检查", flush=True)
    problems = preflight(config)
    if problems:
        for problem in problems:
            print(f"[未就绪] {problem}", file=sys.stderr, flush=True)
        return 1
    print("检查通过：Python、前端依赖、数据库与端口可用。", flush=True)
    return 0 if args.check else run(config, args.no_browser, args.timeout)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
