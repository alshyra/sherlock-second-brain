"""Tests for memory storage: CRUD, frontmatter round-trip, id safety."""

from __future__ import annotations

import pytest

from sherlock_second_brain.adapters.filesystem import Storage
from sherlock_second_brain.adapters.frontmatter import parse_memory, render_memory
from sherlock_second_brain.domain.errors import MemoryNotFoundError, MemoryValidationError
from sherlock_second_brain.domain.models.memory import Memory


def test_create_memory_minimal(storage: Storage) -> None:
    memory = storage.create_memory(summary="Le NAS tourne sur Fedora 44", content="Serveur Fedora 44.")
    assert memory.id.startswith("mem-")
    assert memory.tags == []
    assert memory.source is None
    assert memory.created_at == memory.updated_at
    assert (storage.memories_dir / f"{memory.id}.md").exists()


def test_memory_id_increments_per_day(storage: Storage) -> None:
    m1 = storage.create_memory(summary="a", content="x")
    m2 = storage.create_memory(summary="b", content="y")
    assert m1.id.endswith("001")
    assert m2.id.endswith("002")
    assert m1.id != m2.id


def test_memory_requires_summary(storage: Storage) -> None:
    with pytest.raises(MemoryValidationError):
        storage.create_memory(summary="   ", content="x")


def test_frontmatter_round_trip_keeps_accents(storage: Storage) -> None:
    memory = storage.create_memory(
        summary="Très long record TXT",
        content="Échec DNS-01 car le record est trop long.",
        tags=["traefik", "ssl"],
        references=["https://example.com/docs"],
        source="slack",
    )
    raw = (storage.memories_dir / f"{memory.id}.md").read_text(encoding="utf-8")
    assert "Très long record TXT" in raw
    assert "Échec DNS-01" in raw

    parsed = storage.get_memory(memory.id)
    assert parsed.id == memory.id
    assert parsed.summary == "Très long record TXT"
    assert parsed.content == "Échec DNS-01 car le record est trop long."
    assert parsed.tags == ["traefik", "ssl"]
    assert parsed.references == ["https://example.com/docs"]
    assert parsed.source == "slack"
    assert parsed.created_at == memory.created_at


def test_update_memory_touches_timestamp(storage: Storage) -> None:
    memory = storage.create_memory(summary="s", content="c")
    memory.content = "nouveau contenu"
    updated = storage.update_memory(memory)
    assert updated.content == "nouveau contenu"
    assert updated.updated_at >= updated.created_at


def test_list_memories_filters_by_tag(storage: Storage) -> None:
    a = storage.create_memory(summary="a", content="x", tags=["nas"])
    storage.create_memory(summary="b", content="y", tags=["traefik"])
    assert {m.id for m in storage.list_memories()} == {
        a.id,
        storage.list_memories()[1].id,
    }
    assert [m.id for m in storage.list_memories(tag="nas")] == [a.id]


def test_delete_memory(storage: Storage) -> None:
    memory = storage.create_memory(summary="a", content="x")
    storage.delete_memory(memory.id)
    with pytest.raises(MemoryNotFoundError):
        storage.get_memory(memory.id)


def test_get_missing_raises(storage: Storage) -> None:
    with pytest.raises(MemoryNotFoundError):
        storage.get_memory("mem-2020-01-01-999")


def test_delete_rejects_malformed_id(storage: Storage) -> None:
    with pytest.raises(MemoryNotFoundError):
        storage.delete_memory("../etc")


def test_parse_memory_tolerates_hand_edited_file(storage: Storage) -> None:
    path = storage.memories_dir / "mem-2026-08-08-042.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Note éditée à la main\n\nDu contenu sans frontmatter ni id.\n",
        encoding="utf-8",
    )
    memory = storage.get_memory("mem-2026-08-08-042")
    assert memory.id == "mem-2026-08-08-042"
    assert memory.summary == "# Note éditée à la main"
    assert "Du contenu sans frontmatter" in memory.content


def test_parse_memory_rejects_invalid(storage: Storage) -> None:
    path = storage.memories_dir / "mem-2026-08-08-043.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nid: mem-2026-08-08-043\ntags: pas-une-liste\n---\n\ncorps\n",
        encoding="utf-8",
    )
    with pytest.raises(MemoryValidationError):
        storage.get_memory("mem-2026-08-08-043")


def test_render_parse_round_trip() -> None:
    memory = Memory(
        id="mem-2026-08-08-001",
        summary="Résumé accentué : très long",
        content="Corps de la note avec des accents é è à ç.",
        tags=["ssl"],
        references=["https://example.com"],
        source="slack",
        created_at="2026-08-08T09:00:00",
        updated_at="2026-08-08T09:00:00",
    )
    parsed = parse_memory(render_memory(memory))
    assert parsed.model_dump() == memory.model_dump()
