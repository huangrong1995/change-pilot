from pathlib import Path

import pytest

from runtime.models import OutputInvalidError
from runtime.skill_loader import load_skill
from runtime.validator import OutputValidator

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def validator():
    bundle = load_skill(ROOT)
    return OutputValidator(bundle.output_schema, bundle.sensitive_patterns)


def test_validates_and_normalizes_line(validator):
    result = validator.process({"customer_output": "扫码：提升稳定性"})
    assert result.title == "扫码"
    assert result.description == "提升稳定性"


def test_rejects_schema_violation(validator):
    with pytest.raises(OutputInvalidError):
        validator.process({"customer_output": {"description": ""}})


def test_rejects_sensitive_output(validator):
    with pytest.raises(OutputInvalidError):
        validator.process({"customer_output": {"title": None, "description": "修复 BUG-12345"}})


def test_rejects_non_object(validator):
    with pytest.raises(OutputInvalidError):
        validator.process("not json")
