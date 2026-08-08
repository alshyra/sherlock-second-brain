"""Domain utilities: identifiers, slugs, time."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

CASE_ID_PATTERN = r"^case-\d{4}-\d{2}-\d{2}-\d{3}$"
MEMORY_ID_PATTERN = r"^mem-\d{4}-\d{2}-\d{2}-\d{3}$"


def now_iso() -> str:
    """Current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    """Turn arbitrary text into a safe lowercase slug (keeps accents)."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9àâçéèêëîïôûùüÿœæ'-]+", "-", text)
    text = text.strip("-")
    return text or uuid.uuid4().hex[:8]
