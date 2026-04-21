"""Emulação de mouse+teclado via python-uinput a partir do DualSense (FEAT-MOUSE-01).

Cria um device virtual uinput expondo:
  - BTN_LEFT, BTN_RIGHT, BTN_MIDDLE
  - REL_X, REL_Y (movimento) e REL_WHEEL, REL_HWHEEL (rolagem)
  - KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT (D-pad → setas)

Mapeamento canônico (FEAT-MOUSE-01, decidido pelo usuário):

| DualSense                | Saída emulada          | evdev code    |
|--------------------------|------------------------|---------------|
| Cross (X) ou L2          | Botão esquerdo         | BTN_LEFT      |
| Triangle (△) ou R2       | Botão direito          | BTN_RIGHT     |
| R3                       | Botão do meio          | BTN_MIDDLE    |
| D-pad up/down/left/right | Setas do teclado       | KEY_*         |
| Analógico esquerdo       | Movimento              | REL_X/REL_Y   |
| Analógico direito        | Rolagem                | REL_WHEEL/REL_HWHEEL |

Política:
  - `dispatch()` é chamado a cada tick do poll loop (default 60 Hz) com o
    snapshot dos sticks + triggers analógicos + conjunto de botões canônicos.
  - Botões têm edge-trigger (press/release só no delta). Estado anterior
    guardado na instância via `_last_buttons_emulated`.
  - Movimento usa deadzone de 20/128 (~16%) e escala `mouse_speed` (default 6).
  - Rolagem usa deadzone maior (40/128) e é rate-limited a 1 evento por 50ms
    (via `time.monotonic`, imune a NTP jumps).
  - Device só é criado via `start()` quando toggle explícito é ligado. Default OFF.
"""
from __future__ import annotations

import contextlib
import math
import time
from dataclasses import dataclass, field
from typing import Any

from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

DEVICE_NAME = "Hefesto Virtual Mouse+Keyboard"

STICK_CENTER = 128
MOVE_DEADZONE = 20
SCROLL_DEADZONE = 40
SCROLL_RATE_LIMIT_SEC = 0.050
DEFAULT_MOUSE_SPEED = 6
DEFAULT_SCROLL_SPEED = 1
TRIGGER_PRESS_THRESHOLD = 64

BUTTON_TO_UINPUT: dict[str, str] = {
    "cross": "BTN_LEFT",
    "triangle": "BTN_RIGHT",
    "r3": "BTN_MIDDLE",
}

DPAD_TO_KEY: dict[str, str] = {
    "dpad_up": "KEY_UP",
    "dpad_down": "KEY_DOWN",
    "dpad_left": "KEY_LEFT",
    "dpad_right": "KEY_RIGHT",
}


def _build_capabilities() -> list[tuple[Any, ...]]:
    """Lista de eventos que o uinput device expõe. Import lazy."""
    import uinput

    rels = [
        uinput.REL_X,
        uinput.REL_Y,
        uinput.REL_WHEEL,
        uinput.REL_HWHEEL,
    ]
    buttons = [
        uinput.BTN_LEFT,
        uinput.BTN_RIGHT,
        uinput.BTN_MIDDLE,
    ]
    keys = [
        uinput.KEY_UP,
        uinput.KEY_DOWN,
        uinput.KEY_LEFT,
        uinput.KEY_RIGHT,
    ]
    return [*rels, *buttons, *keys]


def _compute_move(raw: int, speed: int) -> int:
    """Converte valor 0-255 de stick em delta REL_X/REL_Y aplicando deadzone."""
    offset = raw - STICK_CENTER
    if abs(offset) < MOVE_DEADZONE:
        return 0
    return int(offset / STICK_CENTER * speed)


def _compute_scroll_step(raw: int) -> int:
    """Converte valor 0-255 de stick direito em passo de rolagem discreto.

    Retorna +1, -1 ou 0 conforme a direção dominante após deadzone.
    """
    offset = raw - STICK_CENTER
    if abs(offset) < SCROLL_DEADZONE:
        return 0
    return 1 if offset > 0 else -1


