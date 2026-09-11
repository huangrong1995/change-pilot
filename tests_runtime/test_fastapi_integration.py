import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from runtime.models import ModelReply
from runtime.prompt_builder import PromptBuilder
from runtime.runtime import ChangePilotRuntime
from runtime.skill_loader import load_skill
from runtime.validator import OutputValidator
from server.app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    configured = True
    _model = "test-model"

    async def acomplete(self, messages):
        return ModelReply(json.dumps({
            "customer_output": {"title": "扫码", "description": "提升稳定性"},
            "analysis": {"change_types": ["optimization"]},
            "validation": {"passed": True},
        }))

    def complete(self, messages):
        raise AssertionError("HTTP route must use async client")


def test_http_uses_real_runtime_with_mocked_provider(monkeypatch):
    bundle = load_skill(ROOT)
    runtime = ChangePilotRuntime(bundle, PromptBuilder(), FakeClient(),
                                 OutputValidator(bundle.output_schema, bundle.sensitive_patterns))
    monkeypatch.setenv("CHANGE_PILOT_API_TOKEN", "test-token")
    client = TestClient(create_app(runtime=runtime))
    response = client.post("/v1/change-pilot", headers={"Authorization": "Bearer test-token"},
                           json={"raw_text": "修复扫码", "mode": "debug"})
    assert response.status_code == 200
    assert response.json()["customer_output"] == "扫码：提升稳定性"
    assert response.json()["analysis"]["change_types"] == ["optimization"]


def test_health_does_not_expose_provider_key(monkeypatch):
    monkeypatch.setenv("CHANGE_PILOT_API_TOKEN", "test-token")
    monkeypatch.setenv("CHANGE_PILOT_API_KEY", "secret-provider-key")
    client = TestClient(create_app())
    body = client.get("/health").json()
    assert "secret-provider-key" not in json.dumps(body)
    assert "provider" in body
