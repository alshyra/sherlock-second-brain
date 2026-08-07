"""DTO d'entrée pour l'outil MCP ``case_update``.

Typifie le ``fields`` dict accepté par ``case_update`` : champs optionnels,
validation du résultat d'hypothèse dès la couche d'interface.
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
