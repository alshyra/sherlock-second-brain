"""Lexical index: search fallback when chromadb is not installed.

Pure Python, no external dependency. Used at the composition root when the
``[vector]`` extra is absent — index writes are no-ops (no index exists),
only reads work.
"""

from __future__ import annotations

import re
from typing import Any

from sherlock_second_brain.adapters.documents import enumerate_documents
from sherlock_second_brain.application.ports import DocumentSource, SearchIndex


class LexicalIndex(SearchIndex):
    """Search over fiches/cases/skills by simple token overlap."""

    def __init__(self, source: DocumentSource) -> None:
        self._source = source

    @property
    def available(self) -> bool:
        return False

    def _documents(self) -> list[tuple[str, str, dict[str, str]]]:
        """Return (id, text, metadata) for every fiche, case and skill."""
        return enumerate_documents(self._source)

    def rebuild(self) -> int:
        """No vector index to rebuild. Returns 0."""
        return 0

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Score each document by fraction of query tokens found."""
        tokens = set(re.findall(r"\w+", text.lower()))
        scored: list[tuple[float, dict[str, Any]]] = []
        for doc_id, doc_text, meta in self._documents():
            doc_tokens = set(re.findall(r"\w+", doc_text.lower()))
            overlap = len(tokens & doc_tokens)
            if overlap:
                score = overlap / max(1, len(tokens))
                scored.append((score, {"id": doc_id, "score": score, **meta}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:top_k]]

    def upsert_single(self, doc_id: str, text: str, metadata: dict[str, str]) -> None:
        """No persistent index to update."""
        return

    def delete_doc(self, doc_id: str) -> None:
        """No persistent index to delete from."""
        return
