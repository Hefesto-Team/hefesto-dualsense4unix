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

from hefesto.utils.logging_config import get_logger

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


class EvdevReader:
    """Lê input do DualSense via evdev em thread dedicada.

    `start()` abre o device e inicia o loop. `snapshot()` retorna o estado
    atual (thread-safe). `stop()` encerra limpo.
    """

    # Mapeamento de evdev keycode -> nome canônico no domínio Hefesto.
    #
    # Botões com keycode evdev estável no kernel hid_playstation:
    # cross, circle, triangle, square, l1, r1, l2_btn, r2_btn,
    # create, options, ps, l3, r3.
    #
    # Botões sem keycode evdev estável (não estão aqui — injetados por outros caminhos):
    # - "mic_btn": vem por HID-raw via `ds.state.micBtn` (byte misc2, bit 0x04).
    #   Injetado em `PyDualSenseController.read_state()`. Ver INFRA-MIC-HID-01.
    # - dpad (up/down/left/right): vem via `_refresh_dpad_buttons` (ABS_HAT0X/Y).
    # - touchpad_press: possível via BTN_TOUCH, mas keycode inconsistente — pendente.
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

    def __init__(self, device_path: Path | None = None) -> None:
        self._device_path = device_path or find_dualsense_evdev()
        self._lock = threading.RLock()
        self._snapshot = EvdevSnapshot()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._dpad_x = 0
        self._dpad_y = 0
        self._pressed: set[str] = set()

    def is_available(self) -> bool:
        return self._device_path is not None

    def start(self) -> bool:
        if not self.is_available():
            logger.debug("evdev_reader_unavailable")
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="hefesto-evdev",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_flag.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

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

    def _run(self) -> None:
        """Loop principal com auto-reconnect (HOTFIX-3).

        Se o device evdev sumir (USB re-enumera, sleep transient,
        driver unbind), detectamos via OSError no read_loop, zeramos o
        snapshot dos botões pra não ficar com 'botão preso', e tentamos
        reabrir. Retry com backoff exponencial (0.5s -> 5s).
        """
        try:
            from evdev import InputDevice, ecodes
        except ImportError:
            logger.warning("evdev_module_missing")
            return

        backoff = 0.5
        while not self._stop_flag.is_set():
            path = self._device_path or find_dualsense_evdev()
            if path is None:
                logger.debug("evdev_device_not_found_retry", backoff=backoff)
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue

            try:
                dev = InputDevice(str(path))
            except Exception as exc:
                logger.warning("evdev_open_failed", err=str(exc), path=str(path))
                self._device_path = None
                if self._stop_flag.wait(backoff):
                    break
                backoff = min(backoff * 2, 5.0)
                continue

            logger.info("evdev_reader_started", path=str(path), name=dev.name)
            backoff = 0.5
            self._device_path = path

            try:
                for event in dev.read_loop():
                    if self._stop_flag.is_set():
                        break
                    self._handle_event(event, ecodes)
            except OSError as exc:
                logger.warning("evdev_read_lost", err=str(exc), path=str(path))
                self._reset_buttons_on_disconnect()
                self._device_path = None
            except Exception as exc:
                logger.warning("evdev_read_loop_error", err=str(exc))
                self._reset_buttons_on_disconnect()
            finally:
                with contextlib.suppress(Exception):
                    dev.close()

            if not self._stop_flag.is_set():
                time.sleep(0.1)  # grace period antes de tentar reabrir

    def _reset_buttons_on_disconnect(self) -> None:
        """Limpa botões 'travados' quando o device caiu.

        Sem isso, se o controle some com um botão fisicamente pressionado,
        o snapshot fica com ele indefinidamente até o reader voltar.
        """
        with self._lock:
            self._pressed.clear()
            self._dpad_x = 0
            self._dpad_y = 0
            self._snapshot = self._with(buttons_pressed=frozenset())

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
        return EvdevSnapshot(
            l2_raw=changes.get("l2_raw", current.l2_raw),
            r2_raw=changes.get("r2_raw", current.r2_raw),
            lx=changes.get("lx", current.lx),
            ly=changes.get("ly", current.ly),
            rx=changes.get("rx", current.rx),
            ry=changes.get("ry", current.ry),
            buttons_pressed=changes.get("buttons_pressed", current.buttons_pressed),
        )


__all__ = [
    "DUALSENSE_PIDS",
    "DUALSENSE_VENDOR",
    "EvdevReader",
    "EvdevSnapshot",
    "find_dualsense_evdev",
]
