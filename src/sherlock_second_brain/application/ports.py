"""Ports (Protocols) : contrats que les adapters doivent implémenter.

La couche ``application`` dépend uniquement de ces protocoles — jamais des
adapters concrets — pour rester testable et indépendante du stockage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from sherlock_second_brain.domain.models.case import Case


class CaseRepository(Protocol):
    def create_case(
        self,
        title: str,
        goal: str,
        context: str = "",
        tags: list[str] | None = None,
        references: list[str] | None = None,
    ) -> Case: ...

    def get_case(self, case_id: str) -> Case: ...

    def list_cases(self, status: str | None = None, tag: str | None = None) -> list[Case]: ...

    def update_case(self, case: Case) -> Case: ...

    def delete_case(self, case_id: str) -> None: ...

    def add_evidence(
        self, case_id: str, content: str, summary: str, filename: str | None = None
    ) -> Case: ...


class FicheRepository(Protocol):
    def write_fiche(self, slug: str, content: str) -> Path: ...

    def read_fiche(self, slug: str) -> str: ...

    def list_fiches(self) -> list[Path]: ...

    def delete_fiche(self, slug: str) -> None: ...


class SkillRepository(Protocol):
    def write_skill(self, slug: str, content: str) -> Path: ...

    def read_skill(self, slug: str) -> str: ...

    def list_skills(self) -> list[Path]: ...

    def delete_skill(self, slug: str) -> None: ...


class DocumentSource(Protocol):
    """Sources de documents pour l'index (fiches, cases, skills)."""

    def list_fiches(self) -> list[Path]: ...

    def list_cases(self) -> list[Case]: ...

    def list_skills(self) -> list[Path]: ...


class SearchIndex(Protocol):
    @property
    def available(self) -> bool: ...

    def rebuild(self) -> int: ...

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]: ...

    def upsert_single(self, doc_id: str, text: str, metadata: dict[str, str]) -> None: ...

    def delete_doc(self, doc_id: str) -> None: ...
