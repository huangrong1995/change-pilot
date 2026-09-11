"""Startup-only loading of the authoritative Change Pilot skill assets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from runtime.models import ChangePilotRuntimeError, SkillBundle


REQUIRED_PROMPTS = ("analyze.md", "transform.md", "validate.md")
REQUIRED_RULES = ("core-rules.md", "terminology.yaml", "sensitive-patterns.yaml")


class SkillLoadError(ChangePilotRuntimeError):
    message = "change pilot skill could not be loaded"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SkillLoadError("skill asset unreadable") from exc


def _required(directory: Path, name: str) -> str:
    path = directory / name
    if not path.is_file():
        raise SkillLoadError("required skill asset is missing")
    return _read(path)


def _patterns(content: str) -> list[str]:
    try:
        value: Any = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise SkillLoadError("sensitive policy is invalid") from exc
    groups = value.get("patterns") if isinstance(value, dict) else None
    if not isinstance(groups, dict):
        raise SkillLoadError("sensitive policy is invalid")
    result: list[str] = []
    for group in groups.values():
        if not isinstance(group, list) or not all(isinstance(item, str) for item in group):
            raise SkillLoadError("sensitive policy is invalid")
        result.extend(group)
    return result


def _schema(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SkillLoadError("output schema is invalid") from exc
    if not isinstance(value, dict):
        raise SkillLoadError("output schema is invalid")
    return value


def load_skill(skill_dir: str | Path) -> SkillBundle:
    root = Path(skill_dir).resolve()
    skill_md = _required(root, "SKILL.md")
    prompts = {name: _required(root / "prompts", name) for name in REQUIRED_PROMPTS}
    rules = {name: _required(root / "rules", name) for name in REQUIRED_RULES}
    schema = _schema(_required(root / "schemas", "output.schema.json"))
    return SkillBundle(
        skill_md=skill_md,
        prompts=prompts,
        rules=rules,
        sensitive_patterns=_patterns(rules["sensitive-patterns.yaml"]),
        output_schema=schema,
        source_dir=str(root),
    )
