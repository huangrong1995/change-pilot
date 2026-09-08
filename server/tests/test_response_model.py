from server.app.models.response import ChangePilotResponse, build_customer_output_line


def test_customer_output_line_joins_with_full_width_colon():
    line = build_customer_output_line("扫码功能优化", "优化扫码功能，提升扫码稳定性。")
    assert line == "扫码功能优化：优化扫码功能，提升扫码稳定性。"


def test_customer_output_line_no_title():
    line = build_customer_output_line(None, "修复了登录问题。")
    assert line == "修复了登录问题。"


def test_response_envelope_default_mode():
    r = ChangePilotResponse(
        success=True,
        request_id="req_abc",
        customer_output="扫码功能优化：优化扫码功能，提升扫码稳定性。",
        processing_time_ms=1234,
    )
    assert r.success is True
    assert r.analysis is None
    assert r.processing_time_ms == 1234
    d = r.model_dump()
    assert d["success"] is True
    assert d["request_id"] == "req_abc"


def test_response_envelope_debug_mode_includes_analysis_and_validation():
    r = ChangePilotResponse(
        success=True,
        request_id="req_abc",
        customer_output="扫码功能优化：优化扫码功能，提升扫码稳定性。",
        analysis={"change_types": ["optimization"], "business_intent": "x"},
        validation={"passed": True, "technical_leakage": False},
        processing_time_ms=1234,
    )
    d = r.model_dump()
    assert d["analysis"] is not None
    assert d["validation"] is not None
