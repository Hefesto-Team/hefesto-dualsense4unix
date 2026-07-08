"""FEAT-NATIVE-MODE-01 — Modo Nativo ("release total" do controle).

Cobre o setter do daemon (neutraliza saída + gate + pause + flag), a
idempotência, a restauração ao desligar, o gate do autoswitch e a rota IPC.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def tmp_config(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Isola o config_dir (flags de sessão) num tmp."""
    from hefesto_dualsense4unix.utils import session as session_mod

    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


@pytest.fixture
def daemon(tmp_config: Any, monkeypatch: pytest.MonkeyPatch) -> Daemon:
    d = Daemon(controller=FakeController())
    # Evita uinput real: os setters de emulação viram no-op que registram.
    d.set_mouse_emulation = MagicMock(return_value=False)  # type: ignore[method-assign]
    d.set_gamepad_emulation = MagicMock(return_value=True)  # type: ignore[method-assign]
    return d


def test_native_on_neutraliza_e_gate(daemon: Daemon, tmp_config: Any) -> None:
    daemon.config.rumble_active = (100, 100)
    assert daemon.set_native_mode(True) is True
    assert daemon.is_native_mode() is True
    assert daemon.store.native_mode_active is True
    assert daemon.is_paused() is True
    # Rumble em passthrough (o hefesto não re-asserta).
    assert daemon.config.rumble_active is None
    # Emulação desligada (libera grab/uinput) com origin="profile": NÃO carimba o
    # lock manual de 30s — senão o restore ao desligar seria bloqueado.
    daemon.set_mouse_emulation.assert_called_with(False, origin="profile")  # type: ignore[attr-defined]
    daemon.set_gamepad_emulation.assert_called_with(False, origin="profile")  # type: ignore[attr-defined]
    # O lock manual NÃO foi carimbado pelo release.
    assert daemon._emu_manual_ts == float("-inf")
    # Flag persistido.
    assert (tmp_config / "native_mode.flag").exists()


def test_native_off_restaura_e_limpa(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch, tmp_config: Any
) -> None:
    daemon.set_native_mode(True)
    reapplied: list[str] = []
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: reapplied.append("x"))
    assert daemon.set_native_mode(False) is False
    assert daemon.is_native_mode() is False
    assert daemon.store.native_mode_active is False
    assert daemon.is_paused() is False  # resume
    assert reapplied == ["x"]  # re-aplicou o último perfil
    assert not (tmp_config / "native_mode.flag").exists()


def test_native_off_nao_despausa_pause_manual(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-NATIVE-RESUME-CLOBBERS-PAUSE-01: se a usuária já estava pausada ANTES
    do Modo Nativo, desligá-lo NÃO deve des-pausar (só des-pausa se o native
    foi quem pausou)."""
    daemon._paused = True  # pause manual anterior
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    daemon.set_native_mode(True)
    daemon.set_native_mode(False)
    assert daemon.is_paused() is True  # continua pausada


def test_native_idempotente(daemon: Daemon) -> None:
    daemon.set_native_mode(True)
    daemon.set_mouse_emulation.reset_mock()  # type: ignore[attr-defined]
    # Ligar de novo é no-op (não re-neutraliza).
    assert daemon.set_native_mode(True) is True
    daemon.set_mouse_emulation.assert_not_called()  # type: ignore[attr-defined]


def test_autoswitch_gateado_por_native_mode() -> None:
    store = StateStore()
    store.set_native_mode_active(True)
    manager = MagicMock()
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    sw._activate("qualquer", {"wm_class": "Sackboy"})
    manager.activate.assert_not_called()  # não ativa perfil em modo nativo


def test_state_full_inclui_native_mode(daemon: Daemon) -> None:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=MagicMock(),
        daemon=daemon,
    )
    daemon.set_native_mode(True)
    import asyncio

    state = asyncio.run(server._handle_daemon_state_full({}))
    assert state["native_mode"] is True


def test_ipc_native_mode_set_toggle(daemon: Daemon) -> None:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=MagicMock(),
        daemon=daemon,
    )
    import asyncio

    # Sem 'enabled' → toggle (off→on).
    r1 = asyncio.run(server._handle_native_mode_set({}))
    assert r1 == {"status": "ok", "native_mode": True}
    # Toggle de novo (on→off) — restore chamará _reapply; stub para não tocar disco.
    daemon._reapply_last_profile = lambda: None  # type: ignore[method-assign]
    r2 = asyncio.run(server._handle_native_mode_set({}))
    assert r2 == {"status": "ok", "native_mode": False}
