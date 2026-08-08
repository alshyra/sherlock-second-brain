"""Tests du DTO d'entrée de ``case_update``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sherlock_second_brain.adapters.dto.case_update import CaseUpdateFields


def test_empty_fields_default() -> None:
    fields = CaseUpdateFields()
    assert fields.model_dump() == {
        "finding": None,
        "step_action": None,
        "step_result": None,
        "conclusion": None,
        "hypothesis_statement": None,
        "hypothesis_test": None,
        "hypothesis_result": None,
        "tags": None,
        "references": None,
    }


def test_rejects_invalid_hypothesis_result() -> None:
    with pytest.raises(ValidationError):
        CaseUpdateFields(hypothesis_result="peut-etre")


def test_accepts_valid_hypothesis_result() -> None:
    fields = CaseUpdateFields(hypothesis_result="confirmed")
    assert fields.hypothesis_result == "confirmed"
