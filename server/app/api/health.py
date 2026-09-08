"""GET /health endpoint.

Reports server status, version (read from server package metadata),
agent availability (whether ``claude`` is on PATH), and skill
availability (whether the configured skill directory has SKILL.md).
"""
from __future__ import annotations
import shutil
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from server.app.config import Settings


router = APIRouter()


class HealthReport(BaseModel):
    status: str
    version: str
    agent: dict
    skill: dict


def _read_version() -> str:
    # Phase 1–4 hardcode 0.1.0; Phase 5 reads from pyproject.
    return "0.1.0"


def build_health(settings: Settings) -> HealthReport:
    skill_path = Path(settings.skill_dir) / "SKILL.md"
    return HealthReport(
        status="ok",
        version=_read_version(),
        agent={"available": shutil.which("claude") is not None},
        skill={"available": skill_path.exists()},
    )


@router.get("/health", response_model=HealthReport)
def get_health() -> HealthReport:
    from server.app.config import load_settings
    return build_health(load_settings())
