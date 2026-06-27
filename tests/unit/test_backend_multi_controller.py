"""Testes do suporte a N DualSense (FEAT-DSX-MULTI-CONTROLLER-01).

Cobre:
  - fan-out de escrita (gatilhos, lightbar, rumble, LEDs de player, LED do mic)
    para TODOS os controles conectados;
  - detecção/dedupe de múltiplos controles em `_enumerate_device_keys`;
  - hotplug-in: controle plugado em runtime recebe o PERFIL ATIVO;
  - hotplug-out: controle removido é fechado (sem vazar handle) e o primário é
    promovido quando cai;
  - NÃO-regressão do caso de 1 controle.

O INPUT/EMULAÇÃO permanece single-controller (lê do primário) — coberto pelos
testes de `read_state` em `test_controller.py`.
"""
from __future__ import annotations

from unittest.mock import patch

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import TriggerEffect
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader


def _null_evdev() -> EvdevReader:
    """EvdevReader sem device — força is_available=False (não interfere)."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _FakeTrigger:
    def __init__(self) -> None:
        self.mode: object = None
        self.forces: list[int] = [0] * 7

    def setForce(self, idx: int, value: int) -> None:  # noqa: N802 — API pydualsense
        self.forces[idx] = value


class _FakeLight:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []
        self.playerNumber: object = None  # atributo espelhado da pydualsense

    def setColorI(self, r: int, g: int, b: int) -> None:  # noqa: N802 — API pydualsense
        self.colors.append((r, g, b))


class _FakeAudio:
    def __init__(self) -> None:
        self.mic_led_history: list[bool] = []

    def setMicrophoneLED(self, flag: bool) -> None:  # noqa: N802 — API pydualsense
        self.mic_led_history.append(flag)


class _FakeHandle:
    """Stub de um handle pydualsense aberto (um controle)."""

    def __init__(self, *, connected: bool = True, transport_name: str = "USB") -> None:
        self.connected = connected
        self.triggerL = _FakeTrigger()
        self.triggerR = _FakeTrigger()
        self.light = _FakeLight()
        self.audio = _FakeAudio()
        self.left_motor: list[int] = []
        self.right_motor: list[int] = []
        self.closed = False
        self.conType = type("CT", (), {"name": transport_name})()

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.left_motor.append(intensity)

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.right_motor.append(intensity)

    def close(self) -> None:
        self.closed = True


def _with_two_handles() -> tuple[PyDualSenseController, _FakeHandle, _FakeHandle]:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    h1, h2 = _FakeHandle(), _FakeHandle()
    inst._handles = {"a": h1, "b": h2}  # type: ignore[dict-item]
    inst._primary_key = "a"
    return inst, h1, h2


class TestFanOut:
    def test_set_led_aplica_em_todos(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_led((10, 20, 30))
        assert h1.light.colors == [(10, 20, 30)]
        assert h2.light.colors == [(10, 20, 30)]

    def test_set_trigger_aplica_em_todos(self) -> None:
        from pydualsense.enums import TriggerModes

        inst, h1, h2 = _with_two_handles()
        inst.set_trigger("right", TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0)))
        for h in (h1, h2):
            assert h.triggerR.mode == TriggerModes(1)
            assert h.triggerR.forces == [5, 200, 0, 0, 0, 0, 0]
            # lado oposto intacto
            assert h.triggerL.forces == [0] * 7

    def test_set_rumble_aplica_em_todos(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_rumble(weak=10, strong=20)
        for h in (h1, h2):
            assert h.left_motor == [20]
            assert h.right_motor == [10]

    def test_set_mic_led_aplica_em_todos(self) -> None:
        inst, h1, h2 = _with_two_handles()
        inst.set_mic_led(True)
        assert h1.audio.mic_led_history == [True]
        assert h2.audio.mic_led_history == [True]

    def test_set_player_leds_aplica_em_todos(self) -> None:
        from pydualsense.enums import PlayerID

        inst, h1, h2 = _with_two_handles()
        inst.set_player_leds((True, False, True, False, False))
        # bit0 + bit2 = 1 + 4 = 5
        assert h1.light.playerNumber == PlayerID(5)
        assert h2.light.playerNumber == PlayerID(5)

    def test_handle_que_falha_nao_derruba_os_outros(self) -> None:
        """Uma exceção num handle não impede a escrita nos demais."""
        inst, h1, h2 = _with_two_handles()

        def _boom(*_a: object, **_k: object) -> None:
            raise RuntimeError("device morto")

        h1.light.setColorI = _boom  # type: ignore[method-assign]
        inst.set_led((1, 2, 3))  # não deve propagar
        assert h2.light.colors == [(1, 2, 3)]


class TestEnumerate:
    def test_enumerate_device_keys_dedupe_e_filtra(self) -> None:
        import hidapi

        class _DI:
            # Espelha a API real do hidapi: serial_number vem de wchar_t* → str
            # (ou None); path vem de char* → bytes.
            def __init__(self, pid: int, path: bytes, serial: str | None) -> None:
                self.vendor_id = 0x054C
                self.product_id = pid
                self.path = path
                self.serial_number = serial

        fake = [
            _DI(0x0CE6, b"/dev/hidraw0", "AA:BB"),
            _DI(0x0CE6, b"/dev/hidraw1", "AA:BB"),  # mesmo serial -> dedupe
            _DI(0x0DF2, b"/dev/hidraw2", "CC:DD"),  # Edge
            _DI(0x9999, b"/dev/hidraw3", "EE:FF"),  # não-DualSense -> filtra
            _DI(0x0CE6, b"/dev/hidraw4", None),  # sem serial -> chave por path
        ]

        with patch.object(hidapi, "enumerate", lambda vendor_id=0: fake):
            keys = PyDualSenseController._enumerate_device_keys()

        got = {key: (path, edge) for key, path, edge in keys}
        assert len(keys) == 3
        assert got["AA:BB"] == (b"/dev/hidraw0", False)  # 1º vence o dedupe
        assert got["CC:DD"] == (b"/dev/hidraw2", True)  # Edge detectado
        assert "EE:FF" not in got  # PID não-DualSense filtrado
        assert got["/dev/hidraw4"] == (b"/dev/hidraw4", False)  # fallback path


class TestHotplug:
    def test_hotplug_in_reaplica_perfil_no_novo_controle(self) -> None:
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        inst._handles = {"a": h1}  # type: ignore[dict-item]
        inst._primary_key = "a"

        # Define o "perfil ativo" no controle existente (popula _desired).
        inst.set_trigger("right", TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0)))
        inst.set_led((255, 0, 0))
        inst.set_player_leds((True, False, True, False, False))
        inst.set_mic_led(True)

        # Controle "b" é plugado em runtime.
        h2 = _FakeHandle()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[
                ("a", b"/dev/hidraw0", False),
                ("b", b"/dev/hidraw1", False),
            ],
        ), patch.object(PyDualSenseController, "_open_one", return_value=h2):
            inst.connect()

        # O novo controle recebeu o perfil ativo.
        assert h2.light.colors[-1] == (255, 0, 0)
        assert h2.triggerR.forces == [5, 200, 0, 0, 0, 0, 0]
        assert h2.audio.mic_led_history[-1] is True
        assert h2.light.playerNumber is not None
        # O controle existente continua intacto e ainda é o primário.
        assert inst._primary_key == "a"
        assert inst._ds is h1
        assert "b" in inst._handles

    def test_rumble_nao_e_reaplicado_no_hotplug(self) -> None:
        """Rumble é transitório — não entra no perfil ativo, logo um controle
        plugado depois NÃO recebe um rumble antigo."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        inst._handles = {"a": h1}  # type: ignore[dict-item]
        inst._primary_key = "a"
        inst.set_rumble(weak=10, strong=20)

        h2 = _FakeHandle()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[
                ("a", b"/dev/hidraw0", False),
                ("b", b"/dev/hidraw1", False),
            ],
        ), patch.object(PyDualSenseController, "_open_one", return_value=h2):
            inst.connect()

        assert h2.left_motor == []
        assert h2.right_motor == []

    def test_hotplug_out_fecha_controle_removido(self) -> None:
        inst, h1, h2 = _with_two_handles()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("a", b"/dev/hidraw0", False)],
        ):
            inst.connect()

        assert h2.closed is True
        assert "b" not in inst._handles
        assert "a" in inst._handles
        assert inst._primary_key == "a"
        assert inst._ds is h1

    def test_hotplug_out_promove_proximo_primario(self) -> None:
        inst, h1, h2 = _with_two_handles()
        # O primário ("a") é removido; "b" deve ser promovido.
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("b", b"/dev/hidraw1", False)],
        ):
            inst.connect()

        assert h1.closed is True
        assert inst._primary_key == "b"
        assert inst._ds is h2
        assert inst._transport == "usb"


