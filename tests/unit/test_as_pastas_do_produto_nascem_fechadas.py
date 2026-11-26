"""As pastas do produto nascem fechadas (AS-PASTAS-DO-PRODUTO-NASCEM-FECHADAS-01).

Medido em 25/11/2026 (lar de mentira, umask 022, ``medir_pastas.py`` da leva): as cinco pastas
(config, data, cache, state, runtime) nasciam ``0755`` pelo ``mkdir`` sem modo, e a que já existia
aberta ficava aberta. O ``xdg_paths`` passa a ser o dono do modo: nascem ``0700``, e a aberta fecha
uma vez por processo, com ``ensure`` e na subida do serviço e da janela. As cópias do
``maquina.json`` já passavam pelo escritor atômico (``0600``).

MORDIDAS (25/11/2026, executadas sobre a cura e devolvidas):

- o ``mkdir`` sem ``mode``: ``test_as_cinco_pastas_nascem_0700``;
- sem o ``chmod`` da aberta: ``test_a_pasta_que_ja_existia_aberta_fecha_na_subida``;
- ``escrever_inteiro`` trocado por ``write_bytes`` na cópia recusada:
  ``test_a_copia_do_documento_recusado_sai_0600``.
"""
from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import maquina, xdg_paths
from tests.unit.test_ambiente_do_jogo_01_o_terminal_nao_vai_junto import TestOGanchoDoJogo

_PASTAS = ("config_dir", "data_dir", "cache_dir", "state_dir", "runtime_dir")


def _modo(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    for nome, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"),
                      ("XDG_CACHE_HOME", ".cache"), ("XDG_STATE_HOME", ".local/state"),
                      ("XDG_RUNTIME_DIR", "run")):
        monkeypatch.setenv(nome, str(tmp_path / sub))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(xdg_paths, "_JA_CONFERIDAS", set())
    antigo = os.umask(0o022)
    try:
        yield tmp_path
    finally:
        os.umask(antigo)


def test_as_cinco_pastas_nascem_0700(lar: Path) -> None:
    for nome in _PASTAS:
        pasta = getattr(xdg_paths, nome)(ensure=True)
        assert pasta.is_relative_to(lar)
        assert _modo(pasta) == 0o700, nome


def test_a_pasta_que_ja_existia_aberta_fecha_na_subida(lar: Path) -> None:
    for nome in _PASTAS:
        getattr(xdg_paths, nome)(ensure=True).chmod(0o755)
    pastas = [getattr(xdg_paths, nome)() for nome in _PASTAS]
    assert [_modo(p) for p in pastas] == [0o755] * 5, "pedir o caminho mudou o modo"
    assert [_modo(p) for p in xdg_paths.fechar_as_pastas_do_produto()] == [0o700] * 5
    pastas[3].chmod(0o750)
    xdg_paths._JA_CONFERIDAS.clear()
    assert _modo(xdg_paths.state_dir(ensure=True)) == 0o700


def test_a_subida_do_servico_e_da_janela_fecha_as_pastas() -> None:
    import inspect

    from hefesto_dualsense4unix.mods import supervisor

    assert "fechar_as_pastas_do_produto()" in inspect.getsource(supervisor.Supervisor.iniciar)
    janela = (Path(supervisor.__file__).parents[1] / "interface" / "janela.py").read_text("utf-8")
    assert "fechar_as_pastas_do_produto()" in janela


def test_a_pasta_que_nao_existe_nao_nasce_sem_o_ensure(lar: Path) -> None:
    assert not xdg_paths.state_dir().exists()
    assert not any(p.exists() for p in xdg_paths.fechar_as_pastas_do_produto())


def test_a_copia_do_documento_recusado_sai_0600(lar: Path) -> None:
    alvo = maquina.caminho_da_maquina()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text('{"forma": "x"}', encoding="utf-8")
    maquina._guardar_os_bytes_recusados()
    maquina._guardar_a_copia_de_antes_da_migracao()
    for sufixo in (".invalido", ".com-os-lugares"):
        copia = alvo.with_name(alvo.name + sufixo)
        assert _modo(copia) == 0o600, sufixo


def test_o_lancador_escreve_no_launch_env_com_a_pasta_fechada(lar: Path) -> None:
    estado = lar / "state" / "hefesto-dualsense4unix"
    estado.mkdir(parents=True, mode=0o700)
    jogo, _ = TestOGanchoDoJogo()._roda(lar, "env")
    assert jogo["SteamAppId"] == "9931993"
    assert _modo(estado) == 0o700
    ultimo = (estado / "launch_env" / "last_run").read_text(encoding="utf-8")
    assert "appid=9931993" in ultimo
    assert (estado / "launch_env" / "fonte_do_ambiente").exists()
    assert subprocess.run(["test", "-r", str(estado / "launch_env" / "last_run")],
                          check=False).returncode == 0
