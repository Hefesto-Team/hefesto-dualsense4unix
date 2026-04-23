"""Testes da interface `IController` e das validações dos dataclasses."""
from __future__ import annotations

import pytest

from hefesto.core.controller import (
    ControllerState,
    IController,
    TriggerEffect,
)
from hefesto.testing import FakeController


class TestTriggerEffect:
    def test_defaults_are_zero(self) -> None:
        eff = TriggerEffect(mode=0)
        assert eff.forces == (0, 0, 0, 0, 0, 0, 0)

    def test_mode_out_of_byte_raises(self) -> None:
        with pytest.raises(ValueError, match="mode fora de byte"):
            TriggerEffect(mode=300)

    def test_forces_wrong_arity_raises(self) -> None:
        with pytest.raises(ValueError, match="forces precisa ter 7"):
            TriggerEffect(mode=1, forces=(0, 0, 0))  # type: ignore[arg-type]

    def test_force_byte_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="forces\\[3\\] fora de byte"):
            TriggerEffect(mode=1, forces=(0, 0, 0, 256, 0, 0, 0))


class TestControllerState:
    def test_basic_snapshot(self) -> None:
        s = ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        assert s.battery_pct == 50
        assert s.raw_lx == 128

    def test_battery_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="battery_pct"):
            ControllerState(
                battery_pct=150, l2_raw=0, r2_raw=0, connected=True, transport="usb"
            )

    def test_raw_byte_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="l2_raw"):
            ControllerState(
                battery_pct=50, l2_raw=999, r2_raw=0, connected=True, transport="usb"
            )


class TestFakeController:
    def test_implements_interface(self) -> None:
        fc = FakeController()
        assert isinstance(fc, IController)

    def test_read_before_connect_fails(self) -> None:
        fc = FakeController()
        with pytest.raises(RuntimeError, match="não conectado"):
            fc.read_state()

    def test_default_state_after_connect(self) -> None:
        fc = FakeController(transport="usb")
        fc.connect()
        state = fc.read_state()
        assert state.connected is True
        assert state.transport == "usb"
        assert state.battery_pct == 75

    def test_replay_sequence(self) -> None:
        states = [
            ControllerState(
                battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="bt"
            ),
            ControllerState(
                battery_pct=79, l2_raw=50, r2_raw=100, connected=True, transport="bt"
            ),
            ControllerState(
                battery_pct=79, l2_raw=200, r2_raw=255, connected=True, transport="bt"
            ),
        ]
        fc = FakeController(transport="bt", states=states)
        fc.connect()
        assert fc.read_state() == states[0]
        assert fc.read_state() == states[1]
        assert fc.read_state() == states[2]
        assert fc.read_state() == states[2]  # últimos repetem

    def test_transport_bt_propaga(self) -> None:
        fc = FakeController(transport="bt")
        fc.connect()
        assert fc.get_transport() == "bt"
        assert fc.read_state().transport == "bt"

    def test_commands_gravados(self) -> None:
        fc = FakeController()
        fc.connect()
        fc.set_trigger("right", TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0)))
        fc.set_led((255, 0, 128))
        fc.set_rumble(weak=100, strong=200)
        kinds = [c.kind for c in fc.commands]
        assert kinds == ["connect", "set_trigger", "set_led", "set_rumble"]

    def test_disconnect_marks_disconnected(self) -> None:
        fc = FakeController()
        fc.connect()
        assert fc.is_connected() is True
        fc.disconnect()
        assert fc.is_connected() is False


