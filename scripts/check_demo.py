"""Offline reproducible project checks; every command must succeed."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Sequence
import argparse
from datetime import datetime
import os
import shutil
import subprocess
import sys
import socket

PYTHON_FORMAT_PATHS = [
    "backend/app/test_dependencies.py",
    "backend/app/testing_services.py",
    "backend/app/design_services.py",
    "backend/app/sample_services.py",
    "backend/app/coordination_services.py",
    "backend/app/package_services.py",
    "backend/app/overview_services.py",
    "backend/app/schemas.py",
    "backend/app/domain/parser.py",
    "backend/app/domain/values.py",
    "backend/app/domain/package.py",
    "backend/app/domain/testing.py",
    "backend/app/services.py",
    "scripts/check_demo.py",
    "backend/tests/test_check_demo.py",
    "backend/tests/test_fmea_dependency_regression.py",
    "backend/tests/test_parser_regression.py",
    "backend/tests/test_sample_revision_regression.py",
    "backend/tests/test_coordination_freshness.py",
    "backend/tests/run_regression_e2e.py",
]


@dataclass(frozen=True)
class Check:
    name: str
    cwd: Path
    command: list[str]


def browser_ports() -> tuple[int, int]:
    with socket.socket() as api_listener, socket.socket() as ui_listener:
        api_listener.bind(("127.0.0.1", 0))
        ui_listener.bind(("127.0.0.1", 0))
        return api_listener.getsockname()[1], ui_listener.getsockname()[1]


def plan(root: Path, evidence: Path, include_e2e: bool = True) -> list[Check]:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"
    steps = [
        Check(
            "backend",
            root,
            [
                sys.executable,
                "-m",
                "pytest",
                "backend/tests",
                "-q",
                "--cov-branch",
                f"--cov-report=json:{evidence / 'coverage-backend.json'}",
            ],
        ),
        Check(
            "core-coverage",
            root,
            [
                sys.executable,
                "scripts/check_core_coverage.py",
                str(evidence / "coverage-backend.json"),
            ],
        ),
        Check(
            "python-format",
            root,
            [sys.executable, "-m", "black", "--check", *PYTHON_FORMAT_PATHS],
        ),
        Check("frontend", root / "frontend", [npm, "run", "test:coverage"]),
        Check("lint", root / "frontend", [npm, "run", "lint"]),
        Check("build", root / "frontend", [npm, "run", "build"]),
    ]
    if include_e2e:
        node = shutil.which("node") or "node"
        for suite in ("fixes", "cockpit", "change"):
            steps.append(
                Check(
                    f"browser-{suite}",
                    root / "frontend",
                    [
                        node,
                        "node_modules/@playwright/test/cli.js",
                        "test",
                        "--config",
                        f"playwright.{suite}.config.ts",
                    ],
                )
            )
    return steps


def execute(checks: Sequence[Check], runner: Callable[[Check], int]) -> int:
    for check in checks:
        print(f"Running {check.name}", flush=True)
        code = runner(check)
        if code:
            print(f"FAILED {check.name}: exit {code}", flush=True)
            return code
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Run unit/integration/build checks only; browser acceptance remains unverified",
    )
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument(
        "--only",
        nargs="+",
        choices=[
            "backend",
            "core-coverage",
            "python-format",
            "frontend",
            "lint",
            "build",
            "browser-fixes",
            "browser-cockpit",
            "browser-change",
        ],
        help="Run named checks only; other acceptance steps remain unexecuted in this invocation",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence = (
        args.evidence_dir
        or root
        / "docs/test-evidence"
        / datetime.now().strftime("%Y-%m-%d")
        / datetime.now().strftime("CHECK-%H%M%S")
    ).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "COVERAGE_FILE": str(evidence / ".coverage"),
        "ZHIYAN_EVIDENCE_DIR": str(evidence / "browser"),
    }

    def logged(check: Check) -> int:
        check_env = dict(env)
        if check.name.startswith("browser-"):
            api_port, ui_port = browser_ports()
            check_env.update(
                ZHIYAN_E2E_API_PORT=str(api_port), ZHIYAN_E2E_UI_PORT=str(ui_port)
            )
        with (evidence / f"{check.name}.txt").open("w", encoding="utf-8") as output:
            output.write(f"cwd: {check.cwd}\ncommand: {check.command!r}\n")
            output.flush()
            if check.name.startswith("browser-"):
                output.write(f"Loopback ports: API={api_port}, UI={ui_port}\n")
                output.flush()
            try:
                result = subprocess.run(
                    check.command,
                    cwd=check.cwd,
                    env=check_env,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            except OSError as exc:
                output.write(f"Unable to execute: {exc}\n")
                return 2
            output.write(f"\nexit_code: {result.returncode}\n")
            return result.returncode

    steps = plan(root, evidence, include_e2e=not args.skip_e2e)
    if args.only:
        steps = [check for check in steps if check.name in args.only]
        print(f"Selected checks only: {[check.name for check in steps]}", flush=True)
    result = execute(steps, logged)
    print(f"Evidence: {evidence}", flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
