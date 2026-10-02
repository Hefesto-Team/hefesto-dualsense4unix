"""Corretora final cross-cutting (2026-07-20) — 3 achados de INTERAÇÃO entre ondas."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import ipc_handlers as ih_mod
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    NINTENDO_REAL_OUI,
    ExternalIdentityRegistry,
    ExternalLedSync,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

MAC_1 = "AA:BB:CC:00:00:01"
UNIQ_1 = "aabbcc000001"

NINTENDO_UNIQ = f"{NINTENDO_REAL_OUI}000001"
BITDO_UNIQ = "aabbcc000002"

_NOME_DO_PRO = "Nintendo Co., Ltd. Pro Controller"


class _FakeLedNode:
    """Nó sysfs de LED falso — mesma forma de `_FakeNode` do REPLICA-03."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        pass


def _fake_pydual_handle() -> Any:
    from types import SimpleNamespace

    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    return SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
    )


class TestLedSetRespeitaAAutoridadeDoJogo:
    """Achado 1 (HIGH): combo `display_authority=='game'` + `led.set`/`led.player_set`."""

    def _server(self, node: _FakeLedNode) -> tuple[IpcServer, StateStore, bp.PyDualSenseController]:
        ctl = bp.PyDualSenseController()
        ctl._handles = {MAC_1: _fake_pydual_handle()}
        ctl._sysfs = {MAC_1: node}
        store = StateStore()
        store.update_controller_state(
            ControllerState(
                battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
            )
        )
        manager = ProfileManager(controller=ctl, store=store)
        server = IpcServer(
            controller=ctl,
            store=store,
            profile_manager=manager,
            socket_path=Path("/tmp/nao-usado-corretora-final.sock"),
        )
        return server, store, ctl

    @pytest.mark.asyncio
    async def test_led_set_manual_e_corrigido_pela_cor_do_jogo(self) -> None:
        node = _FakeLedNode()
        server, _store, ctl = self._server(node)
        ctl.set_game_authority_provider(lambda: "game")
        assert ctl.set_game_output_for(MAC_1, led=(0, 255, 0)) is True
        node.rgb_calls.clear()

        resultado = await server._handle_led_set({"rgb": [255, 0, 0]})

        assert resultado["status"] == "ok"
        assert node.rgb_calls[-1] == (0, 255, 0), (
            "a cor do jogo tem de vencer na hora, não só no próximo reassert"
        )

    @pytest.mark.asyncio
    async def test_led_player_set_manual_e_corrigido_pela_cor_do_jogo(self) -> None:
        node = _FakeLedNode()
        server, _store, ctl = self._server(node)
        ctl.set_game_authority_provider(lambda: "game")
        assert ctl.set_game_output_for(
            MAC_1, player_leds=(False, False, True, False, False)
        ) is True
        node.player_calls.clear()

        resultado = await server._handle_led_player_set(
            {"bits": [True, False, False, False, False]}
        )

        assert resultado["status"] == "ok"
        assert node.player_calls[-1] == (True, False, False, False, False)
        assert (False, False, True, False, False) not in node.player_calls

    @pytest.mark.asyncio
    async def test_sem_jogo_a_cor_manual_gruda_normalmente(self) -> None:
        """Regressão: fora de sessão de jogo, `led.set` continua valendo — o"""
        node = _FakeLedNode()
        server, _store, ctl = self._server(node)
        ctl.set_game_authority_provider(lambda: "daemon")

        resultado = await server._handle_led_set({"rgb": [10, 20, 30]})

        assert resultado["status"] == "ok"
        assert node.rgb_calls[-1] == (10, 20, 30)


