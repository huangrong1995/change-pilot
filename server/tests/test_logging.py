import logging
from server.app.logging import get_logger, RequestContext


def _captured_records(log):
    """Return a handler attached to the change_pilot logger that collects
    emitted records into `records`."""
    class Recorder(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            self.records.append(record)
    handler = Recorder()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s request_id=%(request_id)s %(message)s"))
    log.addHandler(handler)
    return handler


def test_log_line_contains_request_id_and_no_raw_text():
    log = get_logger()
    handler = _captured_records(log)
    try:
        with RequestContext(request_id="req_test_123"):
            # Caller passes only SANITIZED context fields as extra, never raw_text.
            log.info("started", extra={"operation": "change-pilot", "status": "started"})
        record = handler.records[0]
        assert record.request_id == "req_test_123"
        assert record.operation == "change-pilot"
        formatted = handler.format(record)
        assert "req_test_123" in formatted
        # No internal/secret value was ever passed, so none appears in output.
        assert "secret-internals-BUG-12345" not in formatted
    finally:
        log.removeHandler(handler)


def test_get_logger_returns_named_logger():
    log = get_logger()
    assert log.name == "change_pilot"


def test_request_context_resets_after_exit():
    from server.app.logging import current_request_id
    assert current_request_id() is None
    with RequestContext(request_id="abc"):
        assert current_request_id() == "abc"
    assert current_request_id() is None
