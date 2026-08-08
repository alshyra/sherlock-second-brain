"""Énumération partagée des documents indexables (fiches, cases, skills).

Les adapters ``chroma`` et ``lexical`` parcourent exactement les mêmes
documents sources ; la construction (id, texte, métadonnées) est factorisée ici.
"""

from __future__ import annotations

import json

from sherlock_second_brain.application.ports import DocumentSource


def enumerate_documents(source: DocumentSource) -> list[tuple[str, str, dict[str, str]]]:
    """Return (id, text, metadata) for every fiche, case and skill."""
    docs: list[tuple[str, str, dict[str, str]]] = []
    for path in source.list_fiches():
        text = path.read_text(encoding="utf-8")
        docs.append((f"fiche:{path.stem}", text, {"kind": "fiche", "slug": path.stem}))
    for case in source.list_cases():
        text = json.dumps(case.model_dump(), ensure_ascii=False)
        docs.append((f"case:{case.id}", text, {"kind": "case", "id": case.id}))
    for path in source.list_skills():
        text = path.read_text(encoding="utf-8")
        docs.append((f"skill:{path.parent.name}", text, {"kind": "skill", "slug": path.parent.name}))
    return docs
