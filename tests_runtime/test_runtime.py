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


def test_html_br_in_model_output_is_normalized_to_newline():
    # The model occasionally emits literal <br> as a line separator; it must never
    # surface as markup in the customer-facing output.
    payload = json.dumps({"customer_output": {
        "title": "PaymentServer功能优化",
        "description": "1.新增辅芯日志上送主芯功能。<br>2.优化P300背光键盘控制逻辑。<br>版本变更：<br>PaymentServer升级至 V1.0.71T",
    }})
    result = make_runtime(payload).transform("paymentserver升级", None, "default")
    assert result.description == "1.新增辅芯日志上送主芯功能。\n2.优化P300背光键盘控制逻辑。"
    assert result.customer_line == (
        "版本变更：\nPaymentServer升级至 V1.0.71T\n"
        "PaymentServer功能优化：1.新增辅芯日志上送主芯功能。\n2.优化P300背光键盘控制逻辑。"
    )
    assert "<br" not in result.customer_line


def test_html_br_in_version_block_from_model_is_not_duplicated():
    # Even when the model already supplied the version block (with <br>), the
    # deterministic extractor must not append a second block, and the <br> is
    # normalized to a real line break.
    payload = json.dumps({"customer_output": {
        "title": "PaymentServer功能优化",
        "description": "优化PaymentServer功能。\n版本变更：<br>PaymentServer_V1.0.71T",
    }})
    result = make_runtime(payload).transform(
        "paymentserver_V1.0.71T升级", None, "default")
    assert result.description == "优化PaymentServer功能。"
    assert result.customer_line == (
        "版本变更：\nPaymentServer_V1.0.71T\n"
        "PaymentServer功能优化：优化PaymentServer功能。"
    )
    assert result.customer_line.count("版本变更：") == 1


def test_nbsp_is_normalized_to_space():
    payload = json.dumps({"customer_output": {
        "title": "扫码", "description": "优化&nbsp;扫码功能&nbsp;稳定性",
    }})
    result = make_runtime(payload).transform("修复扫码", None, "default")
    assert result.description == "优化 扫码功能 稳定性"


def _make_raw(prefix: str, body: str) -> str:
    return f"{prefix} # 详细信息: {body}"


def test_fullwidth_detail_colon_preserves_prefix():
    # Real change sheets mark 详细信息 with the full-width colon ``：`` as often
    # as the ASCII ``:`` (53 of 64 rows in one sheet). Both must preserve the
    # ``{类别}: {模块} # 详细信息`` prefix verbatim.
    raw = "新功能：客显 # 详细信息：新增N950DS客显兼容版本以及识别功能#patch6/6\n测试方法：N950产品启动正常，客显正常显示\n自测checklist：https://newlandnpt.feishu.cn/sheets/CZxnsTacThhoWRt3i4jcY6Gcnhc"
    payload = json.dumps({"customer_output": {
        "title": "新功能", "description": "新增N950DS客显兼容版本以及识别功能。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == "新功能：客显 # 详细信息： 新增N950DS客显兼容版本以及识别功能。"
    # patch id / checklist must never leak into the customer line
    assert "patch" not in result.customer_line
    assert "feishu" not in result.customer_line


def test_ascii_detail_colon_preserves_prefix():
    raw = "改进:adbd # 详细信息: 优化用户版本下的系统日志输出"
    payload = json.dumps({"customer_output": {
        "title": "改进", "description": "优化用户版本下的系统日志输出。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == "改进:adbd # 详细信息: 优化用户版本下的系统日志输出。"


def test_fixed_prefix_without_version_leaves_no_block():
    raw = _make_raw("改进: 触摸屏", "优化触摸灵敏度。")
    payload = json.dumps({"customer_output": {
        "title": "改进", "description": "优化触摸灵敏度。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == "改进: 触摸屏 # 详细信息: 优化触摸灵敏度。"


def test_fixed_prefix_body_stops_at_next_section():
    # A ``#``-led section after 详细信息 must not leak into the refined body: the
    # model is only asked to refine the text up to the next section.
    raw = "新功能: 安全模块 # 详细信息: 支持黑色背景常驻显示。\n # 备注: 内部备注"
    payload = json.dumps({"customer_output": {
        "title": "新功能", "description": "支持黑色背景常驻显示。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == (
        "新功能: 安全模块 # 详细信息: 支持黑色背景常驻显示。"
    )
    assert "备注" not in result.customer_line


def test_fixed_prefix_is_preserved_verbatim_with_version_block():
    # A change sheet with the fixed ``{类别}: {模块} # 详细信息:`` header must
    # keep the prefix verbatim, put the deterministic version block on top, and
    # append the model's refined description after the prefix.
    raw = _make_raw(
        "新功能: 安全模块(NDK)",
        "基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13；支持黑色背景常驻显示。",
    )
    payload = json.dumps({"customer_output": {
        "title": "新功能",
        "description": "新增虚拟LED灯显示控制功能，支持黑色背景常驻显示。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == (
        "版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13\n"
        "新功能: 安全模块(NDK) # 详细信息: 新增虚拟LED灯显示控制功能，支持黑色背景常驻显示。"
    )
    # title is retained on the model payload but not used in the customer line.
    assert result.title == "新功能"