class TestSingleControllerNaoRegride:
    def test_um_controle_se_comporta_como_antes(self) -> None:
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle()
        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("a", b"/dev/hidraw0", False)],
        ), patch.object(PyDualSenseController, "_open_one", return_value=h1):
            inst.connect()

        assert inst._ds is h1
        assert inst.is_connected() is True
        assert inst._offline is False
        assert len(inst._handles) == 1

        # Output vai para o único handle.
        inst.set_led((1, 2, 3))
        assert h1.light.colors == [(1, 2, 3)]

        # disconnect fecha tudo.
        inst.disconnect()
        assert h1.closed is True
        assert inst._ds is None
        assert inst.is_connected() is False


class TestDescribeControllers:
    def test_descreve_cada_controle(self) -> None:
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        h1 = _FakeHandle(transport_name="USB")
        h2 = _FakeHandle(transport_name="BT")
        inst._handles = {"a": h1, "b": h2}  # type: ignore[dict-item]
        inst._primary_key = "a"

        desc = inst.describe_controllers()
        assert desc == [
            {"connected": True, "transport": "usb", "is_primary": True},
            {"connected": True, "transport": "bt", "is_primary": False},
        ]

    def test_offline_devolve_entrada_neutra(self) -> None:
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        assert inst.describe_controllers() == [
            {"connected": False, "transport": None, "is_primary": False}
        ]


class TestPinnedPyDualSense:
    def test_abre_por_path(self, monkeypatch: object) -> None:
        """_PinnedPyDualSense.__find_device abre o device pelo path informado."""
        import hidapi

        from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

        captured: dict[str, object] = {}

        class _FakeDev:
            pass

        def _fake_device(*, path: bytes) -> _FakeDev:
            captured["path"] = path
            return _FakeDev()

        monkeypatch.setattr(hidapi, "Device", _fake_device)  # type: ignore[attr-defined]
        pinned = _PinnedPyDualSense(b"/dev/hidraw9", is_edge=True)
        dev, is_edge = pinned._pydualsense__find_device()

        assert captured["path"] == b"/dev/hidraw9"
        assert is_edge is True
        assert isinstance(dev, _FakeDev)
