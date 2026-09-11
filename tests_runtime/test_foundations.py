from pathlib import Path

from runtime.models import ModelReply, ModelUsage, SkillBundle, TransformResult
from runtime.skill_loader import load_skill

ROOT = Path(__file__).resolve().parents[1]


def test_load_skill_bundle():
    bundle = load_skill(ROOT)
    assert isinstance(bundle, SkillBundle)
    assert "analyze.md" in bundle.prompts
    assert bundle.sensitive_patterns
    assert bundle.output_schema["required"] == ["customer_output"]


def test_models_are_immutable():
    result = TransformResult("t", "d", "t：d")
    assert result.usage == ModelUsage()
    try:
        result.title = "changed"
    except AttributeError:
        pass
    else:
        raise AssertionError("TransformResult must be immutable")


def test_model_reply_defaults_usage():
    assert ModelReply("text").usage.total_tokens == 0
