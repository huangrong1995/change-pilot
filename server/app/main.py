"""FastAPI application factory.

Wires routers, exception handlers, auth-token configuration, and the
service-wide startup check (claude + skill + token present).
"""
from __future__ import annotations

from fastapi import FastAPI

from server.app import auth as auth_mod
from server.app import errors as errors_mod
from server.app.api import change_pilot as cp_router
from server.app.api import health as health_router
from server.app.config import load_settings
from server.app.logging import get_logger


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Change Pilot Agent Server", version="0.1.0")

    errors_mod.install_error_handlers(app)
    # AuthError subclasses Unauthorized and is handled by install_error_handlers,
    # so no separate auth exception handler is registered (Task 4 consolidation).
    auth_mod.set_expected_token(settings.api_token)

    app.include_router(health_router.router)
    app.include_router(cp_router.router)

    # Enforce max request size at the ASGI layer (defense-in-depth, see spec section 39).
    @app.middleware("http")
    async def _enforce_request_size(request, call_next):
        from fastapi.responses import JSONResponse
        cl = request.headers.get("content-length")
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