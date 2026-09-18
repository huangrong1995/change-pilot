"""Deterministic version-change extraction (runtime fallback for the model)."""
from runtime.version_extractor import extract_version_changes


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
