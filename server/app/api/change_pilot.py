"""POST /v1/change-pilot — the lightweight transformation API."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request

from runtime.models import (
    ChangePilotRuntimeError,
    OutputInvalidError,
    ProviderConfigurationError,
    ProviderError,
    ProviderTimeoutError,
)
from server.app.auth import require_bearer_token
from server.app.errors import AgentFailed, AgentOutputInvalid, AgentTimeout
from server.app.logging import RequestContext, get_logger
from server.app.models.request import ChangePilotRequest
from server.app.models.response import ChangePilotResponse


router = APIRouter(prefix="/v1")


def _new_request_id() -> str:
    import secrets
    return "req_" + secrets.token_hex(8)


@router.post("/change-pilot", response_model=ChangePilotResponse)
async def post_change_pilot(
    body: ChangePilotRequest,
    request: Request,
    _auth: None = Depends(require_bearer_token),
) -> ChangePilotResponse:
    runtime = getattr(request.app.state, "change_pilot_runtime", None)
    log = get_logger()
    request_id = _new_request_id()
    started = time.monotonic()
    with RequestContext(request_id=request_id):
        log.info("change-pilot received", extra={
            "operation": "change-pilot", "status": "started", "mode": body.mode,
        })
        if runtime is None:
            raise AgentFailed("change pilot runtime is unavailable")
        context = body.context.model_dump(exclude_none=True) if body.context else None
        try:
            result = await runtime.transform_async(body.raw_text, context, body.mode)
        except OutputInvalidError as exc:
            _log_failure(log, started, "output_invalid", exc)
            raise AgentOutputInvalid("agent output failed validation") from exc
        except ProviderTimeoutError as exc:
            _log_failure(log, started, "timeout", exc)
            raise AgentTimeout("agent request timed out") from exc
        except (ProviderConfigurationError, ProviderError, ChangePilotRuntimeError) as exc:
            _log_failure(log, started, "agent_failed", exc)
            raise AgentFailed("agent execution failed") from exc
        duration_ms = int((time.monotonic() - started) * 1000)
        log.info("change-pilot completed", extra={
            "operation": "change-pilot", "status": "completed",
            "duration_ms": duration_ms, "mode": body.mode,
        })
        return ChangePilotResponse(
            success=True,
            request_id=request_id,
            customer_output=result.customer_line,
            analysis=result.analysis if body.mode == "debug" else None,
            validation=result.validation if body.mode == "debug" else None,
            processing_time_ms=duration_ms,
        )


def _log_failure(log, started: float, status: str, exc: Exception) -> None:
    log.warning("change-pilot failed", extra={
        "operation": "change-pilot",
        "status": status,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "error_class": exc.__class__.__name__,
    })
