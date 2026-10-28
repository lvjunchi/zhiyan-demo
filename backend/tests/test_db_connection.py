from __future__ import annotations

import concurrent.futures
from pathlib import Path

from app.db import connect


def use_and_close(connection) -> int:
    try:
        row = connection.execute("SELECT 1 AS value").fetchone()
        return int(row["value"])
    finally:
        connection.close()


def test_connection_is_usable_and_closable_from_dependency_thread(
    tmp_path: Path,
) -> None:
    connection = connect(tmp_path / "cross-thread.db")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(use_and_close, connection).result() == 1
