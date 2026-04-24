"""Fixtures compartilhadas entre testes unit e integration."""

import os

import pytest


@pytest.fixture(scope="session")
def repo_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _hefesto_fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ativa HEFESTO_FAKE=1 em todo teste.

    Garantia defensiva: subsystems que fazem probing de hardware real
    (TouchpadReader enumerando evdev, ex.) devem pular a inicialização
    quando o flag está presente — caso contrário testes em ambiente dev
    com DualSense conectado sofrem latência extra (>60ms) que empurra
    janelas de teste curtas para fora do budget. FakeController já é
    o padrão nas suítes; o env var apenas torna esse contrato explícito
    para outros módulos consumirem.
    """
    if not os.environ.get("HEFESTO_FAKE"):
        monkeypatch.setenv("HEFESTO_FAKE", "1")
