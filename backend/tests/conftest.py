import pytest
from fastapi.testclient import TestClient

from app import design_services, services
from app.db import connect
from app.main import create_app


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "zhiyan-test.db"


@pytest.fixture()
def app(db_path):
    return create_app(db_path=str(db_path))


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def catalog_client(client, db_path):
    connection = connect(db_path)
    try:
        services.seed_catalog(connection)
    finally:
        connection.close()
    return client


@pytest.fixture()
def design_client(catalog_client, db_path):
    connection = connect(db_path)
    try:
        design_services.seed_history(connection)
    finally:
        connection.close()
    return catalog_client
