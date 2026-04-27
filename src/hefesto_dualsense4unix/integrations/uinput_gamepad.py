"""Gamepad virtual Xbox360 via python-uinput (W6.3).

Cria `/dev/input/js*` que o kernel registra como Xbox 360 compatível,
permitindo que jogos que só reconhecem Xbox controllers recebam input
do DualSense já traduzido.

Fluxo do daemon:
  - Controle físico lê input via `EvdevReader` (HOTFIX-2).
  - Daemon decide: combo sagrado (HotkeyManager) consome, resto repassa.
  - `UinputGamepad.forward(snapshot)` aplica os eventos relevantes no
    device virtual.
  - Jogo lê o device virtual como se fosse Xbox 360.

O device virtual tem VID/PID do Xbox 360 (045e:028e).
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

XBOX360_VENDOR = 0x045E
XBOX360_PRODUCT = 0x028E
DEVICE_NAME = "Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"

# Mapeamento canonico Hefesto - Dualsense4Unix (HOTFIX-2) -> evdev constant usado no uinput.
# Layout Xbox: cross=A, circle=B, square=X, triangle=Y.
BUTTON_TO_UINPUT: dict[str, str] = {
    "cross": "BTN_A",
    "circle": "BTN_B",
    "square": "BTN_X",
    "triangle": "BTN_Y",
    "l1": "BTN_TL",
    "r1": "BTN_TR",
    "create": "BTN_SELECT",
    "options": "BTN_START",
    "ps": "BTN_MODE",
    "l3": "BTN_THUMBL",
    "r3": "BTN_THUMBR",
}


def _build_capabilities() -> list[tuple[Any, ...]]:
    """Lista de eventos que o uinput device expõe.

    python-uinput espera tuples já em formato `(type, code, minmax_extra)`
    para eventos ABS. Retornamos lazy para não importar uinput em ambientes
    sem o módulo.
    """
    import uinput  # import local — evita custo no import do módulo

    # Axes 0-255 (igual ao evdev do DualSense)
    abs_axes = [
        (*uinput.ABS_X, 0, 255, 0, 0),
        (*uinput.ABS_Y, 0, 255, 0, 0),
        (*uinput.ABS_RX, 0, 255, 0, 0),
        (*uinput.ABS_RY, 0, 255, 0, 0),
        (*uinput.ABS_Z, 0, 255, 0, 0),   # LT
        (*uinput.ABS_RZ, 0, 255, 0, 0),  # RT
        (*uinput.ABS_HAT0X, -1, 1, 0, 0),
        (*uinput.ABS_HAT0Y, -1, 1, 0, 0),
    ]
    buttons = [
        uinput.BTN_A, uinput.BTN_B, uinput.BTN_X, uinput.BTN_Y,
        uinput.BTN_TL, uinput.BTN_TR,
        uinput.BTN_SELECT, uinput.BTN_START, uinput.BTN_MODE,
        uinput.BTN_THUMBL, uinput.BTN_THUMBR,
    ]
    return [*abs_axes, *buttons]


@dataclass
class UinputGamepad:
    """Wrapper do device virtual. Lazy-creates no `start()`."""

    name: str = DEVICE_NAME
    vendor: int = XBOX360_VENDOR
    product: int = XBOX360_PRODUCT

    _device: Any = None
    _uinput_mod: Any = None
    _last_buttons: frozenset[str] = field(default_factory=frozenset)

    def start(self) -> bool:
        """Cria o device. Retorna False se /dev/uinput indisponível."""
        if self._device is not None:
            return True
        try:
            import uinput
        except ImportError:
            logger.warning("python-uinput não instalado — emulacao indisponivel")
            return False
        try:
            caps = _build_capabilities()
            self._device = uinput.Device(
                caps, name=self.name, vendor=self.vendor, product=self.product
            )
            self._uinput_mod = uinput
            logger.info("uinput_device_created", name=self.name,
                        vendor=hex(self.vendor), product=hex(self.product))
            return True
        except Exception as exc:
            logger.warning("uinput_device_create_failed", err=str(exc))
            return False

    def stop(self) -> None:
        if self._device is None:
            return
        with contextlib.suppress(Exception):
            self._device.destroy()
        self._device = None
        self._last_buttons = frozenset()

    def is_active(self) -> bool:
        return self._device is not None

    def forward_analog(
        self,
        *,
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        l2: int,
        r2: int,
    ) -> None:
        """Aplica valores analógicos no device virtual."""
        if self._device is None or self._uinput_mod is None:
            return
        u = self._uinput_mod
        self._device.emit(u.ABS_X, lx, syn=False)
        self._device.emit(u.ABS_Y, ly, syn=False)
        self._device.emit(u.ABS_RX, rx, syn=False)
        self._device.emit(u.ABS_RY, ry, syn=False)
        self._device.emit(u.ABS_Z, l2, syn=False)
        self._device.emit(u.ABS_RZ, r2, syn=False)
        self._device.syn()

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        """Aplica set de botões pressionados. Diff com último snapshot."""
        if self._device is None or self._uinput_mod is None:
            return

        newly_pressed = pressed - self._last_buttons
        newly_released = self._last_buttons - pressed

        dpad_x, dpad_y = self._dpad_vector(pressed)
        last_dpad_x, last_dpad_y = self._dpad_vector(self._last_buttons)

        u = self._uinput_mod
        for name in newly_pressed:
            ev = self._resolve_evdev(name, u)
            if ev is not None:
                self._device.emit(ev, 1, syn=False)
        for name in newly_released:
            ev = self._resolve_evdev(name, u)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)

        if dpad_x != last_dpad_x:
            self._device.emit(u.ABS_HAT0X, dpad_x, syn=False)
        if dpad_y != last_dpad_y:
            self._device.emit(u.ABS_HAT0Y, dpad_y, syn=False)

        self._device.syn()
        self._last_buttons = frozenset(pressed)

    def _resolve_evdev(self, hefesto_name: str, uinput_mod: Any) -> Any | None:
        if hefesto_name in BUTTON_TO_UINPUT:
            key = BUTTON_TO_UINPUT[hefesto_name]
            return getattr(uinput_mod, key, None)
        # l2_btn / r2_btn digital viram triggers ABS (já tratados em analog)
        return None

    @staticmethod
    def _dpad_vector(pressed: frozenset[str]) -> tuple[int, int]:
        x = 0
        y = 0
        if "dpad_left" in pressed:
            x = -1
        elif "dpad_right" in pressed:
            x = 1
        if "dpad_up" in pressed:
            y = -1
        elif "dpad_down" in pressed:
            y = 1
        return x, y


__all__ = [
    "BUTTON_TO_UINPUT",
    "DEVICE_NAME",
    "XBOX360_PRODUCT",
    "XBOX360_VENDOR",
    "UinputGamepad",
]
