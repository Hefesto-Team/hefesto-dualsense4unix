"""Motor de rumble com throttle anti-spam.

Rumble passado do jogo (via UDP ou passthrough) pode chegar a centenas de
Hz. Aplicar cada atualização esgota a bateria, satura o motor HID e
deteriora os motors pequenos do DualSense. `RumbleEngine` agrupa os
comandos recebidos numa janela curta e aplica só o último a cada tick
de saída.

Uso:
    engine = RumbleEngine(controller, min_interval_sec=0.02)
    engine.set(weak=80, strong=150)    # pode ser chamado 1000x/s
    # tick() é chamado pelo poll loop do daemon e aplica se janela
    # estourou. Também aplica automaticamente quando weak+strong cai
    # para 0 (garantir desligamento imediato).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from hefesto.core.controller import IController

DEFAULT_MIN_INTERVAL_SEC = 0.02  # 50Hz ceiling para motores HID
RUMBLE_MIN = 0
RUMBLE_MAX = 255


@dataclass
class RumbleCommand:
    weak: int
    strong: int

    def is_stop(self) -> bool:
        return self.weak == 0 and self.strong == 0


class RumbleEngine:
    """Throttle: aplica no máximo 1x por `min_interval_sec`, exceto stop.

    Guarda o último comando pedido; `tick(now)` aplica se o intervalo
    estourou OU se o comando é stop (0,0). Em stop o throttle é ignorado
    para garantir desligamento imediato quando o jogo solta o gatilho.
    """

    def __init__(
        self,
        controller: IController,
        min_interval_sec: float = DEFAULT_MIN_INTERVAL_SEC,
        *,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._controller = controller
        self._min_interval = min_interval_sec
        self._time = time_fn or time.monotonic
        self._pending: RumbleCommand | None = None
        self._last_applied: RumbleCommand | None = None
        self._last_applied_at: float = 0.0

    def set(self, weak: int, strong: int) -> None:
        weak = _clamp(weak)
        strong = _clamp(strong)
        self._pending = RumbleCommand(weak=weak, strong=strong)

    def tick(self) -> RumbleCommand | None:
        """Aplica `pending` se tempo permitir. Retorna o comando aplicado ou None."""
        if self._pending is None:
            return None

        now = self._time()
        cmd = self._pending

        if cmd.is_stop():
            return self._apply(cmd, now)

        if self._last_applied is None:
            return self._apply(cmd, now)

        interval = now - self._last_applied_at
        if interval >= self._min_interval:
            return self._apply(cmd, now)
        return None

    def stop(self) -> None:
        """Forçar desligamento imediato dos motores."""
        self.set(0, 0)
        self.tick()

    @property
    def last_applied(self) -> RumbleCommand | None:
        return self._last_applied

    def _apply(self, cmd: RumbleCommand, now: float) -> RumbleCommand:
        self._controller.set_rumble(weak=cmd.weak, strong=cmd.strong)
        self._last_applied = cmd
        self._last_applied_at = now
        self._pending = None
        return cmd


def _clamp(value: int) -> int:
    if value < RUMBLE_MIN:
        return RUMBLE_MIN
    if value > RUMBLE_MAX:
        return RUMBLE_MAX
    return value


__all__ = [
    "DEFAULT_MIN_INTERVAL_SEC",
    "RUMBLE_MAX",
    "RUMBLE_MIN",
    "RumbleCommand",
    "RumbleEngine",
]
