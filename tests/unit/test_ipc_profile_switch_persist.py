"""CLUSTER-IPC-STATE-PROFILE-01 Bug B — `profile.switch` persiste em paridade.

Garante que o handler IPC `profile.switch`:
  - Continua chamando `manager.activate(name)` (que persiste session.json,
    canônico do daemon — não duplicar).
  - Adicionalmente escreve `active_profile.txt` (marker da CLI legada) via
    `utils.session.save_active_marker`.
  - Falha em ativar (perfil inválido) → marker NÃO é tocado (atomicidade).
  - Lock manual (Bug C) é armado depois de persistir, antes de retornar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import (
    MANUAL_PROFILE_LOCK_SEC,
    StateStore,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola profiles_dir + config_dir em tmp_path."""
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    config = tmp_path / "config"
    config.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            profiles.mkdir(parents=True, exist_ok=True)
        return profiles

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            config.mkdir(parents=True, exist_ok=True)
        return config

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    from hefesto_dualsense4unix.utils import xdg_paths
    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    return tmp_path


@pytest.fixture
async def running_server(isolated_dirs: Path) -> Any:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))
    save_profile(
        Profile(
            name="shooter",
            match=MatchCriteria(window_class=["Doom"]),
            priority=10,
            triggers=TriggersConfig(
                left=TriggerConfig(mode="Off"),
                right=TriggerConfig(mode="Rigid", params=[5, 200]),
            ),
            leds=LedsConfig(lightbar=(255, 0, 0)),
        )
    )

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
    )

    socket_path = isolated_dirs / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon_mock,
    )
    await server.start()
    try:
        yield server, socket_path, fc, store, isolated_dirs
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_profile_switch_grava_active_marker(running_server: Any) -> None:
    """`profile.switch` cria/atualiza `active_profile.txt` com o nome aplicado."""
    _server, socket_path, _fc, _store, tmp_root = running_server
    marker = tmp_root / "config" / "active_profile.txt"
    assert not marker.exists()

    async with IpcClient.connect(socket_path) as client:
        result = await client.call("profile.switch", {"name": "shooter"})

    assert result == {"active_profile": "shooter"}
    assert marker.exists()
    assert marker.read_text(encoding="utf-8").strip() == "shooter"


@pytest.mark.asyncio
async def test_profile_switch_falha_nao_toca_marker(running_server: Any) -> None:
    """Perfil inexistente → IPC erro; marker NÃO é tocado.

    Atomicidade do conjunto: se `manager.activate` levantar, o marker
    permanece no estado anterior (ou ausente).
    """
    _server, socket_path, _fc, _store, tmp_root = running_server
    marker = tmp_root / "config" / "active_profile.txt"
    assert not marker.exists()

    async with IpcClient.connect(socket_path) as client:
        with pytest.raises(IpcError):
            await client.call("profile.switch", {"name": "ghost"})

    assert not marker.exists()


@pytest.mark.asyncio
async def test_profile_switch_arma_lock_manual(running_server: Any) -> None:
    """Após `profile.switch`, `manual_profile_lock_active` deve retornar True.

    Cobre integração Bug B + Bug C: handler arma lock por
    MANUAL_PROFILE_LOCK_SEC após persistir o marker.
    """
    import time

    _server, socket_path, _fc, store, _tmp_root = running_server
    assert store.manual_profile_lock_active(time.monotonic()) is False

    async with IpcClient.connect(socket_path) as client:
        await client.call("profile.switch", {"name": "shooter"})

    now = time.monotonic()
    assert store.manual_profile_lock_active(now) is True
    # Lock no futuro: ativo até now + MANUAL_PROFILE_LOCK_SEC (≈30s).
    assert store.manual_profile_lock_active(now + MANUAL_PROFILE_LOCK_SEC - 1) is True
    # Após o limite, lock expira.
    assert store.manual_profile_lock_active(now + MANUAL_PROFILE_LOCK_SEC + 1) is False
