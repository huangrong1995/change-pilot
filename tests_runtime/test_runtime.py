import json
from pathlib import Path

import pytest

from runtime.models import ModelReply, ModelUsage, OutputInvalidError
from runtime.prompt_builder import PromptBuilder
from runtime.runtime import ChangePilotRuntime
from runtime.skill_loader import load_skill
from runtime.validator import OutputValidator

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    configured = True
    _model = "test-model"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        return ModelReply(self.payload, ModelUsage(total_tokens=4))

    async def acomplete(self, messages):
        self.calls += 1
        return ModelReply(self.payload, ModelUsage(total_tokens=4))


def make_runtime(payload):
    bundle = load_skill(ROOT)
    return ChangePilotRuntime(
        bundle,
        PromptBuilder(),
        FakeClient(payload),
        OutputValidator(bundle.output_schema, bundle.sensitive_patterns),
    )


def test_sync_transform_returns_customer_line():
    runtime = make_runtime(json.dumps({"customer_output": {"title": "扫码", "description": "提升稳定性"}}))
    result = runtime.transform("修复扫码", None, "default")
    assert result.customer_line == "扫码：提升稳定性"
    assert result.usage.total_tokens == 4


@pytest.mark.asyncio
async def test_async_transform_returns_debug_fields():
    runtime = make_runtime(json.dumps({
        "customer_output": {"title": "扫码", "description": "提升稳定性"},
        "analysis": {"change_types": ["optimization"]},
        "validation": {"passed": True},
    }))
    result = await runtime.transform_async("修复扫码", {"product": "POS"}, "debug")
    assert result.analysis == {"change_types": ["optimization"]}
    assert result.validation == {"passed": True}


def test_invalid_json_is_rejected():
    with pytest.raises(OutputInvalidError):
        make_runtime("not-json").transform("x", None, "default")


def test_think_block_prefix_is_stripped():
    # Reasoning models (e.g. MiniMax-M3) sometimes emit a <think> block before JSON.
    payload = ("<think>analysis of the change</think>\n\n"
               '{"customer_output": {"title": "扫码", "description": "提升稳定性"}}')
    result = make_runtime(payload).transform("修复扫码", None, "default")
    assert result.customer_line == "扫码：提升稳定性"


def test_reasoning_sketch_with_braces_is_ignored():
    # A reasoning draft may itself contain a balanced object; the real payload
    # (with top-level customer_output) must win.
    payload = ('{"title": "draft"}\n\n'
               '{"customer_output": {"title": "扫码", "description": "提升稳定性"}}')
    result = make_runtime(payload).transform("修复扫码", None, "default")
    assert result.customer_line == "扫码：提升稳定性"
