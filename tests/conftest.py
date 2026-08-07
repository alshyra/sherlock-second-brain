"""Shared pytest fixtures for second-brain tests."""

from __future__ import annotations

import pytest

from second_brain.storage import Storage


@pytest.fixture
def storage(tmp_path) -> Storage:
    return Storage(tmp_path / "data")
