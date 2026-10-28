import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "demo_checks", ROOT / "scripts/check_demo.py"
)
checks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checks
SPEC.loader.exec_module(checks)


def test_windows_check_plan_enforces_core_gate_and_never_installs_or_uses_bash(
    tmp_path,
):
    steps = checks.plan(ROOT, tmp_path)
    names = [step.name for step in steps]
    assert names.index("backend") < names.index("core-coverage")
    assert {
        "frontend",
        "lint",
        "build",
        "python-format",
        "browser-fixes",
        "browser-cockpit",
        "browser-change",
    } <= set(names)
    commands = " ".join(" ".join(step.command) for step in steps)
    assert "--cov-branch" in commands
    assert "check_core_coverage.py" in commands
    assert "bash" not in commands
    assert "install" not in commands
    assert "ci" not in [part for step in steps for part in step.command]
    assert all(step.cwd in (ROOT, ROOT / "frontend") for step in steps)
    assert not any(
        step.name.startswith("browser-")
        for step in checks.plan(ROOT, tmp_path, include_e2e=False)
    )


def test_check_runner_stops_on_failure_and_propagates_exit_code(tmp_path):
    steps = [
        checks.Check(name, tmp_path, [name])
        for name in ("backend", "core-coverage", "frontend")
    ]
    visited = []

    def fail_core(step):
        visited.append(step.name)
        return 7 if step.name == "core-coverage" else 0

    assert checks.execute(steps, fail_core) == 7
    assert visited == ["backend", "core-coverage"]


def test_check_runner_reports_success_only_after_all_steps(tmp_path):
    visited = []
    steps = [
        checks.Check("one", tmp_path, ["one"]),
        checks.Check("two", tmp_path, ["two"]),
    ]

    def success(step):
        visited.append(step.name)
        return 0

    assert checks.execute(steps, success) == 0
    assert visited == ["one", "two"]


def test_browser_checks_get_distinct_available_loopback_ports():
    import socket

    ports = checks.browser_ports()
    assert len(set(ports)) == 2
    assert all(0 < port < 65536 for port in ports)
    for port in ports:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
