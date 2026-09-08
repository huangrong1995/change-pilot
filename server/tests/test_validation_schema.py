import pytest
from pathlib import Path
from server.app.validation.schema import validate_skill_output, validate_against_output_schema, SchemaViolation


def test_validate_skill_output_minimal():
    parsed = {"customer_output": {"description": "x"}}
    validate_skill_output(parsed)


def test_validate_skill_output_rejects_missing_customer_output():
    with pytest.raises(SchemaViolation):
        validate_skill_output({})


def test_validate_skill_output_rejects_missing_description():
    with pytest.raises(SchemaViolation):
        validate_skill_output({"customer_output": {"title": "t"}})


def test_validate_skill_output_accepts_debug_shape():
    parsed = {
        "customer_output": {"description": "x"},
        "analysis": {"change_types": ["optimization"], "business_intent": "i"},
        "validation": {"passed": True},
    }
    validate_skill_output(parsed)


def test_validate_against_output_schema_uses_skill_schema(tmp_path):
    schema_file = tmp_path / "output.schema.json"
    schema_file.write_text(
        '{"type":"object","required":["customer_output"],"properties":{"customer_output":{"type":"object","required":["description"],"properties":{"description":{"type":"string"}}}}}'
    )
    validate_against_output_schema({"customer_output": {"description": "x"}}, schema_file)


def test_validate_against_output_schema_rejects(tmp_path):
    schema_file = tmp_path / "output.schema.json"
    schema_file.write_text(
        '{"type":"object","required":["customer_output"],"properties":{"customer_output":{"type":"object","required":["description"],"properties":{"description":{"type":"string"}}}}}'
    )
    with pytest.raises(SchemaViolation):
        validate_against_output_schema({"customer_output": {}}, schema_file)


@pytest.mark.parametrize(
    "content",
    [
        pytest.param('{"type":"object","required":[', id="malformed-json"),
        pytest.param('{"type":"not-a-real-type"}', id="invalid-schema"),
    ],
)
def test_validate_against_output_schema_fails_closed(tmp_path, content):
    schema_file = tmp_path / "output.schema.json"
    schema_file.write_text(content)
    with pytest.raises(SchemaViolation):
        validate_against_output_schema({"customer_output": {"description": "x"}}, schema_file)


def test_validate_against_output_schema_unreadable_schema(tmp_path, monkeypatch):
    schema_file = tmp_path / "output.schema.json"
    schema_file.write_text('{"type":"object"}')

    def raise_unreadable(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", raise_unreadable)
    with pytest.raises(SchemaViolation):
        validate_against_output_schema({"customer_output": {"description": "x"}}, schema_file)
