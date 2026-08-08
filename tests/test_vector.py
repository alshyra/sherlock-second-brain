"""Tests de la recherche hybride : legs vectoriel, lexical et fusion RRF."""

from __future__ import annotations

from sherlock_second_brain.adapters.chroma import VectorIndex
from sherlock_second_brain.adapters.filesystem import Storage
from sherlock_second_brain.adapters.hybrid import HybridIndex
from sherlock_second_brain.adapters.lexical import LexicalIndex
from sherlock_second_brain.domain.models.case import Case


def _seed(storage: Storage) -> None:
    storage.write_fiche(
        "traefik-ssl-renew",
        "# Traefik SSL renewal\nLe renouvellement Let's Encrypt échoue quand le record DNS TXT est trop long.",
    )
    storage.write_fiche(
        "postgres-backup",
        "# Sauvegarde PostgreSQL\nLe backup quotidien échoue quand l'espace disque est plein.",
    )
    case = Case.create_case(
        storage.next_case_id(),
        title="Cert échec",
        goal="Comprendre l'échec de renouvellement",
        context="DNS-01 renvoie un record trop long",
    )
    storage.save_case(case)
    rel = storage.write_evidence(case.id, "01.log", "invalid response from http-01")
    case.add_evidence("cause", rel)
    storage.save_case(case)


def _hybrid(storage: Storage) -> HybridIndex:
    return HybridIndex(VectorIndex(storage, storage.vector_dir), LexicalIndex(storage))


def test_vector_leg_returns_semantic_results(storage: Storage) -> None:
    _seed(storage)
    idx = VectorIndex(storage, storage.vector_dir)
    assert idx.rebuild() == 3  # 2 fiches + 1 case
    results = idx.query("renouvellement certificat DNS record trop long", top_k=5)
    assert any(r["id"] == "fiche:traefik-ssl-renew" for r in results)


def test_lexical_leg_returns_token_overlap(storage: Storage) -> None:
    _seed(storage)
    idx = LexicalIndex(storage)
    results = idx.query("postgres backup disque plein", top_k=5)
    assert any(r["id"] == "fiche:postgres-backup" for r in results)


def test_lexical_returns_nothing_on_no_overlap(storage: Storage) -> None:
    _seed(storage)
    assert LexicalIndex(storage).query("zebre philosophie quantique", top_k=5) == []


def test_hybrid_fuses_rankings(storage: Storage) -> None:
    _seed(storage)
    idx = _hybrid(storage)
    idx.rebuild()
    results = idx.query("renouvellement TLS record trop long", top_k=5)
    assert results, "expected at least one result"
    assert any(r["id"] == "fiche:traefik-ssl-renew" for r in results)


def test_hybrid_keeps_doc_found_by_lexical_only(storage: Storage) -> None:
    _seed(storage)
    idx = _hybrid(storage)
    idx.rebuild()
    results = idx.query("backup quotidien espace disque", top_k=5)
    # the lexical leg finds postgres-backup even if the vector leg misses it
    assert any(r["id"] == "fiche:postgres-backup" for r in results)


def test_hybrid_rebuild_uses_vector(storage: Storage) -> None:
    _seed(storage)
    idx = _hybrid(storage)
    assert idx.rebuild() == 3
    assert idx.available is True


def test_rebuild_resets_collection_before_reinsert(storage: Storage) -> None:
    _seed(storage)
    idx = VectorIndex(storage, storage.vector_dir)
    assert idx.rebuild() == 3
    storage.write_fiche("nouvelle-fiche", "# Nouvelle fiche\nContenu ajouté plus tard.")
    assert idx.rebuild() == 4
    results = idx.query("nouvelle fiche contenu ajouté", top_k=5)
    assert any(r["id"] == "fiche:nouvelle-fiche" for r in results)
