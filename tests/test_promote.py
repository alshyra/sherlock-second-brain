"""Tests for case promotion into fiches and skills."""

from __future__ import annotations

import pytest

from sherlock_second_brain.adapters.filesystem import Storage
from sherlock_second_brain.application.promotion_service import PromotionService
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.models.memory import Memory
from sherlock_second_brain.domain.models.step import Step


def _service(storage: Storage) -> PromotionService:
    return PromotionService(storage, storage, storage, storage)


def _resolved_case(storage: Storage) -> Case:
    case = storage.create_case(
        title="Fix SSL renewal",
        goal="Understand why the Let's Encrypt renewal fails",
        context="Cert failing for 3 days",
        tags=["traefik", "ssl"],
        references=["https://example.com/docs"],
    )
    storage.add_evidence(case.id, "error: invalid response", "cause of refusal", "01.log")
    case = storage.get_case(case.id)
    case.findings.append("DNS-01 returns a TXT record that is too long")
    case.conclusion = "Reducing the TXT record size fixes the problem"
    case.steps = [
        *case.steps,
        Step(order=1, action="test the TXT record", result="too long"),
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
    assert "## Findings" in result["content"]
    assert "cause of refusal" not in result["content"]  # evidence stays in the case
    fiche = storage.read_fiche(result["slug"])
    assert case.title in fiche
    assert "cause of refusal" not in fiche


def test_promote_to_skill(storage: Storage) -> None:
    case = _resolved_case(storage)
    result = _service(storage).promote(case, "skill")
    assert result["target"] == "skill"
    assert result["path"].endswith("SKILL.md")
    assert "## Procedure" in result["content"]
    assert "name:" in result["content"]
    skill = storage.read_skill(result["slug"])
    assert "1. test the TXT record" in skill


def test_promotion_marks_case(storage: Storage) -> None:
    case = _resolved_case(storage)
    _service(storage).promote(case, "fiche")
    updated = storage.get_case(case.id)
    assert updated.promotion is not None
    assert updated.promotion.target == "fiche"


def test_fiche_badges_promotion_status(storage: Storage) -> None:
    case = _resolved_case(storage)
    result = _service(storage).promote(case, "fiche")
    assert "Status: validated" in result["content"]
    fiche = storage.read_fiche(result["slug"])
    assert "Status: validated" in fiche


def _memory(storage: Storage) -> Memory:
    return storage.create_memory(
        summary="Le NAS tourne sur Fedora 44",
        content="Serveur Fedora 44 avec Jellyfin et les *Arr.",
        tags=["nas", "infra"],
        references=["https://fedoraproject.org"],
        source="slack",
    )


def test_promote_memory_to_fiche(storage: Storage) -> None:
    memory = _memory(storage)
    result = _service(storage).promote_memory(memory)
    assert result["target"] == "fiche"
    assert result["path"].startswith("fiches/")
    assert "Le NAS tourne sur Fedora 44" in result["content"]
    assert "Status: validated" in result["content"]
    fiche = storage.read_fiche(result["slug"])
    assert "Jellyfin" in fiche
    assert "## References" in fiche


def test_promote_memory_marks_memory(storage: Storage) -> None:
    memory = _memory(storage)
    _service(storage).promote_memory(memory)
    updated = storage.get_memory(memory.id)
    assert updated.promotion is not None
    assert updated.promotion.target == "fiche"


def test_promote_memory_twice_rejected(storage: Storage) -> None:
    memory = _memory(storage)
    svc = _service(storage)
    svc.promote_memory(memory)
    with pytest.raises(ValueError):
        svc.promote_memory(storage.get_memory(memory.id))
