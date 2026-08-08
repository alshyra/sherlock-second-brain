"""Tests for memory persistence: frontmatter round-trip, id safety."""

from __future__ import annotations

import pytest

from sherlock_second_brain.adapters.filesystem import Storage
from sherlock_second_brain.adapters.frontmatter import parse_memory, render_memory
from sherlock_second_brain.domain.errors import MemoryNotFoundError, MemoryValidationError
from sherlock_second_brain.domain.models.memory import Memory


def _new_memory(storage: Storage, *, tags: list[str] | None = None) -> Memory:
    return Memory.create_memory(storage.next_memory_id(), summary="s", content="c", tags=tags)


def test_save_memory_persists_round_trip(storage: Storage) -> None:
    memory = Memory.create_memory(
        storage.next_memory_id(),
        summary="Le NAS tourne sur Fedora 44",
        content="Serveur Fedora 44.",
        tags=["nas"],
        references=["https://fedoraproject.org"],
        source="slack",
    )
    storage.save_memory(memory)
    loaded = storage.get_memory(memory.id)
    assert loaded.model_dump() == memory.model_dump()


def test_memory_id_increments_per_day(storage: Storage) -> None:
    first = _new_memory(storage)
    storage.save_memory(first)
    second = _new_memory(storage)
    storage.save_memory(second)
    assert first.id.endswith("001")
    assert second.id.endswith("002")


def test_frontmatter_round_trip_keeps_accents(storage: Storage) -> None:
    memory = Memory.create_memory(
        storage.next_memory_id(),
        summary="Très long record TXT",
        content="Échec DNS-01 car le record est trop long.",
        tags=["traefik", "ssl"],
        references=["https://example.com/docs"],
        source="slack",
    )
    storage.save_memory(memory)
    raw = (storage.memories_dir / f"{memory.id}.md").read_text(encoding="utf-8")
    assert "Très long record TXT" in raw
    assert "Échec DNS-01" in raw

    parsed = storage.get_memory(memory.id)
    assert parsed.summary == "Très long record TXT"
    assert parsed.content == "Échec DNS-01 car le record est trop long."
    assert parsed.tags == ["traefik", "ssl"]
    assert parsed.source == "slack"


def test_save_memory_updates_content(storage: Storage) -> None:
    memory = _new_memory(storage)
    storage.save_memory(memory)
    memory.set_content("nouveau contenu")
    storage.save_memory(memory)
    assert storage.get_memory(memory.id).content == "nouveau contenu"


def test_list_memories_is_raw(storage: Storage) -> None:
    a = _new_memory(storage, tags=["nas"])
    b = _new_memory(storage, tags=["traefik"])
    storage.save_memory(a)
    storage.save_memory(b)
    assert {m.id for m in storage.list_memories()} == {a.id, b.id}


def test_delete_memory(storage: Storage) -> None:
    memory = _new_memory(storage)
    storage.save_memory(memory)
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
