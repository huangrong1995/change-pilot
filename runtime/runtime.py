"""Shared synchronous and asynchronous runtime orchestration."""
from __future__ import annotations

import asyncio
import json
import re
import threading

from runtime.models import ModelReply, OutputInvalidError, TransformResult
from runtime.prompt_builder import PromptBuilder
from runtime.version_extractor import build_version_block, extract_version_changes
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
        _, model_text = _extract_prefix_and_body(raw_text)
        messages = self._messages(model_text, context, mode)
        async with self._async_semaphore:
            reply = await self._client.acomplete(messages)
        return self._finish(reply, raw_text)

    def transform(self, raw_text, context, mode) -> TransformResult:
        _, model_text = _extract_prefix_and_body(raw_text)
        messages = self._messages(model_text, context, mode)
        with self._sync_semaphore:
            reply = self._client.complete(messages)
        return self._finish(reply, raw_text)

    def _messages(self, raw_text, context, mode):
        return [
            {"role": "system", "content": self._builder.system_message(self._bundle)},
            {"role": "user", "content": self._builder.user_message(raw_text, context, mode)},
        ]

    def _finish(self, reply: ModelReply, raw_text: str) -> TransformResult:
        try:
            parsed = json.loads(_extract_json(reply.text))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise OutputInvalidError("model output is not valid JSON") from exc
        verified = self._validator.process(parsed)
        prefix, _ = _extract_prefix_and_body(raw_text)
        # The model's refined customer description. A version block the model
        # itself emitted is split out; the deterministic extractor on the full
        # raw source wins, falling back to the model's block only when the raw
        # text states no version change.
        description = _normalize_html_artifacts(verified.description)
        model_block, description = _split_version_block(description)
        version_block = build_version_block(extract_version_changes(raw_text)) or model_block
        note = _normalize_html_artifacts(verified.note) if verified.note else None
        if prefix:
            # Fixed-prefix template: version block, then the verbatim prefix
            # followed by the refined description.
            line = f"{prefix} {description}" if description else prefix
            customer_line = _prepend_version_block(line, version_block)
        else:
            # No fixed prefix in the source: keep the plain 标题：描述 render.
            customer_line = _render_customer_line(
                verified.title, description, version_block)
        if note:
            # A refined attention note surfaces as a standalone 注意： line after
            # the description so customers see sync/deployment caveats.
            customer_line += "\n注意：" + note
        return TransformResult(
            title=verified.title,
            description=description,
            customer_line=customer_line,
            note=note,
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


# A model-emitted HTML line break in any casing/slash variant: ``<br>``,
# ``<br/>``, ``<BR />``, etc.
_HTML_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _normalize_html_artifacts(text: str) -> str:
    """Collapse model-emitted HTML artifacts into plain text so customer-facing
    output never shows literal markup. ``<br>`` (any variant) becomes a line
    break, ``&nbsp;`` becomes a space. The model occasionally emits these instead
    of ``\\n`` (e.g. ``版本变更：<br>PaymentServer升级至 V1.0.71T``)."""
    if not text:
        return text
    text = _HTML_BR.sub("\n", text)
    text = text.replace("&nbsp;", " ")
    return text


_VERSION_HEADER = "版本变更："


def _split_version_block(description: str) -> tuple[str | None, str]:
    """Return ``(version_block, body)`` split from a model description.

    ``version_block`` is the ``版本变更：`` section (header plus its lines) with
    trailing blank lines trimmed, or ``None`` when the description carries no such
    section. ``body`` is everything before that section, with leading/trailing
    blank lines trimmed. The version block is always rendered first, so this is
    what moves a model-emitted ``版本变更：`` section to the front of the output."""
    lines = description.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith(_VERSION_HEADER):
            block_lines = lines[i:]
            while block_lines and not block_lines[-1].strip():
                block_lines.pop()
            block = "\n".join(block_lines).strip()
            body = "\n".join(lines[:i]).strip()
            return (block or None), body
    return None, description.strip()


def _render_customer_line(title: str | None, description: str,
                          version_block: str | None) -> str:
    """Render the customer-facing line, leading with the version block.

    The ``版本变更：`` block (when present) is a standalone leading section,
    followed by the usual ``标题：描述`` line, so release notes open with
    version changes rather than burying them inside the description."""
    line = build_customer_output_line(title, description)
    return _prepend_version_block(line, version_block)


def _prepend_version_block(line: str, version_block: str | None) -> str:
    if not version_block:
        return line
    return version_block + "\n" + line


# A fixed change-sheet prefix of the form ``新功能: 安全模块(NDK) # 详细信息:``.
# The ``详细信息`` marker may be followed by either an ASCII ``:`` or a full-width
# ``：`` (the two change sheets use both inconsistently). The prefix (including
# the marker) is preserved verbatim for the customer line; the body between it
# and the next ``#``-led section (or the end) is what the customerization model
# refines.
#
# The marker must sit on the FIRST line (right after a short ``类别: 模块``
# header): some change sheets bury a ``… # 详细信息：…`` line inside a longer
# document (e.g. after a ``版本信息`` section), and matching it there would treat
# the entire leading text as a bogus "prefix" and echo it verbatim. Requiring no
# ``\n`` before the marker keeps the prefixed path for genuine leading headers
# and lets the rest fall back to the plain ``标题：描述`` render.
_SOURCE_SECTION = re.compile(
    r"^([^\n]*?#\s*详细信息[:：])\s*(.*?)(?=\n\s*#|\Z)",
    re.DOTALL | re.IGNORECASE,
)


def _clean_prefix(prefix: str) -> str:
    """Drop intermediate `` # <label>：<value>`` sections from a matched prefix.

    A few change points interleave BUG/飞书ID/patch references between the module
    name and ``详细信息``, e.g. ``错误修复：eSIM服务 # BUG：… # 详细信息：``. Those
    sections carry no customer value, so the verbatim prefix keeps only the leading
    ``类别: 模块`` and the trailing ``# 详细信息`` marker."""
    first = prefix.find("#")
    last = prefix.rfind("#")
    if first == -1:
        return prefix
    module = prefix[:first].strip()
    marker = prefix[last:]
    return f"{module} {marker}".strip()


def _extract_prefix_and_body(raw_text: str) -> tuple[str, str]:
    """Return ``(prefix, body)`` split by the fixed change-sheet header.

    ``prefix`` is the verbatim leading section up to and including the
    ``# 详细信息:`` marker (e.g. ``新功能: 安全模块(NDK) # 详细信息:``), with any
    intermediate `` # BUG：…`` / `` # 飞书ID：…`` sections stripped. ``body`` is
    the content after it, up to the next ``#``-led section or the end of the
    input. When the input carries no such header, returns ``("", raw_text)`` so
    callers fall back to the plain title-driven render."""
    m = _SOURCE_SECTION.search(raw_text)
    if not m:
        return "", raw_text.strip()
    prefix = _clean_prefix(m.group(1).strip())
    body = m.group(2).strip()
    return prefix, body
