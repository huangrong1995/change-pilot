"""Uniform error envelope and global handlers.

All public-facing errors go through ``install_error_handlers``. The wire
format is always:

    {
      "success": false,
      "error": {"code": "<UPPER_SNAKE>", "message": "<human readable>"}
    }

Error codes (per spec section 27):
  INVALID_REQUEST, UNAUTHORIZED, REQUEST_TOO_LARGE,
  AGENT_START_FAILED, AGENT_TIMEOUT, AGENT_FAILED,
  AGENT_OUTPUT_INVALID, SESSION_NOT_FOUND, SERVER_BUSY,
  INTERNAL_ERROR.
"""
from __future__ import annotations
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from server.app.logging import get_logger


logger = get_logger()


class ChangePilotError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidRequest(ChangePilotError):
    code = "INVALID_REQUEST"
    status_code = 400


class Unauthorized(ChangePilotError):
    code = "UNAUTHORIZED"
    status_code = 401


class RequestTooLarge(ChangePilotError):
    code = "REQUEST_TOO_LARGE"
    status_code = 413


class AgentStartFailed(ChangePilotError):
    code = "AGENT_START_FAILED"
    status_code = 502


class AgentTimeout(ChangePilotError):
    code = "AGENT_TIMEOUT"
    status_code = 504


class AgentFailed(ChangePilotError):
    code = "AGENT_FAILED"
    status_code = 502


class AgentOutputInvalid(ChangePilotError):
    code = "AGENT_OUTPUT_INVALID"
    status_code = 502


class SessionNotFound(ChangePilotError):
    code = "SESSION_NOT_FOUND"
    status_code = 404


class ServerBusy(ChangePilotError):
    code = "SERVER_BUSY"
    status_code = 503


def _envelope(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ChangePilotError)
    async def _change_pilot_handler(_req: Request, exc: ChangePilotError):
        return _envelope(exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_req: Request, exc: RequestValidationError):
        return _envelope("INVALID_REQUEST", str(exc.errors()), 400)

    @app.exception_handler(HTTPException)
    async def _http_handler(_req: Request, exc: HTTPException):
        code = {
            400: "INVALID_REQUEST",
            401: "UNAUTHORIZED",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            413: "REQUEST_TOO_LARGE",
        }.get(exc.status_code, "HTTP_ERROR")
        return _envelope(code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        logger.exception("Unhandled exception: %r", exc)
        return _envelope("INTERNAL_ERROR", "internal server error", 500)
