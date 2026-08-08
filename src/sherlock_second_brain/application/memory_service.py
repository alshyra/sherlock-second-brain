"""Use case: lifecycle of memories (thin orchestration).

Business rules live on the ``Memory`` aggregate (domain). This service only
orders the calls and keeps the index in sync. Unlike cases, the index is
maintained on every mutation (including create) so a freshly added memory is
immediately searchable — that is its whole purpose.
"""

from __future__ import annotations

from typing import Any

from sherlock_second_brain.application.ports import MemoryRepository, SearchIndex
from sherlock_second_brain.domain.models.memory import Memory


class MemoryService:
    """Coordinates memory operations through their ports."""

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
        memory = Memory.create_memory(
            self._repository.next_memory_id(),
            summary=summary,
            content=content,
            tags=tags,
            references=references,
            source=source,
        )
        self._repository.save_memory(memory)
        self._reindex(memory)
        return memory

    def get(self, memory_id: str) -> Memory:
        return self._repository.get_memory(memory_id)

    def list_memories(self, tag: str = "") -> list[Memory]:
        memories = self._repository.list_memories()
        if tag:
            memories = [m for m in memories if tag in m.tags]
        return memories

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
            memory.set_summary(summary)
        if content is not None:
            memory.set_content(content)
        if tags is not None:
            memory.set_tags(tags)
        if references is not None:
            memory.set_references(references)
        if source is not None:
            memory.set_source(source)
        self._repository.save_memory(memory)
        self._reindex(memory)
        return memory

    def delete(self, memory_id: str) -> None:
        self._repository.delete_memory(memory_id)
        self._index.delete_doc(f"memory:{memory_id}")
