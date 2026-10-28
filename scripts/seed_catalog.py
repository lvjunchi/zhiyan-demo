from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import connect, run_migrations  # noqa: E402
from app.services import seed_catalog  # noqa: E402


def main() -> None:
    db_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "data" / "zhiyan.db"
    )
    connection = connect(db_path)
    try:
        run_migrations(connection)
        result = seed_catalog(connection)
    finally:
        connection.close()
    print(
        json.dumps(
            {"database": str(db_path), "seeded": result},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
