import pytest
from fastapi.testclient import TestClient

from server.app.main import create_app
from server.app.auth import set_expected_token
from server.app.config import load_settings


@pytest.fixture
def app():
    a = create_app()
    set_expected_token("test-token")
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def settings():
    return load_settings()
