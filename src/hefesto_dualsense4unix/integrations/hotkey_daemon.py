"""Hotkey Manager consumindo eventos de botão do próprio event bus.

Escuta `EventTopic.BUTTON_DOWN` (entregue pelo poll loop no futuro — em
W1.2 o loop só publica state.update; em W8.1 consolidamos detecção de
botão via diff de estados consecutivos, mantendo compat com o bus).

Política (V2-4 + V3-2 + FEAT-HOTKEY-STEAM-01):
  - Os combos next/prev (PS + D-pad) estão DESATIVADOS no daemon
    (disabled_until_wired) até a troca de perfil por hotkey ser ligada ao
    ProfileManager — ver daemon/subsystems/hotkey.py. NÃO há leitura de
    `daemon.toml`; config efetiva vem de env vars + IPC daemon.reload.
  - Modo jogo: segurar o botão PS (ps_long_press) suspende a emulação.
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

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_BUFFER_MS = 150
DEFAULT_COMBO_NEXT = ("ps", "dpad_up")
DEFAULT_COMBO_PREV = ("ps", "dpad_down")
PS_BUTTON = "ps"
# FEAT-EMULATION-GAMEMODE-LONGPRESS-01: segurar o PS por este tempo (sem outro
# botao) alterna o "modo jogo" (suprime a emulacao de mouse/teclado).
# 0 (ou negativo) desliga o gesto — o PS solo entao so faz a acao de toque
# curto (ex.: abrir Steam) e o modo jogo passa a ser so pelo combo.
# Default 0: o long-press estava causando modo-jogo ACIDENTAL (o toque de abrir
# a Steam que passava de ~1s alternava o modo). O modo jogo agora e' so pelo
# combo deliberado PS+Options. Quem quiser o gesto de volta: ps_long_press_ms>0.
DEFAULT_PS_LONG_PRESS_MS = 0
# FEAT-EMULATION-GAMEMODE-COMBO-01: combo que alterna o modo jogo. Default
# PS+Options — gesto deliberado que NAO colide com o PS solo (Steam) nem com
# next/prev (PS+dpad). Tupla vazia desliga o combo.
DEFAULT_COMBO_GAMEMODE = ("ps", "options")


@dataclass
class HotkeyConfig:
    buffer_ms: int = DEFAULT_BUFFER_MS
    next_profile: tuple[str, ...] = DEFAULT_COMBO_NEXT
    prev_profile: tuple[str, ...] = DEFAULT_COMBO_PREV
    passthrough_in_emulation: bool = False
    ps_long_press_ms: int = DEFAULT_PS_LONG_PRESS_MS
    gamemode_toggle: tuple[str, ...] = DEFAULT_COMBO_GAMEMODE


@dataclass
class HotkeyManager:
    """Detecta combos a partir do snapshot atual de botões pressionados."""

    on_next: Any | None = None
    on_prev: Any | None = None
    on_ps_solo: Any | None = None
    on_ps_long_press: Any | None = None
    config: HotkeyConfig = field(default_factory=HotkeyConfig)

    _first_seen_at: dict[frozenset[str], float] = field(default_factory=dict)
    _last_fired: frozenset[str] | None = None
    # FEAT-HOTKEY-COMBO-NO-LEAK-02 (latch): membros de um combo PS+X ficam
    # bloqueados da emulação até serem TODOS soltos — não só enquanto o PS
    # estiver pressionado. Fecha o leak de Meta na ordem de release (soltar o
    # PS antes do Options ao alternar o modo-jogo virava um tap de Meta).
    _combo_latch: set[str] = field(default_factory=set)

    # Estado do PS solo (FEAT-HOTKEY-STEAM-01):
    # _ps_pressed_at: timestamp do primeiro observe em que PS apareceu.
    # _ps_combo_fired: se um combo com PS ja disparou neste ciclo de press.
    _ps_pressed_at: float | None = None
    _ps_combo_fired: bool = False
    # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: se o long-press do PS ja disparou
    # neste ciclo de hold (evita repetir e suprime o PS solo no release).
    _ps_long_press_fired: bool = False

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
        # FEAT-EMULATION-GAMEMODE-COMBO-01: combo (default PS+Options) alterna o
        # modo jogo. So registrado se nao-vazio — frozenset() vazio e' subconjunto
        # de tudo e dispararia a cada tick.
        if self.config.gamemode_toggle:
            combos["gamemode"] = frozenset(
                b.lower() for b in self.config.gamemode_toggle
            )

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
            elif (
                self.config.ps_long_press_ms > 0
                and not self._ps_long_press_fired
                and not self._ps_combo_fired
                and (t - self._ps_pressed_at) * 1000 >= self.config.ps_long_press_ms
            ):
                # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: PS segurado alem do
                # threshold sem combo — dispara o long-press uma vez (toggle do
                # modo jogo). Marca para suprimir o PS solo no release seguinte.
                self._ps_long_press_fired = True
                logger.info(
                    "ps_long_press_fired",
                    held_ms=round((t - self._ps_pressed_at) * 1000, 1),
                )
                self._fire_ps_long_press()
                return "ps_long_press"
            return None

        # PS não esta mais pressionado. Verifica se houve release.
        if self._ps_pressed_at is None:
            # Não estava registrado: reset e sai.
            self._ps_combo_fired = False
            self._ps_long_press_fired = False
            return None

        pressed_at = self._ps_pressed_at
        fired_during = self._ps_combo_fired
        long_press_fired = self._ps_long_press_fired
        self._ps_pressed_at = None
        self._ps_combo_fired = False
        self._ps_long_press_fired = False

        if fired_during:
            logger.debug(
                "ps_solo_suppressed_by_combo",
                held_ms=round((t - pressed_at) * 1000, 1),
            )
            return None

        if long_press_fired:
            # Long-press ja disparou neste hold — o release não abre Steam.
            logger.debug(
                "ps_solo_suppressed_by_long_press",
                held_ms=round((t - pressed_at) * 1000, 1),
            )
            return None

        # Release sem combo nem long-press — considera PS solo (toque curto).
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
        for combo_tuple in (
            self.config.next_profile,
            self.config.prev_profile,
            self.config.gamemode_toggle,
        ):
            if not combo_tuple:
                continue
            combo = frozenset(b.lower() for b in combo_tuple)
            if combo.issubset(buttons):
                return False
        return True

    def combo_buttons_active(self, pressed: Iterable[str]) -> frozenset[str]:
        """Botões a NÃO despachar à emulação por pertencerem a um combo PS+X.

        FEAT-HOTKEY-COMBO-NO-LEAK-01/02. O poll loop subtrai este conjunto dos
        botões enviados à emulação de mouse/teclado — senão 'options'→Meta e
        dpad→setas vazam pro desktop ao usar um combo (PS+Options, PS+dpad),
        podendo travar o modificador se a supressão ligar no mesmo tick.

        LATCH (no-leak-02): um membro entra no latch quando o combo está "em
        formação" (PS + membro pressionados juntos) e SÓ sai quando é solto —
        não quando o PS é solto. Fecha o leak de ordem-de-release: ao alternar
        o modo-jogo com PS+Options e soltar o PS ANTES do Options, o 'options'
        continua latchado (bloqueado) até ser solto, em vez de virar um tap de
        Meta para o COSMIC no tick seguinte.
        """
        buttons = frozenset(str(b).lower() for b in pressed)
        # 1. Enquanto o combo se forma (PS + membro juntos), latcha os membros.
        if PS_BUTTON in buttons:
            for combo_tuple in (
                self.config.next_profile,
                self.config.prev_profile,
                self.config.gamemode_toggle,
            ):
                if not combo_tuple:
                    continue
                combo = frozenset(b.lower() for b in combo_tuple)
                if PS_BUTTON not in combo:
                    continue
                self._combo_latch |= {b for b in combo if b in buttons}
        # 2. Release = unlatch: solta do latch o que não está mais pressionado.
        self._combo_latch &= buttons
        # 3. Bloqueia da emulação tudo que segue latchado (e pressionado).
        return frozenset(self._combo_latch)

    def _fire(self, name: str, combo: frozenset[str]) -> None:
        logger.info("hotkey_fired", combo=name, buttons=sorted(combo))
        # FEAT-EMULATION-GAMEMODE-COMBO-01: o combo gamemode reaproveita o
        # callback de long-press (toggle da supressao da emulacao).
        if name == "gamemode":
            cb = self.on_ps_long_press
        elif name == "next":
            cb = self.on_next
        else:
            cb = self.on_prev
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

    def _fire_ps_long_press(self) -> None:
        cb = self.on_ps_long_press
        if cb is None:
            return
        try:
            result = cb()
            if asyncio.iscoroutine(result):
                with contextlib.suppress(RuntimeError, Exception):
                    asyncio.get_running_loop().create_task(result)
        except Exception as exc:
            logger.warning("hotkey_ps_long_press_callback_failed", err=str(exc))


__all__ = [
    "DEFAULT_BUFFER_MS",
    "DEFAULT_COMBO_GAMEMODE",
    "DEFAULT_COMBO_NEXT",
    "DEFAULT_COMBO_PREV",
    "DEFAULT_PS_LONG_PRESS_MS",
    "PS_BUTTON",
    "HotkeyConfig",
    "HotkeyManager",
]
