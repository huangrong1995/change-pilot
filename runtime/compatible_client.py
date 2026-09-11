"""OpenAI-compatible Chat Completions adapter.

Talks to any provider exposing an OpenAI-compatible ``/chat/completions``
endpoint, configured only by base_url, API key, and model (e.g. MiniMax,
DeepSeek, Qwen). Only the final response text and token counters escape;
raw payloads and API keys are never logged or returned.
"""
from __future__ import annotations

import openai

from runtime.models import (
    ChangePilotRuntimeError,
    ModelReply,
    ModelUsage,
    ProviderConfigurationError,
    ProviderError,
    ProviderTimeoutError,
)


_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_RETRIES = 1


class CompatibleClient:
    def __init__(self, *, base_url, api_key, model, max_tokens=1024,
                 timeout_seconds=_DEFAULT_TIMEOUT, max_retries=_DEFAULT_MAX_RETRIES):
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._sync = None
        self._async = None

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _require_sync(self):
        if not self._api_key:
            raise ProviderConfigurationError()
        if self._sync is None:
            self._sync = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                max_retries=self._max_retries,
            )
        return self._sync

    def _require_async(self):
        if not self._api_key:
            raise ProviderConfigurationError()
        if self._async is None:
            self._async = openai.AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                max_retries=self._max_retries,
            )
        return self._async

    def _build_kwargs(self, messages):
        return {
            "model": self._model,
            "messages": list(messages),
            "max_tokens": self._max_tokens,
        }

    def complete(self, messages) -> ModelReply:
        return _guard_errors(lambda: self._require_sync().chat.completions.create(
            **self._build_kwargs(messages)))

    async def acomplete(self, messages) -> ModelReply:
        try:
            response = await self._require_async().chat.completions.create(
                **self._build_kwargs(messages))
        except openai.APITimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except openai.AuthenticationError as exc:
            raise ProviderError("model provider authentication failed") from exc
        except openai.BadRequestError as exc:
            raise ProviderError("model provider rejected the request") from exc
        except openai.PermissionDeniedError as exc:
            raise ProviderError("model provider forbade the request") from exc
        except openai.RateLimitError as exc:
            raise ProviderError("model provider rate limit exceeded") from exc
        except openai.APIError as exc:
            raise ProviderError("model provider request failed") from exc
        except ChangePilotRuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError("model provider request failed") from exc
        return _extract_reply(response)


def _guard_errors(call):
    try:
        result = call()
    except openai.APITimeoutError as exc:
        raise ProviderTimeoutError() from exc
    except openai.AuthenticationError as exc:
        raise ProviderError("model provider authentication failed") from exc
    except openai.BadRequestError as exc:
        raise ProviderError("model provider rejected the request") from exc
    except openai.PermissionDeniedError as exc:
        raise ProviderError("model provider forbade the request") from exc
    except openai.RateLimitError as exc:
        raise ProviderError("model provider rate limit exceeded") from exc
    except openai.APIError as exc:
        raise ProviderError("model provider request failed") from exc
    except ChangePilotRuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 - keep the public path sanitized
        raise ProviderError("model provider request failed") from exc
    return _extract_reply(result)


def _extract_reply(response) -> ModelReply:
    try:
        text = response.choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError) as exc:
        raise ProviderError("model provider returned an empty response") from exc
    if not text.strip():
        raise ProviderError("model provider returned an empty response")
    usage = getattr(response, "usage", None)
    model_usage = ModelUsage()
    if usage is not None:
        model_usage = ModelUsage(
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        )
    return ModelReply(text=text, usage=model_usage)
