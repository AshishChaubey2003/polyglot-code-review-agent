"""Shared pytest fixtures: loads the .py snippets under tests/fixtures/."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str) -> str:
        return (FIXTURES_DIR / name).read_text()

    return _load
