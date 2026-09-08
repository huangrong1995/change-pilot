import re
from pathlib import Path
import pytest
from server.app.validation.sensitive import load_patterns, find_sensitive_matches, check_description, SensitiveLeak

SAMPLE_YAML = r"""
patterns:
  bug:
    - '(?i)BUG[-_ ]?\d+'
  commit:
    - '\b[0-9a-f]{7,40}\b'
  file:
    - '[\w./-]+\.(cpp|java|so)'
"""

@pytest.fixture
def patterns_file(tmp_path) -> Path:
    p = tmp_path / "sensitive-patterns.yaml"
    p.write_text(SAMPLE_YAML)
    return p

def test_load_patterns_returns_flat_list(patterns_file):
    flat = load_patterns(patterns_file)
    assert any("BUG" in s for s in flat)
    assert any("[0-9a-f]" in s for s in flat)

def test_find_sensitive_matches_detects_bug_id():
    matches = find_sensitive_matches(["(?i)BUG[-_ ]?\\d+"], "see BUG-12345 for details")
    assert "BUG-12345" in matches

def test_find_sensitive_matches_detects_commit_hash():
    matches = find_sensitive_matches(["\\b[0-9a-f]{7,40}\\b"], "commit 921c90779da61d8ae67ae9ec0901214ff2ba8ba8 landed")
    assert any(m.startswith("921c9077") for m in matches)

def test_find_sensitive_matches_returns_empty_on_clean_text():
    matches = find_sensitive_matches(["(?i)BUG[-_ ]?\\d+", "\\b[0-9a-f]{7,40}\\b"], "扫码功能优化，提升扫码稳定性。")
    assert matches == []

def test_check_description_passes_when_clean(patterns_file):
    check_description("扫码功能优化", patterns_file)

def test_check_description_raises_on_bug_id_leak(patterns_file):
    with pytest.raises(SensitiveLeak) as ei:
        check_description("修复 BUG-12345 提到的问题", patterns_file)
    assert "BUG-12345" in str(ei.value)

def test_check_description_raises_on_file_path_leak(patterns_file):
    with pytest.raises(SensitiveLeak) as ei:
        check_description("修改 src/main.cpp 解决崩溃", patterns_file)
    assert ".cpp" in str(ei.value)
