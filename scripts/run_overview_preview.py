"""Test-only empty overview server; never opens the daily workspace database."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import design_services, services  # noqa: E402
from app.db import connect, run_migrations  # noqa: E402
from app.main import create_app  # noqa: E402
from app.schemas import ProjectCreate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="zhiyan-empty-overview-") as directory:
        database = Path(directory) / "empty.db"
        connection = connect(database)
        try:
            run_migrations(connection)
            services.seed_catalog(connection)
            design_services.seed_history(connection)
            services.create_project(
                connection,
                ProjectCreate(
                    display_code="P01",
                    name="法士特—陕汽定制项目试点",
                    customer="陕汽集团",
                    product="重型商用车变速器",
                ),
            )
        finally:
            connection.close()
        uvicorn.run(
            create_app(database), host="127.0.0.1", port=args.port, log_level="warning"
        )


if __name__ == "__main__":
    main()
