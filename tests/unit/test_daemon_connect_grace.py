"""Settling/grace pós-conexão (BUG-DAEMON-CONNECT-GHOST-INPUT-01).

Ao conectar o DualSense, o estado inicial cru (HID-raw com `micBtn` fantasma +
snapshot evdev ainda populando) era tratado como input real:
  - `mic_btn` fantasma → BUTTON_DOWN → mic_button_loop → muta o microfone.
  - botões no 1º snapshot → BUTTON_DOWN + sequência de teclas (Super/Alt+Tab…).

A correção introduz um período de assentamento (`INPUT_GRACE_SEC`) + baseline
no 1º tick conectado. Estes testes INJETAM o estado fantasma via FakeController
(o FakeController não reproduz o HID sujo real) e provam que:

1. Durante o settling, NENHUM BUTTON_DOWN/tecla/toggle do mic ocorre.
2. Depois do settling, pressionar funciona normalmente.
3. Botão fisicamente segurado na conexão só dispara ao soltar e re-pressionar.
4. Reconexão rearma o settling.
5. `UinputKeyboardDevice.prime` semeia o edge-tracker sem emitir.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import (
    INPUT_GRACE_SEC,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController


def _state(buttons: frozenset[str] | None = None) -> ControllerState:
    return ControllerState(
        battery_pct=80,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
        buttons_pressed=buttons or frozenset(),
    )


def _config(**over: object) -> DaemonConfig:
    base: dict[str, object] = dict(
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False,
        ps_button_action="none",
        mic_button_toggles_system=False,
    )
    base.update(over)
    return DaemonConfig(**base)  # type: ignore[arg-type]


class _GhostThenIdle(FakeController):
    """Retorna `ghost` em todo read enquanto o teste não liberar; usado para
    simular um botão fantasma/segurado presente desde o 1º read_state."""

    def __init__(self, ghost: Iterable[str]) -> None:
        super().__init__(transport="usb", states=[_state(frozenset(ghost))])


# ---------------------------------------------------------------------------
# 1. Settling suprime o mute fantasma do microfone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_input_settling_suppresses_mic_btn_down() -> None:
    """mic_btn presente no 1º read NÃO dispara BUTTON_DOWN nem toggle do mic
    durante o grace-period (default 0.3s)."""
    fc = _GhostThenIdle(ghost={"mic_btn"})
    bus = EventBus()
    store = StateStore()

    mock_audio = MagicMock()
    mock_audio.toggle_default_source_mute.return_value = True

    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)

    with patch(
        "hefesto_dualsense4unix.integrations.audio_control.AudioControl",
        return_value=mock_audio,
    ):
        daemon = Daemon(
            controller=fc,
            bus=bus,
            store=store,
            config=_config(mic_button_toggles_system=True),
        )
        run_task = asyncio.create_task(daemon.run())
        # Janela inteiramente DENTRO do grace (0.15s < 0.3s).
        await asyncio.sleep(0.15)
        # Ainda em settling — confirma que de fato lemos estado (ticks correm).
        assert store.counter("poll.tick") >= 1
        assert store.counter("input.settling.tick") >= 1
        daemon.stop()
        await run_task

    # Nenhum BUTTON_DOWN publicado e nenhum toggle do microfone.
    assert down_queue.qsize() == 0
    assert store.counter("button.down.emitted") == 0
    mock_audio.toggle_default_source_mute.assert_not_called()
    assert True not in fc.mic_led_history


@pytest.mark.asyncio
async def test_input_settling_publishes_state_update_and_battery() -> None:
    """Durante o settling, STATE_UPDATE e bateria continuam sendo publicados —
    só o input emulado é suprimido (não a telemetria)."""
    fc = _GhostThenIdle(ghost={"mic_btn"})
    bus = EventBus()
    store = StateStore()

    state_queue = bus.subscribe(EventTopic.STATE_UPDATE)
    battery_queue = bus.subscribe(EventTopic.BATTERY_CHANGE)

    daemon = Daemon(controller=fc, bus=bus, store=store, config=_config())
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.15)  # dentro do grace
    daemon.stop()
    await run_task

    assert state_queue.qsize() >= 1
    assert battery_queue.qsize() >= 1  # 1ª leitura de bateria sempre emite
    assert store.counter("poll.tick") >= 1


# ---------------------------------------------------------------------------
# 2. Settling suprime as teclas fantasma (keyboard emulation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_input_settling_suppresses_keyboard_dispatch() -> None:
    """Com `options` no snapshot evdev desde o 1º tick, o device de teclado é
    SEMEADO (prime) mas NÃO recebe dispatch durante o settling — zero teclas."""
    fc = FakeController(transport="usb", states=[_state()])
    # evdev snapshot com 'options' (binding default → KEY_LEFTMETA).
    snap = MagicMock()
    snap.buttons_pressed = ["options"]
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = snap
    fc._evdev = mock_evdev

    bus = EventBus()
    store = StateStore()
    daemon = Daemon(controller=fc, bus=bus, store=store, config=_config())

    # Device de teclado mockado (simula já iniciado).
    mock_kbd = MagicMock()
    daemon._keyboard_device = mock_kbd

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.15)  # dentro do grace
    daemon.stop()
    await run_task

    # Nenhum dispatch (zero teclas emitidas) durante o settling…
    mock_kbd.dispatch.assert_not_called()
    # …mas o edge-tracker foi semeado com o baseline (prime chamado).
    assert mock_kbd.prime.called
    primed = mock_kbd.prime.call_args[0][0]
    assert "options" in primed


# ---------------------------------------------------------------------------
# 3. Depois do settling, pressionar funciona
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_press_after_settling_emits_button_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Botão pressionado DEPOIS do grace dispara BUTTON_DOWN normalmente."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.05
    )
    fc = FakeController(transport="usb", states=[_state()])  # começa sem botões
    bus = EventBus()
    store = StateStore()
    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)

    daemon = Daemon(controller=fc, bus=bus, store=store, config=_config())
    run_task = asyncio.create_task(daemon.run())

    # Passa o grace (0.05s) com folga e SÓ ENTÃO injeta a pressão.
    await asyncio.sleep(0.15)
    assert down_queue.qsize() == 0  # nada disparou no settling (estava vazio)
    fc.set_buttons(["cross"])
    await asyncio.sleep(0.10)
    daemon.stop()
    await run_task

    # cross pressionado pós-grace → exatamente um BUTTON_DOWN.
    downs = []
    while not down_queue.empty():
        downs.append(down_queue.get_nowait())
    assert any(e["button"] == "cross" for e in downs)
    assert store.counter("button.down.emitted") >= 1


@pytest.mark.asyncio
async def test_mic_toggle_after_settling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Toggle manual do mic (apertando o botão de verdade) funciona após o grace."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.05
    )
    fc = FakeController(transport="usb", states=[_state()])
    bus = EventBus()
    store = StateStore()

    mock_audio = MagicMock()
    mock_audio.toggle_default_source_mute.return_value = True

    with patch(
        "hefesto_dualsense4unix.integrations.audio_control.AudioControl",
        return_value=mock_audio,
    ):
        daemon = Daemon(
            controller=fc,
            bus=bus,
            store=store,
            config=_config(mic_button_toggles_system=True),
        )
        run_task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.15)  # passa o grace
        mock_audio.toggle_default_source_mute.assert_not_called()
        fc.set_buttons(["mic_btn"])  # aperto real pós-grace
        await asyncio.sleep(0.12)
        daemon.stop()
        await run_task

    mock_audio.toggle_default_source_mute.assert_called()
    assert True in fc.mic_led_history


# ---------------------------------------------------------------------------
# 4. Botão segurado na conexão só dispara após soltar e re-pressionar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_held_button_at_connect_only_fires_after_release_repress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Botão fisicamente segurado durante a conexão NÃO dispara até ser solto
    e re-pressionado (baseline no 1º tick + re-sync durante o grace)."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.05
    )
    fc = FakeController(transport="usb", states=[_state()])
    fc.set_buttons(["cross"])  # cross já segurado na conexão (ghost/held)
    bus = EventBus()
    store = StateStore()
    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)

    daemon = Daemon(controller=fc, bus=bus, store=store, config=_config())
    run_task = asyncio.create_task(daemon.run())

    # Mantém segurado bem além do grace: como é baseline, NÃO deve disparar.
    await asyncio.sleep(0.18)
    assert down_queue.qsize() == 0, "botão segurado na conexão disparou indevidamente"

    # Solta…
    fc.set_buttons([])
    await asyncio.sleep(0.06)
    # …e re-pressiona → AGORA dispara.
    fc.set_buttons(["cross"])
    await asyncio.sleep(0.06)
    daemon.stop()
    await run_task

    downs = []
    while not down_queue.empty():
        downs.append(down_queue.get_nowait())
    cross_downs = [e for e in downs if e["button"] == "cross"]
    assert len(cross_downs) == 1, f"esperado 1 DOWN pós re-press, obtido {cross_downs}"


# ---------------------------------------------------------------------------
# 5. Reconexão rearma o settling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_arm_input_grace_advances_ready_at() -> None:
    """`_arm_input_grace` empurra `_input_ready_at` para o futuro usando o relógio
    do event loop + INPUT_GRACE_SEC."""
    fc = FakeController(transport="usb", states=[_state()])
    daemon = Daemon(controller=fc, config=_config())
    assert daemon._input_ready_at == 0.0

    loop = asyncio.get_running_loop()
    before = loop.time()
    daemon._arm_input_grace()
    after = loop.time()

    assert daemon._input_ready_at >= before + INPUT_GRACE_SEC
    assert daemon._input_ready_at <= after + INPUT_GRACE_SEC + 0.01


def test_arm_input_grace_noop_without_loop() -> None:
    """Fora de um event loop, `_arm_input_grace` é no-op (não levanta)."""
    fc = FakeController(transport="usb", states=[_state()])
    daemon = Daemon(controller=fc, config=_config())
    daemon._arm_input_grace()  # sem loop rodando
    assert daemon._input_ready_at == 0.0


@pytest.mark.asyncio
async def test_reconnect_rearms_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    """`connection.reconnect` rearma o settling após reconectar."""
    from hefesto_dualsense4unix.daemon import connection as conn

    fc = FakeController(transport="usb", states=[_state()])
    fc.connect()
    daemon = Daemon(controller=fc, config=_config(auto_reconnect=True))
    daemon._executor = MagicMock()

    # Backoff curto e _run_blocking síncrono (sem executor real).
    monkeypatch.setattr(daemon.config, "reconnect_backoff_sec", 0.0)

    async def _run_blocking(fn, *args):  # type: ignore[no-untyped-def]
        return fn(*args)

    monkeypatch.setattr(daemon, "_run_blocking", _run_blocking)

    loop = asyncio.get_running_loop()
    before = loop.time()
    await conn.reconnect(daemon)

    assert daemon._input_ready_at >= before + INPUT_GRACE_SEC
    assert fc.is_connected() is True


@pytest.mark.asyncio
async def test_disconnect_reconnect_cycle_resuppresses_ghost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ciclo unplug→replug detectado pelo poll loop reaplica o settling: um
    mic_btn fantasma logo após o replug NÃO toggla o microfone."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.10
    )

    class _Flappy(FakeController):
        """Conecta; depois de `online_reads` leituras cai (is_connected=False)
        por uma janela e volta com mic_btn fantasma no 1º read pós-replug."""

        def __init__(self) -> None:
            super().__init__(transport="usb", states=[_state()])
            self._reads = 0
            self._ghost_after_replug = False

        def read_state(self) -> ControllerState:
            self._reads += 1
            if self._ghost_after_replug:
                return _state(frozenset({"mic_btn"}))
            return _state()

        def drop(self) -> None:
            self._connected = False

        def replug_with_ghost(self) -> None:
            self._connected = True
            self._ghost_after_replug = True

    fc = _Flappy()
    bus = EventBus()
    store = StateStore()
    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)

    mock_audio = MagicMock()
    mock_audio.toggle_default_source_mute.return_value = True

    with patch(
        "hefesto_dualsense4unix.integrations.audio_control.AudioControl",
        return_value=mock_audio,
    ):
        daemon = Daemon(
            controller=fc,
            bus=bus,
            store=store,
            config=_config(mic_button_toggles_system=True),
        )
        run_task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.18)  # passa o grace inicial
        # Unplug: o poll loop verá is_connected()==False e rearmará a borda.
        fc.drop()
        await asyncio.sleep(0.05)
        # Replug com mic_btn fantasma no 1º read.
        fc.replug_with_ghost()
        # Janela DENTRO do novo grace (0.10s).
        await asyncio.sleep(0.06)
        daemon.stop()
        await run_task

    # O fantasma pós-replug foi suprimido pelo settling rearmado.
    assert down_queue.qsize() == 0
    mock_audio.toggle_default_source_mute.assert_not_called()


# ---------------------------------------------------------------------------
# 6. UinputKeyboardDevice.prime semeia sem emitir
# ---------------------------------------------------------------------------


def test_keyboard_prime_sets_state_without_emitting() -> None:
    """`prime` define `_pressed_buttons` (filtrado por bindings) sem emitir; o
    dispatch seguinte com o mesmo conjunto não gera press."""
    from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

    dev = UinputKeyboardDevice()
    fake_uinput_dev = MagicMock()
    dev._device = fake_uinput_dev
    dev._uinput_mod = MagicMock()

    # 'options' tem binding default; 'xyz' não — deve ser filtrado.
    dev.prime(frozenset({"options", "xyz"}))
    assert dev._pressed_buttons == frozenset({"options"})
    # Nada foi emitido pelo prime.
    fake_uinput_dev.emit.assert_not_called()

    # dispatch com o MESMO conjunto não dispara press (já é baseline).
    dev.dispatch(frozenset({"options"}))
    fake_uinput_dev.emit.assert_not_called()

    # Soltar agora SIM emite release (transição True→False).
    dev.dispatch(frozenset())
    assert fake_uinput_dev.emit.called


def test_keyboard_prime_noop_without_device() -> None:
    """`prime` é no-op se o device ainda não foi criado (estado consistente
    com `dispatch`, que também é no-op)."""
    from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

    dev = UinputKeyboardDevice()
    dev.prime(frozenset({"options"}))
    assert dev._pressed_buttons == frozenset()
