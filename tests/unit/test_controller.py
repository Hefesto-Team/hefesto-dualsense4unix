"""Testes da interface `IController` e das validações dos dataclasses."""
from __future__ import annotations

import pytest

from hefesto.core.controller import (
    ControllerState,
    IController,
    TriggerEffect,
)
from tests.fixtures.fake_controller import FakeController


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
        with pytest.raises(RuntimeError, match="nao conectado"):
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
        with pytest.raises(RuntimeError, match="nao inicializado"):
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
        """HOTFIX-1: trigger analog vem de L2_value/R2_value, nao L2/R2."""
        from hefesto.core.backend_pydualsense import PyDualSenseController

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

        inst = PyDualSenseController()
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

        inst = PyDualSenseController()
        inst._ds = FakeDs()  # type: ignore[assignment]
        inst._transport = "bt"

        state = inst.read_state()
        assert state.battery_pct == 0

    def test_is_connected_false_quando_disconnected_prop(self) -> None:
        """HOTFIX-1: is_connected usa ds.connected, nao conType."""
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
