"""Shared enumeration of indexable documents (fiches, cases, skills, memories).

The ``chroma`` and ``lexical`` adapters walk exactly the same source documents;
the (id, text, metadata) construction is factored here.
"""

from __future__ import annotations

import json

from sherlock_second_brain.application.ports import DocumentSource


def enumerate_documents(source: DocumentSource) -> list[tuple[str, str, dict[str, str]]]:
    """Return (id, text, metadata) for every fiche, case, skill and memory."""
    docs: list[tuple[str, str, dict[str, str]]] = []
    for doc in source.list_fiches():
        docs.append((f"fiche:{doc.slug}", doc.content, {"kind": "fiche", "slug": doc.slug}))
    for case in source.list_cases():
        text = json.dumps(case.model_dump(), ensure_ascii=False)
        docs.append((f"case:{case.id}", text, {"kind": "case", "id": case.id}))
    for doc in source.list_skills():
        docs.append((f"skill:{doc.slug}", doc.content, {"kind": "skill", "slug": doc.slug}))
    for memory in source.list_memories():
        text = f"{memory.summary}\n{memory.content}"
        docs.append((f"memory:{memory.id}", text, {"kind": "memory", "id": memory.id}))
    return docs
