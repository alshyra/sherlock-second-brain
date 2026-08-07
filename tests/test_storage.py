"""Tests for case storage CRUD, schema validation and atomicity."""

from __future__ import annotations

import json

import jsonschema
import pytest

from second_brain.adapters.filesystem import SCHEMA_PATH, Storage
from second_brain.domain.errors import CaseNotFoundError, CaseValidationError
from second_brain.domain.text import slugify


def test_create_case_minimal(storage: Storage) -> None:
    case = storage.create_case(title="Debug Traefik", goal="Comprendre l'échec du renouvellement")
    assert case.id.startswith("case-")
    assert case.status == "open"
    assert case.tags == []
    assert case.created_at == case.updated_at


def test_case_id_increments_per_day(storage: Storage) -> None:
    c1 = storage.create_case(title="a", goal="g")
    c2 = storage.create_case(title="b", goal="g")
    assert c1.id.endswith("001")
    assert c2.id.endswith("002")
    assert c1.id != c2.id


def test_schema_validation_rejects_invalid(storage: Storage) -> None:
    with pytest.raises(CaseValidationError):
        storage.create_case(title="   ", goal="g")


def test_written_case_matches_json_schema(storage: Storage) -> None:
    case = storage.create_case(title="Plan migration", goal="Migrer vers S3", tags=["s3"])
    storage.add_evidence(case.id, "log line 1", "preuve de la cause")
    updated = storage.get_case(case.id)
    updated.findings.append("cause identifiée")
    storage.update_case(updated)

    schema = json.loads(SCHEMA_PATH.read_text())
    raw = json.loads(storage.case_abs_path(case.id).read_text())
    jsonschema.validate(raw, schema)


def test_get_missing_raises(storage: Storage) -> None:
    with pytest.raises(CaseNotFoundError):
        storage.get_case("case-2020-01-01-999")


def test_update_requires_existing(storage: Storage) -> None:
    from second_brain.domain.models.case import Case

    now = "2026-08-07T00:00:00"
    bogus = Case(id="case-2026-08-07-999", title="t", status="open", goal="g", context="", created_at=now, updated_at=now)
    with pytest.raises(CaseNotFoundError):
        storage.update_case(bogus)


def test_list_cases_filters(storage: Storage) -> None:
    a = storage.create_case(title="a", goal="g", tags=["traefik"])
    b = storage.create_case(title="b", goal="g", tags=["nas"])
    resolved = storage.get_case(b.id)
    resolved.status = "resolved"
    storage.update_case(resolved)

    all_cases = storage.list_cases()
    assert {c.id for c in all_cases} == {a.id, b.id}
    assert [c.id for c in storage.list_cases(status="resolved")] == [b.id]
    assert [c.id for c in storage.list_cases(tag="traefik")] == [a.id]


def test_delete_case(storage: Storage) -> None:
    case = storage.create_case(title="a", goal="g")
    storage.delete_case(case.id)
    with pytest.raises(CaseNotFoundError):
        storage.get_case(case.id)


def test_delete_case_rejects_malformed_id(storage: Storage) -> None:
    with pytest.raises(CaseNotFoundError):
        storage.delete_case("../etc")


def test_evidence_persists_to_disk(storage: Storage) -> None:
    case = storage.create_case(title="a", goal="g")
    updated = storage.add_evidence(case.id, "ERROR 500", "erreur serveur", filename="err.log")
    assert len(updated.evidence) == 1
    ev_file = storage.cases_dir / case.id / "evidence" / "err.log"
    assert ev_file.read_text() == "ERROR 500"
    assert updated.evidence[0].path == "evidence/err.log"


def test_evidence_filename_ignores_parent_dirs(storage: Storage) -> None:
    case = storage.create_case(title="a", goal="g")
    updated = storage.add_evidence(case.id, "x", "résumé", filename="../../evil.txt")
    assert updated.evidence[0].path == "evidence/evil.txt"
    assert not (storage.root / "evil.txt").exists()
    assert (storage.cases_dir / case.id / "evidence" / "evil.txt").exists()


def test_slugify() -> None:
    assert slugify("Hello World!") == "hello-world"
    assert slugify("  TRÈS  Long   ") == "très-long"
    assert slugify("...") != ""
