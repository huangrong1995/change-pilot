"""POST /v1/change-pilot — the core business API.

Pipeline:
  1. Authenticate via Bearer token (FastAPI dependency).
  2. Validate request body against ``ChangePilotRequest``.
  3. Generate ``request_id`` and start timer.
  4. Delegate to ``ClaudeRunner.run_async``.
  5. Validate the structured output against the skill's output schema.
  6. Run sensitive-pattern re-check on the description.
  7. Build the response envelope (single-line for default, full for debug).
  8. Log completion (no raw_text).
"""
from __future__ import annotations
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi import status

from server.app.agent.runner import ClaudeRunner
from server.app.auth import require_bearer_token
from server.app.config import load_settings
from server.app.errors import AgentFailed, AgentOutputInvalid, AgentStartFailed, AgentTimeout, ServerBusy
from server.app.logging import RequestContext, get_logger
from server.app.models.request import ChangePilotRequest
from server.app.models.response import (
    ChangePilotResponse,
    build_customer_output_line,
)
from server.app.validation.schema import (
    SchemaViolation,
    validate_against_output_schema,
)
from server.app.validation.sensitive import (
    SensitiveLeak,
    check_description,
)


router = APIRouter(prefix="/v1")


def _new_request_id() -> str:
    import secrets
    return "req_" + secrets.token_hex(8)


@router.post("/change-pilot", response_model=ChangePilotResponse)
async def post_change_pilot(
    body: ChangePilotRequest,
    _auth: None = Depends(require_bearer_token),
) -> ChangePilotResponse:
    settings = load_settings()
    log = get_logger()
    request_id = _new_request_id()
    started = time.monotonic()

    with RequestContext(request_id=request_id):
        log.info("change-pilot received", extra={
            "operation": "change-pilot",
            "status": "started",
            "mode": body.mode,
        })
        runner = ClaudeRunner(
            skill_dir=settings.skill_dir,
            timeout_seconds=settings.agent_timeout_seconds,
        )
        context_dict = body.context.model_dump(exclude_none=True) if body.context else None
        try:
            run_result = await runner.run_async(
                raw_text=body.raw_text,
                context=context_dict,
                mode=body.mode,
            )
        except (AgentTimeout, AgentStartFailed, AgentFailed) as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            log.exception("change-pilot failed", extra={
                "operation": "change-pilot",
                "status": "failed",
                "duration_ms": duration_ms,
                "error_class": exc.__class__.__name__,
            })
            safe_messages = {
                AgentTimeout: "agent request timed out",
                AgentStartFailed: "agent could not be started",
                AgentFailed: "agent execution failed",
            }
            raise exc.__class__(safe_messages[type(exc)]) from exc
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            log.exception("change-pilot failed", extra={
                "operation": "change-pilot",
                "status": "failed",
                "duration_ms": duration_ms,
                "error_class": exc.__class__.__name__,
            })
            raise

        # Validate against the skill's output schema.
        output_schema_path = settings.skill_dir / "schemas" / "output.schema.json"
        try:
            parsed = {
                "customer_output": {
                    "title": run_result.title,
                    "description": run_result.description,
                },
                **({"analysis": run_result.analysis} if run_result.analysis is not None else {}),
                **({"validation": run_result.validation} if run_result.validation is not None else {}),
            }
            validate_against_output_schema(parsed, output_schema_path)
        except SchemaViolation as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            log.warning("schema rejected", extra={
                "operation": "change-pilot",
                "status": "schema_rejected",
                "duration_ms": duration_ms,
            })
            raise AgentOutputInvalid("agent output failed validation") from exc

        # Build the customer-facing single-line output (default mode).
        customer_line = build_customer_output_line(run_result.title, run_result.description)

        # Sensitive-pattern re-check.
        sensitive_yaml = settings.skill_dir / "rules" / "sensitive-patterns.yaml"
        try:
            check_description(customer_line, sensitive_yaml)
        except SensitiveLeak as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            log.warning("sensitive leak detected", extra={
                "operation": "change-pilot",
                "status": "sensitive_leak",
                "duration_ms": duration_ms,
            })
            raise AgentOutputInvalid("agent output failed validation") from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        log.info("change-pilot completed", extra={
            "operation": "change-pilot",
            "status": "completed",
            "duration_ms": duration_ms,
            "mode": body.mode,
        })

        return ChangePilotResponse(
            success=True,
            request_id=request_id,
            customer_output=customer_line,
            analysis=run_result.analysis if body.mode == "debug" else None,
            validation=run_result.validation if body.mode == "debug" else None,
            processing_time_ms=duration_ms,
        )