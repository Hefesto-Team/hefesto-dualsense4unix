"""Testes do backend resiliente quando o DualSense não está plugado.

Cobre BUG-DAEMON-NO-DEVICE-FATAL-01: `PyDualSenseController.connect()`
deixa de relançar `Exception("No device detected")` e marca estado
offline-OK; setters viram no-op; `read_state()` devolve snapshot neutro;
hot-reconnect funciona quando o controle aparece depois.
"""
from __future__ import annotations

from unittest.mock import patch

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader


def _null_evdev() -> EvdevReader:
    """EvdevReader sem device — força is_available=False."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _FakePydualsense:
    """Stub mínimo de pydualsense para hot-reconnect feliz."""

    def __init__(self) -> None:
        self.connected = True
        self._init_called = False

    def init(self) -> None:
        self._init_called = True

    def close(self) -> None:
        self.connected = False


class TestConnectResiliente:
    def test_connect_swallows_no_device_detected_marks_offline(self) -> None:
        """Quando pydualsense.init() levanta `Exception("No device detected")`,
        o backend marca _offline=True e retorna sem propagar."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())

        class _FakeDs:
            connected = False

            def init(self) -> None:
                raise Exception("No device detected")

        with patch(
            "hefesto_dualsense4unix.core.backend_pydualsense.pydualsense",
            return_value=_FakeDs(),
        ):
            # Não deve levantar.
            inst.connect()

        assert inst._offline is True
        assert inst._ds is None
        assert inst.is_connected() is False

    def test_connect_propaga_outras_excecoes(self) -> None:
        """Erros distintos de "No device detected" continuam propagando para
        o `connect_with_retry` fazer backoff."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())

        class _FakeDs:
            def init(self) -> None:
                raise RuntimeError("hidraw permission denied")

        with patch(
            "hefesto_dualsense4unix.core.backend_pydualsense.pydualsense",
            return_value=_FakeDs(),
        ):
            try:
                inst.connect()
            except RuntimeError as exc:
                assert "hidraw permission denied" in str(exc)
            else:
                raise AssertionError("connect deveria ter relançado RuntimeError")

        # Após exceção, _offline NÃO foi marcado (não é offline-OK).
        assert inst._offline is False
        assert inst._ds is None


class TestReadStateOffline:
    def test_read_state_offline_retorna_defaults(self) -> None:
        """Controller offline → snapshot neutro, sem exceção."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        inst._offline = True
        # _ds permanece None — read_state deve aceitar.

        state = inst.read_state()
        assert state.connected is False
        assert state.battery_pct == 0
        assert state.l2_raw == 0
        assert state.r2_raw == 0
        assert state.raw_lx == 128
        assert state.raw_ly == 128
        assert state.raw_rx == 128
        assert state.raw_ry == 128
        assert state.buttons_pressed == frozenset()


class TestSettersOffline:
    def test_setters_offline_sao_noop(self) -> None:
        """Todos os setters de output viram no-op silencioso quando offline."""
        from hefesto_dualsense4unix.core.controller import TriggerEffect

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        # _ds=None → caminho offline.

        # Não deve levantar nem chamar nada do pydualsense.
        inst.set_trigger("left", TriggerEffect(mode=0))
        inst.set_trigger("right", TriggerEffect(mode=0))
        inst.set_led((10, 20, 30))
        inst.set_rumble(weak=10, strong=20)
        inst.set_mic_led(True)
        inst.set_player_leds((True, False, True, False, True))

        # get_battery offline retorna 0.
        assert inst.get_battery() == 0


class TestHotReconnect:
    def test_connect_apos_offline_recupera_quando_device_aparece(self) -> None:
        """Sequência: 1ª connect → "No device detected" (offline);
        2ª connect → device aparece, _offline limpa e _ds populado."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())

        # 1ª chamada — sem device.
        class _MissingDs:
            connected = False

            def init(self) -> None:
                raise Exception("No device detected")

        with patch(
            "hefesto_dualsense4unix.core.backend_pydualsense.pydualsense",
            return_value=_MissingDs(),
        ):
            inst.connect()
        assert inst._offline is True
        assert inst._ds is None

        # 2ª chamada — device aparece. Usa um stub que detect_transport aceita.
        present = _FakePydualsense()
        # Atributo conType com .name='USB' para _detect_transport reconhecer.
        present.conType = type("CT", (), {"name": "USB"})()  # type: ignore[attr-defined]

        with patch(
            "hefesto_dualsense4unix.core.backend_pydualsense.pydualsense",
            return_value=present,
        ):
            inst.connect()

        assert inst._offline is False
        assert inst._ds is present
        assert inst.is_connected() is True
        assert inst._transport == "usb"

    def test_connect_idempotente_quando_ja_conectado(self) -> None:
        """connect() chamado novamente quando já conectado é no-op
        (não tenta reinicializar pydualsense)."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        present = _FakePydualsense()
        inst._ds = present  # type: ignore[assignment]
        inst._offline = False

        # Patch para falhar se invocado — provando que connect() retorna cedo.
        def _explode() -> None:
            raise AssertionError("pydualsense() não deveria ser invocado")

        with patch(
            "hefesto_dualsense4unix.core.backend_pydualsense.pydualsense",
            side_effect=_explode,
        ):
            inst.connect()

        assert inst._ds is present
