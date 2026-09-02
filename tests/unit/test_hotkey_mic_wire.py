"""Wire-up do botão de microfone no daemon.

MIC-DA-MESA-ELEICAO-01 (01/09/2026) — ESTE ARQUIVO MUDOU DE CONTRATO, e o
contrato velho está aqui em cima porque é o que ele afirmava:

    1. `BUTTON_DOWN` com `button='mic_btn'` dispara
       `AudioControl.toggle_default_source_mute()`;
    2. o retorno do toggle é repassado ao `controller.set_mic_led()`.

Os dois CAÍRAM por decisão dela: *"O botão de silenciar é confuso e mexendo com
ambos os canais de áudio é péssimo."* O botão agora ELEGE o canal do controle
que apertou, e não muta nada. E a borda não vem mais do `BUTTON_DOWN` — que não
carrega `uniq`, e onde o botão do mic nem chega, porque o `hid-playstation`
consome a borda —, vem do tópico `MIC_DA_MESA`.

O que este arquivo continua guardando, e continua valendo palavra por palavra:

    3. com `mic_button_toggles_system=False`, nada é acionado;
    4. eventos de OUTROS botões não acionam o microfone.

As réguas do gesto novo moram em `test_mic_da_mesa_*`.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController

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
async def test_mic_btn_do_button_down_nao_muta_mais_nada() -> None:
    """O `BUTTON_DOWN` do `mic_btn` deixou de mexer no mudo do sistema.

    ERA o teste `test_mic_btn_down_dispara_toggle_e_set_mic_led`, e o que ele
    exigia é justamente o que ela mandou parar de fazer. A cena é a mesma — o
    botão apertado, com o wire-up ligado —, e o desfecho esperado inverteu:
    **nenhum toggle**.

    Não é "o botão parou de funcionar": o gesto mudou de porta. Ele age pelo
    tópico `MIC_DA_MESA`, que carrega o `uniq` de quem apertou, e o que ele faz
    é ELEGER (ver `test_mic_da_mesa_o_ipc_a_tela_e_o_gesto.py`).
    """
    states = [
        _make_state(frozenset()),
        _make_state(frozenset({"mic_btn"})),
        _make_state(frozenset()),
    ]
    fc = FakeController(states=states)

    mock_audio = MagicMock()
    mock_audio.toggle_default_source_mute.return_value = True  # mutado

    with patch("hefesto_dualsense4unix.integrations.audio_control.AudioControl", return_value=mock_audio):  # noqa: E501
        daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=True))
        await _run_daemon_ticks(daemon, n_ticks=3)

    mock_audio.toggle_default_source_mute.assert_not_called()


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

    with patch("hefesto_dualsense4unix.integrations.audio_control.AudioControl", return_value=mock_audio):  # noqa: E501
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

    with patch("hefesto_dualsense4unix.integrations.audio_control.AudioControl", return_value=mock_audio):  # noqa: E501
        daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=True))
        await _run_daemon_ticks(daemon, n_ticks=3)

    # toggle não foi chamado para botoes que não são mic_btn.
    mock_audio.toggle_default_source_mute.assert_not_called()
    # mic_led nunca foi colocado True (mutado) pelo wire-up.
    assert True not in fc.mic_led_history


@pytest.mark.asyncio
async def test_o_led_do_mic_nao_e_pintado_pelo_button_down() -> None:
    """ERA `test_toggle_retorna_false_set_mic_led_false`, e caiu com o toggle.

    O LED passou a ser pintado da RELEITURA da eleição — nunca do eco de uma
    escrita —, e só pelo caminho que tem `uniq`. Aqui, com o gesto vindo do
    `BUTTON_DOWN`, nada é aceso nem apagado.
    """
    states = [
        _make_state(frozenset()),
        _make_state(frozenset({"mic_btn"})),
        _make_state(frozenset()),
    ]
    fc = FakeController(states=states)

    mock_audio = MagicMock()

    with patch("hefesto_dualsense4unix.integrations.audio_control.AudioControl", return_value=mock_audio):  # noqa: E501
        daemon = Daemon(controller=fc, config=_config_base(mic_button_toggles_system=True))
        await _run_daemon_ticks(daemon, n_ticks=3)

    mock_audio.toggle_default_source_mute.assert_not_called()
    assert fc.mic_led_history == [], "o LED não foi tocado por este caminho"
