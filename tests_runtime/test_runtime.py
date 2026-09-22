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


def test_intermediate_bug_id_section_is_stripped_from_prefix():
    # A `` # BUG：…`` section between the module name and ``详细信息`` carries
    # internal ticket IDs that must never surface on the customer line. Only the
    # leading ``类别: 模块`` and the ``# 详细信息`` marker are kept.
    raw = "错误修复：eSIM服务 # BUG：5243041440，5240807933，5240795948，5246663509，5246732037 # 详细信息：修复eSIM服务无法正常连接运营商网络的问题。"
    payload = json.dumps({"customer_output": {
        "title": "错误修复", "description": "修复eSIM服务无法正常连接运营商网络的问题。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == (
        "错误修复：eSIM服务 # 详细信息： 修复eSIM服务无法正常连接运营商网络的问题。"
    )
    assert "BUG" not in result.customer_line
    assert "5243" not in result.customer_line


def test_intermediate_feishu_id_section_is_stripped_from_prefix():
    # Same normalization for a `` # 飞书ID：…`` section.
    raw = "错误修复： SystemUI # 飞书ID：5916803698 # 详细信息：修复状态栏文字重叠问题。"
    payload = json.dumps({"customer_output": {
        "title": "错误修复", "description": "修复状态栏文字重叠问题。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == (
        "错误修复： SystemUI # 详细信息： 修复状态栏文字重叠问题。"
    )
    assert "飞书" not in result.customer_line
    assert "5916" not in result.customer_line


def test_attention_note_is_rendered_as_trailing_line():
    # A 注／注意 source section is refined by the model into customer_output.note
    # and rendered as a standalone 注意： line after the description.
    raw = "改进：MDB模块 # 详细信息：降低功耗，修改MDB串口波特率为460800。\n注：需同步MDB固件、mdbserver、NLPUpdater更新，只影响U2000产品，其他产品不需要同步更新。\n测试方法：测试U2000 MDB基本功能是否正常。\n自测checklist: https://example"
    payload = json.dumps({"customer_output": {
        "title": "改进", "description": "降低功耗，修改MDB串口波特率为460800。",
        "note": "此变更需同步更新相关固件与组件，仅影响U2000产品。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == (
        "改进：MDB模块 # 详细信息： 降低功耗，修改MDB串口波特率为460800。\n"
        "注意：此变更需同步更新相关固件与组件，仅影响U2000产品。"
    )
    assert result.note == "此变更需同步更新相关固件与组件，仅影响U2000产品。"


def test_attention_note_in_no_prefix_render():
    raw = "优化扫码功能。注意：此功能仅影响A12及以上平台。"
    payload = json.dumps({"customer_output": {
        "title": "扫码", "description": "优化扫码功能。",
        "note": "此功能仅影响A12及以上平台。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == "扫码：优化扫码功能。\n注意：此功能仅影响A12及以上平台。"


def test_attention_note_follows_version_block():
    # With a version upgrade, the 注意： line stays last: version block, then the
    # title line, then the note.
    raw = "基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13。注意：需配合最新固件使用。"
    payload = json.dumps({"customer_output": {
        "title": "新功能", "description": "新增虚拟LED灯显示控制功能。",
        "note": "需配合最新固件使用。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    assert result.customer_line == (
        "版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13\n"
        "新功能：新增虚拟LED灯显示控制功能。\n"
        "注意：需配合最新固件使用。"
    )


def test_absent_note_leaves_no_note_line():
    # No attention note in the source / model output → no 注意： line at all.
    payload = json.dumps({"customer_output": {
        "title": "扫码", "description": "优化扫码稳定性。",
    }})
    result = make_runtime(payload).transform("修复扫码", None, "default")
    assert result.customer_line == "扫码：优化扫码稳定性。"
    assert result.note is None
    assert "注意" not in result.customer_line


def test_buried_detail_marker_is_not_treated_as_prefix():
    # A ``# 详细信息`` line buried mid-document (not a leading ``类别: 模块``
    # header) must NOT turn the whole leading text into a bogus prefix. Real
    # change sheets occasionally carry a ``… # 详细信息：…`` line after a
    # ``版本信息`` section; that source is a no-prefix point, so it should render
    # plain ``标题：描述`` with the AI title — never echo the whole ``1、版本信息…``
    # preamble verbatim.
    raw = (
        "1、版本信息\n"
        "3652/3654通用安全模块MASTER版本信息\n"
        "master版本由3.6.00.16变更为3.6.00.17；\n"
        "2、详细变更说明\n"
        "新增接口NDK_RfidFunisSupport，获取设备是否支持HCE或LPCD模式；\n"
        "3、自测checklist：\n"
        "https://newlandnpt.feishu.cn/sheets/NjGisIWrW\n"
        "新功能：安全模块 # 详细信息：MAPP_V9.63.20.06"
    )
    payload = json.dumps({"customer_output": {
        "title": "安全模块",
        "description": "新增RFID功能查询接口，支持查询设备是否支持HCE或LPCD模式。",
    }})
    result = make_runtime(payload).transform(raw, None, "default")
    # Renders as a no-prefix point with the AI title, not the bogus prefix.
    assert result.customer_line == (
        "安全模块：新增RFID功能查询接口，支持查询设备是否支持HCE或LPCD模式。"
    )
    # The preamble / checklist / buried marker must never surface as a prefix.
    assert "1、版本信息" not in result.customer_line
    assert "feishu" not in result.customer_line
    assert "MAPP_V9.63.20.06" not in result.customer_line


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
