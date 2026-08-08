"""Markdown + YAML frontmatter serialization for memories.

A memory is persisted as a single ``memories/<id>.md`` file whose YAML
frontmatter holds the metadata and whose body holds the free-form content.
Parsing is tolerant to hand edits: missing optional fields fall back to their
pydantic defaults, and the id is derived from the filename when absent.
"""

from __future__ import annotations

import re
from typing import Any

import yaml
from pydantic import ValidationError

from sherlock_second_brain.domain.errors import MemoryValidationError
from sherlock_second_brain.domain.models.memory import Memory
from sherlock_second_brain.domain.text import now_iso

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)

_FIELD_ORDER = ["id", "summary", "source", "tags", "references", "created_at", "updated_at", "promotion"]


def render_memory(memory: Memory) -> str:
    """Render a memory as a frontmatter + body markdown document."""
    data = memory.model_dump(mode="json", exclude={"content"})
    data = {key: data[key] for key in _FIELD_ORDER if key in data and data[key] not in (None, [], {})}
    frontmatter = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{frontmatter}\n---\n\n{memory.content.strip()}\n"


def parse_memory(text: str, id_from_filename: str | None = None) -> Memory:
    """Parse a frontmatter + body markdown document into a ``Memory``.

    ``id_from_filename`` is used as fallback when the frontmatter omits ``id``
    (hand-edited file): ``memories/mem-2026-08-08-001.md`` → ``mem-...``.
    """
    match = _FRONTMATTER_RE.match(text)
    if match:
        raw: dict[str, Any] = yaml.safe_load(match.group(1)) or {}
        content = match.group(2).strip()
    else:
        raw, content = {}, text.strip()

    if not raw.get("id") and id_from_filename:
        raw["id"] = id_from_filename
    if not raw.get("summary") and content:
        raw["summary"] = content.splitlines()[0][:120]
    raw.setdefault("content", content)
    raw.setdefault("created_at", now_iso())
    raw.setdefault("updated_at", now_iso())
    try:
        return Memory.model_validate(raw)
    except ValidationError as exc:
        raise MemoryValidationError(str(exc)) from exc
