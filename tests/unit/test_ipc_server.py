"""Testes do IPC server JSON-RPC 2.0."""
from __future__ import annotations

import asyncio
import json
import socket as _socket
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
from hefesto.testing import FakeController


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
async def test_daemon_reload_sem_daemon_retorna_erro(running_server):
    """daemon.reload sem daemon configurado retorna IpcError limpo (sem daemon)."""
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        with pytest.raises(IpcError) as exc:
            await client.call("daemon.reload")
    # Handler levanta ValueError("daemon não disponível...") -> CODE_INVALID_PARAMS.
    assert exc.value.code == CODE_INVALID_PARAMS


@pytest.mark.asyncio
async def test_metodo_desconhecido_retorna_erro(running_server):
    _server, socket_path, _ = running_server
    async with IpcClient.connect(socket_path) as client:
        with pytest.raises(IpcError) as exc:
            await client.call("não.existe")
    assert exc.value.code == CODE_METHOD_NOT_FOUND


@pytest.mark.asyncio
async def test_json_malformado_retorna_parse_error(running_server):
    _server, socket_path, _ = running_server
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        writer.write(b"{isto nao e json}\n")  # noqa-acento
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


# --- BUG-IPC-01: detecção de socket vivo vs. resto-morto -----------------


def _make_server(tmp_path: Path, socket_name: str = "hefesto.sock") -> IpcServer:
    """Fabrica IpcServer mínimo para testes de ciclo start/stop."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / socket_name,
    )


@pytest.mark.asyncio
async def test_start_em_path_livre_cria_listener(
    tmp_path: Path, isolated_profiles_dir: Path
):
    """Caso (a): path livre -> start cria o socket normalmente."""
    server = _make_server(tmp_path, "livre.sock")
    assert not server.socket_path.exists()
    try:
        await server.start()
        assert server.socket_path.exists()
        assert server._socket_inode is not None
    finally:
        await server.stop()
    assert not server.socket_path.exists()


@pytest.mark.asyncio
async def test_start_falha_quando_outro_daemon_escuta(
    tmp_path: Path, isolated_profiles_dir: Path
):
    """Caso (b): socket vivo -> RuntimeError e o path não é tocado."""
    server_a = _make_server(tmp_path, "ocupado.sock")
    server_b = _make_server(tmp_path, "ocupado.sock")
    await server_a.start()
    inode_original = server_a.socket_path.stat().st_ino
    try:
        with pytest.raises(RuntimeError, match="socket ocupado"):
            await server_b.start()
        # Socket do primeiro permanece intacto (mesmo inode).
        assert server_a.socket_path.exists()
        assert server_a.socket_path.stat().st_ino == inode_original
    finally:
        await server_a.stop()


@pytest.mark.asyncio
async def test_start_remove_socket_resto_morto(
    tmp_path: Path, isolated_profiles_dir: Path
):
    """Caso (c): arquivo-resto sem listener -> unlink e recria."""
    stale = tmp_path / "resto.sock"
    # Cria socket AF_UNIX sem listen() -> connect recebe ConnectionRefusedError.
    sck = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    sck.bind(str(stale))
    sck.close()  # deixa o nó no filesystem, mas não há listener
    assert stale.exists()

    server = _make_server(tmp_path, "resto.sock")
    try:
        await server.start()
        assert server.socket_path.exists()
        # Prova empírica de que o listener está ativo agora (antes não estava):
        # um connect síncrono deve ter sucesso. O ext4 pode reusar o inode do
        # arquivo órfão, por isso comparar inode é frágil — connect é o teste
        # canônico de "socket vivo".
        probe = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        probe.settimeout(0.5)
        try:
            probe.connect(str(server.socket_path))
        finally:
            probe.close()
        assert server._socket_inode == server.socket_path.stat().st_ino
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_stop_remove_proprio_socket(
    tmp_path: Path, isolated_profiles_dir: Path
):
    """Caso (d): stop() remove o socket quando ainda somos o owner."""
    server = _make_server(tmp_path, "dono.sock")
    await server.start()
    assert server.socket_path.exists()
    await server.stop()
    assert not server.socket_path.exists()


@pytest.mark.asyncio
async def test_stop_preserva_socket_recriado_por_outro(
    tmp_path: Path, isolated_profiles_dir: Path
):
    """Se inode divergir (outro daemon recriou o socket), stop() NÃO apaga."""
    server = _make_server(tmp_path, "compartilhado.sock")
    await server.start()

    # Simula outro daemon recriando o socket: apaga o atual e recria novo nó.
    server.socket_path.unlink()
    server.socket_path.touch()
    novo_inode = server.socket_path.stat().st_ino

    await server.stop()
    # Como o inode atual diverge do registrado, stop não apagou.
    assert server.socket_path.exists()
    assert server.socket_path.stat().st_ino == novo_inode
    server.socket_path.unlink()


# --- AUDIT-FINDING-IPC-DRAFT-RUMBLE-POLICY-01 -----------------------------


@pytest.mark.asyncio
async def test_apply_draft_rumble_aplica_policy(
    tmp_path: Path, isolated_profiles_dir: Path
) -> None:
    """`profile.apply_draft` deve escalar rumble via _apply_rumble_policy.

    Cenário: policy "economia" (mult 0.3) + draft rumble (weak=200, strong=200).
    Esperado:
        - controller.set_rumble chamado com (60, 60) (valores efetivos escalados);
        - daemon.config.rumble_active persiste (200, 200) (valores brutos) para
          o poll loop continuar reaplicando a política a cada tick.
    """
    from dataclasses import dataclass, field
    from unittest.mock import MagicMock

    from hefesto.daemon.lifecycle import DaemonConfig

    @dataclass
    class _FakeDaemon:
        config: DaemonConfig = field(default_factory=DaemonConfig)
        store: object | None = None
        _rumble_engine: object | None = None

    cfg = DaemonConfig()
    cfg.rumble_policy = "economia"  # type: ignore[assignment]
    fake_daemon = _FakeDaemon(config=cfg)

    controller = MagicMock()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=controller, store=store)
    server = IpcServer(
        controller=controller,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "apply_draft_rumble.sock",
        daemon=fake_daemon,
    )

    resultado = await server._handle_profile_apply_draft(
        {"rumble": {"weak": 200, "strong": 200}}
    )

    assert "rumble" in resultado["applied"]
    # Valores efetivos (200 * 0.3 = 60) enviados ao hardware.
    controller.set_rumble.assert_called_once_with(weak=60, strong=60)
    # Valores brutos persistidos para re-asserção do poll loop.
    assert fake_daemon.config.rumble_active == (200, 200)
