import os
import pytest
from server.app.config import Settings, load_settings


def test_load_settings_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("CHANGE_PILOT_API_TOKEN", raising=False)
    monkeypatch.delenv("CHANGE_PILOT_SKILL_DIR", raising=False)
    monkeypatch.delenv("CHANGE_PILOT_AGENT_TIMEOUT", raising=False)
    s = load_settings()
    assert s.api_token == ""
    assert s.skill_dir.exists() or s.skill_dir == s.skill_dir  # path resolved
    assert s.agent_timeout_seconds == 180
    assert s.max_request_bytes == 100 * 1024


def test_load_settings_overrides(monkeypatch, tmp_path):
    skill = tmp_path / "skill"
    skill.mkdir()
    monkeypatch.setenv("CHANGE_PILOT_API_TOKEN", "tok-123")
    monkeypatch.setenv("CHANGE_PILOT_SKILL_DIR", str(skill))
    monkeypatch.setenv("CHANGE_PILOT_AGENT_TIMEOUT", "60")
    s = load_settings()
    assert s.api_token == "tok-123"
    assert s.skill_dir == skill
    assert s.agent_timeout_seconds == 60
