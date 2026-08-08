"""Shared pytest fixtures for second-brain tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.adapters.filesystem import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "data")
