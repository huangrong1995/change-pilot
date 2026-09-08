import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from server.app.auth import install_auth_exception_handler, require_bearer_token, set_expected_token


@pytest.fixture(autouse=True)
def _reset_token():
    set_expected_token("")
    yield


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    def protected(_: str = Depends(require_bearer_token)):
        return {"ok": True}

    install_auth_exception_handler(app)
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


def test_malformed_header_returns_401():
    set_expected_token("real-token")
    client = TestClient(_make_app())

    r = client.get("/protected", headers={"Authorization": "Basic abc"})

    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_correct_token_returns_200():
    set_expected_token("real-token")
    client = TestClient(_make_app())

    r = client.get("/protected", headers={"Authorization": "Bearer real-token"})

    assert r.status_code == 200
    assert r.json()["ok"] is True
