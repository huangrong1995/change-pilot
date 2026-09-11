"""Shared synchronous and asynchronous runtime orchestration."""
from __future__ import annotations

import asyncio
import json
import threading

from runtime.models import ModelReply, OutputInvalidError, TransformResult
from runtime.prompt_builder import PromptBuilder
from runtime.validator import OutputValidator
from server.app.models.response import build_customer_output_line


class ChangePilotRuntime:
    def __init__(self, bundle, builder: PromptBuilder, client,
                 validator: OutputValidator, *, max_concurrency: int = 4):
        self._bundle = bundle
        self._builder = builder
        self._client = client
        self._validator = validator
        self._async_semaphore = asyncio.Semaphore(max_concurrency)
        self._sync_semaphore = threading.Semaphore(max_concurrency)
        self.model = getattr(client, "_model", None)

    @property
    def provider_configured(self) -> bool:
        return bool(getattr(self._client, "configured", False))

    @property
    def skill_available(self) -> bool:
        return True

    @property
    def client(self):
        return self._client

    async def transform_async(self, raw_text, context, mode) -> TransformResult:
        messages = self._messages(raw_text, context, mode)
        async with self._async_semaphore:
            reply = await self._client.acomplete(messages)
        return self._finish(reply)

    def transform(self, raw_text, context, mode) -> TransformResult:
        messages = self._messages(raw_text, context, mode)
        with self._sync_semaphore:
            reply = self._client.complete(messages)
        return self._finish(reply)

    def _messages(self, raw_text, context, mode):
        return [
            {"role": "system", "content": self._builder.system_message(self._bundle)},
            {"role": "user", "content": self._builder.user_message(raw_text, context, mode)},
        ]

    def _finish(self, reply: ModelReply) -> TransformResult:
        try:
            parsed = json.loads(_extract_json(reply.text))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise OutputInvalidError("model output is not valid JSON") from exc
        verified = self._validator.process(parsed)
        return TransformResult(
            title=verified.title,
            description=verified.description,
            customer_line=build_customer_output_line(verified.title, verified.description),
            analysis=verified.analysis,
            validation=verified.validation,
            usage=reply.usage,
        )


_MAX_JSON_SCAN = 8


def _strip_code_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else ""
        if value.rstrip().endswith("```"):
            value = value.rstrip()[:-3]
    return value.strip()


def _strip_think_block(text: str) -> str:
    """Drop a leading reasoning/thinking block that some reasoning models emit
    before the actual JSON payload (e.g. ``<think>...</think>``, ``<reasoning>``).
    Matches on the first closing tag so JSON after the block is preserved.
    """
    value = text.strip()
    for open_tag, close_tag in (("<think>", "</think>"),
                                ("<reasoning>", "</reasoning>")):
        if value.lower().startswith(open_tag):
            idx = value.lower().find(close_tag)
            if idx != -1:
                value = value[idx + len(close_tag):].strip()
    return value


def _extract_json(text: str) -> str:
    """Strip reasoning/think blocks and code fences, then isolate the JSON object
    the model emitted. Reasoning blocks may themselves contain '{'/'}' (e.g. a
    model sketching ``{"title": ...}`` in its thinking) or a standalone partial
    object, so a naive first-`{` slice is not reliable. Walk each '{' as a
    candidate start, scan forward to its matching '}', keep every balanced
    candidate that parses, and prefer the one with a top-level `customer_output`
    key (the skill's required output contract) over smaller reasoning drafts.
    Fails closed (raises) if no balanced JSON object parses.
    """
    value = _strip_think_block(text)
    value = _strip_code_fence(value)
    starts = [i for i, ch in enumerate(value) if ch == "{"][:_MAX_JSON_SCAN]
    parseable: list[str] = []
    for i in starts:
        depth = 0
        closed = None
        for pos in range(i, len(value)):
            ch = value[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    closed = pos
                    break
        if closed is None:
            continue
        candidate = value[i:closed + 1]
        try:
            json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        parseable.append(candidate)
    if not parseable:
        raise ValueError("no JSON object found in model output")
    # Prefer the object that matches the skill's required output contract (has a
    # top-level customer_output key); reasoning drafts are usually smaller partial
    # objects and should not be selected over the real payload.
    for candidate in parseable:
        try:
            if "customer_output" in json.loads(candidate):
                return candidate
        except (json.JSONDecodeError, TypeError):
            continue
    return parseable[0]
