"""Tests for case promotion into fiches and skills."""

from __future__ import annotations

import pytest

from sherlock_second_brain.adapters.filesystem import Storage
from sherlock_second_brain.application.promotion_service import PromotionService
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.models.memory import Memory


def _service(storage: Storage) -> PromotionService:
    return PromotionService(storage, storage, storage, storage)


def _resolved_case(storage: Storage) -> Case:
    case = Case.create_case(
        storage.next_case_id(),
        title="Fix SSL renewal",
        goal="Understand why the Let's Encrypt renewal fails",
        context="Cert failing for 3 days",
        tags=["traefik", "ssl"],
        references=["https://example.com/docs"],
    )
    storage.save_case(case)
    rel = storage.write_evidence(case.id, "01.log", "error: invalid response")
    case.add_evidence("cause of refusal", rel)
    case.add_finding("DNS-01 returns a TXT record that is too long")
    case.set_conclusion("Reducing the TXT record size fixes the problem")
    case.add_step("test the TXT record", "too long")
    case.set_status("resolved")
    storage.save_case(case)
    return storage.get_case(case.id)


def test_cannot_promote_open_case(storage: Storage) -> None:
    case = Case.create_case(storage.next_case_id(), title="a", goal="g")
    storage.save_case(case)
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
    memory = Memory.create_memory(
        storage.next_memory_id(),
        summary="Le NAS tourne sur Fedora 44",
        content="Serveur Fedora 44 avec Jellyfin et les *Arr.",
        tags=["nas", "infra"],
        references=["https://fedoraproject.org"],
        source="slack",
    )
    storage.save_memory(memory)
    return memory


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
