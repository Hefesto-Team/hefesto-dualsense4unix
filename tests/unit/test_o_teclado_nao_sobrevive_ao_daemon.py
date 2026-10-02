#!/usr/bin/env python3
"""A RÉGUA DO TECLADO ÓRFÃO — quem fecha o que o daemon abriu."""
from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import (
    TOKEN_CLOSE_OSK,
    TOKEN_TOGGLE_OSK,
)
from hefesto_dualsense4unix.daemon.subsystems import keyboard as subsistema
from hefesto_dualsense4unix.daemon.subsystems.keyboard import _OSKController

_DUBLE = "sleep"
_DUBLE_ARGV = [_DUBLE, "600"]


def _vivo(pid: int) -> bool:
    """O PID existe E ainda roda? Pergunta ao kernel, não a um atributo Python."""
    if not Path(f"/proc/{pid}").exists():
        return False
    return not subsistema._pid_e_zumbi(pid)


def _comm_real(pid: int) -> str | None:
    """O `/proc/<pid>/comm` lido pela régua, sem passar pelo produto."""
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _esperar_morrer(pid: int, *, segundos: float = 5.0) -> bool:
    """O `SIGTERM` é assíncrono: espera o kernel derrubar o processo."""
    limite = time.monotonic() + segundos
    while True:
        with contextlib.suppress(ChildProcessError, OSError):
            os.waitpid(pid, os.WNOHANG)
        if not _vivo(pid):
            return True
        if time.monotonic() >= limite:
            return False
        time.sleep(0.02)


