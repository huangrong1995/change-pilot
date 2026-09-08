import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from server.app.auth import require_bearer_token, set_expected_token
from server.app.errors import install_error_handlers


@pytest.fixture(autouse=True)
def _reset_token():
    set_expected_token("")
    yield


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    def protected(_: str = Depends(require_bearer_token)):
        return {"ok": True}

    install_error_handlers(app)
    return app


def test_missing_token_returns_401():
    set_expected_token("real-token")
    client = TestClient(_make_app())

    r = client.get("/protected")

    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.json()["error"]["message"] == "missing or malformed Authorization header"


def test_wrong_token_returns_401():
    set_expected_token("real-token")
    client = TestClient(_make_app())

    r = client.get("/protected", headers={"Authorization": "Bearer wrong"})

    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.json()["error"]["message"] == "invalid token"


def test_malformed_header_returns_401():
    set_expected_token("real-token")
    client = TestClient(_make_app())

    r = client.get("/protected", headers={"Authorization": "Basic abc"})

    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.json()["error"]["message"] == "missing or malformed Authorization header"


def test_empty_configured_token_rejects_any_bearer():
    set_expected_token("")
    client = TestClient(_make_app())

    r = client.get("/protected", headers={"Authorization": "Bearer some-token"})

    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"
    assert r.json()["error"]["message"] == "invalid token"


def test_correct_token_returns_200():
    set_expected_token("real-token")
    client = TestClient(_make_app())

    r = client.get("/protected", headers={"Authorization": "Bearer real-token"})

    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_token_whitespace_is_stripped():
    set_expected_token("real-token")
    client = TestClient(_make_app())

    r = client.get("/protected", headers={"Authorization": "Bearer   real-token  "})

    assert r.status_code == 200
    assert r.json()["ok"] is True
