"""Adapter ChromaDB : index vectoriel sur les fiches, cases et skills.

Chroma est une dépendance obligatoire : la recherche est hybride (vectoriel +
lexical) et ``server.py`` compose ``VectorIndex`` avec ``LexicalIndex`` via
``HybridIndex``. Le modèle d'embedding est multilingue (MiniLM-L12) pour une KB
en français.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from chromadb import PersistentClient
from chromadb.api.types import Documents, Embeddings
from chromadb.config import Settings
from fastembed import TextEmbedding

from sherlock_second_brain.adapters.documents import enumerate_documents
from sherlock_second_brain.application.ports import DocumentSource, SearchIndex

logger = logging.getLogger(__name__)

_COLLECTION = "sherlock_second_brain"
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class FastembedEmbeddingFunction:
    """Embedding function Chroma adossée à fastembed (modèle multilingue).

    L'instance fastembed est créée paresseusement au premier appel (le modèle
    est téléchargé une fois puis mis en cache localement). L'interface est
    celle dictée par Chroma (``EmbeddingFunction``) — volontairement non
    subtypée ici car les generics de chroma sont trop stricts pour fastembed.
    """

    def __init__(self, model_name: str = EMBED_MODEL) -> None:
        self._model_name = model_name
        self._model: Any = None  # noqa: ANN401  # API fastembed dynamique

    def __call__(self, input: Documents) -> Embeddings:
        if self._model is None:
            self._model = TextEmbedding(model_name=self._model_name)
        return cast(Embeddings, list(self._model.embed(input)))

    def embed_query(self, input: Documents) -> Embeddings:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "fastembed_multilingual"

    def get_config(self) -> dict[str, str]:
        return {"model_name": self._model_name}

    @classmethod
    def build_from_config(cls, config: dict[str, str]) -> FastembedEmbeddingFunction:
        return cls(model_name=config.get("model_name", EMBED_MODEL))

    def is_legacy(self) -> bool:
        return False

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]

    def default_space(self) -> str:
        return "cosine"


class VectorIndex(SearchIndex):
    """Thin wrapper around a persistent ChromaDB collection."""

    def __init__(
        self,
        source: DocumentSource,
        vector_dir: Path,
        embedding_function: Any = None,  # noqa: ANN401  # interface dictée par Chroma
    ) -> None:
        self._source = source
        self._vector_dir = vector_dir
        self._embedding_function: Any = (  # noqa: ANN401  # interface dictée par Chroma
            embedding_function or FastembedEmbeddingFunction()
        )
        self._client: Any = None  # noqa: ANN401  # API ChromaDB dynamique
        self._collection: Any = None  # noqa: ANN401  # API ChromaDB dynamique

    @property
    def available(self) -> bool:
        return True

    def _ensure(self, reset: bool = False) -> Any:  # noqa: ANN401  # API ChromaDB dynamique
        if self._client is None:
            self._vector_dir.mkdir(parents=True, exist_ok=True)
            self._client = PersistentClient(
                path=str(self._vector_dir), settings=Settings(anonymized_telemetry=False)
            )
        if self._collection is None:
            if reset:
                try:
                    self._client.delete_collection(_COLLECTION)
                except Exception:  # collection absente au premier rebuild
                    pass
            self._collection = self._client.get_or_create_collection(
                name=_COLLECTION,
                embedding_function=self._embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _documents(self) -> list[tuple[str, str, dict[str, str]]]:
        """Return (id, text, metadata) for every fiche, case and skill."""
        return enumerate_documents(self._source)

    def rebuild(self) -> int:
        """Recreate the collection from all source files. Returns doc count."""
        col = self._ensure(reset=True)
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
