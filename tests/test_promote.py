"""Tests for case promotion into fiches and skills."""

from __future__ import annotations

import pytest

from second_brain.adapters.filesystem import Storage
from second_brain.application.promotion_service import PromotionService
from second_brain.domain.models.case import Case
from second_brain.domain.models.step import Step


def _service(storage: Storage) -> PromotionService:
    return PromotionService(storage, storage, storage)


def _resolved_case(storage: Storage) -> Case:
    case = storage.create_case(
        title="Réparer le renouvellement SSL",
        goal="Comprendre pourquoi le renouvellement Let's Encrypt échoue",
        context="Cert en échec depuis 3 jours",
        tags=["traefik", "ssl"],
        references=["https://example.com/docs"],
    )
    storage.add_evidence(case.id, "error: invalid response", "cause du refus", "01.log")
    case = storage.get_case(case.id)
    case.findings.append("Le DNS-01 renvoie un TXT trop long")
    case.conclusion = "Réduire la taille du record TXT résout le problème"
    case.steps = [
        *case.steps,
        Step(order=1, action="tester le record TXT", result="trop long"),
    ]
    case.status = "resolved"
    storage.update_case(case)
    return storage.get_case(case.id)


def test_cannot_promote_open_case(storage: Storage) -> None:
    case = storage.create_case(title="a", goal="g")
    with pytest.raises(ValueError):
        _service(storage).promote(case, "fiche")


def test_invalid_target(storage: Storage) -> None:
    case = _resolved_case(storage)
    with pytest.raises(ValueError):
        _service(storage).promote(case, "memo")


def test_promote_to_fiche(storage: Storage) -> None:
    case = _resolved_case(storage)
    result = _service(storage).promote(case, "fiche")
    assert result["target"] == "fiche"
    assert result["path"].startswith("fiches/")
    assert "## Constats" in result["content"]
    assert "cause du refus" not in result["content"]  # preuve reste dans le case
    fiche = storage.read_fiche(result["slug"])
    assert case.title in fiche
    assert "cause du refus" not in fiche


def test_promote_to_skill(storage: Storage) -> None:
    case = _resolved_case(storage)
    result = _service(storage).promote(case, "skill")
    assert result["target"] == "skill"
    assert result["path"].endswith("SKILL.md")
    assert "## Procédure" in result["content"]
    assert "name:" in result["content"]
    skill = storage.read_skill(result["slug"])
    assert "1. tester le record TXT" in skill


def test_promotion_marks_case(storage: Storage) -> None:
    case = _resolved_case(storage)
    _service(storage).promote(case, "fiche")
    updated = storage.get_case(case.id)
    assert updated.promotion is not None
    assert updated.promotion.target == "fiche"


def test_fiche_badges_promotion_status(storage: Storage) -> None:
    case = _resolved_case(storage)
    result = _service(storage).promote(case, "fiche")
    assert "Statut : validé" in result["content"]
    fiche = storage.read_fiche(result["slug"])
    assert "Statut : validé" in fiche
