"""Testes do IPC server JSON-RPC 2.0."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hefesto.cli.ipc_client import IpcClient, IpcError
from hefesto.core.controller import ControllerState
from hefesto.daemon.ipc_server import (
    CODE_INVALID_PARAMS,
    CODE_METHOD_NOT_FOUND,
    CODE_PROFILE_NOT_FOUND,
    IpcServer,
)
from hefesto.daemon.state_store import StateStore
from hefesto.profiles import loader as loader_module
from hefesto.profiles.loader import save_profile
from hefesto.profiles.manager import ProfileManager
from hefesto.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from tests.fixtures.fake_controller import FakeController


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
    """IpcServer no ar em socket de tmp_path. Yields (server, socket_path, fake)."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=75, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
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

    socket_path = tmp_path / "hefesto.sock"
    server = IpcServer(
        controller=fc, store=store, profile_manager=manager, socket_path=socket_path
    )
    await server.start()
    try:
        yield server, socket_path, fc
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_profile_list_retorna_todos(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("profile.list")
    names = sorted(p["name"] for p in result["profiles"])
    assert names == ["fallback", "shooter"]


@pytest.mark.asyncio
async def test_profile_switch_ativa_e_retorna_nome(running_server):
    server, socket_path, fc = running_server
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("profile.switch", {"name": "shooter"})
    assert result == {"active_profile": "shooter"}
    assert server.store.active_profile == "shooter"

    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 2
    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert leds[-1].payload == (255, 0, 0)


@pytest.mark.asyncio
async def test_profile_switch_inexistente(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        with pytest.raises(IpcError) as exc_info:
            await client.call("profile.switch", {"name": "ghost"})
    assert exc_info.value.code == CODE_PROFILE_NOT_FOUND


@pytest.mark.asyncio
async def test_trigger_set_e_reset(running_server):
    _server, socket_path, fc = running_server
    async with IpcClient.connect(socket_path) as client:
        assert await client.call(
            "trigger.set",
            {"side": "right", "mode": "Rigid", "params": [5, 200]},
        ) == {"status": "ok"}

        assert await client.call("trigger.reset", {"side": "right"}) == {"status": "ok"}
        assert await client.call("trigger.reset") == {"status": "ok"}  # both

    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) >= 4  # 1 set + 1 reset + 2 reset both


@pytest.mark.asyncio
async def test_trigger_set_side_invalido(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        with pytest.raises(IpcError) as exc:
            await client.call("trigger.set", {"side": "middle", "mode": "Off", "params": []})
    assert exc.value.code == CODE_INVALID_PARAMS


@pytest.mark.asyncio
async def test_led_set(running_server):
    _server, socket_path, fc = running_server
    async with IpcClient.connect(socket_path) as client:
        await client.call("led.set", {"rgb": [255, 128, 0]})
    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert leds[-1].payload == (255, 128, 0)


@pytest.mark.asyncio
async def test_led_set_fora_de_byte(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        with pytest.raises(IpcError) as exc:
            await client.call("led.set", {"rgb": [300, 0, 0]})
    assert exc.value.code == CODE_INVALID_PARAMS


@pytest.mark.asyncio
async def test_daemon_status(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.status")
    assert result["connected"] is True
    assert result["transport"] == "usb"
    assert result["battery_pct"] == 75


@pytest.mark.asyncio
async def test_controller_list(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("controller.list")
    assert result["controllers"][0]["connected"] is True


@pytest.mark.asyncio
async def test_daemon_reload(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.reload")
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_metodo_desconhecido_retorna_erro(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        with pytest.raises(IpcError) as exc:
            await client.call("nao.existe")
    assert exc.value.code == CODE_METHOD_NOT_FOUND


@pytest.mark.asyncio
async def test_json_malformado_retorna_parse_error(running_server):
    _server, socket_path, _ = running_server
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        writer.write(b"{isto nao e json}\n")
        await writer.drain()
        raw = await reader.readline()
    finally:
        writer.close()
        await writer.wait_closed()
    response = json.loads(raw.decode("utf-8"))
    assert "error" in response


@pytest.mark.asyncio
async def test_socket_permissao_0600(running_server):
    _server, socket_path, _ = running_server
    import stat

    mode = stat.S_IMODE(socket_path.stat().st_mode)
    assert mode == 0o600
