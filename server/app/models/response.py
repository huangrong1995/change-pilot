"""Response envelope for POST /v1/change-pilot.

Default mode emits ``customer_output`` as a single full-width-colon line
matching the skill's default render. Debug mode additionally passes
through ``analysis`` and ``validation`` blocks from the skill's
``output.schema.json``.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


FULL_WIDTH_COLON = "："


def build_customer_output_line(title: str | None, description: str) -> str:
    if title:
        return f"{title}{FULL_WIDTH_COLON}{description}"
    return description


class ChangePilotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool = True
    request_id: str
    customer_output: str
    analysis: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    processing_time_ms: int = Field(ge=0)
