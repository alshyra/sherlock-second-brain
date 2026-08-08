"""Tests for rich domain aggregates: invariants and behavior."""

from __future__ import annotations

import pytest

from sherlock_second_brain.domain.errors import CaseValidationError, MemoryValidationError
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.models.memory import Memory

_CASE_ID = "case-2026-08-08-001"
_MEM_ID = "mem-2026-08-08-001"


def _case() -> Case:
    return Case.create_case(_CASE_ID, title="t", goal="g")


# ── Case factory ────────────────────────────────────────────────


def test_create_case_defaults() -> None:
    case = _case()
    assert case.id == _CASE_ID
    assert case.status == "open"
    assert case.created_at == case.updated_at
    assert case.findings == []


def test_create_case_requires_title() -> None:
    with pytest.raises(CaseValidationError):
        Case.create_case(_CASE_ID, title="   ", goal="g")


def test_create_case_strips_fields() -> None:
    case = Case.create_case(_CASE_ID, title="  Titre  ", goal="  g  ")
    assert case.title == "Titre"
    assert case.goal == "g"


# ── Case mutations ──────────────────────────────────────────────


def test_add_step_increments_order() -> None:
    case = _case()
    case.add_step("a")
    case.add_step("b", "ok")
    assert [s.order for s in case.steps] == [1, 2]
    assert case.steps[1].result == "ok"


def test_add_hypothesis_auto_ids() -> None:
    case = _case()
    case.add_hypothesis("a", "test a")
    case.add_hypothesis("b")
    assert [h.id for h in case.hypotheses] == ["h1", "h2"]
    assert case.hypotheses[1].test == ""


def test_set_hypothesis_result_targets_last() -> None:
    case = _case()
    case.add_hypothesis("a")
    case.add_hypothesis("b")
    case.set_hypothesis_result("confirmed")
    assert case.hypotheses[-1].result == "confirmed"
    assert case.hypotheses[0].result is None


def test_add_evidence_creates_file_evidence() -> None:
    case = _case()
    case.add_evidence("preuve", "evidence/01.log")
    assert case.evidence[0].type == "file"
    assert case.evidence[0].summary == "preuve"
    assert case.evidence[0].path == "evidence/01.log"


def test_set_status_rejects_invalid() -> None:
    case = _case()
    with pytest.raises(CaseValidationError):
        case.set_status("inconnu")
    assert case.status == "open"


# ── Case promotion (validation act) ─────────────────────────────


def test_promote_requires_resolved() -> None:
    case = _case()
    with pytest.raises(ValueError):
        case.promote("fiche", "fiches/x.md")


def test_promote_rejects_invalid_target() -> None:
    case = _case()
    case.set_status("resolved")
    with pytest.raises(ValueError):
        case.promote("skilll", "fiches/x.md")


def test_promote_is_one_shot() -> None:
    case = _case()
    case.set_status("resolved")
    case.promote("fiche", "fiches/x.md")
    with pytest.raises(ValueError):
        case.promote("skill", "skills/x/SKILL.md")
    assert case.promotion is not None
    assert case.promotion.target == "fiche"
    assert case.promotion.path == "fiches/x.md"


# ── Memory ──────────────────────────────────────────────────────


def test_memory_create_requires_summary() -> None:
    with pytest.raises(MemoryValidationError):
        Memory.create_memory(_MEM_ID, summary="  ", content="c")


def test_memory_create_defaults() -> None:
    memory = Memory.create_memory(_MEM_ID, summary="s", content="c", source="slack")
    assert memory.id == _MEM_ID
    assert memory.tags == []
    assert memory.source == "slack"
    assert memory.created_at == memory.updated_at


def test_memory_set_summary_requires_non_blank() -> None:
    memory = Memory.create_memory(_MEM_ID, summary="s", content="c")
    with pytest.raises(MemoryValidationError):
        memory.set_summary("   ")


def test_memory_promote_is_one_shot() -> None:
    memory = Memory.create_memory(_MEM_ID, summary="s", content="c")
    memory.promote("fiches/x.md")
    assert memory.promotion is not None
    assert memory.promotion.target == "fiche"
    with pytest.raises(ValueError):
        memory.promote("fiches/x.md")
