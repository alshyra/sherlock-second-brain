"""Pydantic model for a piece of evidence attached to a case."""

from __future__ import annotations

from pydantic import BaseModel


class Evidence(BaseModel):
    path: str
    type: str
    summary: str
