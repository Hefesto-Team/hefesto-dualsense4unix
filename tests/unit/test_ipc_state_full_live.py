"""CLUSTER-IPC-STATE-PROFILE-01 Bug A — `daemon.state_full` ao vivo.

Garante que o handler IPC retorna o último `state` lido pelo `_poll_loop`
(`daemon._last_state`) em vez do snapshot do StateStore — que pode estar
estagnado quando o evdev_reader não conectou ou o backend HID-raw está
em fallback degenerado.

Critérios cobertos:
  1. daemon._last_state preferido sobre store.controller_state.
  2. buttons populados de state.buttons_pressed (sem chamar `_evdev.snapshot`).
  3. fallback gracioso quando _last_state é None: cai no store.
  4. fallback final quando ambos None: campos neutros canônicos.
  5. log `state_stale_neutral_warning` aciona após 3 chamadas com
     state neutro + controller conectado.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController


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


def _make_state(
    *,
    lx: int = 128,
    ly: int = 128,
    rx: int = 128,
    ry: int = 128,
    l2: int = 0,
    r2: int = 0,
    buttons: frozenset[str] = frozenset(),
    connected: bool = True,
) -> ControllerState:
    return ControllerState(
        battery_pct=80,
        l2_raw=l2,
        r2_raw=r2,
        connected=connected,
        transport="usb",
        raw_lx=lx,
        raw_ly=ly,
        raw_rx=rx,
        raw_ry=ry,
        buttons_pressed=buttons,
    )


@pytest.fixture
async def running_server(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
    )
    daemon_mock._rumble_engine = None

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon_mock,
    )
    await server.start()
    try:
        yield server, socket_path, fc, store, daemon_mock
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_state_full_prefere_last_state_do_daemon(running_server: Any) -> None:
    """Quando daemon._last_state está populado, vence sobre store.controller_state."""
    _server, socket_path, _fc, store, daemon = running_server

    # Store tem um state estagnado (neutro)
    store.update_controller_state(_make_state(lx=128, ly=128))
    # Daemon tem o state LIVE com cross apertado e stick mexido
    daemon._last_state = _make_state(
        lx=200, ly=50, l2=180, buttons=frozenset({"cross", "l1"})
    )

    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")

    assert result["lx"] == 200
    assert result["ly"] == 50
    assert result["l2_raw"] == 180
    assert result["buttons"] == ["cross", "l1"]


@pytest.mark.asyncio
async def test_state_full_fallback_para_store_quando_last_state_none(
    running_server: Any,
) -> None:
    """Sem daemon._last_state, cai no store.controller_state."""
    _server, socket_path, _fc, store, daemon = running_server

    daemon._last_state = None
    store.update_controller_state(
        _make_state(lx=99, ly=33, r2=120, buttons=frozenset({"square"}))
    )

    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")

    assert result["lx"] == 99
    assert result["ly"] == 33
    assert result["r2_raw"] == 120
    assert result["buttons"] == ["square"]


@pytest.mark.asyncio
async def test_state_full_neutro_quando_ambos_none(running_server: Any) -> None:
    """Sem store nem daemon._last_state, retorna neutro canônico."""
    _server, socket_path, _fc, _store, daemon = running_server
    daemon._last_state = None
    # Store fresco (sem update_controller_state) → controller_state é None

    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")

    assert result["lx"] == 128
    assert result["ly"] == 128
    assert result["rx"] == 128
    assert result["ry"] == 128
    assert result["l2_raw"] == 0
    assert result["r2_raw"] == 0
    assert result["buttons"] == []
    assert result["connected"] is False


@pytest.mark.asyncio
async def test_state_full_buttons_de_state_buttons_pressed(
    running_server: Any,
) -> None:
    """`buttons` vem de state.buttons_pressed; não chama _evdev.snapshot.

    Validação indireta da armadilha A-09: o handler IPC NÃO deve adicionar
    consumidor de evdev paralelo ao poll loop. O FakeController não tem
    `_evdev`, então qualquer tentativa de chamar `_evdev.snapshot()` aqui
    quebraria — ainda assim o teste deve passar porque buttons sai de
    state.buttons_pressed.
    """
    _server, socket_path, fc, _store, daemon = running_server
    assert getattr(fc, "_evdev", None) is None  # FakeController sem evdev
    daemon._last_state = _make_state(
        buttons=frozenset({"triangle", "circle", "r2"})
    )

    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")

    assert result["buttons"] == ["circle", "r2", "triangle"]


@pytest.mark.asyncio
async def test_state_full_aciona_warning_quando_neutro_persistente(
    running_server: Any,
) -> None:
    """Após 3 chamadas com state neutro + connected, contador stale incrementa."""
    _server, socket_path, _fc, store, daemon = running_server
    daemon._last_state = _make_state(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), connected=True,
    )

    async with IpcClient.connect(socket_path) as client:
        for _ in range(4):
            await client.call("daemon.state_full")

    # bump foi chamado pelo menos 3 vezes (3 chamadas = 3 incrementos)
    assert store.counter("state_full.stale_neutral") >= 3


class TestPlayerPorControle:
    """LEIGO-01b — o `state_full` carrega o número do jogador de cada controle.

    A GUI rotulava os cards por POSIÇÃO na lista (`idx+1`), o que mente: com o
    co-op desligado todos os controles alimentam o mesmo gamepad virtual (um
    jogador só) e, com ele ligado, os índices são reusados. O número só pode
    vir do daemon — então ele tem de estar no payload.
    """

    @pytest.mark.asyncio
    async def test_controllers_ganham_o_campo_player(self, running_server: Any) -> None:
        _server, socket_path, fc, _store, daemon = running_server
        # Controller com o método real de descrição (o FakeController não o tem)
        # e daemon sem gamepad virtual: ninguém é jogador (modo desktop).
        fc.describe_controllers = lambda: [  # type: ignore[attr-defined]
            {"index": 0, "connected": True, "transport": "usb",
             "is_primary": True, "uniq": "aabbcc001100"},
        ]
        daemon._gamepad_device = None

        async with IpcClient.connect(socket_path) as client:
            result = await client.call("daemon.state_full")

        # STATUS-01/COR-05/BT-03: além do `player`, cada entrada carrega os
        # campos por controle — aqui tudo None/"desconhecida" (FakeController
        # sem sysfs/desired, sem coop, sem registry, `_last_state` None).
        assert result["controllers"] == [
            {"index": 0, "connected": True, "transport": "usb",
             "is_primary": True, "uniq": "aabbcc001100", "player": None,
             "player_slot": None, "lightbar_rgb": None, "lightbar_on": False,
             "lightbar_source": "desconhecida", "inputs": None,
             "vpad_backend": None, "vpad_motivo": None},
        ]

    @pytest.mark.asyncio
    async def test_payload_segue_serializavel_com_daemon_dublado(
        self, running_server: Any
    ) -> None:
        """Blindagem: `_coop_manager` MagicMock não pode estourar o json.dumps.

        O daemon dos testes é um MagicMock — sem coerção, `player_indexes()`
        devolveria um mock e o `state_full` inteiro deixaria de serializar
        (a mesma armadilha que o `_as_str_or_none` já cobria).
        """
        _server, socket_path, fc, _store, _daemon = running_server
        fc.describe_controllers = lambda: [  # type: ignore[attr-defined]
            {"index": 0, "connected": True, "transport": "usb",
             "is_primary": True, "uniq": "aabbcc001100"},
        ]

        async with IpcClient.connect(socket_path) as client:
            result = await client.call("daemon.state_full")

        assert result["controllers"][0]["player"] is None


class TestVpadDegradadoNoEstado:
    """VPAD-05 — fallback nunca silencioso: o `state_full` carrega o dado
    honesto da degradação (`gamepad_emulation.degraded`/`degraded_motivo`).

    É daqui que o banner da GUI (fase 2) e o doctor consomem — flavor dualsense
    em backend uinput = vpad sem hidraw (vibração in-game morta) e sem launch
    option segura; o motivo é o que a factory pendurou no vpad.
    """

    @pytest.mark.asyncio
    async def test_dualsense_em_uinput_expoe_degraded_e_motivo(
        self, running_server: Any
    ) -> None:
        from types import SimpleNamespace

        _server, socket_path, _fc, _store, daemon = running_server
        daemon._gamepad_device = SimpleNamespace(
            flavor="dualsense", backend="uinput", ff_supported=True,
            fallback_motivo="uhid_bind_falhou", ff_play_count=0,
            ff_last_sent=(0, 0),
        )

        async with IpcClient.connect(socket_path) as client:
            result = await client.call("daemon.state_full")

        gp = result["gamepad_emulation"]
        assert gp["backend"] == "uinput"
        assert gp["degraded"] is True
        assert gp["degraded_motivo"] == "uhid_bind_falhou"

    @pytest.mark.asyncio
    async def test_uhid_saudavel_nao_e_degradado(self, running_server: Any) -> None:
        from types import SimpleNamespace

        _server, socket_path, _fc, _store, daemon = running_server
        daemon._gamepad_device = SimpleNamespace(
            flavor="dualsense", backend="uhid", ff_supported=True,
            fallback_motivo=None, ff_play_count=0, ff_last_sent=(0, 0),
        )

        async with IpcClient.connect(socket_path) as client:
            result = await client.call("daemon.state_full")

        gp = result["gamepad_emulation"]
        assert gp["backend"] == "uhid"
        assert gp["degraded"] is False
        assert "degraded_motivo" not in gp

    @pytest.mark.asyncio
    async def test_mascara_xbox_nao_e_degradada(self, running_server: Any) -> None:
        """Xbox é uinput por design — o dado não pode acusar degradação."""
        from types import SimpleNamespace

        _server, socket_path, _fc, _store, daemon = running_server
        daemon._gamepad_device = SimpleNamespace(
            flavor="xbox", backend="uinput", ff_supported=True,
            fallback_motivo=None, ff_play_count=0, ff_last_sent=(0, 0),
        )

        async with IpcClient.connect(socket_path) as client:
            result = await client.call("daemon.state_full")

        gp = result["gamepad_emulation"]
        assert gp["degraded"] is False
        assert "degraded_motivo" not in gp
