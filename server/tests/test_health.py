def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "agent" in body
    assert "skill" in body


def test_health_does_not_require_auth(client):
    r = client.get("/health")
    assert r.status_code == 200
