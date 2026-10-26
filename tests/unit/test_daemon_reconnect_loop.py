"""Testes do reconnect_loop não-bloqueante (BUG-DAEMON-NO-DEVICE-FATAL-01)."""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController


def _mk_state() -> ControllerState:
    return ControllerState(
        battery_pct=75,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
    )


PRAZO_S = 5.0


async def _esperar(condicao: Callable[[], bool], o_que: str, prazo_s: float = PRAZO_S) -> None:
    """Espera a CONDIÇÃO, não o relógio: sob carga o `run()` chega ao IPC tarde, e 0,15 s fixos
    desmentiam o teste. Estourou o prazo, a mensagem diz o que não aconteceu."""
    limite = time.monotonic() + prazo_s
    while not condicao():
        if time.monotonic() >= limite:
            pytest.fail(f"em {prazo_s:.0f} s não aconteceu: {o_que}")
        await asyncio.sleep(0.01)


def _controle(*, plugado: bool) -> FakeController:
    """O dublê com a tomada pedida: desplugado, o `connect()` não liga até o `plugar()`."""
    return FakeController(transport="usb", states=[_mk_state()], plugado=plugado)


@pytest.mark.asyncio
@pytest.mark.parametrize("passo_lento_s", [0.0, 0.3])
async def test_run_inicia_ipc_antes_de_conectar(
    monkeypatch: pytest.MonkeyPatch, passo_lento_s: float
) -> None:
    """Subsystems sobem mesmo quando o controle não conecta — `_start_ipc` é chamado ANTES do
    primeiro `connect()`. A espera é pela condição, e o `passo_lento_s` põe à mão o que a carga
    da máquina faz: um passo do `run()` antes do IPC que demora o dobro do prazo de hoje."""
    fc = _controle(plugado=False)
    bus = EventBus()
    eventos: list[str] = []

    async def _fake_start_ipc(self):  # type: ignore[no-untyped-def]
        eventos.append("ipc")
        self._ipc_server = object()

    monkeypatch.setattr(Daemon, "_start_ipc", _fake_start_ipc, raising=True)

    if passo_lento_s:
        async def _passo_lento(self):  # type: ignore[no-untyped-def]
            await asyncio.sleep(passo_lento_s)

        monkeypatch.setattr(Daemon, "_sync_game_signal", _passo_lento, raising=True)

    conecta_original = fc.connect

    def _conecta_e_anota() -> None:
        eventos.append("connect")
        conecta_original()

    monkeypatch.setattr(fc, "connect", _conecta_e_anota)

    daemon = Daemon(
        controller=fc,
        bus=bus,
        config=DaemonConfig(
            poll_hz=120,
            ipc_enabled=True,
            udp_enabled=False,
            autoswitch_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    try:
        await _esperar(lambda: "ipc" in eventos, "o `run()` chamar `_start_ipc` (o IPC subir)")
        await _esperar(
            lambda: "connect" in eventos, "o `run()` tentar o primeiro `connect()` do controle"
        )
        assert eventos.index("ipc") < eventos.index("connect"), (
            f"o IPC tem de subir ANTES do primeiro connect: {eventos}"
        )
        assert daemon._ipc_server is not None
        assert fc.is_connected() is False
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_reconnect_loop_publica_controller_connected_em_transicao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """reconnect_loop emite CONTROLLER_CONNECTED quando hardware aparece"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    fc = _controle(plugado=False)
    bus = EventBus()

    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    queue = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    daemon = Daemon(
        controller=fc,
        bus=bus,
        config=DaemonConfig(
            poll_hz=120,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await _esperar(
        lambda: fc.tentativas_de_conexao >= 1, "o `run()` tentar o `connect()` inicial, sem tomada"
    )
    fc.plugar()
    payload = await asyncio.wait_for(queue.get(), timeout=2.0)
    assert payload == {"transport": "usb", "uniq": None}
    daemon.stop()
    await asyncio.wait_for(run_task, timeout=2.0)


class _DepthLock:
    """RLock instrumentado: expõe a profundidade de aquisição vigente."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.depth = 0

    def __enter__(self) -> _DepthLock:
        self._lock.acquire()
        self.depth += 1
        return self

    def __exit__(self, *exc: object) -> None:
        self.depth -= 1
        self._lock.release()


def _config() -> DaemonConfig:
    """Config hermética padrão destes testes (sem IPC/UDP/autoswitch)."""
    return DaemonConfig(
        poll_hz=120,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        keyboard_emulation_enabled=False,
        mic_button_toggles_system=False,
    )


def _intercepta_upgrade(
    monkeypatch: pytest.MonkeyPatch, lock: _DepthLock
) -> list[dict[str, object]]:
    """Troca `upgrade_primary_vpad_to_uhid` por um espião que registra a"""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    chamadas: list[dict[str, object]] = []

    def _fake_upgrade(_daemon: object) -> bool:
        chamadas.append(
            {
                "thread": threading.current_thread().name,
                "lock_depth": lock.depth,
            }
        )
        return True

    monkeypatch.setattr(gp, "upgrade_primary_vpad_to_uhid", _fake_upgrade)
    return chamadas


@pytest.mark.asyncio
async def test_hotplug_tardio_promove_o_vpad_exatamente_uma_vez(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VPAD-01: a transição offline→online do probe chama a promoção 1x — e só"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    lock = _DepthLock()
    chamadas = _intercepta_upgrade(monkeypatch, lock)

    fc = _controle(plugado=False)
    bus = EventBus()
    queue = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    daemon = Daemon(controller=fc, bus=bus, config=_config())
    daemon._emu_lock = lock

    run_task = asyncio.create_task(daemon.run())
    try:
        await _esperar(
            lambda: fc.tentativas_de_conexao >= 1,
            "o `run()` tentar o `connect()` inicial, sem tomada",
        )
        fc.plugar()
        await asyncio.wait_for(queue.get(), timeout=2.0)
        for _ in range(40):
            if chamadas:
                break
            await asyncio.sleep(0.05)
        assert len(chamadas) == 1, "offline→online tem que promover exatamente 1x"
        assert str(chamadas[0]["thread"]).startswith("hefesto-hid"), (
            "a promoção deve rodar via _run_blocking (executor) — síncrona no "
            "event loop ela congelaria o input por até UHID_BIND_TIMEOUT_S"
        )
        assert chamadas[0]["lock_depth"] == 1, (
            "a promoção deve segurar o _emu_lock (serializada com os toggles "
            "de emulação do IPC/GUI)"
        )
        await asyncio.sleep(0.2)
        assert len(chamadas) == 1
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_conectado_no_boot_so_o_gancho_do_boot_promove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Já conectado no boot: quem promove é o gancho do lifecycle (síncrono,"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    lock = _DepthLock()
    chamadas = _intercepta_upgrade(monkeypatch, lock)

    fc = _controle(plugado=True)
    bus = EventBus()
    queue = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    daemon = Daemon(controller=fc, bus=bus, config=_config())
    daemon._emu_lock = lock

    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.wait_for(queue.get(), timeout=2.0)
        await asyncio.sleep(0.3)
        assert len(chamadas) == 1, "conectado no boot = só o gancho do boot"
        assert not str(chamadas[0]["thread"]).startswith("hefesto-hid"), (
            "a chamada única deve ser a do boot (lifecycle, thread do event "
            "loop) — o reconnect_loop não viu transição nenhuma"
        )
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_offline_continuo_nao_promove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem transição não há promoção: controle nunca aparece, vpad em paz."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    lock = _DepthLock()
    chamadas = _intercepta_upgrade(monkeypatch, lock)

    fc = _controle(plugado=False)
    bus = EventBus()
    daemon = Daemon(controller=fc, bus=bus, config=_config())
    daemon._emu_lock = lock

    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.sleep(0.3)
        assert chamadas == []
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_reconnect_loop_respeita_stop_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_stop_event sinalizado durante o sleep do probe finaliza a task em ≤500ms."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 30.0)
    monkeypatch.setattr(conn_mod, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 30.0)

    fc = _controle(plugado=False)
    bus = EventBus()
    daemon = Daemon(
        controller=fc,
        bus=bus,
        config=DaemonConfig(
            poll_hz=120,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.2)

    daemon.stop()
    await asyncio.wait_for(run_task, timeout=0.7)
