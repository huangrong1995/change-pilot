"""GET /health endpoint for runtime readiness."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel


router = APIRouter()


class HealthReport(BaseModel):
    status: str
    version: str
    runtime: dict
    agent: dict
    skill: dict
    provider: dict


def _read_version() -> str:
    return "0.1.0"


def build_health(runtime) -> HealthReport:
    available = runtime is not None
    return HealthReport(
        status="ok",
        version=_read_version(),
        runtime={"available": available},
        agent={"available": available},
        skill={"available": available},
        provider={
            "configured": bool(runtime and runtime.provider_configured),
            "model": getattr(runtime, "model", None) if runtime else None,
        },
    )


@router.get("/health", response_model=HealthReport)
def get_health(request: Request) -> HealthReport:
    return build_health(getattr(request.app.state, "change_pilot_runtime", None))
