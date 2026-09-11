"""Compose the trusted system prompt and the dynamic user prompt."""
from __future__ import annotations

import json
from typing import Any

from runtime.models import SkillBundle


_INSTRUCTIONS = (
    "You are Change Pilot, transforming R&D change-point descriptions into "
    "customer-facing release notes. SKILL.md and the bundled prompts and rules "
    "are the single source of business rules — follow them exactly.\n"
    "Return exactly one JSON object matching schemas/output.schema.json: "
    "{\"customer_output\": {\"title\": <str|null>, \"description\": <non-empty str>}}. "
    "Include analysis and validation only when the user prompt requests debug mode. "
    "Default mode returns customer_output only, using the full-width colon ：.\n"
    "Never emit chain-of-thought, reasoning, confidence scores, or any text outside "
    "the JSON object. Do not call tools.\n"
)


class PromptBuilder:
    def system_message(self, bundle: SkillBundle) -> str:
        sections = [
            bundle.skill_md,
            _INSTRUCTIONS,
            "# Loaded prompts\n\n" + _render_files(bundle.prompts),
            "# Loaded rules\n\n" + _render_files({k: v for k, v in bundle.rules.items()
                                                  if k != "sensitive-patterns.yaml"}),
            "# Output schema\n\n" + json.dumps(bundle.output_schema, ensure_ascii=False, indent=2),
        ]
        return "\n\n".join(sections)

    def user_message(self, raw_text: str, context: Any, mode: str) -> str:
        ctx = context if isinstance(context, dict) else {}
        return (
            f"Mode: {mode}\n"
            "Target output (default): {title}：{description}\n"
            f"raw_text:\n{raw_text}\n\n"
            "context (disambiguation only, do not invent from):\n"
            f"{json.dumps(ctx, ensure_ascii=False)}"
        )


def _render_files(files: dict[str, str]) -> str:
    return "\n\n".join(f"## {name}\n{content}" for name, content in files.items())
