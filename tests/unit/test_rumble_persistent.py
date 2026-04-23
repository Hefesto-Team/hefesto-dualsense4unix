"""Testes de persistência de rumble — BUG-RUMBLE-APPLY-IGNORED-01.

Cenários:
  (a) rumble.set (50, 100) → daemon.config.rumble_active == (50, 100).
  (b) Mock controller; 5 ticks de poll loop re-afirmam rumble.
  (c) rumble.stop → rumble_active == (0, 0).
  (d) rumble.passthrough {enabled: True} → rumble_active is None,
      poll loop não chama set_rumble.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from hefesto.core.controller import ControllerState
from hefesto.daemon.ipc_server import IpcServer
from hefesto.daemon.lifecycle import Daemon, DaemonConfig
from hefesto.daemon.state_store import StateStore
from hefesto.profiles.manager import ProfileManager
from hefesto.testing import FakeController

# ---------------------------------------------------------------------------
# Fixture de servidor IPC + daemon compartilhado
# ---------------------------------------------------------------------------


@pytest.fixture
async def server_with_daemon(tmp_path: Path):
    """IpcServer ligado a um Daemon com FakeController. Yields (server, daemon, fc)."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=90, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    cfg = DaemonConfig(
        poll_hz=60,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        auto_reconnect=False,
    )
    daemon = Daemon(controller=fc, store=store, config=cfg)
    manager = ProfileManager(controller=fc, store=store)

    socket_path = tmp_path / "hefesto_test.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon,
    )
    await server.start()
    try:
        yield server, daemon, fc
    finally:
        await server.stop()


# ---------------------------------------------------------------------------
# Cenário (a): rumble.set persiste em daemon.config.rumble_active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rumble_set_persiste_em_config(server_with_daemon: Any) -> None:
    """(a) Após rumble.set (50, 100), daemon.config.rumble_active == (50, 100)."""
    server, daemon, _fc = server_with_daemon

    result = await server._handle_rumble_set({"weak": 50, "strong": 100})

    assert result["status"] == "ok"
    assert result["weak"] == 50
    assert result["strong"] == 100
    assert daemon.config.rumble_active == (50, 100), (
        f"rumble_active deveria ser (50, 100), encontrado: {daemon.config.rumble_active}"
    )


# ---------------------------------------------------------------------------
# Cenário (b): poll loop re-afirma rumble a cada tick que cruza a deadline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_loop_reafirma_rumble() -> None:
    """(b) 5 ticks com next_rumble_assert_at=0 → _reassert_rumble chamado >=1 vez."""
    chamadas: list[tuple[int, int]] = []

    class FakeControllerCaptura(FakeController):
        def set_rumble(self, weak: int = 0, strong: int = 0) -> None:
            chamadas.append((weak, strong))

    states = [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(20)
    ]
    fc = FakeControllerCaptura(transport="usb", states=states)
    store = StateStore()
    cfg = DaemonConfig(
        poll_hz=120,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        auto_reconnect=False,
    )
    daemon = Daemon(controller=fc, store=store, config=cfg)
    # Fixar rumble_active antes de run para re-asserção começar imediatamente.
    daemon.config.rumble_active = (80, 150)
    # FEAT-RUMBLE-POLICY-01: política "max" para receber valores sem escala neste teste.
    daemon.config.rumble_policy = "max"  # type: ignore[assignment]

    task = asyncio.create_task(daemon.run())
    # Aguardar ~300ms (cobre pelo menos 1 janela de 200ms de re-asserção).
    await asyncio.sleep(0.35)
    daemon.stop()
    await task

    # Deve ter chamado set_rumble com (80, 150) pelo menos 1 vez via _reassert_rumble.
    assert any(w == 80 and s == 150 for w, s in chamadas), (
        f"Esperava set_rumble(80, 150) mas chamadas foram: {chamadas}"
    )


# ---------------------------------------------------------------------------
# Cenário (c): rumble.stop → rumble_active == (0, 0)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rumble_stop_persiste_zero(server_with_daemon: Any) -> None:
    """(c) Após rumble.stop, daemon.config.rumble_active == (0, 0)."""
    server, daemon, _fc = server_with_daemon

    # Primeiro fixar valor diferente de zero.
    await server._handle_rumble_set({"weak": 120, "strong": 200})
    assert daemon.config.rumble_active == (120, 200)

    result = await server._handle_rumble_stop({})

    assert result["status"] == "ok"
    assert daemon.config.rumble_active == (0, 0), (
        f"rumble_active deveria ser (0, 0) após stop, encontrado: {daemon.config.rumble_active}"
    )


# ---------------------------------------------------------------------------
# Cenário (d): rumble.passthrough → rumble_active is None, poll não chama set_rumble
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rumble_passthrough_zera_active_e_poll_nao_reafirma() -> None:
    """(d) passthrough=True → rumble_active is None; poll loop não chama set_rumble."""
    chamadas: list[tuple[int, int]] = []

    class FakeControllerCaptura(FakeController):
        def set_rumble(self, weak: int = 0, strong: int = 0) -> None:
            chamadas.append((weak, strong))

    states = [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(30)
    ]
    fc = FakeControllerCaptura(transport="usb", states=states)
    store = StateStore()
    cfg = DaemonConfig(
        poll_hz=120,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        auto_reconnect=False,
    )
    daemon = Daemon(controller=fc, store=store, config=cfg)
    manager = ProfileManager(controller=fc, store=store)

    # Usar handler IPC direto para simular passthrough.
    socket_path = Path("/tmp/hefesto_test_passthrough.sock")
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon,
    )

    # Simular: primeiro fixar rumble, depois passthrough.
    await server._handle_rumble_set({"weak": 60, "strong": 90})
    assert daemon.config.rumble_active == (60, 90)

    result = await server._handle_rumble_passthrough({"enabled": True})
    assert result["status"] == "ok"
    assert result["passthrough"] is True
    assert daemon.config.rumble_active is None, (
        "rumble_active deveria ser None após passthrough, "
        f"encontrado: {daemon.config.rumble_active}"
    )

    # Zerar lista de chamadas acumuladas até aqui.
    chamadas.clear()

    # Rodar poll loop por ~350ms; com rumble_active=None nenhuma re-asserção deve ocorrer.
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.35)
    daemon.stop()
    await task

    # Nenhuma chamada a set_rumble via _reassert_rumble (rumble_active is None).
    # Nota: FakeController.connect() e disconnect() podem chamar set_rumble internamente
    # apenas se o controlador fake usar essa lógica. O FakeController padrão não chama.
    assert chamadas == [], (
        f"Poll loop não deveria chamar set_rumble com rumble_active=None. Chamadas: {chamadas}"
    )
