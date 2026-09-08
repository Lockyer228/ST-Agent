"""TurnOutcome schema for Strands structured output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TurnOutcome(BaseModel):
    kind: Literal["question", "delivered", "blocked"]
    message: str
    question: str | None = None
    confirm: bool = False
    required_input: str | None = None
    blocker: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
