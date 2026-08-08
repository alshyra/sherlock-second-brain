"""Tests du service applicatif ``CaseService``."""

from __future__ import annotations

import pytest

from second_brain.adapters.filesystem import Storage
from second_brain.adapters.lexical import LexicalIndex
from second_brain.application.case_service import CaseService
from second_brain.domain.errors import CaseNotFoundError


def _service(storage: Storage) -> CaseService:
    index = LexicalIndex(storage)
    return CaseService(storage, index)


def test_update_sets_hypothesis_result(storage: Storage) -> None:
    svc = _service(storage)
    case = svc.create(title="t", goal="g")
    svc.update(
        case.id,
        hypothesis_statement="le DNS est en cause",
        hypothesis_test="lancer dig",
        hypothesis_result="confirmed",
    )
    updated = svc.get(case.id)
    assert len(updated.hypotheses) == 1
    assert updated.hypotheses[0].result == "confirmed"


def test_update_appends_finding_and_step(storage: Storage) -> None:
    svc = _service(storage)
    case = svc.create(title="t", goal="g")
    svc.update(case.id, finding="constat 1", step_action="run test", step_result="ok")
    updated = svc.get(case.id)
    assert updated.findings == ["constat 1"]
    assert updated.steps[0].action == "run test"
    assert updated.steps[0].result == "ok"


def test_delete_removes_case(storage: Storage) -> None:
    svc = _service(storage)
    case = svc.create(title="t", goal="g")
    svc.delete(case.id)
    with pytest.raises(CaseNotFoundError):
        svc.get(case.id)
