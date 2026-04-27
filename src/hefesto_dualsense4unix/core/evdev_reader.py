"""Leitor de input do DualSense via evdev.

Contorna o conflito com `hid_playstation` kernel driver: quando o kernel
assume o controle como joystick (`/dev/input/event*`), `pydualsense` não
recebe reports de input — mas o próprio kernel expõe tudo via evdev.

Usado pelo `PyDualSenseController` como fonte primária de input; o
pydualsense mantém o caminho de output (`set_trigger`, `set_led`,
`set_rumble`), que continua funcionando via HID-raw.

Thread dedicada lê eventos e atualiza um snapshot protegido por RLock.
"""
from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DUALSENSE_VENDOR = 0x054C
DUALSENSE_PIDS = {0x0CE6, 0x0DF2}  # DualSense + DualSense Edge


@dataclass
class EvdevSnapshot:
    """Snapshot imutável do estado lido via evdev."""

    l2_raw: int = 0
    r2_raw: int = 0
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    buttons_pressed: frozenset[str] = field(default_factory=frozenset)


def find_dualsense_evdev() -> Path | None:
    """Retorna path do evdev principal do DualSense; None se não houver."""
    try:
        from evdev import InputDevice, list_devices
    except ImportError:
        return None
    for path in list_devices():
        try:
            dev = InputDevice(path)
            try:
                is_gamepad = (
                    dev.info.vendor == DUALSENSE_VENDOR
                    and dev.info.product in DUALSENSE_PIDS
                )
                # O evdev principal tem gamepad caps (BTN_GAMEPAD)
                if is_gamepad:
                    caps = dev.capabilities()
                    from evdev import ecodes

                    buttons = caps.get(ecodes.EV_KEY, [])
                    if ecodes.BTN_GAMEPAD in buttons or ecodes.BTN_SOUTH in buttons:
                        return Path(path)
            finally:
                dev.close()
        except Exception:
            continue
    return None


