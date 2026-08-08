"""Input DTO for the ``case_update`` MCP tool.

Types the ``fields`` dict accepted by ``case_update``: optional fields, with
hypothesis-result validation already at the interface layer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

HYPOTHESIS_RESULT_PATTERN = r"^(confirmed|refuted|inconclusive)$"


class CaseUpdateFields(BaseModel):
    finding: str | None = None
    step_action: str | None = None
    step_result: str | None = None
    conclusion: str | None = None
    hypothesis_statement: str | None = None
    hypothesis_test: str | None = None
    hypothesis_result: str | None = Field(default=None, pattern=HYPOTHESIS_RESULT_PATTERN)
    tags: list[str] | None = None
    references: list[str] | None = None
