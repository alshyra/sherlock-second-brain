"""Pydantic model for an investigation (case) — a rich aggregate.

``Case`` enforces its own invariants: creation defaults (status ``open``,
timestamps), ordered steps/hypotheses, valid status transitions and the
promotion rule (resolved + one-shot). The application layer only orchestrates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sherlock_second_brain.domain.errors import CaseValidationError
from sherlock_second_brain.domain.models.evidence import Evidence
from sherlock_second_brain.domain.models.hypothesis import Hypothesis
from sherlock_second_brain.domain.models.promotion import Promotion
from sherlock_second_brain.domain.models.step import Step
from sherlock_second_brain.domain.rules import VALID_PROMOTION_TARGETS, VALID_STATUS
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

    @classmethod
    def create_case(
        cls,
        next_id: str,
        title: str,
        goal: str,
        context: str = "",
        tags: list[str] | None = None,
        references: list[str] | None = None,
    ) -> Case:
        """Create a new case: enforces invariants and default values."""
        if not title.strip():
            raise CaseValidationError("title is required")
        now = now_iso()
        return cls(
            id=next_id,
            title=title.strip(),
            status="open",
            goal=goal.strip(),
            context=context.strip(),
            tags=tags or [],
            references=references or [],
            created_at=now,
            updated_at=now,
        )

    def touch(self) -> None:
        """Refresh ``updated_at`` after a mutation."""
        self.updated_at = now_iso()

    def add_finding(self, text: str) -> None:
        self.findings.append(text)
        self.touch()

    def add_step(self, action: str, result: str | None = None) -> None:
        self.steps = [*self.steps, Step(order=len(self.steps) + 1, action=action, result=result)]
        self.touch()

    def set_conclusion(self, text: str) -> None:
        self.conclusion = text
        self.touch()

    def add_hypothesis(self, statement: str, test: str = "") -> None:
        self.hypotheses = [
            *self.hypotheses,
            Hypothesis(id=f"h{len(self.hypotheses) + 1}", statement=statement, test=test),
        ]
        self.touch()

    def set_hypothesis_result(self, result: str) -> None:
        if self.hypotheses:
            self.hypotheses[-1].result = result
            self.touch()

    def set_tags(self, tags: list[str]) -> None:
        self.tags = tags
        self.touch()

    def set_references(self, references: list[str]) -> None:
        self.references = references
        self.touch()

    def add_evidence(self, summary: str, rel_path: str) -> None:
        self.evidence = [*self.evidence, Evidence(path=rel_path, type="file", summary=summary)]
        self.touch()

    def set_status(self, status: str) -> None:
        if status not in VALID_STATUS:
            raise CaseValidationError(f"invalid status: {status!r}")
        self.status = status
        self.touch()

    def promote(self, target: str, path: str) -> None:
        """Mark the case as promoted. Promotion is the validation act.

        Requires a valid target, a ``resolved`` case and a single promotion.
        """
        if target not in VALID_PROMOTION_TARGETS:
            raise ValueError(f"invalid promotion target: {target!r} (expected fiche|skill)")
        if self.status != "resolved":
            raise ValueError(f"cannot promote a case in status {self.status!r} — mark it resolved first")
        if self.promotion is not None:
            raise ValueError(f"case already promoted to {self.promotion.target}")
        self.promotion = Promotion(target=target, path=path, date=now_iso())
        self.touch()
