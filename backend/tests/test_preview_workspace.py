import sqlite3
import pytest
from scripts.run_preview_backend import prepare_workspace


def test_persistent_preview_is_copied_once_and_keeps_local_edits(tmp_path):
    source = tmp_path / "source.db"
    connection = sqlite3.connect(source)
    connection.execute("CREATE TABLE values_for_test (value TEXT)")
    connection.execute("INSERT INTO values_for_test VALUES ('original')")
    connection.commit()
    connection.close()
    destination = tmp_path / "local" / "workspace.db"
    assert prepare_workspace(source, destination) == destination.resolve()
    edited = sqlite3.connect(destination)
    edited.execute("UPDATE values_for_test SET value='user edit'")
    edited.commit()
    edited.close()
    assert prepare_workspace(source, destination) == destination.resolve()
    with sqlite3.connect(destination) as current:
        assert (
            current.execute("SELECT value FROM values_for_test").fetchone()[0]
            == "user edit"
        )
    with sqlite3.connect(source) as original:
        assert (
            original.execute("SELECT value FROM values_for_test").fetchone()[0]
            == "original"
        )
    with pytest.raises(ValueError, match="source"):
        prepare_workspace(source, source)


def test_existing_invalid_workspace_is_not_replaced(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (id TEXT)")
    destination = tmp_path / "user-work.db"
    destination.write_bytes(b"existing damaged user data")
    with pytest.raises(sqlite3.DatabaseError):
        prepare_workspace(source, destination)
    assert destination.read_bytes() == b"existing damaged user data"
