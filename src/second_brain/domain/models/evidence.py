"""Modèle pydantic d'une preuve attachée à un case."""

from __future__ import annotations

from pydantic import BaseModel


class Evidence(BaseModel):
    path: str
    type: str
    summary: str
