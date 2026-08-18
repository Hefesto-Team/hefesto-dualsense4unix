"""Testes do backend resiliente quando o DualSense não está plugado.

Cobre BUG-DAEMON-NO-DEVICE-FATAL-01: `PyDualSenseController.connect()`
trata ausência de controle como estado offline-OK (sem propagar), setters
viram no-op, `read_state()` devolve snapshot neutro, e o hot-reconnect funciona
quando o controle aparece depois.

FEAT-DSX-MULTI-CONTROLLER-01: o `connect()` virou um tick de reconciliação de
hotplug. A presença de controles é dirigida por `_enumerate_device_keys()` e a
abertura individual por `_open_one()` — ambos seams de teste.
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
    def test_connect_sem_device_marca_offline(self) -> None:
        """Sem nenhum DualSense (`_enumerate_device_keys()` vazio), o backend
        marca _offline=True e retorna sem propagar."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())

        with patch.object(
            PyDualSenseController, "_enumerate_device_keys", return_value=[]
        ):
            inst.connect()  # não deve levantar

        assert inst._offline is True
        assert inst._ds is None
        assert inst.is_connected() is False

    def test_connect_engole_excecao_de_um_device_e_segue(self) -> None:
        """LIGHTBAR-BT-ADOPT-01 (complemento): erro de UM device (ex.: permissão
        hidraw) NÃO aborta o connect() — é logado e o tick segue até o fim
        (`_refresh_sysfs_leds`/reassert). Antes, a exceção propagava e pulava o
        refresh em TODO tick; com `_suppress_leds` nascendo True, handles JÁ
        abertos ficariam suprimidos para sempre (lightbar/player inaplicáveis).
        O retry natural continua: o device fica fora de `_handles` e o próximo
        tick do reconnect_loop tenta abrir de novo."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())

        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("mac1", b"/dev/hidraw0", False)],
        ), patch.object(
            PyDualSenseController,
            "_open_one",
            side_effect=RuntimeError("hidraw permission denied"),
        ):
            inst.connect()  # não deve levantar

        # O device que falhou não entrou; sem nenhum handle, offline é marcado
        # ao FIM do tick (o connect chegou ao fim em vez de abortar no meio).
        assert inst._offline is True
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
        # sem handles → caminho offline.

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
        """Sequência: 1ª connect → sem device (offline);
        2ª connect → device aparece, _offline limpa e _ds populado."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())

        # 1ª chamada — sem device.
        with patch.object(
            PyDualSenseController, "_enumerate_device_keys", return_value=[]
        ):
            inst.connect()
        assert inst._offline is True
        assert inst._ds is None

        # 2ª chamada — device aparece. Stub que _detect_transport aceita.
        present = _FakePydualsense()
        present.conType = type("CT", (), {"name": "USB"})()  # type: ignore[attr-defined]

        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("mac1", b"/dev/hidraw0", False)],
        ), patch.object(PyDualSenseController, "_open_one", return_value=present):
            inst.connect()

        assert inst._offline is False
        assert inst._ds is present
        assert inst.is_connected() is True
        assert inst._transport == "usb"

    def test_connect_reativa_evdev_no_hotplug_pos_boot_offline(self) -> None:
        """BUG-DAEMON-EVDEV-HOTPLUG-CACHE-01: daemon que bootou offline (evdev
        path=None) re-localiza o evdev quando o controle conecta, em vez de
        cair no HID-raw cru para sempre (sintoma: sticks ~253 em repouso)."""
        from pathlib import Path
        from unittest.mock import MagicMock

        reader = EvdevReader(device_path=None)
        reader._device_path = None  # boot offline: nenhum evdev encontrado
        reader._find_device = MagicMock(  # type: ignore[method-assign]
            return_value=Path("/dev/input/event2")
        )
        reader.start = MagicMock(return_value=True)  # type: ignore[method-assign]
        assert reader.is_available() is False  # antes do connect: sem evdev

        inst = PyDualSenseController(evdev_reader=reader)
        present = _FakePydualsense()
        present.conType = type("CT", (), {"name": "USB"})()  # type: ignore[attr-defined]

        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("mac1", b"/dev/hidraw0", False)],
        ), patch.object(PyDualSenseController, "_open_one", return_value=present):
            inst.connect()

        reader._find_device.assert_called_once()
        assert reader.is_available() is True
        reader.start.assert_called_once()

    def test_connect_idempotente_quando_ja_conectado(self) -> None:
        """connect() para um controle já presente não o reabre (não chama
        `_open_one`) — apenas reconcilia."""
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        present = _FakePydualsense()
        inst._handles = {"mac1": present}  # type: ignore[dict-item]
        inst._primary_key = "mac1"
        inst._offline = False

        def _explode(*_a: object, **_k: object) -> None:
            raise AssertionError("_open_one não deveria ser invocado")

        with patch.object(
            PyDualSenseController,
            "_enumerate_device_keys",
            return_value=[("mac1", b"/dev/hidraw0", False)],
        ), patch.object(PyDualSenseController, "_open_one", side_effect=_explode):
            inst.connect()

        assert inst._ds is present
        assert inst._primary_key == "mac1"
