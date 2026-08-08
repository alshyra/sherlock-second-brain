"""Index hybride : fusion vectoriel + lexical par Reciprocal Rank Fusion.

Chroma est l'index persistant (``VectorIndex``) et la recherche lexicale
(``LexicalIndex``) complète la couverture — un document pertinent pour le
lexical mais manqué par le vectoriel remonte via l'autre leg. Les deux legs
sont fusionnés par RRF, sans normalisation de scores.
"""

from __future__ import annotations

from typing import Any

from sherlock_second_brain.application.ports import SearchIndex

RRF_K = 60  # constante de lissage de la fusion RRF


class HybridIndex(SearchIndex):
    """Combine un index vectoriel et un index lexical via RRF."""

    def __init__(self, vector: SearchIndex, lexical: SearchIndex, k: int = RRF_K) -> None:
        self._vector = vector
        self._lexical = lexical
        self._k = k

    @property
    def available(self) -> bool:
        return self._vector.available

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Fuse vector and lexical rankings by reciprocal rank."""
        vector_rank = {r["id"]: i + 1 for i, r in enumerate(self._vector.query(text, top_k=top_k))}
        lexical_rank = {r["id"]: i + 1 for i, r in enumerate(self._lexical.query(text, top_k=top_k))}

        ids = list(dict.fromkeys([*vector_rank, *lexical_rank]))
        fused = sorted(
            (self._rrf(vector_rank.get(doc_id), lexical_rank.get(doc_id)), doc_id)
            for doc_id in ids
        )
        fused.reverse()
        return [{"id": doc_id, "score": round(score, 4)} for score, doc_id in fused[:top_k]]

    def _rrf(self, vector_pos: int | None, lexical_pos: int | None) -> float:
        """Reciprocal Rank Fusion score for a single document."""
        score = 0.0
        if vector_pos is not None:
            score += 1 / (self._k + vector_pos)
        if lexical_pos is not None:
            score += 1 / (self._k + lexical_pos)
        return score

    def rebuild(self) -> int:
        """Chroma is the persistent index — rebuild it."""
        return self._vector.rebuild()

    def upsert_single(self, doc_id: str, text: str, metadata: dict[str, str]) -> None:
        self._vector.upsert_single(doc_id, text, metadata)

    def delete_doc(self, doc_id: str) -> None:
        self._vector.delete_doc(doc_id)
