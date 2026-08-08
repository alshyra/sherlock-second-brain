"""Ports (Protocols): contracts that adapters must implement.

The ``application`` layer depends only on these protocols — never on concrete
adapters — to stay testable and storage-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.models.memory import Memory


@dataclass(frozen=True)
class KbDoc:
    """A validated KB document (fiche or skill) read through a port.

    Storage-agnostic replacement for ``Path`` in the KB repositories: a remote
    backend returns slug + content, not local file paths.
    """

    slug: str
    content: str


class CaseRepository(Protocol):
    def next_case_id(self) -> str: ...

    def save_case(self, case: Case) -> None: ...

    def get_case(self, case_id: str) -> Case: ...

    def list_cases(self) -> list[Case]: ...

    def delete_case(self, case_id: str) -> None: ...

    def write_evidence(self, case_id: str, filename: str, content: str) -> str: ...


class FicheRepository(Protocol):
    def write_fiche(self, slug: str, content: str) -> str: ...

    def read_fiche(self, slug: str) -> str: ...

    def list_fiches(self) -> list[KbDoc]: ...

    def delete_fiche(self, slug: str) -> None: ...


class SkillRepository(Protocol):
    def write_skill(self, slug: str, content: str) -> str: ...

    def read_skill(self, slug: str) -> str: ...

    def list_skills(self) -> list[KbDoc]: ...

    def delete_skill(self, slug: str) -> None: ...


class MemoryRepository(Protocol):
    def next_memory_id(self) -> str: ...

    def save_memory(self, memory: Memory) -> None: ...

    def get_memory(self, memory_id: str) -> Memory: ...

    def list_memories(self) -> list[Memory]: ...

    def delete_memory(self, memory_id: str) -> None: ...


class DocumentSource(Protocol):
    """Document sources for the index (fiches, cases, skills, memories)."""

    def list_fiches(self) -> list[KbDoc]: ...

    def list_cases(self) -> list[Case]: ...

    def list_skills(self) -> list[KbDoc]: ...

    def list_memories(self) -> list[Memory]: ...


class SearchIndex(Protocol):
    @property
    def available(self) -> bool: ...

    def rebuild(self) -> int: ...

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]: ...

    def upsert_single(self, doc_id: str, text: str, metadata: dict[str, str]) -> None: ...

    def delete_doc(self, doc_id: str) -> None: ...
