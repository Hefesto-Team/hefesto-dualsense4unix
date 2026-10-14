"""O ``XDG_RUNTIME_DIR`` declarado é o runtime do produto, qualquer que seja o platformdirs.

Origem: D-1310-O-RUNTIME-DECLARADO-VENCE-O-PLATFORMDIRS. Do 4.12 em diante o
platformdirs troca a pasta que não é 0700 pela ``/run/user/<uid>``; o resto do
produto lê a variável direto, e o socket do IPC ia parar noutro lugar.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import xdg_paths


class _PlatformdirsQueTroca:
    """O platformdirs 4.12 diante de uma pasta 0755: responde a pasta padrão."""

    appname = xdg_paths._DIRS.appname
    user_runtime_dir = "/run/user/4242/hefesto-dualsense4unix"
    user_cache_dir = "/nao/usado"


@pytest.fixture
def platformdirs_que_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xdg_paths, "_DIRS", _PlatformdirsQueTroca())


@pytest.mark.parametrize("modo", [0o700, 0o755, 0o500])
def test_a_pasta_declarada_vale_em_qualquer_modo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platformdirs_que_troca: None, modo: int
) -> None:
    """A pasta declarada vence o platformdirs: D-1310-O-RUNTIME-DECLARADO-VENCE-O-PLATFORMDIRS."""
    pasta = tmp_path / "run"
    pasta.mkdir()
    pasta.chmod(modo)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(pasta))
    try:
        assert xdg_paths.runtime_dir() == pasta / xdg_paths._DIRS.appname
    finally:
        pasta.chmod(0o700)


def test_sem_a_variavel_quem_responde_e_o_platformdirs(
    monkeypatch: pytest.MonkeyPatch, platformdirs_que_troca: None
) -> None:
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert xdg_paths.runtime_dir() == Path(_PlatformdirsQueTroca.user_runtime_dir)


def test_caminho_relativo_nao_e_declaracao(
    monkeypatch: pytest.MonkeyPatch, platformdirs_que_troca: None
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", "run/relativo")
    assert xdg_paths.runtime_dir() == Path(_PlatformdirsQueTroca.user_runtime_dir)
