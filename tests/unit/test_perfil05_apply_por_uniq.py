"""PERFIL-05 — escrita viva por-controle alinhada com a persistência (por MAC).

Achado do estudo 22/07: a GUI persistia edição por-controle por `uniq` (MAC),
mas os botões "Aplicar" de Gatilho/Lightbar aplicavam AO VIVO pelo caminho de
índice (`_output_target_key`), que cai em BROADCAST quando o alvo desalinha —
"configurei o controle 2 e mudou todos". Agora `led.set`/`led.player_set`/
`trigger.set` aceitam `uniq` opcional e o daemon aplica via
`apply_output_for` (override por-MAC: registra + escreve SÓ naquele controle).

Falha-sem: no HEAD anterior os handlers ignoravam `uniq` e escreviam pelo
caminho clássico (broadcast/índice).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState, OutputSpec
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

UNIQ = "aabbcc000001"  # faixa forjada aa:bb:cc (gate de anonimato)


class _FakeComApplyFor(FakeController):
    """FakeController que expõe `apply_output_for` e grava as chamadas."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_for_calls: list[tuple[str, OutputSpec]] = []
        self.classic_led_calls: list[tuple[int, int, int]] = []
        self.classic_player_calls: list[tuple[bool, ...]] = []
        self.classic_trigger_calls: list[str] = []

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> None:
        self.apply_for_calls.append((uniq, spec))

    def set_led(self, rgb: tuple[int, int, int]) -> None:
        self.classic_led_calls.append(rgb)
        super().set_led(rgb)

    def set_player_leds(self, bits: tuple[bool, ...]) -> None:  # type: ignore[override]
        self.classic_player_calls.append(bits)

    def set_trigger(self, side: str, effect: Any) -> None:
        self.classic_trigger_calls.append(side)
        super().set_trigger(side, effect)


@pytest.fixture
def server_fc(tmp_path: Path) -> tuple[IpcServer, _FakeComApplyFor, StateStore]:
    fc = _FakeComApplyFor(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    fake_daemon = MagicMock()
    fake_daemon.config = DaemonConfig()
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "perfil05.sock",
        daemon=fake_daemon,
    )
    return server, fc, store


@pytest.mark.asyncio
async def test_led_set_com_uniq_vai_por_apply_output_for(
    server_fc: tuple[IpcServer, _FakeComApplyFor, StateStore],
) -> None:
    server, fc, store = server_fc
    resultado = await server._handle_led_set({"rgb": [10, 20, 30], "uniq": UNIQ})
    assert resultado["status"] == "ok"
    assert fc.apply_for_calls == [(UNIQ, OutputSpec(led=(10, 20, 30)))]
    assert fc.classic_led_calls == []  # NÃO caiu no broadcast/índice
    assert store.manual_trigger_active is True  # trava por categoria intacta


@pytest.mark.asyncio
async def test_led_set_sem_uniq_segue_o_caminho_classico(
    server_fc: tuple[IpcServer, _FakeComApplyFor, StateStore],
) -> None:
    server, fc, _store = server_fc
    await server._handle_led_set({"rgb": [10, 20, 30]})
    assert fc.apply_for_calls == []
    assert fc.classic_led_calls == [(10, 20, 30)]


@pytest.mark.asyncio
async def test_player_set_com_uniq_vai_por_apply_output_for(
    server_fc: tuple[IpcServer, _FakeComApplyFor, StateStore],
) -> None:
    server, fc, _store = server_fc
    bits = [True, False, True, False, True]
    await server._handle_led_player_set({"bits": bits, "uniq": UNIQ})
    assert fc.apply_for_calls == [
        (UNIQ, OutputSpec(player_leds=(True, False, True, False, True)))
    ]
    assert fc.classic_player_calls == []


@pytest.mark.asyncio
async def test_trigger_set_com_uniq_vai_por_apply_output_for(
    server_fc: tuple[IpcServer, _FakeComApplyFor, StateStore],
) -> None:
    server, fc, store = server_fc
    resultado = await server._handle_trigger_set(
        {"side": "left", "mode": "Off", "params": [], "uniq": UNIQ}
    )
    assert resultado["status"] == "ok"
    assert len(fc.apply_for_calls) == 1
    uniq, spec = fc.apply_for_calls[0]
    assert uniq == UNIQ
    assert spec.trigger_left is not None
    assert spec.trigger_right is None
    assert fc.classic_trigger_calls == []
    assert store.manual_trigger_active is True


@pytest.mark.asyncio
async def test_uniq_sem_apply_output_for_no_backend_cai_no_classico(
    tmp_path: Path,
) -> None:
    """FakeController PURO (sem apply_output_for): o `uniq` é ignorado com
    segurança e o caminho clássico roda — nenhum backend antigo quebra."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    fake_daemon = MagicMock()
    fake_daemon.config = DaemonConfig()
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "perfil05b.sock",
        daemon=fake_daemon,
    )
    resultado = await server._handle_led_set({"rgb": [1, 2, 3], "uniq": UNIQ})
    assert resultado["status"] == "ok"
