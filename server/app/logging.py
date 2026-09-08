"""Structured logger that never logs raw request bodies.

Each log record carries the current ``request_id`` (set by
``RequestContext``) but never the raw_text or other sensitive fields.
Callers are responsible for passing only sanitized ``extra`` keys.
"""
from __future__ import annotations
import contextvars
import logging
import sys

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "change_pilot_request_id", default=None
)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get() or "-"
        return True


_FORMAT = "%(asctime)s %(levelname)s request_id=%(request_id)s %(message)s"


def configure(level: str = "INFO") -> None:
    """Idempotently configure the ``change_pilot`` logger."""
    log = logging.getLogger("change_pilot")
    if log.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(_RequestIdFilter())
    log.addHandler(handler)
    log.setLevel(level.upper())
    log.propagate = False


def get_logger() -> logging.Logger:
    configure()
    return logging.getLogger("change_pilot")


class RequestContext:
    """Context manager that sets the current request_id for log records."""

    def __init__(self, request_id: str):
        self._token = None
        self._request_id = request_id

    def __enter__(self) -> "RequestContext":
        self._token = _request_id_var.set(self._request_id)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._token is not None:
            _request_id_var.reset(self._token)


def current_request_id() -> str | None:
    return _request_id_var.get()
