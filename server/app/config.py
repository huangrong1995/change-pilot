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
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    max_tokens: int = 1024
    provider_timeout_seconds: float = 60.0
    retry_count: int = 1
    max_concurrency: int = 4


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
        api_key=os.environ.get("CHANGE_PILOT_API_KEY", ""),
        base_url=os.environ.get("CHANGE_PILOT_BASE_URL", ""),
        model=os.environ.get("CHANGE_PILOT_MODEL", ""),
        max_tokens=int(os.environ.get("CHANGE_PILOT_MAX_TOKENS", "1024")),
        provider_timeout_seconds=float(os.environ.get("CHANGE_PILOT_PROVIDER_TIMEOUT", "60")),
        retry_count=int(os.environ.get("CHANGE_PILOT_RETRY_COUNT", "1")),
        max_concurrency=int(os.environ.get("CHANGE_PILOT_MAX_CONCURRENCY", "4")),
    )
