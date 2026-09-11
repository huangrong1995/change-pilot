from pathlib import Path

from runtime.models import SkillBundle
from runtime.prompt_builder import PromptBuilder
from runtime.skill_loader import load_skill

ROOT = Path(__file__).resolve().parents[1]


def test_prompts_separate_trusted_and_dynamic_text():
    bundle = load_skill(ROOT)
    builder = PromptBuilder()
    system = builder.system_message(bundle)
    user = builder.user_message("UNIQUE-RAW-TEXT", {"product": "POS"}, "default")
    assert bundle.skill_md in system
    assert "output.schema.json" in system
    assert "UNIQUE-RAW-TEXT" not in system
    assert "UNIQUE-RAW-TEXT" in user
    assert "POS" in user


def test_system_prompt_is_stable():
    bundle = load_skill(ROOT)
    builder = PromptBuilder()
    assert builder.system_message(bundle) == builder.system_message(bundle)
