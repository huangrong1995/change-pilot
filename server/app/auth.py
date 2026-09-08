"""Bearer-token authentication dependency.

The Server has a single expected token configured at startup via
``set_expected_token``. ``require_bearer_token`` raises ``AuthError`` when
the header is missing or doesn't match; ``AuthError`` maps to an
``UNAUTHORIZED`` HTTP 401 through ``install_error_handlers`` in
``server.app.errors``.
"""
from __future__ import annotations

from fastapi import Header

from server.app.errors import Unauthorized

_expected_token: str = ""


def set_expected_token(token: str) -> None:
    """Configure the expected bearer token. Called once at app startup."""
    global _expected_token
    _expected_token = token


class AuthError(Unauthorized):
    """Raised when authentication fails. Mapped to HTTP 401."""


def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("missing or malformed Authorization header")
    presented = authorization[len("Bearer "):].strip()
    if not _expected_token or presented != _expected_token:
        raise AuthError("invalid token")
