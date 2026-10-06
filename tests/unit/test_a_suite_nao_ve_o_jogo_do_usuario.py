"""A suíte não vê o jogo aberto de quem a roda (JOGO-SO-DA-SESSAO, 01/10/2026)."""
from __future__ import annotations

import io
import os
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.testing import FakeController

PID_DE_FORA = "9999999"

REAPER = b"/home/x/.steam/steam/ubuntu12_32/reaper\0SteamLaunch\0AppId=1599660\0--\0jogo.exe\0"


@pytest.fixture
def proc_com_o_jogo(monkeypatch: pytest.MonkeyPatch) -> Iterator[set[str]]:
    """O `/proc` de quem roda a suíte com um jogo da Steam aberto."""
    reapers = {PID_DE_FORA}
    listdir = os.listdir

    def _listdir(caminho: Any = ".") -> list[str]:
        nomes = listdir(caminho)
        if str(caminho) == "/proc" and PID_DE_FORA not in nomes:
            return [*nomes, PID_DE_FORA]
        return nomes

    def _open(caminho: Any, *args: Any, **kwargs: Any) -> Any:
        partes = str(caminho).split("/")
        e_cmdline = len(partes) == 4 and partes[1] == "proc" and partes[3] == "cmdline"
        if e_cmdline and partes[2] in reapers:
            return io.BytesIO(REAPER)
        return open(caminho, *args, **kwargs)

    monkeypatch.setattr(os, "listdir", _listdir)
    monkeypatch.setattr(slo, "open", _open, raising=False)
    slo.invalidar_varredura_de_proc()
    yield reapers
    slo.invalidar_varredura_de_proc()


def test_o_embrulho_esta_no_leitor_do_dono() -> None:
    """O produto lê a cmdline pelo embrulho da sessão, e não pelo leitor cru."""
    assert getattr(slo._cmdline_of, "_so_da_sessao", False), (
        "JOGO-SO-DA-SESSAO: o `_cmdline_of` do steam_launch_options é o leitor "
        "cru; a suíte veria o jogo aberto de quem a roda"
    )


def test_o_jogo_de_fora_nao_chega_a_pergunta(proc_com_o_jogo: set[str]) -> None:
    """Com o jogo do usuário aberto, «há jogo da Steam?» responde não, nas duas perguntas."""
    assert slo.cmdline_de_pid(PID_DE_FORA).startswith("/home/x/.steam"), (
        "o /proc de mentira não serve o reaper: a régua não mediria nada"
    )
    assert slo.steam_game_running() is False
    slo.invalidar_varredura_de_proc()
    assert slo.steam_game_running_appid() is None


def test_o_jogo_que_a_sessao_nasceu_continua_visto(proc_com_o_jogo: set[str]) -> None:
    """O processo que um teste nasce não some: o embrulho não é mais frouxo que o produto."""
    filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        proc_com_o_jogo.add(str(filho.pid))
        assert slo.steam_game_running_appid() == 1599660
    finally:
        filho.kill()
        filho.wait(timeout=10)


def test_a_cmdline_que_nao_e_jogo_passa_intacta() -> None:
    """Só a cmdline do reaper é filtrada; o resto do `/proc` chega igual."""
    for pid in (1, os.getpid(), os.getppid()):
        assert slo._cmdline_of(pid) == slo.cmdline_de_pid(pid)


class _AuthorityController(FakeController):
    """FakeController com os pontos de contato do sinal de jogo."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.provider: Any = None
        self.defend_calls = 0

    def set_game_authority_provider(self, fn: Any) -> None:
        self.provider = fn

    def defend_display(self) -> None:
        self.defend_calls += 1

    def replay_retained_game_outputs(self) -> None:
        pass


async def test_o_sinal_de_jogo_nao_le_o_jogo_dela(proc_com_o_jogo: set[str]) -> None:
    """O caso medido: sem evidência e com o detector são, a autoridade é `daemon`."""
    ctrl = _AuthorityController(transport="usb")
    daemon = Daemon(
        controller=ctrl, config=DaemonConfig(ipc_enabled=False, udp_enabled=False)
    )
    daemon._executor = ThreadPoolExecutor(max_workers=1)
    try:
        daemon._wire_game_signal()
        daemon.store.set_window_detect_backend("xlib", healthy=True)
        await daemon._sync_game_signal()
    finally:
        daemon._executor.shutdown(wait=True)
    assert daemon.display_authority == "daemon"
    assert ctrl.defend_calls == 1