class _EvdevReconnectLoop:
    """Loop base de leitura evdev com auto-reconnect e backoff exponencial.

    Encapsula o padrão duplicado entre `EvdevReader` e `TouchpadReader`.
    Subclasses implementam hooks: `_find_device`, `_handle_event`,
    `_reset_on_disconnect`, `_log_prefix` (prefixo para log events).
    """

    _device_path: Path | None
    _stop_flag: threading.Event
    _thread: threading.Thread | None
    _THREAD_NAME: ClassVar[str] = "hefesto-evdev-base"

    def _find_device(self) -> Path | None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _handle_event(self, event: Any, ecodes: Any) -> None:  # pragma: no cover
        raise NotImplementedError

    def _reset_on_disconnect(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _log_prefix(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def is_available(self) -> bool:
        return self._device_path is not None

    def start(self) -> bool:
        if not self.is_available():
            prefix = self._log_prefix()
            key = "evdev_reader_unavailable" if prefix == "evdev" else f"{prefix}_unavailable"
            logger.debug(key)
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._run, name=self._THREAD_NAME, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        """Loop com auto-reconnect; OSError no read_loop dispara reset + reabrir."""
        try:
            from evdev import InputDevice, ecodes
        except ImportError:
            logger.warning("evdev_module_missing")
            return

        prefix = self._log_prefix()
        backoff = 0.5
        while not self._stop_flag.is_set():
            path = self._device_path or self._find_device()
            if path is None:
                if prefix == "evdev":
                    logger.debug("evdev_device_not_found_retry", backoff=backoff)
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue
            try:
                dev = InputDevice(str(path))
            except Exception as exc:
                logger.warning(f"{prefix}_open_failed", err=str(exc), path=str(path))
                self._device_path = None
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue

            logger.info(f"{prefix}_started", path=str(path), name=dev.name)
            backoff = 0.5
            self._device_path = path
            try:
                for event in dev.read_loop():
                    if self._stop_flag.is_set():
                        break
                    self._handle_event(event, ecodes)
            except OSError as exc:
                logger.warning(f"{prefix}_read_lost", err=str(exc), path=str(path))
                self._reset_on_disconnect()
                self._device_path = None
            except Exception as exc:
                logger.warning(f"{prefix}_loop_error", err=str(exc))
                self._reset_on_disconnect()
            finally:
                with contextlib.suppress(Exception):
                    dev.close()
            if not self._stop_flag.is_set():
                time.sleep(0.1)  # grace period antes de tentar reabrir


class EvdevReader(_EvdevReconnectLoop):
    """Lê input do DualSense via evdev em thread dedicada.

    `start()` abre o device e inicia o loop. `snapshot()` retorna o estado
    atual (thread-safe). `stop()` encerra limpo.
    """

    # Mapeamento de evdev keycode -> nome canônico no domínio Hefesto - Dualsense4Unix.
    #
    # Botões com keycode evdev estável no kernel hid_playstation:
    # cross, circle, triangle, square, l1, r1, l2_btn, r2_btn,
    # create, options, ps, l3, r3.
    #
    # Botões sem keycode evdev estável no device principal (injetados por outros caminhos):
    # - "mic_btn": vem por HID-raw via `ds.state.micBtn` (byte misc2, bit 0x04).
    #   Injetado em `PyDualSenseController.read_state()`. Ver INFRA-MIC-HID-01.
    # - dpad (up/down/left/right): vem via `_refresh_dpad_buttons` (ABS_HAT0X/Y).
    # - touchpad_*_press: device separado (name contém "Touchpad"); lido por
    #   `TouchpadReader` abaixo (INFRA-EVDEV-TOUCHPAD-01).
    BUTTON_MAP: ClassVar[dict[str, str]] = {
        "BTN_SOUTH": "cross",
        "BTN_EAST": "circle",
        "BTN_NORTH": "triangle",
        "BTN_WEST": "square",
        "BTN_TL": "l1",
        "BTN_TR": "r1",
        "BTN_TL2": "l2_btn",
        "BTN_TR2": "r2_btn",
        "BTN_SELECT": "create",
        "BTN_START": "options",
        "BTN_MODE": "ps",
        "BTN_THUMBL": "l3",
        "BTN_THUMBR": "r3",
    }

    _THREAD_NAME: ClassVar[str] = "hefesto-evdev"

    def __init__(self, device_path: Path | None = None) -> None:
        self._device_path = device_path or find_dualsense_evdev()
        self._lock = threading.RLock()
        self._snapshot = EvdevSnapshot()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._dpad_x = 0
        self._dpad_y = 0
        self._pressed: set[str] = set()

    def snapshot(self) -> EvdevSnapshot:
        with self._lock:
            return EvdevSnapshot(
                l2_raw=self._snapshot.l2_raw,
                r2_raw=self._snapshot.r2_raw,
                lx=self._snapshot.lx,
                ly=self._snapshot.ly,
                rx=self._snapshot.rx,
                ry=self._snapshot.ry,
                buttons_pressed=self._snapshot.buttons_pressed,
            )

    # Hooks do loop base ------------------------------------------------

    def _find_device(self) -> Path | None:
        return find_dualsense_evdev()

    def _log_prefix(self) -> str:
        return "evdev"

    def _reset_on_disconnect(self) -> None:
        """Limpa botões 'travados' quando o device caiu."""
        with self._lock:
            self._pressed.clear()
            self._dpad_x = 0
            self._dpad_y = 0
            self._snapshot = self._with(buttons_pressed=frozenset())

    # Alias retrocompatível para testes legados (HOTFIX-3).
    _reset_buttons_on_disconnect = _reset_on_disconnect

    def _handle_event(self, event: Any, ecodes: Any) -> None:
        if event.type == ecodes.EV_ABS:
            self._handle_abs(event.code, event.value, ecodes)
        elif event.type == ecodes.EV_KEY:
            self._handle_key(event.code, event.value, ecodes)

    def _handle_abs(self, code: int, value: int, ecodes: Any) -> None:
        with self._lock:
            if code == ecodes.ABS_X:
                self._snapshot = self._with(lx=value & 0xFF)
            elif code == ecodes.ABS_Y:
                self._snapshot = self._with(ly=value & 0xFF)
            elif code == ecodes.ABS_RX:
                self._snapshot = self._with(rx=value & 0xFF)
            elif code == ecodes.ABS_RY:
                self._snapshot = self._with(ry=value & 0xFF)
            elif code == ecodes.ABS_Z:
                self._snapshot = self._with(l2_raw=value & 0xFF)
            elif code == ecodes.ABS_RZ:
                self._snapshot = self._with(r2_raw=value & 0xFF)
            elif code == ecodes.ABS_HAT0X:
                self._dpad_x = int(value)
                self._refresh_dpad_buttons()
            elif code == ecodes.ABS_HAT0Y:
                self._dpad_y = int(value)
                self._refresh_dpad_buttons()

    def _handle_key(self, code: int, value: int, ecodes: Any) -> None:
        # evdev retorna keycode numerico; converte pra nome canonico
        name = self._keycode_name(code, ecodes)
        if name is None:
            return
        with self._lock:
            if value == 1:
                self._pressed.add(name)
            elif value == 0:
                self._pressed.discard(name)
            self._sync_buttons_to_snapshot()

    def _keycode_name(self, code: int, ecodes: Any) -> str | None:
        for evdev_name, hefesto_name in self.BUTTON_MAP.items():
            ev_code = getattr(ecodes, evdev_name, None)
            if ev_code is not None and ev_code == code:
                return hefesto_name
        return None

    def _refresh_dpad_buttons(self) -> None:
        for d in ("dpad_up", "dpad_down", "dpad_left", "dpad_right"):
            self._pressed.discard(d)
        if self._dpad_y < 0:
            self._pressed.add("dpad_up")
        elif self._dpad_y > 0:
            self._pressed.add("dpad_down")
        if self._dpad_x < 0:
            self._pressed.add("dpad_left")
        elif self._dpad_x > 0:
            self._pressed.add("dpad_right")
        self._sync_buttons_to_snapshot()

    def _sync_buttons_to_snapshot(self) -> None:
        self._snapshot = self._with(buttons_pressed=frozenset(self._pressed))

    def _with(self, **changes: Any) -> EvdevSnapshot:
        current = self._snapshot
        fields = ("l2_raw", "r2_raw", "lx", "ly", "rx", "ry", "buttons_pressed")
        values = {f: changes.get(f, getattr(current, f)) for f in fields}
        return EvdevSnapshot(**values)


def find_dualsense_touchpad_evdev() -> Path | None:
    """Retorna path do evdev do touchpad do DualSense; None se ausente.

    O touchpad é exposto pelo kernel `hid_playstation` como um event
    device separado do gamepad principal: mesmo vendor/product Sony
    DualSense, mas nome contendo "Touchpad" (ex: "Sony Interactive
    Entertainment DualSense Wireless Controller Touchpad").

    INFRA-EVDEV-TOUCHPAD-01 — validação empírica 2026-04-24.
    """
    try:
        from evdev import InputDevice, list_devices
    except ImportError:
        return None
    for path in list_devices():
        try:
            dev = InputDevice(path)
            try:
                if (
                    dev.info.vendor == DUALSENSE_VENDOR
                    and dev.info.product in DUALSENSE_PIDS
                    and "Touchpad" in dev.name
                ):
                    return Path(path)
            finally:
                dev.close()
        except Exception:
            continue
    return None


class TouchpadReader(_EvdevReconnectLoop):
    """Lê click físico do touchpad do DualSense regionalizado.

    O touchpad emite `BTN_LEFT` (click firme mecânico, não toque leve) +
    `ABS_X` (0 a 1919) no device separado descoberto por
    `find_dualsense_touchpad_evdev`. Correlacionamos o último `ABS_X`
    observado com o press para discriminar três regiões: esquerda,
    meio, direita (limites 640 e 1280 sobre largura 1920).

    Threadsafe via RLock. Consultar o estado via `regions_pressed()`.
    """

    # Largura do touchpad em unidades absolutas do kernel hid_playstation
    # (empírico, DualSense USB 054c:0ce6 com kernel 6.x):
    _TOUCHPAD_WIDTH: ClassVar[int] = 1920
    # Limites de região (terços): [0, 640) esquerda; [640, 1280) meio;
    # [1280, 1920) direita.
    _REGION_LEFT_LIMIT: ClassVar[int] = 640
    _REGION_RIGHT_LIMIT: ClassVar[int] = 1280
    _THREAD_NAME: ClassVar[str] = "hefesto-touchpad"

    def __init__(self, device_path: Path | None = None) -> None:
        self._device_path = device_path or find_dualsense_touchpad_evdev()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._last_abs_x: int = self._TOUCHPAD_WIDTH // 2  # centro por default
        self._regions: frozenset[str] = frozenset()

    def regions_pressed(self) -> frozenset[str]:
        with self._lock:
            return self._regions

    @classmethod
    def _region_from_x(cls, x: int) -> str:
        if x < cls._REGION_LEFT_LIMIT:
            return "touchpad_left_press"
        if x >= cls._REGION_RIGHT_LIMIT:
            return "touchpad_right_press"
        return "touchpad_middle_press"

    # Hooks do loop base ------------------------------------------------

    def _find_device(self) -> Path | None:
        return find_dualsense_touchpad_evdev()

    def _log_prefix(self) -> str:
        return "touchpad_reader"

    def _handle_event(self, event: Any, ecodes: Any) -> None:
        if event.type == ecodes.EV_ABS and event.code == ecodes.ABS_X:
            # Atualiza snapshot de X para correlacionar no próximo BTN_LEFT.
            with self._lock:
                self._last_abs_x = int(event.value)
        elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_LEFT:
            with self._lock:
                if event.value == 1:
                    self._regions = frozenset(
                        {self._region_from_x(self._last_abs_x)}
                    )
                elif event.value == 0:
                    self._regions = frozenset()

    def _reset_on_disconnect(self) -> None:
        with self._lock:
            self._regions = frozenset()


__all__ = [
    "DUALSENSE_PIDS",
    "DUALSENSE_VENDOR",
    "EvdevReader",
    "EvdevSnapshot",
    "TouchpadReader",
    "find_dualsense_evdev",
    "find_dualsense_touchpad_evdev",
]
