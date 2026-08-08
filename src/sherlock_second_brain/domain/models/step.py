"""Modèle pydantic d'une étape d'investigation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Step(BaseModel):
    order: int
    action: str
    result: str | None = None
    evidence: list[str] = Field(default_factory=list)
