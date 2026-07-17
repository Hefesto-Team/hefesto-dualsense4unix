"""PERFIL-03 — fiação do `origin` nos 5 call sites de `ProfileManager.activate`.

A tabela do sprint doc (2026-07-16-sprint-perfis-por-controle.md) lista CINCO
call sites — não três, como revisões antigas afirmavam. Estes testes travam a
fiação de cada um: renomear/remover o parâmetro ou trocar o origin de um call
site quebra aqui, não em silêncio no boot da usuária.

  | Call site                                  | origin       | grava session? |
  |--------------------------------------------|--------------|----------------|
  | ipc_handlers._handle_profile_switch        | "manual"     | sim            |
  | hotkey build_profile_cycle_callback        | "manual"     | sim            |
  | autoswitch AutoSwitcher._activate          | "autoswitch" | não            |
  | connection.restore_last_profile (boot)     | "system"     | não            |
  | lifecycle._reapply_last_profile (nativo)   | "system"     | não            |

O 5º call site também muda a FONTE do nome: sair do Modo Nativo re-aplica o
perfil ATIVO (`store.active_profile` — pode ter vindo do autoswitch), não a
última escolha manual do session.json (mudança não intencional que a nova
semântica introduziria, prevista pela tabela).

NÃO confundir este `origin` com o do latch de `start_gamepad_emulation`
("manual"/"profile") — contratos distintos, por decisão do doc.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Dublês compartilhados
# ---------------------------------------------------------------------------


class _RecordingManager:
    """Substitui ProfileManager nos call sites que o constroem por dentro."""

    activations: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.store = kwargs.get("store")

    def list_profiles(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=n) for n in ("a", "b", "c")]

    def activate(self, name: str, *, origin: str = "manual") -> SimpleNamespace:
        _RecordingManager.activations.append((name, origin))
        if self.store is not None:
            self.store.active_profile = name
        return SimpleNamespace(name=name)


@pytest.fixture()
def recording_manager(monkeypatch: pytest.MonkeyPatch) -> type[_RecordingManager]:
    """Patch de ProfileManager NO MÓDULO DE ORIGEM — os call sites fazem
    import lazy (`from ...profiles.manager import ProfileManager`) na hora da
    chamada, então o patch pega todos."""
    _RecordingManager.activations = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.ProfileManager",
        _RecordingManager,
    )
    return _RecordingManager


# ---------------------------------------------------------------------------
# 1) IPC profile.switch (GUI/CLI) → origin="manual"
# ---------------------------------------------------------------------------


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
    host.daemon = None  # pula o materialize_launch_env
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_active_marker",
        lambda _n: None,
    )

    await host._handle_profile_switch({"name": "vitoria"})

    host.profile_manager.activate.assert_called_once_with(
        "vitoria", origin="manual"
    )


# ---------------------------------------------------------------------------
# 2) Hotkey PS+D-pad (botão físico) → origin="manual"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hotkey_cycle_ativa_com_origin_manual(
    monkeypatch: pytest.MonkeyPatch,
    recording_manager: type[_RecordingManager],
) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
        build_profile_cycle_callback,
    )

    # O ciclo grava o marker da CLI em paridade — anula a escrita REAL em
    # ~/.config (hermeticidade).
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


# ---------------------------------------------------------------------------
# 3) Autoswitch (troca por janela) → origin="autoswitch"
# ---------------------------------------------------------------------------


def test_autoswitch_ativa_com_origin_autoswitch() -> None:
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher

    mgr = MagicMock()
    sw = AutoSwitcher(manager=mgr, window_reader=lambda: {})

    sw._activate("navegacao", {"wm_class": "firefox"})

    mgr.activate.assert_called_once_with("navegacao", origin="autoswitch")


# ---------------------------------------------------------------------------
# 4) Restore de boot → origin="system" (e lê a intenção via resolve_boot_profile)
# ---------------------------------------------------------------------------


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
async def test_restore_de_boot_prefere_o_marker_manual_divergente(
    monkeypatch: pytest.MonkeyPatch,
    recording_manager: type[_RecordingManager],
) -> None:
    """Seed de migração fiado no boot: session.json herdado do clobber do
    autoswitch ('Navegação') + marker manual ('vitoria') → ativa 'vitoria'."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile",
        lambda: "Navegação",
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.read_active_marker",
        lambda: "vitoria",
    )

    await restore_last_profile(_BootDaemon())  # type: ignore[arg-type]

    assert recording_manager.activations == [("vitoria", "system")]


# ---------------------------------------------------------------------------
# 5) Saída do Modo Nativo → origin="system" + prefere store.active_profile
# ---------------------------------------------------------------------------


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
    """Com a semântica nova (session.json = última escolha MANUAL), sair do
    nativo tem que re-aplicar o perfil ATIVO (ex.: o que o autoswitch escolheu
    pela janela do jogo) — não a última manual por cima dele."""
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
    """Fallback preservado: sem perfil ativo em memória (boot direto em
    nativo), o session.json ainda responde."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_last_profile",
        lambda: "ultima_manual",
    )

    Daemon._reapply_last_profile(_reapply_stub(None))  # type: ignore[arg-type]

    assert recording_manager.activations == [("ultima_manual", "system")]
