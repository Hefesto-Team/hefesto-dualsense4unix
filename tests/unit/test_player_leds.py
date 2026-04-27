"""Testes unitários de Player LEDs — FEAT-PLAYER-LEDS-APPLY-01.

Cobre:
  - FakeController.set_player_leds grava last_player_leds corretamente.
  - IpcServer.led.player_set encaminha bitmask ao controller.
  - Validações de parâmetros no handler IPC.
  - Bitmasks canônicos (Player 1, Player 2) e arbitrários funcionam no FakeController.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import CODE_INVALID_PARAMS, IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

# ---------------------------------------------------------------------------
# Fixtures auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


@pytest.fixture
async def running_server(tmp_path: Path, isolated_profiles_dir: Path):
    """IpcServer no ar em socket temporário com FakeController."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))
    manager = ProfileManager(controller=fc, store=store)
    socket_path = tmp_path / "hefesto_test.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
    )
    await server.start()
    try:
        yield server, socket_path, fc
    finally:
        await server.stop()


# ---------------------------------------------------------------------------
# Testes — FakeController direto (sem IPC)
# ---------------------------------------------------------------------------


def test_fake_controller_last_player_leds_inicial_none() -> None:
    """FakeController inicia com last_player_leds None (nunca chamado)."""
    fc = FakeController()
    assert fc.last_player_leds is None


def test_fake_controller_set_player_leds_grava_bits() -> None:
    """set_player_leds grava exatamente o bitmask passado."""
    fc = FakeController()
    bits: tuple[bool, bool, bool, bool, bool] = (True, False, True, False, True)
    fc.set_player_leds(bits)
    assert fc.last_player_leds == bits


def test_fake_controller_set_player_leds_registra_comando() -> None:
    """set_player_leds adiciona FakeControllerCommand com kind='set_player_leds'."""
    fc = FakeController()
    bits: tuple[bool, bool, bool, bool, bool] = (False, False, True, False, False)
    fc.set_player_leds(bits)
    assert any(cmd.kind == "set_player_leds" for cmd in fc.commands)


def test_fake_controller_set_player_leds_sobrescreve() -> None:
    """Chamadas repetidas sobrescrevem last_player_leds com último valor."""
    fc = FakeController()
    fc.set_player_leds((True, True, True, True, True))
    fc.set_player_leds((False, False, False, False, False))
    assert fc.last_player_leds == (False, False, False, False, False)


def test_fake_controller_bitmask_todos_ligados() -> None:
    """Preset 'Todos' — 5 bits True."""
    fc = FakeController()
    fc.set_player_leds((True, True, True, True, True))
    assert fc.last_player_leds == (True, True, True, True, True)


def test_fake_controller_bitmask_todos_apagados() -> None:
    """Preset 'Nenhum' — 5 bits False."""
    fc = FakeController()
    fc.set_player_leds((False, False, False, False, False))
    assert fc.last_player_leds == (False, False, False, False, False)


def test_fake_controller_bitmask_player1_canonico() -> None:
    """Preset Player 1 canônico: apenas LED 3 (bit 2) aceso — bitmask 0b00100 = 4."""
    fc = FakeController()
    bits: tuple[bool, bool, bool, bool, bool] = (False, False, True, False, False)
    fc.set_player_leds(bits)
    assert fc.last_player_leds == bits


def test_fake_controller_bitmask_player2_canonico() -> None:
    """Preset Player 2 canônico: LEDs 2 e 4 (bits 1 e 3) — bitmask 0b01010 = 10."""
    fc = FakeController()
    bits: tuple[bool, bool, bool, bool, bool] = (False, True, False, True, False)
    fc.set_player_leds(bits)
    assert fc.last_player_leds == bits


# ---------------------------------------------------------------------------
# Testes — IpcServer led.player_set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ipc_led_player_set_envia_bitmask(running_server) -> None:
    """led.player_set encaminha bitmask ao controller e retorna status ok."""
    _server, socket_path, fc = running_server
    bits = [True, False, True, False, True]
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("led.player_set", {"bits": bits})
    assert result["status"] == "ok"
    assert result["bits"] == bits
    assert fc.last_player_leds == tuple(bits)


@pytest.mark.asyncio
async def test_ipc_led_player_set_todos_ligados(running_server) -> None:
    """Preset Todos via IPC acende os 5 LEDs."""
    _server, socket_path, fc = running_server
    bits = [True, True, True, True, True]
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("led.player_set", {"bits": bits})
    assert result["status"] == "ok"
    assert fc.last_player_leds == (True, True, True, True, True)


@pytest.mark.asyncio
async def test_ipc_led_player_set_todos_apagados(running_server) -> None:
    """Preset Nenhum via IPC apaga os 5 LEDs."""
    _server, socket_path, fc = running_server
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("led.player_set", {"bits": [False] * 5})
    assert result["status"] == "ok"
    assert fc.last_player_leds == (False, False, False, False, False)


@pytest.mark.asyncio
async def test_ipc_led_player_set_bits_curtos_rejeitado(running_server) -> None:
    """bits com menos de 5 elementos retorna erro CODE_INVALID_PARAMS."""
    _server, socket_path, _fc = running_server
    with pytest.raises(IpcError) as exc_info:
        async with IpcClient.connect(socket_path) as client:
            await client.call("led.player_set", {"bits": [True, False]})
    assert exc_info.value.code == CODE_INVALID_PARAMS


@pytest.mark.asyncio
async def test_ipc_led_player_set_bits_longos_rejeitado(running_server) -> None:
    """bits com mais de 5 elementos retorna erro CODE_INVALID_PARAMS."""
    _server, socket_path, _fc = running_server
    with pytest.raises(IpcError) as exc_info:
        async with IpcClient.connect(socket_path) as client:
            await client.call("led.player_set", {"bits": [True] * 6})
    assert exc_info.value.code == CODE_INVALID_PARAMS


@pytest.mark.asyncio
async def test_ipc_led_player_set_bits_ausente_rejeitado(running_server) -> None:
    """Ausência de 'bits' nos parâmetros retorna CODE_INVALID_PARAMS."""
    _server, socket_path, _fc = running_server
    with pytest.raises(IpcError) as exc_info:
        async with IpcClient.connect(socket_path) as client:
            await client.call("led.player_set", {})
    assert exc_info.value.code == CODE_INVALID_PARAMS


@pytest.mark.asyncio
async def test_ipc_led_player_set_bits_inteiros_rejeitado(running_server) -> None:
    """bits com inteiros (não booleanos) retorna CODE_INVALID_PARAMS."""
    _server, socket_path, _fc = running_server
    with pytest.raises(IpcError) as exc_info:
        async with IpcClient.connect(socket_path) as client:
            await client.call("led.player_set", {"bits": [1, 0, 1, 0, 1]})
    assert exc_info.value.code == CODE_INVALID_PARAMS


@pytest.mark.asyncio
async def test_ipc_led_player_set_sequencia_sobrescreve(running_server) -> None:
    """Duas chamadas em sequência: segundo bitmask prevalece."""
    _server, socket_path, fc = running_server
    async with IpcClient.connect(socket_path) as client:
        await client.call("led.player_set", {"bits": [True] * 5})
        await client.call("led.player_set", {"bits": [False] * 5})
    assert fc.last_player_leds == (False, False, False, False, False)
