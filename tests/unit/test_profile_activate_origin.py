"""PERFIL-03 — fiação do `origin` nos 5 call sites de `ProfileManager.activate`."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import ANY, MagicMock

import pytest


class _RecordingManager:
    """Substitui ProfileManager nos call sites que o constroem por dentro."""

    activations: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.store = kwargs.get("store")

    def list_profiles(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=n) for n in ("a", "b", "c")]

    def activate(
        self,
        name: str,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> SimpleNamespace:
        _RecordingManager.activations.append((name, origin))
        if self.store is not None:
            self.store.active_profile = name
        return SimpleNamespace(name=name)


@pytest.fixture()
def recording_manager(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingManager]:
    """Patch de ProfileManager NO MÓDULO DE ORIGEM — os call sites fazem"""
    _RecordingManager.activations = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.ProfileManager",
        _RecordingManager,
    )
    return _RecordingManager


# 1) IPC profile.switch (GUI/CLI) → origin="manual"


@pytest.mark.asyncio
async def test_ipc_profile_switch_ativa_com_origin_manual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Host(IpcHandlersMixin):
        pass

    host = _Host()
    host.profile_manager = MagicMock()
    host.profile_manager.activate.return_value = SimpleNamespace(name="vitoria")
    host.store = MagicMock()
    host.daemon = None
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_active_marker",
        lambda _n: None,
    )

    await host._handle_profile_switch({"name": "vitoria"})

    host.profile_manager.activate.assert_called_once_with(
        "vitoria", origin="manual", relatorio=ANY
    )


@pytest.mark.asyncio
async def test_hotkey_cycle_ativa_com_origin_manual(
    monkeypatch: pytest.MonkeyPatch,
    recording_manager: type[_RecordingManager],
) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
        build_profile_cycle_callback,
    )

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_active_marker",
        lambda _n: None,
    )

    class _Store:
        active_profile = "a"
        native_mode_active = False

        def clear_manual_trigger_active(self) -> None:
            pass

        def mark_manual_profile_lock(self, _t: float) -> None:
            pass

    class _Daemon:
        store = _Store()
        controller = MagicMock()
        _keyboard_device = None

        async def _run_blocking(self, fn: Any, *args: Any) -> Any:
            return fn(*args)

    await build_profile_cycle_callback(_Daemon(), +1)()

    assert recording_manager.activations == [("b", "manual")]


def test_autoswitch_ativa_com_origin_autoswitch() -> None:
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher

    mgr = MagicMock()
    sw = AutoSwitcher(manager=mgr, window_reader=lambda: {})

    sw._activate("navegacao", {"wm_class": "firefox"})

    mgr.activate.assert_called_once_with(
        "navegacao", origin="autoswitch", relatorio=ANY
    )


def _no_disco(*nomes: str) -> None:
    """Os perfis no disco isolado: a escolha do usuário só vale se o perfil abre."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    for nome in nomes:
        loader.save_profile(Profile(name=nome, match=MatchAny()), origem="régua")


class _BootDaemon:
    def __init__(self) -> None:
        self.controller = MagicMock()
        self.store = SimpleNamespace(active_profile=None)
        self._native_mode = False
        self._keyboard_device = None

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


@pytest.mark.asyncio
async def test_restore_de_boot_ativa_com_origin_system(
    monkeypatch: pytest.MonkeyPatch,
    recording_manager: type[_RecordingManager],
) -> None:
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile

    _no_disco("vitoria")
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile",
        lambda: "vitoria",
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.read_active_marker",
        lambda: None,
    )

    await restore_last_profile(_BootDaemon())  # type: ignore[arg-type]

    assert recording_manager.activations == [("vitoria", "system")]


@pytest.mark.asyncio
async def test_restore_de_boot_le_a_sessao_e_o_marcador_e_so_espelho(
    monkeypatch: pytest.MonkeyPatch,
    recording_manager: type[_RecordingManager],
) -> None:
    """O marcador divergente não desvia o boot: a escolha é a do `session.json`."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile

    _no_disco("Navegação", "vitoria")
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile",
        lambda: "Navegação",
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.read_active_marker",
        lambda: "vitoria",
    )

    await restore_last_profile(_BootDaemon())  # type: ignore[arg-type]

    assert recording_manager.activations == [("Navegação", "system")]


def _reapply_stub(active: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        store=SimpleNamespace(active_profile=active),
        controller=MagicMock(),
        apply_profile_mouse=lambda *a: None,
        apply_profile_suppression=lambda *a: None,
        _keyboard_device=None,
    )


def test_saida_do_nativo_reaplica_o_perfil_ativo_com_origin_system(
    monkeypatch: pytest.MonkeyPatch,
    recording_manager: type[_RecordingManager],
) -> None:
    """Com a semântica nova (session.json = última escolha MANUAL), sair do"""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile",
        lambda: "ultima_manual",
    )

    Daemon._reapply_last_profile(_reapply_stub("do_autoswitch"))  # type: ignore[arg-type]

    assert recording_manager.activations == [("do_autoswitch", "system")]


def test_saida_do_nativo_sem_ativo_cai_no_session(
    monkeypatch: pytest.MonkeyPatch,
    recording_manager: type[_RecordingManager],
) -> None:
    """Fallback preservado: sem perfil ativo em memória (boot direto em"""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    _no_disco("ultima_manual")
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile",
        lambda: "ultima_manual",
    )

    Daemon._reapply_last_profile(_reapply_stub(None))  # type: ignore[arg-type]

    assert recording_manager.activations == [("ultima_manual", "system")]
