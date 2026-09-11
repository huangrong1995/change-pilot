from types import SimpleNamespace

import openai
import pytest

from runtime.compatible_client import CompatibleClient
from runtime.models import ProviderConfigurationError, ProviderError, ProviderTimeoutError


class _Completions:
    def __init__(self, fn):
        self._fn = fn

    def create(self, **kwargs):
        return self._fn(kwargs)


class _Chat:
    def __init__(self, fn):
        self.completions = _Completions(fn)


class _Client:
    def __init__(self, fn):
        self.chat = _Chat(fn)


def _response(content="ok"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
    )


def test_complete_extracts_only_text_and_usage():
    client = CompatibleClient(base_url="http://provider", api_key="key", model="model")
    client._sync = _Client(lambda kwargs: _response('{"ok":true}'))
    reply = client.complete([{"role": "user", "content": "x"}])
    assert reply.text == '{"ok":true}'
    assert reply.usage.total_tokens == 5


def test_missing_key_is_configuration_error():
    client = CompatibleClient(base_url="http://provider", api_key="", model="model")
    with pytest.raises(ProviderConfigurationError):
        client.complete([])


def test_timeout_is_sanitized():
    client = CompatibleClient(base_url="http://provider", api_key="key", model="model")
    timeout = openai.APITimeoutError.__new__(openai.APITimeoutError)
    client._sync = _Client(lambda kwargs: (_ for _ in ()).throw(timeout))
    with pytest.raises(ProviderTimeoutError):
        client.complete([])


def test_provider_errors_are_sanitized():
    client = CompatibleClient(base_url="http://provider", api_key="key", model="model")
    error = openai.APIError.__new__(openai.APIError)
    client._sync = _Client(lambda kwargs: (_ for _ in ()).throw(error))
    with pytest.raises(ProviderError) as exc_info:
        client.complete([])
    assert "provider" in str(exc_info.value)
