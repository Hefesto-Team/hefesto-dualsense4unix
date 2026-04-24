"""Testes de wire-up do botao Mic no Daemon (FEAT-HOTKEY-MIC-01).

Verifica que:
1. BUTTON_DOWN com button='mic_btn' dispara AudioControl.toggle_default_source_mute().
2. O retorno de toggle e repassado ao controller.set_mic_led().
3. Com mic_button_toggles_system=False, o subscriber não e criado.
4. Eventos de outros botoes não disparam toggle.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from hefesto.core.controller import ControllerState
from hefesto.core.events import EventTopic
from hefesto.daemon.lifecycle import Daemon, DaemonConfig
from hefesto.testing.fake_controller import FakeController

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(buttons: frozenset[str] | None = None) -> ControllerState:
    """Cria ControllerState com botoes opcionais."""
    return ControllerState(
        battery_pct=75,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
        buttons_pressed=buttons or frozenset(),
    )


async def _run_daemon_ticks(
    daemon: Daemon,
    n_ticks: int,
    *,
    timeout: float = 5.0,
) -> None:
    """Executa o daemon por n_ticks de poll e para.

    Substitui _poll_loop por versão limitada que publica BUTTON_DOWN
    e para apos n_ticks, permitindo que _mic_button_loop consuma eventos.
    """
    poll_count = 0

    async def _limited_poll() -> None:
        nonlocal poll_count
        period = 1.0 / max(1, daemon.config.poll_hz)
        loop = asyncio.get_running_loop()
        previous_buttons: frozenset[str] = frozenset()

        while not daemon._is_stopping():
            if poll_count >= n_ticks:
                daemon.stop()
                break
            try:
                state = await loop.run_in_executor(daemon._executor, daemon.controller.read_state)
            except Exception:
                break
            daemon.store.update_controller_state(state)
            daemon.bus.publish(EventTopic.STATE_UPDATE, state)
            daemon.store.bump("poll.tick")

            current_buttons = state.buttons_pressed
            pressed_now = current_buttons - previous_buttons
            for name in sorted(pressed_now):
                daemon.bus.publish(EventTopic.BUTTON_DOWN, {"button": name, "pressed": True})
            previous_buttons = current_buttons
            poll_count += 1
            await asyncio.sleep(period)

    daemon._poll_loop = _limited_poll  # type: ignore[method-assign]
    await asyncio.wait_for(daemon.run(), timeout=timeout)


def _config_base(*, mic_button_toggles_system: bool = True) -> DaemonConfig:
    """Cria DaemonConfig minima para testes."""
    return DaemonConfig(
        poll_hz=60,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        ps_button_action="none",
        mic_button_toggles_system=mic_button_toggles_system,
    )


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mic_btn_down_dispara_toggle_e_set_mic_led() -> None:
    """BUTTON_DOWN mic_btn aciona toggle_default_source_mute e set_mic_led."""
    states = [
        _make_state(frozenset()),
        _make_state(frozenset({"mic_btn"})),
        _make_state(frozenset()),
    ]
    fc = FakeController(states=states)

    mock_audio = MagicMock()
    mock_audio.toggle_default_source_mute.return_value = True  # mutado

    with patch("hefesto.integrations.audio_control.AudioControl", return_value=mock_audio):
        daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=True))
        await _run_daemon_ticks(daemon, n_ticks=3)

    mock_audio.toggle_default_source_mute.assert_called()
    assert True in fc.mic_led_history


@pytest.mark.asyncio
async def test_mic_button_toggles_system_false_nao_subscreve() -> None:
    """Com mic_button_toggles_system=False, o subscriber não é criado e toggle não é chamado.

    Pós-AUDIT-FINDING-PROFILE-MIC-LED-RESET-01: `apply_led_settings` não toca
    mic_led; portanto mic_led_history fica vazio se nenhum wire-up de hotkey
    mic disparar. O invariante deste teste é que toggle não foi chamado e que
    _audio permanece None.
    """
    states = [
        _make_state(frozenset({"mic_btn"})),
        _make_state(frozenset()),
    ]
    fc = FakeController(states=states)

    mock_audio = MagicMock()

    with patch("hefesto.integrations.audio_control.AudioControl", return_value=mock_audio):
        daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=False))
        await _run_daemon_ticks(daemon, n_ticks=2)

    # _audio nunca foi criado — nenhum subscriber registrado.
    assert daemon._audio is None
    # toggle_default_source_mute nunca foi invocado.
    mock_audio.toggle_default_source_mute.assert_not_called()
    # mic_led nunca foi colocado True pelo wire-up (somente False pode vir do perfil).
    assert True not in fc.mic_led_history


@pytest.mark.asyncio
async def test_outros_botoes_nao_disparam_toggle() -> None:
    """Eventos de outros botoes (cross, circle) não chamam toggle do microfone.

    Pós-AUDIT-FINDING-PROFILE-MIC-LED-RESET-01: `apply_led_settings` não toca
    mic_led. O invariante deste teste é que toggle não foi chamado e mic_led
    nunca ficou True (mutado) pelo wire-up.
    """
    states = [
        _make_state(frozenset({"cross"})),
        _make_state(frozenset({"circle"})),
        _make_state(frozenset()),
    ]
    fc = FakeController(states=states)

    mock_audio = MagicMock()
    mock_audio.toggle_default_source_mute.return_value = False

    with patch("hefesto.integrations.audio_control.AudioControl", return_value=mock_audio):
        daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=True))
        await _run_daemon_ticks(daemon, n_ticks=3)

    # toggle não foi chamado para botoes que não são mic_btn.
    mock_audio.toggle_default_source_mute.assert_not_called()
    # mic_led nunca foi colocado True (mutado) pelo wire-up.
    assert True not in fc.mic_led_history


@pytest.mark.asyncio
async def test_toggle_retorna_false_set_mic_led_false() -> None:
    """Quando toggle retorna False (não mutado), set_mic_led e chamado com False."""
    states = [
        _make_state(frozenset()),
        _make_state(frozenset({"mic_btn"})),
        _make_state(frozenset()),
    ]
    fc = FakeController(states=states)

    mock_audio = MagicMock()
    mock_audio.toggle_default_source_mute.return_value = False  # não mutado

    with patch("hefesto.integrations.audio_control.AudioControl", return_value=mock_audio):
        daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=True))
        await _run_daemon_ticks(daemon, n_ticks=3)

    mock_audio.toggle_default_source_mute.assert_called()
    assert False in fc.mic_led_history
