"""Testes de reload de configuração em runtime (REFACTOR-DAEMON-RELOAD-01).

Cobre:
  - reload_config com ps_button_action="none" não abre Steam.
  - reload_config com mouse_emulation_enabled=True liga mouse via set_mouse_emulation.
  - reload_config recria o HotkeyManager (closures frescas).
  - IPC daemon.reload retorna config atualizado.
  - IPC daemon.reload rejeita campo desconhecido.
  - IPC daemon.reload retorna erro limpo se daemon is None.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto.daemon.ipc_server import IpcServer
from hefesto.daemon.lifecycle import Daemon, DaemonConfig
from hefesto.daemon.state_store import StateStore
from hefesto.testing import FakeController

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _make_daemon(
    ps_button_action: str = "steam",
    ps_button_command: list[str] | None = None,
    mouse_emulation_enabled: bool = False,
) -> Daemon:
    """Constroi Daemon mínimo sem IPC/UDP/autoswitch para testes unitários."""
    return Daemon(
        controller=FakeController(transport="usb", states=[]),
        config=DaemonConfig(
            ps_button_action=ps_button_action,  # type: ignore[arg-type]
            ps_button_command=ps_button_command or [],
            mouse_emulation_enabled=mouse_emulation_enabled,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
        ),
    )


def _make_ipc(daemon: Daemon | None = None) -> IpcServer:
    """Constroi IpcServer mínimo para testes unitários de handlers."""
    fc = FakeController(transport="usb", states=[])
    store = StateStore()
    pm = MagicMock()
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=pm,
        daemon=daemon,
    )


# ---------------------------------------------------------------------------
# reload_config — comportamento de ps_button_action
# ---------------------------------------------------------------------------


def test_reload_config_none_nao_abre_steam(monkeypatch):
    """Após reload com ps_button_action='none', on_ps_solo não chama Steam."""
    from hefesto.integrations import steam_launcher as _sl

    chamadas: list[str] = []
    monkeypatch.setattr(_sl, "open_or_focus_steam", lambda **_kw: chamadas.append("steam") or True)

    daemon = _make_daemon(ps_button_action="steam")
    daemon._start_hotkey_manager()

    # Reload: muda ação para "none".
    novo_cfg = DaemonConfig(
        ps_button_action="none",
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
    )
    daemon.reload_config(novo_cfg)

    # Dispara on_ps_solo diretamente — não deve chamar Steam.
    assert daemon._hotkey_manager is not None
    daemon._hotkey_manager.on_ps_solo()
    assert chamadas == [], "Steam não deve ser chamado após reload para 'none'"


def test_reload_config_steam_chama_launcher(monkeypatch):
    """Apos reload com ps_button_action='steam', on_ps_solo chama Steam."""
    from hefesto.integrations import steam_launcher as _sl

    chamadas: list[str] = []
    monkeypatch.setattr(_sl, "open_or_focus_steam", lambda **_kw: chamadas.append("steam") or True)

    daemon = _make_daemon(ps_button_action="none")
    daemon._start_hotkey_manager()

    novo_cfg = DaemonConfig(
        ps_button_action="steam",
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
    )
    daemon.reload_config(novo_cfg)

    daemon._hotkey_manager.on_ps_solo()
    assert chamadas == ["steam"]


def test_reload_config_recria_hotkey_manager():
    """reload_config sempre recria o HotkeyManager (instancia nova)."""
    daemon = _make_daemon()
    daemon._start_hotkey_manager()
    instancia_antiga = daemon._hotkey_manager

    novo_cfg = DaemonConfig(
        ps_button_action="none",
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
    )
    daemon.reload_config(novo_cfg)

    assert daemon._hotkey_manager is not instancia_antiga
    assert daemon._hotkey_manager is not None


# ---------------------------------------------------------------------------
# reload_config — mouse_emulation_enabled
# ---------------------------------------------------------------------------


def test_reload_config_mouse_ligado_chama_set_mouse_emulation(monkeypatch):
    """Reload com mouse_emulation_enabled=True chama set_mouse_emulation(True)."""
    daemon = _make_daemon(mouse_emulation_enabled=False)
    daemon._start_hotkey_manager()

    chamadas: list[tuple[bool, Any, Any]] = []

    def _fake_set_mouse(
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        chamadas.append((enabled, speed, scroll_speed))
        return True

    monkeypatch.setattr(daemon, "set_mouse_emulation", _fake_set_mouse)

    novo_cfg = DaemonConfig(
        mouse_emulation_enabled=True,
        mouse_speed=8,
        mouse_scroll_speed=2,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
    )
    daemon.reload_config(novo_cfg)

    assert len(chamadas) == 1
    enabled, speed, scroll_speed = chamadas[0]
    assert enabled is True
    assert speed == 8
    assert scroll_speed == 2


def test_reload_config_mouse_sem_mudanca_nao_chama_set_mouse_emulation(monkeypatch):
    """Se mouse_emulation_enabled não mudou, set_mouse_emulation não é chamado."""
    daemon = _make_daemon(mouse_emulation_enabled=False)
    daemon._start_hotkey_manager()

    chamadas: list[bool] = []
    monkeypatch.setattr(
        daemon,
        "set_mouse_emulation",
        lambda enabled, **_kw: chamadas.append(enabled) or True,
    )

    # Novo config: mouse continua False.
    novo_cfg = DaemonConfig(
        mouse_emulation_enabled=False,
        ps_button_action="none",
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
    )
    daemon.reload_config(novo_cfg)

    assert chamadas == [], "set_mouse_emulation não deve ser chamado se estado não mudou"


# ---------------------------------------------------------------------------
# IPC daemon.reload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ipc_daemon_reload_retorna_config_atualizado():
    """Handler IPC daemon.reload retorna config completo apos override."""
    daemon = _make_daemon(ps_button_action="steam")
    daemon._start_hotkey_manager()

    ipc = _make_ipc(daemon=daemon)

    resultado = await ipc._handle_daemon_reload(
        {"config_overrides": {"ps_button_action": "none"}}
    )

    assert resultado["status"] == "ok"
    assert "config" in resultado
    assert resultado["config"]["ps_button_action"] == "none"
    # Config do daemon deve ter sido atualizado.
    assert daemon.config.ps_button_action == "none"


@pytest.mark.asyncio
async def test_ipc_daemon_reload_sem_overrides_preserva_config():
    """Handler sem config_overrides preserva config existente."""
    daemon = _make_daemon(ps_button_action="steam")
    daemon._start_hotkey_manager()

    ipc = _make_ipc(daemon=daemon)

    resultado = await ipc._handle_daemon_reload({})

    assert resultado["status"] == "ok"
    cfg = resultado["config"]
    assert cfg["ps_button_action"] == "steam"


@pytest.mark.asyncio
async def test_ipc_daemon_reload_rejeita_campo_desconhecido():
    """Handler rejeita campo que não existe em DaemonConfig."""
    daemon = _make_daemon()
    daemon._start_hotkey_manager()
    ipc = _make_ipc(daemon=daemon)

    with pytest.raises(ValueError, match="campos desconhecidos"):
        await ipc._handle_daemon_reload(
            {"config_overrides": {"campo_inexistente": 42}}
        )


@pytest.mark.asyncio
async def test_ipc_daemon_reload_daemon_none_retorna_erro():
    """Se daemon is None, handler retorna ValueError limpo."""
    ipc = _make_ipc(daemon=None)

    with pytest.raises(ValueError, match="daemon não disponível"):
        await ipc._handle_daemon_reload({})


@pytest.mark.asyncio
async def test_ipc_daemon_reload_config_overrides_nao_dict_rejeita():
    """config_overrides que não seja dict levanta ValueError."""
    daemon = _make_daemon()
    daemon._start_hotkey_manager()
    ipc = _make_ipc(daemon=daemon)

    with pytest.raises(ValueError, match="deve ser objeto"):
        await ipc._handle_daemon_reload({"config_overrides": "invalido"})