class TestPyDualSenseController:
    """Smoke test do backend real via mock do pydualsense.

    Não conecta a hardware físico. Valida que a classe respeita
    `IController`, inicializa sem quebrar e aceita comandos.
    """

    def test_class_implements_interface(self) -> None:
        from hefesto.core.backend_pydualsense import PyDualSenseController
        inst = PyDualSenseController()
        assert isinstance(inst, IController)

    def test_require_sem_connect_falha(self) -> None:
        from hefesto.core.backend_pydualsense import PyDualSenseController
        inst = PyDualSenseController()
        with pytest.raises(RuntimeError, match="não inicializado"):
            inst.read_state()

    def test_coerce_mode_conhecido(self) -> None:
        from pydualsense.enums import TriggerModes

        from hefesto.core.backend_pydualsense import PyDualSenseController

        coerced = PyDualSenseController._coerce_mode(TriggerModes.Rigid.value)
        assert coerced == TriggerModes.Rigid

    def test_coerce_mode_invalido_mantem_raw(self) -> None:
        from hefesto.core.backend_pydualsense import PyDualSenseController

        coerced = PyDualSenseController._coerce_mode(0x99)
        assert coerced == 0x99

    def test_read_state_usa_analog_trigger_values(self) -> None:
        """HOTFIX-1: trigger analog vem de L2_value/R2_value, não L2/R2."""
        from hefesto.core.backend_pydualsense import PyDualSenseController
        from hefesto.core.evdev_reader import EvdevReader

        class FakeState:
            L2 = False
            R2 = True
            L2_value = 180  # meio-pressionado
            R2_value = 255  # totalmente pressionado
            LX = 128
            LY = 128
            RX = 128
            RY = 128

        class FakeBattery:
            Level = 73

        class FakeDs:
            state = FakeState()
            battery = FakeBattery()
            connected = True

        # Força fallback pro caminho pydualsense usando reader sem device
        null_reader = EvdevReader(device_path=None)
        null_reader._device_path = None  # força is_available=False
        inst = PyDualSenseController(evdev_reader=null_reader)
        inst._ds = FakeDs()  # type: ignore[assignment]
        inst._transport = "usb"

        state = inst.read_state()
        assert state.l2_raw == 180
        assert state.r2_raw == 255
        assert state.battery_pct == 73
        assert state.connected is True
        assert state.transport == "usb"

    def test_read_state_battery_zerado_quando_ausente(self) -> None:
        """Se ds.battery ausente ou Level None, retorna 0 sem explodir."""
        from hefesto.core.backend_pydualsense import PyDualSenseController
        from hefesto.core.evdev_reader import EvdevReader

        class FakeState:
            L2_value = 0
            R2_value = 0
            LX = 128
            LY = 128
            RX = 128
            RY = 128

        class FakeDs:
            state = FakeState()
            battery = None
            connected = True

        null_reader = EvdevReader(device_path=None)
        null_reader._device_path = None
        inst = PyDualSenseController(evdev_reader=null_reader)
        inst._ds = FakeDs()  # type: ignore[assignment]
        inst._transport = "bt"

        state = inst.read_state()
        assert state.battery_pct == 0

    def test_is_connected_false_quando_disconnected_prop(self) -> None:
        """HOTFIX-1: is_connected usa ds.connected, não conType."""
        from hefesto.core.backend_pydualsense import PyDualSenseController

        class FakeDs:
            connected = False

        inst = PyDualSenseController()
        inst._ds = FakeDs()  # type: ignore[assignment]
        assert inst.is_connected() is False

    def test_is_connected_true_quando_connected_prop(self) -> None:
        from hefesto.core.backend_pydualsense import PyDualSenseController

        class FakeDs:
            connected = True

        inst = PyDualSenseController()
        inst._ds = FakeDs()  # type: ignore[assignment]
        assert inst.is_connected() is True

    def test_read_state_usa_evdev_quando_disponivel(self) -> None:
        """HOTFIX-2: se evdev tem device, backend le dele (não do pydualsense)."""
        from hefesto.core.backend_pydualsense import PyDualSenseController
        from hefesto.core.evdev_reader import EvdevReader, EvdevSnapshot

        class FakeState:
            # Valores pydualsense — Não devem aparecer no resultado
            L2_value = 0
            R2_value = 0
            LX = 128
            LY = 128
            RX = 128
            RY = 128

        class FakeBattery:
            Level = 50

        class FakeDs:
            state = FakeState()
            battery = FakeBattery()
            connected = True

        # Reader com snapshot customizado (simula evdev reportando pressão)
        class FakeReader(EvdevReader):
            def __init__(self) -> None:
                super().__init__(device_path=None)
                self._fake_snap = EvdevSnapshot(
                    l2_raw=210, r2_raw=255, lx=30, ly=200, rx=128, ry=128
                )

            def is_available(self) -> bool:
                return True

            def snapshot(self) -> EvdevSnapshot:
                return self._fake_snap

        reader = FakeReader()
        inst = PyDualSenseController(evdev_reader=reader)
        inst._ds = FakeDs()  # type: ignore[assignment]
        inst._transport = "usb"

        state = inst.read_state()
        # Triggers e sticks vêm do evdev, não do pydualsense
        assert state.l2_raw == 210
        assert state.r2_raw == 255
        assert state.raw_lx == 30
        assert state.raw_ly == 200
        # Battery continua vindo do pydualsense (evdev não expõe)
        assert state.battery_pct == 50

    def test_read_state_includes_mic_btn_when_hid_bit_set(self) -> None:
        """Quando ds.state.micBtn=True, 'mic_btn' aparece em buttons_pressed (INFRA-MIC-HID-01)."""
        from hefesto.core.backend_pydualsense import PyDualSenseController
        from hefesto.core.evdev_reader import EvdevReader, EvdevSnapshot

        class FakeStateMic:
            L2_value = 0
            R2_value = 0
            LX = 128
            LY = 128
            RX = 128
            RY = 128
            micBtn = True  # noqa: N815 — simula atributo pydualsense (HID-raw bit 2)

        class FakeBattery:
            Level = 80

        class FakeDsMic:
            state = FakeStateMic()
            battery = FakeBattery()
            connected = True

        class FakeReaderWithButtons(EvdevReader):
            def __init__(self) -> None:
                super().__init__(device_path=None)
                self._fake_snap = EvdevSnapshot(
                    l2_raw=0, r2_raw=0,
                    buttons_pressed=frozenset({"cross"}),
                )

            def is_available(self) -> bool:
                return True

            def snapshot(self) -> EvdevSnapshot:
                return self._fake_snap

        reader = FakeReaderWithButtons()
        inst = PyDualSenseController(evdev_reader=reader)
        inst._ds = FakeDsMic()  # type: ignore[assignment]
        inst._transport = "usb"

        state = inst.read_state()
        assert "mic_btn" in state.buttons_pressed, (
            "mic_btn deve estar em buttons_pressed quando ds.state.micBtn=True"
        )
        # Botão evdev também deve estar preservado
        assert "cross" in state.buttons_pressed

    def test_read_state_mic_btn_false_when_hid_bit_clear(self) -> None:
        """Quando ds.state.micBtn=False, 'mic_btn' NÃO aparece em buttons_pressed."""
        from hefesto.core.backend_pydualsense import PyDualSenseController
        from hefesto.core.evdev_reader import EvdevReader, EvdevSnapshot

        class FakeStateNoMic:
            L2_value = 0
            R2_value = 0
            LX = 128
            LY = 128
            RX = 128
            RY = 128
            micBtn = False  # noqa: N815 — simula atributo pydualsense

        class FakeBattery:
            Level = 80

        class FakeDsNoMic:
            state = FakeStateNoMic()
            battery = FakeBattery()
            connected = True

        class FakeReaderEmpty(EvdevReader):
            def __init__(self) -> None:
                super().__init__(device_path=None)
                self._fake_snap = EvdevSnapshot()

            def is_available(self) -> bool:
                return True

            def snapshot(self) -> EvdevSnapshot:
                return self._fake_snap

        reader = FakeReaderEmpty()
        inst = PyDualSenseController(evdev_reader=reader)
        inst._ds = FakeDsNoMic()  # type: ignore[assignment]
        inst._transport = "usb"

        state = inst.read_state()
        assert "mic_btn" not in state.buttons_pressed

    def test_controller_state_buttons_pressed_default_vazio(self) -> None:
        """ControllerState.buttons_pressed default é frozenset vazio (INFRA-BUTTON-EVENTS-01)."""
        s = ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        assert s.buttons_pressed == frozenset()
        assert isinstance(s.buttons_pressed, frozenset)

    def test_controller_state_buttons_pressed_imutavel(self) -> None:
        """ControllerState é frozen — buttons_pressed não pode ser substituído."""
        s = ControllerState(
            battery_pct=50, l2_raw=0, r2_raw=0, connected=True, transport="usb",
            buttons_pressed=frozenset({"l1", "r1"}),
        )
        assert "l1" in s.buttons_pressed
        assert "r1" in s.buttons_pressed
        with pytest.raises((AttributeError, TypeError)):
            s.buttons_pressed = frozenset()  # type: ignore[misc]

    def test_fake_controller_set_mic_led_grava_historico(self) -> None:
        """FakeController.set_mic_led registra em mic_led_history (INFRA-SET-MIC-LED-01)."""
        fc = FakeController()
        fc.connect()
        fc.set_mic_led(True)
        fc.set_mic_led(False)
        fc.set_mic_led(True)
        assert fc.mic_led_history == [True, False, True]

    def test_fake_controller_mic_btn_pressed_propaga(self) -> None:
        """mic_btn_pressed=True injeta 'mic_btn' em buttons_pressed (INFRA-MIC-HID-01)."""
        fc = FakeController(transport="usb")
        fc.mic_btn_pressed = True
        fc.connect()
        state = fc.read_state()
        assert "mic_btn" in state.buttons_pressed
