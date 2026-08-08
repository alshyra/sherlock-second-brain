"""Tests for the filesystem adapter: persistence primitives, schema, safety."""

from __future__ import annotations

import json

import jsonschema
import pytest

from sherlock_second_brain.adapters.filesystem import SCHEMA_PATH, Storage
from sherlock_second_brain.domain.errors import CaseNotFoundError, CaseValidationError
from sherlock_second_brain.domain.models.case import Case
from sherlock_second_brain.domain.text import slugify


def _new_case(storage: Storage) -> Case:
    return Case.create_case(
        storage.next_case_id(),
        title="Debug Traefik",
        goal="Understand the renewal failure",
    )


def test_save_case_persists_round_trip(storage: Storage) -> None:
    case = _new_case(storage)
    storage.save_case(case)
    loaded = storage.get_case(case.id)
    assert loaded.model_dump() == case.model_dump()


def test_case_id_increments_per_day(storage: Storage) -> None:
    first = _new_case(storage)
    storage.save_case(first)
    second = _new_case(storage)
    storage.save_case(second)
    assert first.id.endswith("001")
    assert second.id.endswith("002")


def test_save_case_rejects_schema_violation(storage: Storage) -> None:
    case = Case(
        id=storage.next_case_id(),
        title="",
        status="open",
        goal="g",
        context="",
        created_at="2026-08-08T00:00:00",
        updated_at="2026-08-08T00:00:00",
    )
    with pytest.raises(CaseValidationError):
        storage.save_case(case)


def test_written_case_matches_json_schema(storage: Storage) -> None:
    case = Case.create_case(
        storage.next_case_id(), title="Plan migration", goal="Migrer vers S3", tags=["s3"]
    )
    storage.save_case(case)
    rel = storage.write_evidence(case.id, "proof.log", "log line 1")
    case.add_evidence("proof of cause", rel)
    case.add_finding("cause identified")
    storage.save_case(case)

    schema = json.loads(SCHEMA_PATH.read_text())
    raw = json.loads(storage.case_abs_path(case.id).read_text())
    jsonschema.validate(raw, schema)


def test_get_missing_raises(storage: Storage) -> None:
    with pytest.raises(CaseNotFoundError):
        storage.get_case("case-2020-01-01-999")


def test_list_cases_is_raw(storage: Storage) -> None:
    a = _new_case(storage)
    b = _new_case(storage)
    storage.save_case(a)
    storage.save_case(b)
    assert {c.id for c in storage.list_cases()} == {a.id, b.id}


def test_delete_case(storage: Storage) -> None:
    case = _new_case(storage)
    storage.save_case(case)
    storage.delete_case(case.id)
    with pytest.raises(CaseNotFoundError):
        storage.get_case(case.id)


def test_delete_case_rejects_malformed_id(storage: Storage) -> None:
    with pytest.raises(CaseNotFoundError):
        storage.delete_case("../etc")


def test_write_evidence_persists_file(storage: Storage) -> None:
    case = _new_case(storage)
    storage.save_case(case)
    rel = storage.write_evidence(case.id, "err.log", "ERROR 500")
    assert rel == "evidence/err.log"
    assert (storage.cases_dir / case.id / "evidence" / "err.log").read_text() == "ERROR 500"


def test_write_evidence_ignores_parent_dirs(storage: Storage) -> None:
    case = _new_case(storage)
    storage.save_case(case)
    rel = storage.write_evidence(case.id, "../../evil.txt", "x")
    assert rel == "evidence/evil.txt"
    assert not (storage.root / "evil.txt").exists()
    assert (storage.cases_dir / case.id / "evidence" / "evil.txt").exists()


def test_slugify() -> None:
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  TRÈS  Long   ") == "très-long"
    assert slugify("...") != ""
