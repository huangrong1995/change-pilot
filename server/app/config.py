"""Server configuration loaded from environment variables."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SKILL_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "change-pilot"


@dataclass(frozen=True)
class Settings:
    api_token: str
    skill_dir: Path
    agent_timeout_seconds: int
    max_request_bytes: int


def load_settings() -> Settings:
    return Settings(
        api_token=os.environ.get("CHANGE_PILOT_API_TOKEN", ""),
        skill_dir=Path(
            os.environ.get(
                "CHANGE_PILOT_SKILL_DIR",
                str(DEFAULT_SKILL_DIR),
            )
        ).resolve(),
        agent_timeout_seconds=int(os.environ.get("CHANGE_PILOT_AGENT_TIMEOUT", "180")),
        max_request_bytes=int(os.environ.get("CHANGE_PILOT_MAX_REQUEST_BYTES", str(100 * 1024))),
    )
