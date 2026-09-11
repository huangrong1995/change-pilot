from pathlib import Path

import pytest

from runtime.skill_loader import SkillLoadError, load_skill

ROOT = Path(__file__).resolve().parents[1]


def test_missing_required_file_fails_closed(tmp_path):
    (tmp_path / "SKILL.md").write_text("# Skill")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "rules").mkdir()
    (tmp_path / "schemas").mkdir()
    with pytest.raises(SkillLoadError):
        load_skill(tmp_path)


def test_malformed_sensitive_policy_fails_closed(tmp_path):
    import shutil
    for name in ("SKILL.md", "prompts", "rules", "schemas"):
        src = ROOT / name
        if name.endswith(".md"):
            shutil.copy(src, tmp_path / name)
        else:
            shutil.copytree(src, tmp_path / name, dirs_exist_ok=True)
    (tmp_path / "rules" / "sensitive-patterns.yaml").write_text("patterns: [not a dict]\n")
    with pytest.raises(SkillLoadError):
        load_skill(tmp_path)


def test_malformed_schema_fails_closed(tmp_path):
    import shutil
    for name in ("SKILL.md", "prompts", "rules", "schemas"):
        src = ROOT / name
        if name.endswith(".md"):
            shutil.copy(src, tmp_path / name)
        else:
            shutil.copytree(src, tmp_path / name, dirs_exist_ok=True)
    (tmp_path / "schemas" / "output.schema.json").write_text("not json")
    with pytest.raises(SkillLoadError):
        load_skill(tmp_path)
