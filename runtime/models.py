"""Typed contracts and sanitized errors for the lightweight runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ChangePilotRuntimeError(Exception):
    code = "AGENT_FAILED"
    message = "runtime error"

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class ProviderConfigurationError(ChangePilotRuntimeError):
    message = "model provider is not configured"


class ProviderError(ChangePilotRuntimeError):
    message = "model provider request failed"


class ProviderTimeoutError(ChangePilotRuntimeError):
    code = "AGENT_TIMEOUT"
    message = "model provider request timed out"


class OutputInvalidError(ChangePilotRuntimeError):
    code = "AGENT_OUTPUT_INVALID"
    message = "model output failed validation"


@dataclass(frozen=True)
class SkillBundle:
    skill_md: str
    prompts: dict[str, str]
    rules: dict[str, str]
    sensitive_patterns: list[str]
    output_schema: dict[str, Any]
    source_dir: str


@dataclass(frozen=True)
class ModelUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ModelReply:
    text: str
    usage: ModelUsage = field(default_factory=ModelUsage)


@dataclass(frozen=True)
class TransformResult:
    title: str | None
    description: str
    customer_line: str
    analysis: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    usage: ModelUsage = field(default_factory=ModelUsage)
