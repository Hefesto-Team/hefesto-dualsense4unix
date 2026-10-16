"""A régua do recado da chave, da pasta ilegível e do IPC que não abre.

A-CHAVE-E-A-PERMISSAO-DIZEM-O-QUE-SAO-01: o recado manda o comando que o
script aceita; a pasta sem permissão não vira «desligado de propósito»; e o
daemon sem socket não fica no ar fingindo que serve.
"""
from __future__ import annotations

import asyncio
import os
import re
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import main as daemon_main
from hefesto_dualsense4unix.daemon.lifecycle import (
    Daemon,
    DaemonConfig,
    IpcIndisponivel,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import chave

RAIZ = Path(__file__).resolve().parents[2]

so_sem_root = pytest.mark.skipif(
    os.geteuid() == 0,
    reason="como root o chmod 000 não nega nada, então a régua não morde",
)


def _argumentos_do_case(script: str) -> set[str]:
    """Os primeiros argumentos que o `case` do `hefesto-chave.sh` aceita."""
    bloco = script[script.index('case "${1:-}" in'):]
    bloco = bloco[: bloco.index("esac")]
    aceitos: set[str] = set()
    for linha in bloco.splitlines()[1:]:
        braco = re.match(r"\s*([A-Za-z|\-\"]+)\)", linha)
        if braco:
            aceitos.update(p.strip('"') for p in braco.group(1).split("|"))
    return aceitos


def test_o_recado_manda_o_comando_que_o_script_aceita() -> None:
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    recado = chave.recado_da_recusa("desligado em 2026-10-09")
    comando = recado.rsplit("Para religar:", 1)[1].split()
    assert comando[0] == "hefesto-chave"
    assert comando[1] in _argumentos_do_case(script), comando


def test_a_regua_do_case_morde_o_comando_que_nao_existe() -> None:
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    assert "estavel" not in _argumentos_do_case(script)
    assert {"on", "off", "estado"} <= _argumentos_do_case(script)


@pytest.fixture
def pasta_sem_leitura(tmp_path: Path) -> Iterator[Path]:
    pasta = tmp_path / "config-fechada"
    pasta.mkdir()
    pasta.chmod(0)
    yield pasta
    pasta.chmod(stat.S_IRWXU)


@so_sem_root
def test_a_pasta_ilegivel_nao_vira_desligado_de_proposito(pasta_sem_leitura: Path) -> None:
    with pytest.raises(chave.PastaIlegivel) as achado:
        chave.motivo_do_desligamento(pasta_sem_leitura)
    assert achado.value.pasta == pasta_sem_leitura
    assert str(pasta_sem_leitura) in str(achado.value)


def _roda_o_main(monkeypatch: pytest.MonkeyPatch) -> int:
    from hefesto_dualsense4unix.daemon.subsystems import vigia_do_laco
    from hefesto_dualsense4unix.utils import migrate_legacy_paths, single_instance

    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_NICE", "0")
    monkeypatch.setattr(migrate_legacy_paths, "migrate_legacy_paths", lambda: None)
    monkeypatch.setattr(single_instance, "acquire_or_takeover", lambda nome: None)
    monkeypatch.setattr(daemon_main, "build_controller", lambda: FakeController())

    async def com_prazo(coro: Any) -> None:
        # Um daemon que ficasse no ar sem o IPC prenderia a régua para sempre.
        await asyncio.wait_for(coro, timeout=5.0)

    monkeypatch.setattr(vigia_do_laco, "vigiado", com_prazo)
    return daemon_main.run_daemon()


@so_sem_root
def test_o_main_sai_com_1_e_a_frase_de_permissao(
    monkeypatch: pytest.MonkeyPatch, pasta_sem_leitura: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: pasta_sem_leitura)
    assert _roda_o_main(monkeypatch) == 1
    erro = capsys.readouterr().err
    assert f"ls -ld {pasta_sem_leitura}" in erro
    assert "permissão" in erro
    assert "desligado pela chave" not in erro


def test_a_chave_de_verdade_continua_com_rc_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = chave.caminho_da_chave(tmp_path)
    alvo.write_text("desligado em 2026-10-09 por hefesto-chave\n", encoding="utf-8")
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: tmp_path)
    assert _roda_o_main(monkeypatch) == 0
    assert "Para religar:  hefesto-chave on" in capsys.readouterr().err


@pytest.fixture
def runtime_sem_escrita(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    pasta = tmp_path / "run"
    pasta.mkdir()
    pasta.chmod(stat.S_IRUSR | stat.S_IXUSR)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(pasta))
    yield pasta
    pasta.chmod(stat.S_IRWXU)


def _daemon_de_teste() -> Daemon:
    return Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(
            poll_hz=60, ipc_enabled=True,
            udp_enabled=False, autoswitch_enabled=False,
        ),
    )


@so_sem_root
@pytest.mark.asyncio
async def test_o_ipc_que_nao_abre_derruba_o_run(runtime_sem_escrita: Path) -> None:
    daemon = _daemon_de_teste()
    tarefa = asyncio.create_task(daemon.run())
    try:
        with pytest.raises(IpcIndisponivel) as achado:
            await asyncio.wait_for(asyncio.shield(tarefa), timeout=5.0)
    except TimeoutError:
        daemon.stop()
        await tarefa
        pytest.fail("o daemon ficou no ar sem o socket do IPC")
    assert str(runtime_sem_escrita) in str(achado.value.caminho)
    assert "ls -ld" in achado.value.recado()


@so_sem_root
def test_o_main_sai_com_1_quando_o_ipc_nao_abre(
    monkeypatch: pytest.MonkeyPatch, runtime_sem_escrita: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from hefesto_dualsense4unix.utils import chave as _chave

    monkeypatch.setattr(_chave, "motivo_do_desligamento", lambda: None)
    assert _roda_o_main(monkeypatch) == 1
    erro = capsys.readouterr().err
    assert "ls -ld" in erro
    assert str(runtime_sem_escrita) in erro


def test_o_socket_ocupado_nao_manda_conferir_permissao(tmp_path: Path) -> None:
    sock = tmp_path / "run" / "hefesto.sock"
    ocupado = IpcIndisponivel(sock, RuntimeError(f"socket ocupado por outro daemon em {sock}"))
    assert f"ls -l {sock}" in ocupado.recado()
    assert "ls -ld" not in ocupado.recado()
    negado = IpcIndisponivel(sock, PermissionError(13, "Permission denied"))
    assert f"ls -ld {sock.parent}" in negado.recado()
