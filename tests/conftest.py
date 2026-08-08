"""Shared pytest fixtures for sherlock-second-brain tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sherlock_second_brain.adapters.filesystem import Storage


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path / "data")
