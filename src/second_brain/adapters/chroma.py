"""Adapter ChromaDB : index vectoriel sur les fiches, cases et skills.

Module *optionnel* : il n'est importé que si l'extra ``[vector]`` (chromadb +
fastembed) est installé. L'optionnalité est gérée à la composition root
(``server.py``) par un try/except d'import, jamais par import paresseux.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from chromadb import PersistentClient
from chromadb.config import Settings

from second_brain.adapters.documents import enumerate_documents
from second_brain.application.ports import DocumentSource, SearchIndex

logger = logging.getLogger(__name__)

_COLLECTION = "second_brain"
_EMBED_MODEL = "BAAI/bge-small-en-v1.5"


class VectorIndex(SearchIndex):
    """Thin wrapper around a persistent ChromaDB collection."""

    def __init__(self, source: DocumentSource, vector_dir: Path) -> None:
        self._source = source
        self._vector_dir = vector_dir
        self._client: Any = None  # noqa: ANN401  # API ChromaDB dynamique
        self._collection: Any = None  # noqa: ANN401  # API ChromaDB dynamique

    @property
    def available(self) -> bool:
        return True

    def _ensure(self) -> Any:  # noqa: ANN401  # API ChromaDB dynamique
        if self._collection is None:
            self._vector_dir.mkdir(parents=True, exist_ok=True)
            self._client = PersistentClient(
                path=str(self._vector_dir), settings=Settings(anonymized_telemetry=False)
            )
            self._collection = self._client.get_or_create_collection(
                name=_COLLECTION, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def _documents(self) -> list[tuple[str, str, dict[str, str]]]:
        """Return (id, text, metadata) for every fiche, case and skill."""
        return enumerate_documents(self._source)

    def rebuild(self) -> int:
        """Recreate the collection from all source files. Returns doc count."""
        col = self._ensure()
        docs = self._documents()
        for batch_start in range(0, len(docs), 100):
            batch = docs[batch_start : batch_start + 100]
            col.upsert(
                ids=[d[0] for d in batch],
                documents=[d[1] for d in batch],
                metadatas=[d[2] for d in batch],
            )
        return len(docs)

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic search over the vector index."""
        col = self._ensure()
        res = col.query(query_texts=[text], n_results=top_k)
        out: list[dict[str, Any]] = []
        for i, dist in enumerate(res["distances"][0]):
            meta = res["metadatas"][0][i]
            out.append({"id": res["ids"][0][i], "score": round(1 - dist, 4), **meta})
        return out

    def upsert_single(self, doc_id: str, text: str, metadata: dict[str, str]) -> None:
        """Re-embed a single document after a write."""
        col = self._ensure()
        col.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])

    def delete_doc(self, doc_id: str) -> None:
        try:
            col = self._ensure()
            col.delete(ids=[doc_id])
        except Exception as exc:
            logger.warning("suppression doc %s dans l'index impossible : %s", doc_id, exc)
