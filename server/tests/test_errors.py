from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from server.app.errors import install_error_handlers
from server.app.errors import AgentTimeout, InvalidRequest


def test_envelope_shape_on_custom_error():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise AgentTimeout("subprocess took too long")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 504
    body = r.json()
    assert body == {
        "success": False,
        "error": {"code": "AGENT_TIMEOUT", "message": "subprocess took too long"},
    }


def test_envelope_shape_on_invalid_request():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/bad")
    def bad():
        raise InvalidRequest("missing raw_text")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/bad")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_REQUEST"


def test_request_validation_error_becomes_invalid_request():
    app = FastAPI()
    install_error_handlers(app)

    from pydantic import BaseModel

    class Payload(BaseModel):
        raw_text: str

    @app.post("/submit")
    def submit(payload: Payload):
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/submit", json={})  # missing required field -> RequestValidationError
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_REQUEST"


def test_http_exception_passthrough():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/notfound")
    def notfound():
        raise HTTPException(status_code=404, detail="nope")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/notfound")
    assert r.status_code == 404


def test_unhandled_exception_becomes_500():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/explode")
    def explode():
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/explode")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"
