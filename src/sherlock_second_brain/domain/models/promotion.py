"""Pydantic model for a promotion (case → fiche/skill)."""

from __future__ import annotations

from pydantic import BaseModel


class Promotion(BaseModel):
    target: str
    path: str
    date: str
