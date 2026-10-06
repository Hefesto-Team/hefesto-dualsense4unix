"""SPRINT-HARMONIA-01 — a emulação de mouse/teclado tem UM dono: o modo desktop."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("harmonia mouse um dono")

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gamepad_sub
from hefesto_dualsense4unix.integrations import virtual_pad
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session


class _FakeWidget:
    def __init__(self) -> None:
        self.sensitive = True
        self.text = ""
        self.visible = True

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = bool(value)

    def set_text(self, value: str) -> None:
        self.text = value

    def set_visible(self, value: bool) -> None:
        self.visible = bool(value)


@pytest.fixture()
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


class _FakeMouseDevice:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    def set_speed(self, **_kw: Any) -> None:
        pass


def _daemon() -> Daemon:
    return Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )


@pytest.fixture()
def daemon(monkeypatch: pytest.MonkeyPatch) -> Daemon:
    """Daemon com o start do mouse dublado (sem uinput de verdade)."""
    d = _daemon()

    def _start(target: Any, **_kw: object) -> bool:
        target._mouse_device = _FakeMouseDevice()
        target.config.mouse_emulation_enabled = True
        session.save_mouse_emulation(
            True,
            speed=target.config.mouse_speed,
            scroll_speed=target.config.mouse_scroll_speed,
        )
        return True

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.mouse.start_mouse_emulation", _start
    )
    return d


def test_preferencia_nunca_configurada_liga_o_mouse(
    tmp_config: Path, daemon: Daemon
) -> None:
    """Aceite do HARM-06: entrar em "Controlar o PC" deixa o cursor"""
    assert session.load_mouse_preference() == (None, None, None)

    assert daemon.restore_mouse_preference() is True
    assert daemon.config.mouse_emulation_enabled is True


def test_preferencia_desligada_de_proposito_e_respeitada(
    tmp_config: Path, daemon: Daemon
) -> None:
    """"Desligado pela usuária" não pode virar "nunca configurada" — senão o"""
    session.save_mouse_emulation(False)

    assert daemon.restore_mouse_preference() is False
    assert daemon.config.mouse_emulation_enabled is False


def test_restore_reaplica_as_velocidades_persistidas(
    tmp_config: Path, daemon: Daemon
) -> None:
    session.save_mouse_emulation(True, speed=11, scroll_speed=4)

    daemon.restore_mouse_preference()

    assert daemon.config.mouse_speed == 11
    assert daemon.config.mouse_scroll_speed == 4


def test_ligar_o_gamepad_nao_apaga_a_preferencia_de_mouse(
    tmp_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A causa-raiz do HARM-06: a exclusão mútua gravava "off" e o round-trip"""
    session.save_mouse_emulation(True, speed=9, scroll_speed=2)
    d = _daemon()
    d._mouse_device = _FakeMouseDevice()
    d.config.mouse_emulation_enabled = True
    monkeypatch.setattr(virtual_pad, "make_virtual_pad", lambda *_a, **_k: None)

    gamepad_sub.start_gamepad_emulation(d, flavor="xbox", origin="manual")

    assert d._mouse_device is None
    assert d.config.mouse_emulation_enabled is False
    assert session.load_mouse_preference() == (True, 9, 2)


def test_round_trip_desktop_gamepad_desktop_preserva(
    tmp_config: Path, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aceite do HARM-06: sair e voltar preserva."""
    monkeypatch.setattr(virtual_pad, "make_virtual_pad", lambda *_a, **_k: None)
    daemon.restore_mouse_preference()
    assert daemon.config.mouse_emulation_enabled is True

    gamepad_sub.start_gamepad_emulation(daemon, flavor="xbox", origin="manual")
    assert daemon.config.mouse_emulation_enabled is False

    assert daemon.restore_mouse_preference() is True
    assert daemon.config.mouse_emulation_enabled is True


@pytest.mark.asyncio
async def test_ipc_restore_liga_o_mouse_e_esta_no_contrato(
    tmp_config: Path, daemon: Daemon
) -> None:
    """O passo `mouse.emulation.restore` do plano do modo desktop tem que EXISTIR
    no contrato IPC — método não registrado faria a Início pintar "Falha ao mudar
    o modo" com o modo já aplicado."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=MagicMock(),
        daemon=daemon,
    )
    handler = server._handlers["mouse.emulation.restore"]

    assert await handler({}) == {"status": "ok", "enabled": True}
    assert daemon.config.mouse_emulation_enabled is True


@pytest.mark.asyncio
async def test_ipc_restore_com_daemon_sem_o_metodo_nao_estoura(
    tmp_config: Path,
) -> None:
    """Daemon antigo/dublado: o modo desktop vale sem o mouse — mas a resposta"""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    class _DaemonSemRestore:
        config = DaemonConfig()

    server = IpcServer(
        controller=FakeController(transport="usb"),
        store=StateStore(),
        profile_manager=MagicMock(),
        daemon=_DaemonSemRestore(),
    )

    assert await server._handlers["mouse.emulation.restore"]({}) == {
        "status": "failed",
        "enabled": False,
    }


def test_desligar_o_mouse_na_mao_persiste_off(tmp_config: Path, daemon: Daemon) -> None:
    """O gesto MANUAL da aba Mouse continua gravando a preferência — é ele que"""
    daemon.restore_mouse_preference()

    daemon.set_mouse_emulation(False, origin="manual")

    assert session.load_mouse_preference()[0] is False
