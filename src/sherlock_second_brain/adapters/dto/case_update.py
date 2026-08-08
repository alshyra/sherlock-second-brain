"""Input DTO for the ``case_update`` MCP tool.

Types the ``fields`` dict accepted by ``case_update``: optional fields, with
hypothesis-result validation already at the interface layer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

HYPOTHESIS_RESULT_PATTERN = r"^(confirmed|refuted|inconclusive)$"


class CaseUpdateFields(BaseModel):
    finding: str | None = Field(default=None, description="Append this finding to the case findings list.")
    step_action: str | None = Field(default=None, description="Append a step with this action (pair it with ``step_result``).")
    step_result: str | None = Field(default=None, description="Result of the step currently being appended.")
    conclusion: str | None = Field(default=None, description="Set the case conclusion (overwrites any previous one).")
    hypothesis_statement: str | None = Field(default=None, description="Append a hypothesis with this statement.")
    hypothesis_test: str | None = Field(default=None, description="Test or check for the hypothesis being appended.")
    hypothesis_result: str | None = Field(
        default=None, pattern=HYPOTHESIS_RESULT_PATTERN, description="Result of the last hypothesis: confirmed, refuted or inconclusive."
    )
    tags: list[str] | None = Field(default=None, description="Replace the case tags with this list.")
    references: list[str] | None = Field(default=None, description="Replace the case references with this list.")
