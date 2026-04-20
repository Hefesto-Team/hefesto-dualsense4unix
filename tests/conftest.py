"""Fixtures compartilhadas entre testes unit e integration."""

import pytest


@pytest.fixture(scope="session")
def repo_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[1]
