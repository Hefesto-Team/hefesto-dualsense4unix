"""Garante que _evdev.snapshot() é chamado exatamente 1x por tick no poll loop.

Contexto (armadilha A-09): antes do refactor REFACTOR-HOTKEY-EVDEV-01,
_dispatch_mouse_emulation e o consumer de hotkey chamavam snapshot()
independentemente — 2 snapshots/tick com ambos ativos. Este teste prova
que após o refactor há exatamente 1 chamada por tick, independentemente
de quantos consumidores estejam ativos.
"""
from __future__ import annotations

import asyncio
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto.core.controller import ControllerState
from hefesto.daemon.lifecycle import Daemon, DaemonConfig
from hefesto.testing import FakeController

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _mk_states(n: int) -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="usb",
        )
        for _ in range(n)
    ]


class _FakeSnap:
    """Snapshot evdev mínimo para testes."""

    buttons_pressed: ClassVar[list[str]] = []


class _FakeSnapComBotoes:
    """Snapshot evdev com botões pré-definidos."""

    buttons_pressed: ClassVar[list[str]] = ["cross", "ps"]


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_chamado_exatamente_uma_vez_por_tick_sem_consumidores():
    """Com evdev disponível mas sem mouse nem hotkey ativos, snapshot() deve ser
    chamado 1x por tick (via _evdev_buttons_once, mesmo que nenhum consumidor use).

    Valida que o refactor não introduziu chamada extra em _poll_loop.
    """
    n_ticks = 10
    call_counter: list[int] = []

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.side_effect = lambda: (call_counter.append(1) or _FakeSnap())
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    # Aguarda n_ticks ticks a 200Hz (~50ms)
    await asyncio.sleep(0.06)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks, f"poll.tick esperado >= {n_ticks}, obtido {ticks}"
    # snapshot() deve ser chamado exatamente 1x por tick
    assert len(call_counter) == ticks, (
        f"snapshot() chamado {len(call_counter)}x para {ticks} ticks "
        f"(esperado 1:1 — sem duplicatas)"
    )


@pytest.mark.asyncio
async def test_snapshot_chamado_exatamente_uma_vez_por_tick_com_hotkey_e_mouse():
    """Com hotkey_manager E mouse_device ativos, snapshot() deve ser chamado
    1x por tick (não 2x como era antes do refactor REFACTOR-HOTKEY-EVDEV-01).

    Este é o cenário crítico da armadilha A-09: 2 consumidores → antes=20 chamadas,
    depois=10 chamadas para 10 ticks.
    """
    n_ticks = 10
    call_counter: list[int] = []

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.side_effect = lambda: (call_counter.append(1) or _FakeSnap())
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
        ),
    )

    # Instancia HotkeyManager diretamente (sem _start_hotkey_manager para
    # evitar dependência de steam_launcher no ambiente de CI).
    from hefesto.integrations.hotkey_daemon import HotkeyManager

    daemon._hotkey_manager = HotkeyManager()

    # Mock de mouse device que registra chamadas a dispatch().
    dispatch_calls: list[Any] = []
    mock_mouse = MagicMock()
    mock_mouse.dispatch.side_effect = lambda **kw: dispatch_calls.append(kw)
    daemon._mouse_device = mock_mouse

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.06)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks, f"poll.tick esperado >= {n_ticks}, obtido {ticks}"

    # CRITÉRIO PRINCIPAL: 1 snapshot por tick, não 2.
    assert len(call_counter) == ticks, (
        f"snapshot() chamado {len(call_counter)}x para {ticks} ticks "
        f"(esperado 1:1 — refactor A-09 falhou se > ticks)"
    )

    # Subproduto: dispatch foi chamado uma vez por tick (mouse ativo).
    assert len(dispatch_calls) == ticks, (
        f"mouse.dispatch chamado {len(dispatch_calls)}x para {ticks} ticks"
    )


@pytest.mark.asyncio
async def test_snapshot_nao_chamado_quando_evdev_indisponivel():
    """Se evdev.is_available() retorna False, snapshot() não deve ser chamado."""
    n_ticks = 5
    call_counter: list[int] = []

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = False
    mock_evdev.snapshot.side_effect = lambda: call_counter.append(1)
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.04)
    daemon.stop()
    await run_task

    assert len(call_counter) == 0, (
        f"snapshot() foi chamado {len(call_counter)}x mesmo com is_available=False"
    )


@pytest.mark.asyncio
async def test_snapshot_excecao_retorna_frozenset_vazio():
    """Se snapshot() lança exceção, _evdev_buttons_once retorna frozenset() vazio
    e o poll loop continua sem travar.
    """
    n_ticks = 5
    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.side_effect = RuntimeError("evdev explodiu")
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.04)
    daemon.stop()
    await run_task

    # Poll loop continuou normalmente apesar da exceção no evdev.
    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks, (
        f"poll loop parou precocemente ({ticks} ticks) após exceção no evdev"
    )


@pytest.mark.asyncio
async def test_botoes_passados_ao_hotkey_manager_e_ao_mouse():
    """Botões retornados por _evdev_buttons_once devem chegar ao hotkey_manager.observe
    E ao mouse_device.dispatch — o mesmo conjunto, não snapshots independentes.
    """
    n_ticks = 5
    botoes_esperados = frozenset(["cross", "ps"])

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _FakeSnapComBotoes()
    fc._evdev = mock_evdev

    hotkey_observes: list[frozenset[str]] = []

    from hefesto.integrations.hotkey_daemon import HotkeyManager

    class _SpyHotkey(HotkeyManager):
        def observe(self, pressed: Any, *, now: Any = None) -> Any:  # type: ignore[override]
            hotkey_observes.append(frozenset(pressed))
            return super().observe(pressed, now=now)

    dispatch_buttons: list[frozenset[str]] = []
    mock_mouse = MagicMock()
    mock_mouse.dispatch.side_effect = lambda **kw: dispatch_buttons.append(
        kw.get("buttons", frozenset())
    )

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
        ),
    )
    daemon._hotkey_manager = _SpyHotkey()
    daemon._mouse_device = mock_mouse

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.04)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks

    # Hotkey e mouse receberam os mesmos botões em todos os ticks.
    assert all(b == botoes_esperados for b in hotkey_observes), (
        f"hotkey_manager recebeu botões incorretos: {hotkey_observes[:3]!r}"
    )
    assert all(b == botoes_esperados for b in dispatch_buttons), (
        f"mouse.dispatch recebeu botões incorretos: {dispatch_buttons[:3]!r}"
    )
