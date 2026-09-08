"""Request model for POST /v1/change-pilot.

Mirrors the skill's ``input.schema.json`` (raw_text required, optional
context, optional mode). Strict ``model_config.extra='forbid'`` enforces
no surprise fields.
"""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field


class ChangePilotContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    product: str | None = None
    version: str | None = None
    module: str | None = None


class ChangePilotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1)
    context: ChangePilotContext | None = None
    mode: str = Field(default="default", pattern="^(default|debug)$")
