"""Hotkey Manager consumindo eventos de botão do próprio event bus.

Escuta `EventTopic.BUTTON_DOWN` (entregue pelo poll loop no futuro — em
W1.2 o loop só publica state.update; em W8.1 consolidamos detecção de
botão via diff de estados consecutivos, mantendo compat com o bus).

Política (V2-4 + V3-2):
  - Combo sagrado configurável em `daemon.toml` `[hotkey]`.
  - Default: PS + D-pad ↑ (próximo perfil), PS + D-pad ↓ (anterior).
  - Buffer de 150ms (V3-2): pressionar PS solo atrasa repasse ao uinput
    pra aguardar possível segundo botão; se passou o buffer, libera.
  - Em modo emulação (uinput gamepad virtual ativo), combo sagrado não
    repassa ao gamepad virtual — evita o combo vazar pro jogo.

Sem hardware físico nesta sprint: manager consome payload genérico
`{"buttons": set[str]}` oriundo do event bus, facilitando testes.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_BUFFER_MS = 150
DEFAULT_COMBO_NEXT = ("ps", "dpad_up")
DEFAULT_COMBO_PREV = ("ps", "dpad_down")


@dataclass
class HotkeyConfig:
    buffer_ms: int = DEFAULT_BUFFER_MS
    next_profile: tuple[str, ...] = DEFAULT_COMBO_NEXT
    prev_profile: tuple[str, ...] = DEFAULT_COMBO_PREV
    passthrough_in_emulation: bool = False


@dataclass
class HotkeyManager:
    """Detecta combos a partir do snapshot atual de botões pressionados."""

    on_next: Any | None = None
    on_prev: Any | None = None
    config: HotkeyConfig = field(default_factory=HotkeyConfig)

    _first_seen_at: dict[frozenset[str], float] = field(default_factory=dict)
    _last_fired: frozenset[str] | None = None

    def observe(
        self,
        pressed: Iterable[str],
        *,
        now: float | None = None,
    ) -> str | None:
        """Processa snapshot de botões. Retorna nome do combo disparado, se houver."""
        t = now if now is not None else time.monotonic()
        buttons = frozenset(str(b).lower() for b in pressed)

        combos = {
            "next": frozenset(b.lower() for b in self.config.next_profile),
            "prev": frozenset(b.lower() for b in self.config.prev_profile),
        }

        # Esquece registros cujo combo não esta mais pressionado
        stale = [key for key in self._first_seen_at if not key.issubset(buttons)]
        for key in stale:
            del self._first_seen_at[key]
        if self._last_fired is not None and not self._last_fired.issubset(buttons):
            self._last_fired = None

        for name, combo in combos.items():
            if not combo.issubset(buttons):
                continue
            self._first_seen_at.setdefault(combo, t)
            held_for = (t - self._first_seen_at[combo]) * 1000
            if held_for < self.config.buffer_ms:
                continue
            if self._last_fired == combo:
                continue
            self._fire(name, combo)
            self._last_fired = combo
            return name

        return None

    def should_passthrough(
        self, pressed: Iterable[str], *, emulation_active: bool
    ) -> bool:
        """Retorna True se os botões devem ser repassados ao uinput.

        Em modo emulação, combos sagrados não passam (V2-4). Demais botões
        passam sempre. Configurável via `passthrough_in_emulation=True`.
        """
        if not emulation_active or self.config.passthrough_in_emulation:
            return True
        buttons = frozenset(str(b).lower() for b in pressed)
        for combo_tuple in (self.config.next_profile, self.config.prev_profile):
            combo = frozenset(b.lower() for b in combo_tuple)
            if combo.issubset(buttons):
                return False
        return True

    def _fire(self, name: str, combo: frozenset[str]) -> None:
        logger.info("hotkey_fired", combo=name, buttons=sorted(combo))
        cb = self.on_next if name == "next" else self.on_prev
        if cb is None:
            return
        try:
            result = cb()
            if asyncio.iscoroutine(result):
                with contextlib.suppress(Exception):
                    asyncio.get_event_loop().create_task(result)
        except Exception as exc:
            logger.warning("hotkey_callback_failed", combo=name, err=str(exc))


__all__ = [
    "DEFAULT_BUFFER_MS",
    "DEFAULT_COMBO_NEXT",
    "DEFAULT_COMBO_PREV",
    "HotkeyConfig",
    "HotkeyManager",
]
