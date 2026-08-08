"""Pydantic model for a memory: a standalone note not tied to a case.

A memory is a low-friction capture ("remember that X"). It enforces its own
invariants (non-blank summary, creation timestamps, one-shot promotion) and is
searchable through the hybrid index.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sherlock_second_brain.domain.errors import MemoryValidationError
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

    @classmethod
    def create_memory(
        cls,
        next_id: str,
        summary: str,
        content: str,
        tags: list[str] | None = None,
        references: list[str] | None = None,
        source: str | None = None,
    ) -> Memory:
        """Create a new memory: enforces invariants and default values."""
        if not summary.strip():
            raise MemoryValidationError("summary is required")
        now = now_iso()
        return cls(
            id=next_id,
            summary=summary.strip(),
            content=content.strip(),
            tags=tags or [],
            references=references or [],
            source=source,
            created_at=now,
            updated_at=now,
        )

    def touch(self) -> None:
        """Refresh ``updated_at`` after a mutation."""
        self.updated_at = now_iso()

    def set_summary(self, summary: str) -> None:
        if not summary.strip():
            raise MemoryValidationError("summary is required")
        self.summary = summary
        self.touch()

    def set_content(self, content: str) -> None:
        self.content = content
        self.touch()

    def set_tags(self, tags: list[str]) -> None:
        self.tags = tags
        self.touch()

    def set_references(self, references: list[str]) -> None:
        self.references = references
        self.touch()

    def set_source(self, source: str | None) -> None:
        self.source = source
        self.touch()

    def promote(self, path: str) -> None:
        """Mark the memory as promoted. Promotion is one-shot."""
        if self.promotion is not None:
            raise ValueError(f"memory already promoted to {self.promotion.target}")
        self.promotion = Promotion(target="fiche", path=path, date=now_iso())
        self.touch()
