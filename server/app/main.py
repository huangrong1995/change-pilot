"""FastAPI application factory.

Wires routers, exception handlers, auth-token configuration, and builds
the shared lightweight runtime once at startup. Does not probe the network
or require a configured provider key to boot.
"""
from __future__ import annotations

from fastapi import FastAPI

from server.app import auth as auth_mod
from server.app import errors as errors_mod
from server.app.api import change_pilot as cp_router
from server.app.api import health as health_router
from server.app.config import Settings, load_settings
from server.app.logging import get_logger
from runtime.compatible_client import CompatibleClient
from runtime.prompt_builder import PromptBuilder
from runtime.runtime import ChangePilotRuntime
from runtime.skill_loader import SkillLoadError, load_skill
from runtime.validator import OutputValidator


def build_runtime(settings: Settings) -> ChangePilotRuntime | None:
    """Load the skill and construct the runtime; None when the skill is unusable."""
    try:
        bundle = load_skill(settings.skill_dir)
    except SkillLoadError as exc:
        get_logger().warning("runtime build failed", extra={
            "operation": "startup", "status": "skill_unavailable", "error": str(exc),
        })
        return None
    client = CompatibleClient(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model,
        max_tokens=settings.max_tokens,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.retry_count,
    )
    return ChangePilotRuntime(
        bundle, PromptBuilder(), client,
        OutputValidator(bundle.output_schema, bundle.sensitive_patterns),
        max_concurrency=settings.max_concurrency,
    )


def create_app(runtime: ChangePilotRuntime | None = None) -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Change Pilot Agent Server", version="0.1.0")

    errors_mod.install_error_handlers(app)
    # AuthError subclasses Unauthorized and is handled by install_error_handlers,
    # so no separate auth exception handler is registered (Task 4 consolidation).
    auth_mod.set_expected_token(settings.api_token)

    app.state.change_pilot_runtime = runtime if runtime is not None else build_runtime(settings)
    app.state.settings = settings

    app.include_router(health_router.router)
    app.include_router(cp_router.router)

    # Enforce max request size at the ASGI layer (defense-in-depth, see spec section 39).
    @app.middleware("http")
    async def _enforce_request_size(request, call_next):
        from fastapi.responses import JSONResponse
        cl = request.headers.get("content-length")
        transfer_encoding = request.headers.get("transfer-encoding")
        if transfer_encoding:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": {
                    "code": "INVALID_REQUEST",
                    "message": "request body requires a valid Content-Length",
                }},
            )
        if cl is not None:
            try:
                if int(cl) > settings.max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"success": False, "error": {
                            "code": "REQUEST_TOO_LARGE",
                            "message": f"request body exceeds {settings.max_request_bytes} bytes",
                        }},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": {
                        "code": "INVALID_REQUEST",
                        "message": "invalid Content-Length header",
                    }},
                )
        return await call_next(request)

    @app.on_event("startup")
    def _startup_log():
        log = get_logger()
        log.info(
            "startup",
            extra={
                "operation": "startup",
                "skill_dir": str(settings.skill_dir),
                "agent_timeout_seconds": settings.agent_timeout_seconds,
                "max_request_bytes": settings.max_request_bytes,
            },
        )

    return app


app = create_app()