from runtime.models import OutputInvalidError, TransformResult


class FakeRuntime:
    def __init__(self, result=None, error=None):
        self.result = result or TransformResult("扫码功能优化", "优化扫码功能，提升扫码稳定性。", "扫码功能优化：优化扫码功能，提升扫码稳定性。", {"change_types": ["optimization"]}, {"passed": True})
        self.error = error
        self.received = None
        self.provider_configured = True
        self.model = "test-model"

    async def transform_async(self, raw_text, context, mode):
        self.received = (raw_text, context, mode)
        if self.error:
            raise self.error
        return self.result


def install(app, result=None, error=None):
    fake = FakeRuntime(result, error)
    app.state.change_pilot_runtime = fake
    return fake


def test_change_pilot_happy_path(client, app, auth_headers):
    install(app)
    r = client.post("/v1/change-pilot", headers=auth_headers, json={"raw_text": "修复扫码稳定性"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["customer_output"] == "扫码功能优化：优化扫码功能，提升扫码稳定性。"
    assert body["request_id"].startswith("req_")
    assert body.get("analysis") is None


def test_change_pilot_requires_auth(client):
    r = client.post("/v1/change-pilot", json={"raw_text": "x"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_change_pilot_rejects_empty_raw_text(client, auth_headers):
    r = client.post("/v1/change-pilot", headers=auth_headers, json={"raw_text": ""})
    assert r.status_code in (400, 422)
    assert r.json()["error"]["code"] == "INVALID_REQUEST"


def test_change_pilot_rejects_unknown_field(client, auth_headers):
    r = client.post("/v1/change-pilot", headers=auth_headers, json={"raw_text": "x", "stealth": True})
    assert r.status_code in (400, 422)


def test_change_pilot_debug_mode_passes_through_analysis(client, app, auth_headers):
    result = TransformResult("扫码功能优化", "优化扫码功能，提升扫码稳定性。", "扫码功能优化：优化扫码功能，提升扫码稳定性。", {"change_types": ["optimization"], "business_intent": "x"}, {"passed": True})
    install(app, result=result)
    body = client.post("/v1/change-pilot", headers=auth_headers, json={"raw_text": "x", "mode": "debug"}).json()
    assert body["analysis"]["business_intent"] == "x"
    assert body["validation"] == {"passed": True}


def test_change_pilot_context_propagates(client, app, auth_headers):
    fake = install(app)
    r = client.post("/v1/change-pilot", headers=auth_headers, json={"raw_text": "x", "context": {"product": "POS", "module": "扫码"}})
    assert r.status_code == 200
    assert fake.received[1] == {"product": "POS", "module": "扫码"}


def test_change_pilot_rejects_invalid_model_output(client, app, auth_headers):
    install(app, error=OutputInvalidError())
    r = client.post("/v1/change-pilot", headers=auth_headers, json={"raw_text": "x"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "AGENT_OUTPUT_INVALID"


def test_change_pilot_runtime_unavailable(client, app, auth_headers):
    app.state.change_pilot_runtime = None
    r = client.post("/v1/change-pilot", headers=auth_headers, json={"raw_text": "x"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "AGENT_FAILED"
