"""Tests for the vector index (lexical fallback + semantic when available)."""

from __future__ import annotations

import pytest

from second_brain.adapters.chroma import VectorIndex
from second_brain.adapters.filesystem import Storage


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


def _index(storage: Storage) -> VectorIndex:
    return VectorIndex(storage, storage.vector_dir)


def test_lexical_search_finds_fiche(storage: Storage) -> None:
    _seed(storage)
    idx = _index(storage)
    results = idx._lexical("renouvellement TLS échoue record trop long", top_k=5)
    assert results, "expected at least one result"
    assert any(r["id"] == "fiche:traefik-ssl-renew" for r in results)


def test_query_works_without_chroma(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(storage)
    monkeypatch.setattr("second_brain.adapters.chroma._CHROMA_AVAILABLE", False)
    idx = _index(storage)
    results = idx.query("renouvellement SSL record trop long")
    assert results
    assert any(r["id"].startswith("fiche:") or r["id"].startswith("case:") for r in results)


def test_rebuild_returns_zero_when_chroma_missing(storage: Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(storage)
    monkeypatch.setattr("second_brain.adapters.chroma._CHROMA_AVAILABLE", False)
    idx = _index(storage)
    assert idx.rebuild() == 0
