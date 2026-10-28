"""Serve an independently seeded synthetic database for browser regression tests."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import connect
from app import services, design_services
from package_scenario import build_ready_project


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8046)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="zhiyan-fix-e2e-") as directory:
        path = Path(directory) / "regression.db"
        app = create_app(path)
        with TestClient(app) as client:
            connection = connect(path)
            try:
                services.seed_catalog(connection)
                design_services.seed_history(connection)
            finally:
                connection.close()
            build_ready_project(client)
        uvicorn.run(
            create_app(path), host="127.0.0.1", port=args.port, log_level="warning"
        )


if __name__ == "__main__":
    main()
