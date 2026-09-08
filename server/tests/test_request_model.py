import pytest
from pydantic import ValidationError

from server.app.models.request import ChangePilotRequest, ChangePilotContext


def test_minimal_request_only_raw_text():
    r = ChangePilotRequest(raw_text="hello")
    assert r.raw_text == "hello"
    assert r.context is None
    assert r.mode == "default"


def test_full_request():
    r = ChangePilotRequest(
        raw_text="x",
        context=ChangePilotContext(product="POS", module="扫码", version="3.5"),
        mode="debug",
    )
    assert r.context.product == "POS"
    assert r.mode == "debug"


def test_empty_raw_text_rejected():
    with pytest.raises(ValidationError):
        ChangePilotRequest(raw_text="")


def test_invalid_mode_rejected():
    with pytest.raises(ValidationError):
        ChangePilotRequest(raw_text="x", mode="verbose")


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        ChangePilotRequest(raw_text="x", surprise_field=1)
