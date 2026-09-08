"""Bearer-token authentication dependency.

The Server has a single expected token configured at startup via
``set_expected_token``. ``require_bearer_token`` raises ``AuthError`` when
the header is missing or doesn't match; ``AuthError`` is mapped to an
``UNAUTHORIZED`` HTTP 401 by the exception handler registered in
``server.app.auth`` via ``install_auth_exception_handler``.
"""
from __future__ import annotations

from fastapi import FastAPI, Header
from fastapi.requests import Request
from fastapi.responses import JSONResponse

_expected_token: str = ""


def set_expected_token(token: str) -> None:
    """Configure the expected bearer token. Called once at app startup."""
    global _expected_token
    _expected_token = token


class AuthError(Exception):
    """Raised when authentication fails. Mapped to HTTP 401."""


def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("missing or malformed Authorization header")
    presented = authorization[len("Bearer "):].strip()
    if not _expected_token or presented != _expected_token:
        raise AuthError("invalid token")


def install_auth_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def _auth_handler(_request: Request, exc: AuthError):
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": {"code": "UNAUTHORIZED", "message": str(exc)}},
        )
