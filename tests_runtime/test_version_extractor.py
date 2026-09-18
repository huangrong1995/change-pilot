"""Deterministic version-change extraction (runtime fallback for the model)."""
from runtime.version_extractor import build_version_block, extract_version_changes


def test_old_and_new_version_yield_upgrade_line():
    raw = "基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13。"
    assert extract_version_changes(raw) == ["NDK_V4.1.12 升级至 NDK_V4.1.13"]


def test_component_subject_with_connector():
    assert extract_version_changes("MDB芯片升级至V1.1.21") == ["MDB芯片升级至 V1.1.21"]


def test_config_file_version_update():
    assert extract_version_changes("配置文件版本号更新至020.057") == ["配置文件版本号更新至 020.057"]


def test_touchscreen_driver_version_change():
    assert extract_version_changes("触屏驱动版本变更为2.0.46") == ["触屏驱动版本变更为 2.0.46"]


def test_bare_version_change_without_subject_is_skipped():
    assert extract_version_changes("版本变更为2.0.47") == []


def test_compatibility_note_is_not_an_upgrade():
    assert extract_version_changes("配置了PaymentServer_V1.0.71T及以上版本使用") == []


def test_long_prefix_new_version_is_not_truncated():
    assert extract_version_changes("设备版本升级至PaymentServer_V1.0.72T") == ["设备版本升级至 PaymentServer_V1.0.72T"]


def test_no_version_change_returns_empty():
    assert extract_version_changes("优化扫码功能，提升扫码稳定性。") == []


def test_duplicates_removed_order_preserved():
    raw = ("NDK_V4.1.12 升级至 NDK_V4.1.13，"
           "同时NDK_V4.1.12 升级至 NDK_V4.1.13，"
           "MDB芯片升级至 V1.1.21")
    assert extract_version_changes(raw) == [
        "NDK_V4.1.12 升级至 NDK_V4.1.13",
        "MDB芯片升级至 V1.1.21",
    ]


def test_build_version_block_none_for_empty():
    assert build_version_block([]) is None


def test_build_version_block_formats_lines():
    block = build_version_block(["NDK_V4.1.12 升级至 NDK_V4.1.13"])
    assert block == "版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"


import json
from pathlib import Path

import pytest

from runtime.models import ModelReply, ModelUsage
from runtime.prompt_builder import PromptBuilder
from runtime.runtime import ChangePilotRuntime
from runtime.skill_loader import load_skill
from runtime.validator import OutputValidator

ROOT = Path(__file__).resolve().parents[1]

RAW_WITH_VERSION = "基于NDK_V4.1.12修改，更新版本号至NDK_V4.1.13。"


class _FakeClient:
    configured = True
    _model = "test-model"

    def __init__(self, payload):
        self.payload = payload

    def complete(self, messages):
        return ModelReply(self.payload, ModelUsage(total_tokens=4))

    async def acomplete(self, messages):
        return ModelReply(self.payload, ModelUsage(total_tokens=4))


def _make_runtime(payload):
    bundle = load_skill(ROOT)
    return ChangePilotRuntime(
        bundle, PromptBuilder(), _FakeClient(payload),
        OutputValidator(bundle.output_schema, bundle.sensitive_patterns),
    )


def test_sync_appends_version_block_when_model_omits_it():
    payload = json.dumps({"customer_output": {"title": "扫码", "description": "优化NDK相关功能。"}})
    result = _make_runtime(payload).transform(RAW_WITH_VERSION, None, "default")
    expected = "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"
    assert result.description == expected
    assert result.customer_line == "扫码：" + expected


@pytest.mark.asyncio
async def test_async_appends_version_block_when_model_omits_it():
    payload = json.dumps({"customer_output": {"title": "扫码", "description": "优化NDK相关功能。"}})
    result = await _make_runtime(payload).transform_async(RAW_WITH_VERSION, None, "default")
    expected = "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"
    assert result.description == expected
    assert result.customer_line == "扫码：" + expected


def test_model_version_block_is_not_duplicated():
    payload = json.dumps({"customer_output": {
        "title": "扫码",
        "description": "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13",
    }})
    result = _make_runtime(payload).transform(RAW_WITH_VERSION, None, "default")
    assert result.description == "优化NDK相关功能。\n版本变更：\nNDK_V4.1.12 升级至 NDK_V4.1.13"


def test_no_version_change_leaves_output_unchanged():
    payload = json.dumps({"customer_output": {"title": "扫码", "description": "优化扫码稳定性。"}})
    result = _make_runtime(payload).transform("修复扫码", None, "default")
    assert result.description == "优化扫码稳定性。"
