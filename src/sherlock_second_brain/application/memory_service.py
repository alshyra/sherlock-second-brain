"""Use case: lifecycle of memories (standalone notes, no case).

A memory is a low-friction capture: unlike cases, the index is maintained on
every mutation (including create) so a freshly added memory is immediately
searchable — that is its whole purpose.
"""

from __future__ import annotations

from typing import Any

from sherlock_second_brain.application.ports import MemoryRepository, SearchIndex
from sherlock_second_brain.domain.models.memory import Memory


class MemoryService:
    """Orchestrates memory operations through its ports."""

    def __init__(self, repository: MemoryRepository, index: SearchIndex) -> None:
        self._repository = repository
        self._index = index

    @staticmethod
    def _doc_text(memory: Memory) -> str:
        return f"{memory.summary}\n{memory.content}"

    def _reindex(self, memory: Memory) -> None:
        self._index.upsert_single(
            f"memory:{memory.id}",
            self._doc_text(memory),
            {"kind": "memory", "id": memory.id},
        )

    def create(
        self,
        summary: str,
        content: str,
        tags: list[str] | None = None,
        references: list[str] | None = None,
        source: str | None = None,
    ) -> Memory:
        memory = self._repository.create_memory(
            summary=summary,
            content=content,
            tags=tags,
            references=references,
            source=source,
        )
        self._reindex(memory)
        return memory

    def get(self, memory_id: str) -> Memory:
        return self._repository.get_memory(memory_id)

    def list_memories(self, tag: str = "") -> list[Memory]:
        return self._repository.list_memories(tag=tag or None)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Hybrid search over the whole index, restricted to memories."""
        results = self._index.query(query, top_k=top_k)
        return [r for r in results if str(r.get("id", "")).startswith("memory:")]

    def update(
        self,
        memory_id: str,
        *,
        summary: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        references: list[str] | None = None,
        source: str | None = None,
    ) -> Memory:
        memory = self._repository.get_memory(memory_id)
        if summary is not None:
            memory.summary = summary
        if content is not None:
            memory.content = content
        if tags is not None:
            memory.tags = tags
        if references is not None:
            memory.references = references
        if source is not None:
            memory.source = source
        updated = self._repository.update_memory(memory)
        self._reindex(updated)
        return updated

    def delete(self, memory_id: str) -> None:
        self._repository.delete_memory(memory_id)
        self._index.delete_doc(f"memory:{memory_id}")
