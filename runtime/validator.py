"""In-memory validation of model output."""
from __future__ import annotations

import jsonschema
from dataclasses import dataclass
from typing import Any

from runtime.models import OutputInvalidError
from server.app.models.response import FULL_WIDTH_COLON, build_customer_output_line
from server.app.validation.sensitive import find_sensitive_matches


@dataclass(frozen=True)
class VerifiedOutput:
    title: str | None
    description: str
    note: str | None
    analysis: dict[str, Any] | None
    validation: dict[str, Any] | None


class OutputValidator:
    def __init__(self, output_schema: dict[str, Any], sensitive_patterns: list[str]):
        self._schema = output_schema
        self._patterns = sensitive_patterns

    def process(self, parsed: Any) -> VerifiedOutput:
        if not isinstance(parsed, dict):
            raise OutputInvalidError("model output is not a JSON object")
        customer = parsed.get("customer_output")
        if isinstance(customer, str):
            title, separator, description = customer.partition(FULL_WIDTH_COLON)
            customer = {"title": title.strip() or None, "description":
                        description.strip() if separator else customer.strip()}
        if not isinstance(customer, dict):
            raise OutputInvalidError("customer_output is invalid")
        title = customer.get("title")
        description = customer.get("description")
        note = customer.get("note")
        normalized = {"customer_output": {"title": title, "description": description}}
        if note is not None:
            normalized["customer_output"]["note"] = note
        for key in ("analysis", "validation"):
            if key in parsed:
                normalized[key] = parsed[key]
        try:
            jsonschema.validate(normalized, self._schema)
        except (jsonschema.ValidationError, jsonschema.SchemaError) as exc:
            raise OutputInvalidError("model output failed schema validation") from exc
        line = build_customer_output_line(title, description)
        if note is not None:
            line += f"\n注意：{note}"
        if find_sensitive_matches(self._patterns, line):
            raise OutputInvalidError("model output contains sensitive patterns")
        return VerifiedOutput(
            title=title, description=description, note=note,
            analysis=parsed.get("analysis"), validation=parsed.get("validation"),
        )
