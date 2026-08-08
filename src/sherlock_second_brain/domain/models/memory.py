"""Pydantic model for a memory: a standalone note not tied to a case.

A memory is a low-friction capture ("remember that X"). It is searchable
through the hybrid index and can be promoted into a validated fiche.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sherlock_second_brain.domain.models.promotion import Promotion
from sherlock_second_brain.domain.text import MEMORY_ID_PATTERN, now_iso


class Memory(BaseModel):
    id: str = Field(pattern=MEMORY_ID_PATTERN)
    summary: str
    content: str
    tags: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    source: str | None = None
    promotion: Promotion | None = None
    created_at: str
    updated_at: str

    def touch(self) -> None:
        """Refresh ``updated_at`` after a mutation."""
        self.updated_at = now_iso()
