"""Domain models for the second brain (cases, fiches, skills)."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

CASE_ID_PATTERN = r"^case-\d{4}-\d{2}-\d{2}-\d{3}$"


def now_iso() -> str:
    """Current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Hypothesis(BaseModel):
    id: str = Field(pattern=r"^h\d+$")
    statement: str
    test: str
    result: str | None = Field(default=None, pattern=r"^(confirmed|refuted|inconclusive)$")
    evidence: list[str] = Field(default_factory=list)


class Step(BaseModel):
    order: int
    action: str
    result: str | None = None
    evidence: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    path: str
    type: str
    summary: str


class Promotion(BaseModel):
    target: str
    path: str
    date: str


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