@pytest.fixture
def mesa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[dict[str, Any]]:
    """Um teclado na tela dublado por `sleep`, e um `XDG_RUNTIME_DIR` só desta régua."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(subsistema, "_OSK_CANDIDATES", (_DUBLE,))
    monkeypatch.setattr(subsistema, "_osk_candidatos", lambda: (_DUBLE,))
    monkeypatch.setattr(subsistema, "_OSK_SPAWN_ARGS", {_DUBLE: list(_DUBLE_ARGV)})
    monkeypatch.setattr(
        subsistema.shutil,
        "which",
        lambda nome: f"/usr/bin/{nome}" if nome == _DUBLE else None,
    )
    monkeypatch.setattr(subsistema, "_OSK_SONDA", [(float("-inf"), False)])

    nascidos: list[int] = []
    popen_real = subprocess.Popen

    def _popen(argv: list[str], **kw: Any) -> Any:
        proc = popen_real(argv, **kw)
        nascidos.append(proc.pid)
        return proc

    monkeypatch.setattr(subsistema.subprocess, "Popen", _popen)

    estado = {"nascidos": nascidos, "runtime": tmp_path}
    try:
        yield estado
    finally:
        for pid in nascidos:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)
        for pid in nascidos:
            with contextlib.suppress(ChildProcessError, OSError):
                os.waitpid(pid, 0)


def _arquivo_de_sessao(_runtime: Path) -> Path:
    """O caminho do arquivo de sessão, PERGUNTADO ao produto."""
    return subsistema._sessao_do_teclado()


@pytest.mark.asyncio
async def test_o_shutdown_do_daemon_fecha_o_teclado_na_tela(
    mesa: dict[str, Any],
) -> None:
    """O daemon PARA e o teclado morre junto."""
    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.connection import shutdown
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    ctrl = _OSKController()
    ctrl.open()
    pid = mesa["nascidos"][0]
    assert _vivo(pid), "o dublê do teclado na tela não chegou a nascer"

    daemon = Daemon(
        controller=FakeController(
            transport="usb",
            states=[ControllerState(battery_pct=80, l2_raw=0, r2_raw=0,
                                    connected=True, transport="usb")],
        ),
        bus=EventBus(),
        config=DaemonConfig(
            auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False, plugins_enabled=False,
        ),
    )
    daemon._osk_controller = ctrl

    await shutdown(daemon)

    assert _esperar_morrer(pid), (
        f"o teclado na tela (pid={pid}) SOBREVIVEU ao shutdown do daemon — é o "
        "defeito (1) da sprint: o `shutdown` fecha o `_keyboard_device` e passa "
        "direto pelo `_osk_controller`, e a janela fica na tela dela sem dono")
    assert getattr(daemon, "_osk_controller", None) is None, (
        "o shutdown fechou o teclado mas deixou o controlador pendurado no "
        "daemon — o slot tem de zerar como o dos outros subsystems")


def test_o_daemon_novo_adota_o_orfao_e_o_r3_fecha(mesa: dict[str, Any]) -> None:
    """Ela aperta R3 depois de o daemon reiniciar — e o teclado FECHA."""
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]
    assert _vivo(pid)

    novo = _OSKController()
    assert novo._process is None, "o controlador novo tem de nascer sem processo"
    assert novo.aberto() is True, (
        "o daemon novo respondeu 'fechado' com o teclado na tela dela — é dessa "
        "mentira que nascem o R3 que não fecha e o L3 que empilha")

    novo.dispatch_token(TOKEN_CLOSE_OSK, "press")
    assert novo.esperar_os_toques(5.0)

    assert _esperar_morrer(pid), (
        f"o R3 do daemon novo não fechou o teclado órfão (pid={pid}) — defeito "
        "(2) da sprint: `close()` voltava na primeira linha porque "
        "`self._process is None` num controlador recém-criado")
    assert novo.aberto() is False
    assert not _arquivo_de_sessao(mesa["runtime"]).exists(), (
        "o teclado morreu mas o arquivo de sessão ficou apontando para ele — o "
        "PID seguinte que o kernel reciclar herdaria essa anotação")


def test_o_l3_do_daemon_novo_nao_empilha_um_segundo_teclado(
    mesa: dict[str, Any],
) -> None:
    """Um teclado na tela, um só — mesmo com o daemon trocado no meio."""
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]

    novo = _OSKController()
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert novo.esperar_os_toques(5.0)

    assert len(mesa["nascidos"]) == 1, (
        "o L3 do daemon novo ABRIU UM SEGUNDO teclado por cima do primeiro — "
        f"pids {mesa['nascidos']!r}. É o defeito (3) da sprint, e a docstring do "
        "controlador já prometia o contrário ('evita stack de janelas "
        "sobrepostas'): a promessa valia dentro de um daemon só")
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert novo.esperar_os_toques(5.0)
    assert _esperar_morrer(pid), (
        "o segundo toque do L3 no daemon novo não fechou o teclado adotado")


def test_pid_que_ja_morreu_nao_e_adotado_e_o_l3_abre_normal(
    mesa: dict[str, Any],
) -> None:
    """Arquivo apontando para um defunto: nada é adotado, nada estoura."""
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    assert _esperar_morrer(pid)
    assert _arquivo_de_sessao(mesa["runtime"]).exists(), (
        "o arranjo deste caso exige o arquivo de sessão ainda apontando para o "
        "PID morto")

    novo = _OSKController()
    assert novo.aberto() is False, (
        "adotou um PID que já morreu — o L3 nunca mais abriria teclado nenhum")
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert novo.esperar_os_toques(5.0)
    assert len(mesa["nascidos"]) == 2, (
        f"com o órfão morto, o L3 tinha de ABRIR: {mesa['nascidos']!r}")
    assert _vivo(mesa["nascidos"][1])


def test_o_defunto_por_colher_nao_conta_como_teclado_na_tela(
    mesa: dict[str, Any],
) -> None:
    """Um zumbi tem `/proc` e `comm` intactos — e não desenha teclado nenhum."""
    antigo = _OSKController()
    antigo.open()
    pid = mesa["nascidos"][0]

    os.kill(pid, signal.SIGTERM)
    limite = time.monotonic() + 5.0
    while time.monotonic() < limite and not subsistema._pid_e_zumbi(pid):
        time.sleep(0.02)
    assert Path(f"/proc/{pid}").exists(), (
        "o arranjo deste caso exige `/proc/<pid>` AINDA legível — sem isso ele "
        "vira o caso do PID morto, que já tem régua própria")
    assert subsistema._pid_e_zumbi(pid) is True

    novo = _OSKController()
    assert novo.aberto() is False, (
        f"o daemon novo adotou um DEFUNTO (pid={pid}): `/proc` e `comm` "
        "continuam lá, mas não há teclado na tela dela — e o L3 nunca mais "
        "abriria nenhum")
    novo.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert novo.esperar_os_toques(5.0)
    assert len(mesa["nascidos"]) == 2, (
        f"com o órfão defunto, o L3 tinha de ABRIR: {mesa['nascidos']!r}")


def _pid_reciclado(mesa: dict[str, Any]) -> subprocess.Popen[bytes]:
    """Arma o caso do PID reciclado: um processo ALHEIO com o nosso número anotado."""
    alheio = subprocess.Popen(
        ["cat"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    mesa["nascidos"].append(alheio.pid)
    assert _vivo(alheio.pid)
    assert _comm_real(alheio.pid) != _DUBLE, (
        "o processo alheio tem de ter um `comm` DIFERENTE do binário anotado — "
        "senão este caso não mede a conferência do `/proc`")

    caminho = _arquivo_de_sessao(mesa["runtime"])
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps({"pid": alheio.pid, "comm": _DUBLE}),
        encoding="utf-8",
    )
    return alheio


def test_pid_reciclado_pelo_kernel_nao_e_adotado(mesa: dict[str, Any]) -> None:
    """O PID vive, mas o `/proc/<pid>/comm` NÃO é o nosso binário: não é nosso."""
    alheio = _pid_reciclado(mesa)
    try:
        assert _OSKController().aberto() is False, (
            "adotou um PID RECICLADO: o número está no arquivo, mas o processo "
            "vivo com esse número não é o teclado que abrimos")
    finally:
        alheio.kill()
        alheio.wait()


def test_o_r3_nao_mata_o_processo_alheio_do_pid_reciclado(
    mesa: dict[str, Any],
) -> None:
    """ESTE É O CASO QUE SEPARA A CURA DE UM `pkill wvkbd`."""
    alheio = _pid_reciclado(mesa)
    try:
        controlador = _OSKController()
        controlador.dispatch_token(TOKEN_CLOSE_OSK, "press")
        assert controlador.esperar_os_toques(5.0)
        assert _vivo(alheio.pid), (
            f"o R3 MATOU UM PROCESSO ALHEIO (pid={alheio.pid}) — é o estrago "
            "que a adoção conservadora existe para não cometer, e o mesmo que "
            "um `pkill wvkbd` faria com o teclado que o COSMIC abriu")
    finally:
        alheio.kill()
        alheio.wait()


def test_o_arquivo_de_sessao_guarda_pid_e_binario(mesa: dict[str, Any]) -> None:
    """O que o `open()` anota é o PID e o NOME do binário que ELE spawnou."""
    ctrl = _OSKController()
    ctrl.open()

    dados = json.loads(_arquivo_de_sessao(mesa["runtime"]).read_text(encoding="utf-8"))
    assert dados == {"pid": mesa["nascidos"][0], "comm": _DUBLE}, (
        f"o arquivo de sessão não guarda o par (pid, binário): {dados!r}")