class TestIdentityRenumberNaoPenduraOEventLoop:
    """Achado 2 (MEDIUM): lock de `lock_for_renumber()` preso por outra thread."""

    @pytest.fixture
    def isolated_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        from hefesto_dualsense4unix.utils import xdg_paths

        def fake_config_dir(ensure: bool = False) -> Path:
            if ensure:
                tmp_path.mkdir(parents=True, exist_ok=True)
            return tmp_path

        monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
        monkeypatch.setattr(id_mod, "_read_boot_id", lambda: "boot-corretora-final")
        monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: "boot-corretora-final")
        return tmp_path

    @pytest.mark.asyncio
    async def test_lock_preso_por_outra_thread_devolve_erro_sem_travar_o_loop(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ih_mod, "_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC", 0.2)

        ext = ExternalIdentityRegistry()
        ext._ordem["aabbcc0000fe"] = 1

        fc = FakeController(transport="usb")
        fc.connect()
        store = StateStore()
        manager = ProfileManager(controller=fc, store=store)

        from dataclasses import dataclass

        @dataclass
        class _FakeDaemon:
            display_authority: str = "daemon"
            identity_registry: Any = None
            external_registry: Any = None

        daemon = _FakeDaemon(external_registry=ext)
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=manager,
            socket_path=isolated_config / "lock_preso.sock",
            daemon=daemon,
        )

        lock = ext.lock_for_renumber()
        lock_preso = threading.Event()
        pode_soltar = threading.Event()

        def _segura_o_lock() -> None:
            with lock:
                lock_preso.set()
                pode_soltar.wait(timeout=5.0)

        thread = threading.Thread(target=_segura_o_lock, daemon=True)
        thread.start()
        try:
            assert lock_preso.wait(timeout=1.0), "thread não tomou o lock"

            batidas = 0

            async def _batida() -> None:
                nonlocal batidas
                for _ in range(15):
                    await asyncio.sleep(0.01)
                    batidas += 1

            tarefa = asyncio.create_task(_batida())
            resultado = await server._handle_identity_renumber({})
            await tarefa

            assert resultado == {"ok": False, "reason": "lock_timeout"}
            assert batidas > 0, "o event loop ficou travado esperando o lock"
        finally:
            pode_soltar.set()
            thread.join(timeout=2.0)

    @pytest.mark.asyncio
    async def test_sem_contencao_continua_funcionando(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regressão: sem lock disputado, o offload continua compactando"""
        monkeypatch.setattr(ih_mod, "_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC", 2.0)

        ext = ExternalIdentityRegistry()
        ext._ordem["aabbcc0000fe"] = 5

        fc = FakeController(transport="usb")
        fc.connect()
        store = StateStore()
        manager = ProfileManager(controller=fc, store=store)

        from dataclasses import dataclass

        @dataclass
        class _FakeDaemon:
            display_authority: str = "daemon"
            identity_registry: Any = None
            external_registry: Any = None

        daemon = _FakeDaemon(external_registry=ext)
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=manager,
            socket_path=isolated_config / "sem_contencao.sock",
            daemon=daemon,
        )

        resultado = await server._handle_identity_renumber({})

        assert resultado == {"ok": True, "renumbered": {"aabbcc0000fe": 1}}
        assert ext.snapshot() == {"aabbcc0000fe": 1}


class TestEnableImuNaoApagaADefesaDosOutrosExternos:
    """Achado 3 (MEDIUM): enable-IMU travando não pode apagar a repintura"""

    def test_enable_imu_trava_mas_o_8bitdo_ja_foi_repintado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ei_mod, "EXTERNAL_PLAYER_LED_ENABLED", True)
        travou = threading.Event()
        pode_prosseguir = threading.Event()

        def _enable_imu_trava(hidraw: str, *, packet_num: int = 0) -> bool:
            travou.set()
            pode_prosseguir.wait(timeout=5.0)
            return True

        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.external_leds.enable_imu",
            _enable_imu_trava,
        )

        escritas: list[tuple[str, int]] = []

        def _apply_player_number(hidraw: str, slot: int) -> bool:
            escritas.append((hidraw, slot))
            return True

        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.external_leds.apply_player_number",
            _apply_player_number,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.external_leds.hid_instance_for_hidraw",
            lambda hidraw: None,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.external_leds.read_player_pattern",
            lambda hid_instance: None,
        )

        inventory = [
            {
                "uniq": NINTENDO_UNIQ,
                "name": _NOME_DO_PRO,
                "bus": "usb",
                "hidraw": "/dev/hidraw-nintendo",
                "evdev_path": "/dev/input/event10",
            },
            {
                "uniq": BITDO_UNIQ,
                "bus": "bluetooth",
                "hidraw": "/dev/hidraw-8bitdo",
                "evdev_path": "/dev/input/event11",
            },
        ]
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_external_gamepads",
            lambda: inventory,
        )

        from types import SimpleNamespace

        registry = ExternalIdentityRegistry()
        daemon = SimpleNamespace(identity_registry=None, display_authority="daemon")
        sync = ExternalLedSync(daemon, registry)

        resultado: dict[str, Any] = {}

        def _tick_em_thread() -> None:
            sync.tick(now=1000.0)
            resultado["terminou"] = True

        thread = threading.Thread(target=_tick_em_thread, daemon=True)
        thread.start()
        try:
            assert travou.wait(timeout=2.0), "enable_imu nunca foi chamado"
            assert ("/dev/hidraw-8bitdo", 2) in escritas or any(
                hidraw == "/dev/hidraw-8bitdo" for hidraw, _slot in escritas
            ), "a defesa de LED do 8BitDo não pode ficar presa atrás do enable-IMU"
            assert any(
                hidraw == "/dev/hidraw-nintendo" for hidraw, _slot in escritas
            ), "a numeração do próprio Nintendo também não pode ficar presa"
        finally:
            pode_prosseguir.set()
            thread.join(timeout=2.0)
        assert resultado.get("terminou") is True

    def test_auto_colors_off_ainda_assim_dispara_o_enable_imu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regressão do invariante documentado (GYRO-02): o enable-IMU é"""
        chamou: list[str] = []

        def _enable_imu(hidraw: str, *, packet_num: int = 0) -> bool:
            chamou.append(hidraw)
            return True

        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.external_leds.enable_imu", _enable_imu
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.discover_external_gamepads",
            lambda: [
                {
                    "uniq": NINTENDO_UNIQ,
                    "name": _NOME_DO_PRO,
                    "bus": "usb",
                    "hidraw": "/dev/hidraw-nintendo",
                    "evdev_path": "/dev/input/event10",
                }
            ],
        )

        from types import SimpleNamespace

        registry = ExternalIdentityRegistry()
        registry_ds = SimpleNamespace(auto_enabled=False)
        daemon = SimpleNamespace(identity_registry=registry_ds, display_authority="daemon")
        sync = ExternalLedSync(daemon, registry)

        sync.tick(now=1000.0)

        assert chamou == ["/dev/hidraw-nintendo"]
