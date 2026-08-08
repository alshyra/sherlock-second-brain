"""Pydantic model for an investigation hypothesis."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Hypothesis(BaseModel):
    id: str = Field(pattern=r"^h\d+$")
    statement: str
    test: str
    result: str | None = Field(default=None, pattern=r"^(confirmed|refuted|inconclusive)$")
    evidence: list[str] = Field(default_factory=list)