@dataclass
class UinputMouseDevice:
    """Wrapper do device virtual de mouse+teclado. Lazy-creates no `start()`."""

    name: str = DEVICE_NAME
    mouse_speed: int = DEFAULT_MOUSE_SPEED
    scroll_speed: int = DEFAULT_SCROLL_SPEED

    _device: Any = None
    _uinput_mod: Any = None
    _last_buttons_emulated: frozenset[str] = field(default_factory=frozenset)
    _last_scroll_at: float = -math.inf

    def start(self) -> bool:
        """Cria o device. Retorna False se /dev/uinput indisponível ou módulo ausente."""
        if self._device is not None:
            return True
        try:
            import uinput
        except ImportError:
            logger.warning("python-uinput não instalado — emulação de mouse indisponível")
            return False
        try:
            caps = _build_capabilities()
            self._device = uinput.Device(caps, name=self.name)
            self._uinput_mod = uinput
            logger.info("uinput_mouse_created", name=self.name)
            return True
        except Exception as exc:
            logger.warning("uinput_mouse_create_failed", err=str(exc))
            return False

    def stop(self) -> None:
        if self._device is None:
            return
        with contextlib.suppress(Exception):
            self._device.destroy()
        self._device = None
        self._uinput_mod = None
        self._last_buttons_emulated = frozenset()
        self._last_scroll_at = -math.inf

    def is_active(self) -> bool:
        return self._device is not None

    def set_speed(self, mouse_speed: int | None = None,
                  scroll_speed: int | None = None) -> None:
        """Ajusta velocidades em runtime (sem recriar device)."""
        if mouse_speed is not None:
            self.mouse_speed = max(1, min(12, int(mouse_speed)))
        if scroll_speed is not None:
            self.scroll_speed = max(1, min(5, int(scroll_speed)))

    def dispatch(
        self,
        *,
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        l2: int,
        r2: int,
        buttons: frozenset[str],
        now: float | None = None,
    ) -> None:
        """Aplica um snapshot de estado no device virtual.

        Args:
            lx, ly: stick esquerdo (0-255) — vira REL_X/REL_Y com deadzone.
            rx, ry: stick direito (0-255) — vira REL_WHEEL/REL_HWHEEL.
            l2, r2: trigger analógico (0-255) — acima de TRIGGER_PRESS_THRESHOLD
                    conta como botão pressionado (L2→cross, R2→triangle).
            buttons: conjunto canônico Hefesto pressionado agora.
            now: timestamp monotônico opcional (injetável em testes). Default
                 usa `time.monotonic()`.
        """
        if self._device is None or self._uinput_mod is None:
            return
        if now is None:
            now = time.monotonic()

        emulated = self._resolve_emulated_set(buttons, l2, r2)
        self._emit_buttons(emulated)
        self._emit_dpad(buttons)
        self._emit_move(lx, ly)
        self._emit_scroll(rx, ry, now)
        self._last_buttons_emulated = emulated

    def _resolve_emulated_set(
        self, buttons: frozenset[str], l2: int, r2: int
    ) -> frozenset[str]:
        """Converte botões Hefesto + triggers analógicos em set canônico emulado.

        L2 analógico acima de TRIGGER_PRESS_THRESHOLD injeta 'cross' virtual.
        R2 análogo injeta 'triangle'. Se usuário também apertou cross/triangle
        físicos, o set continua idempotente (frozenset absorve duplicatas).
        """
        resolved = set(buttons)
        if l2 >= TRIGGER_PRESS_THRESHOLD:
            resolved.add("cross")
        if r2 >= TRIGGER_PRESS_THRESHOLD:
            resolved.add("triangle")
        return frozenset(resolved)

    def _emit_buttons(self, emulated: frozenset[str]) -> None:
        """Edge-triggered press/release dos botões do mouse."""
        u = self._uinput_mod
        # Filtra só botões que mapeiam pra BTN_* (cross, triangle, r3)
        relevant_now = {b for b in emulated if b in BUTTON_TO_UINPUT}
        relevant_last = {b for b in self._last_buttons_emulated if b in BUTTON_TO_UINPUT}

        newly_pressed = relevant_now - relevant_last
        newly_released = relevant_last - relevant_now

        for name in newly_pressed:
            ev = getattr(u, BUTTON_TO_UINPUT[name], None)
            if ev is not None:
                self._device.emit(ev, 1, syn=False)
        for name in newly_released:
            ev = getattr(u, BUTTON_TO_UINPUT[name], None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)

        if newly_pressed or newly_released:
            self._device.syn()

    def _emit_dpad(self, buttons: frozenset[str]) -> None:
        """Edge-triggered D-pad → KEY_UP/DOWN/LEFT/RIGHT."""
        u = self._uinput_mod
        dpad_now = {b for b in buttons if b in DPAD_TO_KEY}
        dpad_last = {b for b in self._last_buttons_emulated if b in DPAD_TO_KEY}

        newly_pressed = dpad_now - dpad_last
        newly_released = dpad_last - dpad_now

        for name in newly_pressed:
            ev = getattr(u, DPAD_TO_KEY[name], None)
            if ev is not None:
                self._device.emit(ev, 1, syn=False)
        for name in newly_released:
            ev = getattr(u, DPAD_TO_KEY[name], None)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)

        if newly_pressed or newly_released:
            self._device.syn()

    def _emit_move(self, lx: int, ly: int) -> None:
        """Stick esquerdo → REL_X/REL_Y com deadzone e escala."""
        dx = _compute_move(lx, self.mouse_speed)
        dy = _compute_move(ly, self.mouse_speed)
        if dx == 0 and dy == 0:
            return
        u = self._uinput_mod
        if dx != 0:
            self._device.emit(u.REL_X, dx, syn=False)
        if dy != 0:
            self._device.emit(u.REL_Y, dy, syn=False)
        self._device.syn()

    def _emit_scroll(self, rx: int, ry: int, now: float) -> None:
        """Stick direito → REL_WHEEL/REL_HWHEEL com deadzone e rate-limit 50ms."""
        step_v = _compute_scroll_step(ry)
        step_h = _compute_scroll_step(rx)
        if step_v == 0 and step_h == 0:
            return
        if (now - self._last_scroll_at) < SCROLL_RATE_LIMIT_SEC:
            return

        u = self._uinput_mod
        # REL_WHEEL convenciona valores positivos para rolar pra cima.
        # Stick direito "para cima" tem ry < 128 (offset negativo).
        # Invertemos o sinal para manter a convenção natural de scroll.
        if step_v != 0:
            self._device.emit(u.REL_WHEEL, -step_v * self.scroll_speed, syn=False)
        if step_h != 0:
            self._device.emit(u.REL_HWHEEL, step_h * self.scroll_speed, syn=False)
        self._device.syn()
        self._last_scroll_at = now


__all__ = [
    "BUTTON_TO_UINPUT",
    "DEFAULT_MOUSE_SPEED",
    "DEFAULT_SCROLL_SPEED",
    "DEVICE_NAME",
    "DPAD_TO_KEY",
    "MOVE_DEADZONE",
    "SCROLL_DEADZONE",
    "SCROLL_RATE_LIMIT_SEC",
    "TRIGGER_PRESS_THRESHOLD",
    "UinputMouseDevice",
    "_compute_move",
    "_compute_scroll_step",
]

# "O único bem verdadeiro é o conhecimento, e o único mal verdadeiro é a ignorância." — Sócrates
