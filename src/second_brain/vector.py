"""Vector index over fiches and cases (ChromaDB + fastembed, in-process).

The index is *derived*: it can always be rebuilt from the source files
(kb/ and cases/). Optional — if chromadb/fastembed are not installed,
search falls back to lexical matching.
"""

from __future__ import annotations

import json
import re
from typing import Any

try:  # optional dependency group
    import chromadb
    from chromadb.config import Settings

    _CHROMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CHROMA_AVAILABLE = False

from second_brain.storage import Storage

_COLLECTION = "second_brain"
_EMBED_MODEL = "BAAI/bge-small-en-v1.5"


class VectorIndex:
    """Thin wrapper around a persistent ChromaDB collection."""

    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self._client: Any | None = None
        self._collection: Any | None = None

    @property
    def available(self) -> bool:
        return _CHROMA_AVAILABLE

    def _ensure(self) -> Any:
        if not _CHROMA_AVAILABLE:
            raise RuntimeError("chromadb is not installed (pip install second-brain[vector])")
        if self._collection is None:
            self.storage.vector_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.storage.vector_dir), settings=Settings(anonymized_telemetry=False)
            )
            self._collection = self._client.get_or_create_collection(
                name=_COLLECTION, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def _documents(self) -> list[tuple[str, str, dict[str, str]]]:
        """Return (id, text, metadata) for every fiche and case."""
        docs: list[tuple[str, str, dict[str, str]]] = []
        for path in self.storage.list_fiches():
            text = path.read_text(encoding="utf-8")
            docs.append((f"fiche:{path.stem}", text, {"kind": "fiche", "slug": path.stem}))
        for case in self.storage.list_cases():
            text = json.dumps(case.model_dump(), ensure_ascii=False)
            docs.append((f"case:{case.id}", text, {"kind": "case", "id": case.id}))
        for path in self.storage.list_skills():
            text = path.read_text(encoding="utf-8")
            docs.append((f"skill:{path.parent.name}", text, {"kind": "skill", "slug": path.parent.name}))
        return docs

    def rebuild(self) -> int:
        """Recreate the collection from all source files. Returns doc count."""
        if not _CHROMA_AVAILABLE:
            return 0
        col = self._ensure()
        ids = [f"{d[0]}" for d in self._documents()]
        for batch_start in range(0, len(ids), 100):
            batch = self._documents()[batch_start : batch_start + 100]
            col.upsert(
                ids=[d[0] for d in batch],
                documents=[d[1] for d in batch],
                metadatas=[d[2] for d in batch],
            )
        return len(ids)

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic search. Falls back to lexical if chromadb missing."""
        if _CHROMA_AVAILABLE:
            try:
                col = self._ensure()
                res = col.query(query_texts=[text], n_results=top_k)
                out: list[dict[str, Any]] = []
                for i, dist in enumerate(res["distances"][0]):
                    meta = res["metadatas"][0][i]
                    out.append({"id": res["ids"][0][i], "score": round(1 - dist, 4), **meta})
                return out
            except Exception:
                # e.g. no embeddings yet — fall back to lexical
                pass
        return self._lexical(text, top_k)

    def _lexical(self, text: str, top_k: int) -> list[dict[str, Any]]:
        tokens = set(re.findall(r"\w+", text.lower()))
        scored: list[tuple[float, dict[str, Any]]] = []
        for d in self._documents():
            doc_tokens = set(re.findall(r"\w+", d[1].lower()))
            overlap = len(tokens & doc_tokens)
            if overlap:
                scored.append((overlap / max(1, len(tokens)), {"id": d[0], "score": overlap / max(1, len(tokens)), **d[2]}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:top_k]]

    def upsert_single(self, doc_id: str, text: str, metadata: dict[str, str]) -> None:
        """Re-embed a single document after a write."""
        if not _CHROMA_AVAILABLE:
            return
        col = self._ensure()
        col.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])

    def delete_doc(self, doc_id: str) -> None:
        if not _CHROMA_AVAILABLE:
            return
        try:
            col = self._ensure()
            col.delete(ids=[doc_id])
        except Exception:
            pass
