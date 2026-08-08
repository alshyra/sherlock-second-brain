"""Tests for the ``MemoryService`` use case (index maintenance)."""

from __future__ import annotations

from typing import Any

import pytest

from sherlock_second_brain.adapters.filesystem import Storage
from sherlock_second_brain.application.memory_service import MemoryService
from sherlock_second_brain.domain.errors import MemoryNotFoundError


class RecordingIndex:
    """Fake SearchIndex recording upsert/delete calls (no embeddings)."""

    def __init__(self) -> None:
        self.upserts: list[tuple[str, str, dict[str, str]]] = []
        self.deletes: list[str] = []
        self.docs: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return True

    def rebuild(self) -> int:
        return 0

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        matches = [doc_id for doc_id in self.docs if doc_id.startswith("memory:")]
        return [
            {"id": doc_id, "score": 0.9}
            for doc_id in matches[:top_k]
        ]

    def upsert_single(self, doc_id: str, text: str, metadata: dict[str, str]) -> None:
        self.upserts.append((doc_id, text, metadata))
        self.docs[doc_id] = text

    def delete_doc(self, doc_id: str) -> None:
        self.deletes.append(doc_id)
        self.docs.pop(doc_id, None)


def _service(storage: Storage) -> tuple[MemoryService, RecordingIndex]:
    index = RecordingIndex()
    return MemoryService(storage, index), index


def test_create_indexes_memory(storage: Storage) -> None:
    svc, index = _service(storage)
    memory = svc.create(summary="Le NAS tourne sur Fedora 44", content="Serveur Fedora 44.")
    assert index.upserts[-1][0] == f"memory:{memory.id}"
    assert index.upserts[-1][1] == "Le NAS tourne sur Fedora 44\nServeur Fedora 44."
    assert index.upserts[-1][2] == {"kind": "memory", "id": memory.id}


def test_update_reindexes(storage: Storage) -> None:
    svc, index = _service(storage)
    memory = svc.create(summary="s", content="c")
    svc.update(memory.id, content="nouveau")
    assert index.docs[f"memory:{memory.id}"] == "s\nnouveau"


def test_delete_removes_from_index(storage: Storage) -> None:
    svc, index = _service(storage)
    memory = svc.create(summary="s", content="c")
    svc.delete(memory.id)
    assert index.deletes == [f"memory:{memory.id}"]
    assert f"memory:{memory.id}" not in index.docs


def test_search_restricts_to_memories(storage: Storage) -> None:
    svc, index = _service(storage)
    svc.create(summary="mémoire NAS", content="Fedora 44")
    index.docs["fiche:autre"] = "autre"
    results = svc.search("nas", top_k=5)
    assert results
    assert all(str(r["id"]).startswith("memory:") for r in results)


def test_get_missing_raises(storage: Storage) -> None:
    svc, _ = _service(storage)
    with pytest.raises(MemoryNotFoundError):
        svc.get("mem-2020-01-01-999")
