"""Central pydantic model: the investigation (case)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sherlock_second_brain.domain.models.evidence import Evidence
from sherlock_second_brain.domain.models.hypothesis import Hypothesis
from sherlock_second_brain.domain.models.promotion import Promotion
from sherlock_second_brain.domain.models.step import Step
from sherlock_second_brain.domain.text import CASE_ID_PATTERN, now_iso


class Case(BaseModel):
    id: str = Field(pattern=CASE_ID_PATTERN)
    title: str
    status: str = Field(pattern=r"^(open|in_progress|resolved|abandoned)$")
    goal: str
    context: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    conclusion: str | None = None
    promotion: Promotion | None = None
    tags: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

    def touch(self) -> None:
        """Refresh ``updated_at`` after a mutation."""
        self.updated_at = now_iso()
