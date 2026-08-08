"""Tests des index de recherche (lexical pur + sémantique ChromaDB)."""

from __future__ import annotations

import pytest

from second_brain.adapters.filesystem import Storage
from second_brain.adapters.lexical import LexicalIndex


def _seed(storage: Storage) -> None:
    storage.write_fiche(
        "traefik-ssl-renew",
        "# Traefik SSL renewal\nLe renouvellement Let's Encrypt échoue quand le record DNS TXT est trop long.",
    )
    case = storage.create_case(
        title="Cert échec",
        goal="Comprendre l'échec de renouvellement",
        context="DNS-01 renvoie un record trop long",
    )
    storage.add_evidence(case.id, "invalid response from http-01", "cause", "01.log")


def test_lexical_search_finds_fiche(storage: Storage) -> None:
    _seed(storage)
    idx = LexicalIndex(storage)
    results = idx.query("renouvellement TLS échoue record trop long", top_k=5)
    assert results, "expected at least one result"
    assert any(r["id"] == "fiche:traefik-ssl-renew" for r in results)


def test_lexical_returns_nothing_on_no_overlap(storage: Storage) -> None:
    _seed(storage)
    idx = LexicalIndex(storage)
    results = idx.query("zebre philosophie quantique", top_k=5)
    assert results == []


def test_lexical_available_is_false(storage: Storage) -> None:
    assert LexicalIndex(storage).available is False


def test_lexical_rebuild_returns_zero(storage: Storage) -> None:
    _seed(storage)
    assert LexicalIndex(storage).rebuild() == 0


def test_chroma_index_builds_when_available(storage: Storage) -> None:
    pytest.importorskip("chromadb")
    from second_brain.adapters.chroma import VectorIndex

    _seed(storage)
    idx = VectorIndex(storage, storage.vector_dir)
    assert idx.available is True
    assert idx.rebuild() == 2  # 1 fiche + 1 case
    results = idx.query("renouvellement TLS échoue record trop long", top_k=5)
    assert any(r["id"] == "fiche:traefik-ssl-renew" for r in results)
