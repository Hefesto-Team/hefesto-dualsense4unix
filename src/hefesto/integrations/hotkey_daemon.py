"""Hotkey Manager consumindo eventos de botão do próprio event bus.

Escuta `EventTopic.BUTTON_DOWN` (entregue pelo poll loop no futuro — em
W1.2 o loop só publica state.update; em W8.1 consolidamos detecção de
botão via diff de estados consecutivos, mantendo compat com o bus).

Política (V2-4 + V3-2 + FEAT-HOTKEY-STEAM-01):
  - Combo sagrado configurável em `daemon.toml` `[hotkey]`.
  - Default: PS + D-pad ↑ (próximo perfil), PS + D-pad ↓ (anterior).
  - Buffer de 150ms (V3-2): pressionar PS solo atrasa repasse ao uinput
    pra aguardar possível segundo botão; se passou o buffer, libera.
  - Em modo emulação (uinput gamepad virtual ativo), combo sagrado não
    repassa ao gamepad virtual — evita o combo vazar pro jogo.
  - PS solo (FEAT-HOTKEY-STEAM-01): se PS é pressionado e solto sem
    combo em `buffer_ms`, dispara `on_ps_solo` (default: abrir/focar
    Steam). Detecção: após o release do PS sem combo ter disparado.

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
PS_BUTTON = "ps"


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
    on_ps_solo: Any | None = None
    config: HotkeyConfig = field(default_factory=HotkeyConfig)

    _first_seen_at: dict[frozenset[str], float] = field(default_factory=dict)
    _last_fired: frozenset[str] | None = None

    # Estado do PS solo (FEAT-HOTKEY-STEAM-01):
    # _ps_pressed_at: timestamp do primeiro observe em que PS apareceu.
    # _ps_combo_fired: se um combo com PS ja disparou neste ciclo de press.
    _ps_pressed_at: float | None = None
    _ps_combo_fired: bool = False

    def observe(
        self,
        pressed: Iterable[str],
        *,
        now: float | None = None,
    ) -> str | None:
        """Processa snapshot de botões. Retorna nome do evento disparado.

        Valores possíveis: `"next"`, `"prev"`, `"ps_solo"` ou `None`.
        """
        t = now if now is not None else time.monotonic()
        buttons = frozenset(str(b).lower() for b in pressed)
        ps_now = PS_BUTTON in buttons

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

        combo_fired: str | None = None
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
            combo_fired = name
            break

        # Rastreamento do PS solo.
        # Se o PS esta pressionado junto com outro botao (combo potencial) e o
        # combo disparou, marca `_ps_combo_fired` para suprimir o solo no release.
        if combo_fired is not None and PS_BUTTON in combos[combo_fired]:
            self._ps_combo_fired = True

        ps_event = self._observe_ps_solo(
            ps_now=ps_now, buttons=buttons, t=t, combo_fired=combo_fired
        )

        return combo_fired or ps_event

    def _observe_ps_solo(
        self,
        *,
        ps_now: bool,
        buttons: frozenset[str],
        t: float,
        combo_fired: str | None,
    ) -> str | None:
        """Detecta o pattern press-then-release do PS sem combo.

        Regras:
          - PS acabou de ser pressionado → armazena timestamp.
          - PS foi liberado → se nenhum combo disparou E o release veio
            depois do buffer, considera PS solo. Se veio antes do buffer,
            também e' PS solo (toque curto). Se ocorreu com outros botoes
            pressionados junto (que não formaram combo), também dispara
            ao release — mantemos a semantica de "PS isolado terminado".
        """
        if ps_now:
            if self._ps_pressed_at is None:
                self._ps_pressed_at = t
            return None

        # PS não esta mais pressionado. Verifica se houve release.
        if self._ps_pressed_at is None:
            # Não estava registrado: reset e sai.
            self._ps_combo_fired = False
            return None

        pressed_at = self._ps_pressed_at
        fired_during = self._ps_combo_fired
        self._ps_pressed_at = None
        self._ps_combo_fired = False

        if fired_during:
            logger.debug(
                "ps_solo_suppressed_by_combo",
                held_ms=round((t - pressed_at) * 1000, 1),
            )
            return None

        # Release sem combo — considera PS solo.
        held_ms = (t - pressed_at) * 1000
        logger.info("ps_solo_released", held_ms=round(held_ms, 1))
        self._fire_ps_solo()
        return "ps_solo"

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
                with contextlib.suppress(RuntimeError, Exception):
                    asyncio.get_running_loop().create_task(result)
        except Exception as exc:
            logger.warning("hotkey_callback_failed", combo=name, err=str(exc))

    def _fire_ps_solo(self) -> None:
        cb = self.on_ps_solo
        if cb is None:
            return
        try:
            result = cb()
            if asyncio.iscoroutine(result):
                with contextlib.suppress(RuntimeError, Exception):
                    asyncio.get_running_loop().create_task(result)
        except Exception as exc:
            logger.warning("hotkey_ps_solo_callback_failed", err=str(exc))


__all__ = [
    "DEFAULT_BUFFER_MS",
    "DEFAULT_COMBO_NEXT",
    "DEFAULT_COMBO_PREV",
    "PS_BUTTON",
    "HotkeyConfig",
    "HotkeyManager",
]
