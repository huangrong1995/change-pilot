"""Schema validation for the skill's structured output.

Two layers:
  - ``validate_skill_output``: structural minimum check (used as fast
    fail-fast before fetching the schema). Mirrors the skill's
    ``output.schema.json`` shape.
  - ``validate_against_output_schema``: full JSON-Schema validation
    against the skill's ``schemas/output.schema.json``. Used in Phase 4
    once we wire the route.
"""
from __future__ import annotations
import json
from pathlib import Path
import jsonschema
from referencing import Registry


class SchemaViolation(Exception):
    """Raised when a payload does not satisfy the skill's output schema."""


REQUIRED_TOP_KEYS = {"customer_output"}
REQUIRED_CO_KEYS = {"description"}


def validate_skill_output(parsed: dict) -> None:
    if not isinstance(parsed, dict):
        raise SchemaViolation("output is not an object")
    missing = REQUIRED_TOP_KEYS - parsed.keys()
    if missing:
        raise SchemaViolation(f"missing top-level keys: {sorted(missing)}")
    co = parsed["customer_output"]
    if not isinstance(co, dict):
        raise SchemaViolation("customer_output is not an object")
    missing_co = REQUIRED_CO_KEYS - co.keys()
    if missing_co:
        raise SchemaViolation(f"customer_output missing: {sorted(missing_co)}")
    desc = co["description"]
    if not isinstance(desc, str) or not desc:
        raise SchemaViolation("customer_output.description is empty")


def validate_against_output_schema(parsed: dict, schema_path: Path) -> None:
    if not schema_path.exists():
        raise SchemaViolation(f"output schema missing at {schema_path}")
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SchemaViolation(f"output schema unreadable at {schema_path}: {exc}") from exc
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaViolation(f"output schema is not valid JSON at {schema_path}: {exc}") from exc
    try:
        jsonschema.validate(instance=parsed, schema=schema)
    except (jsonschema.ValidationError, jsonschema.SchemaError) as exc:
        raise SchemaViolation(str(exc)) from exc
