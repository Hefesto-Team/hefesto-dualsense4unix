"""Hotkey Manager consumindo eventos de botão do próprio event bus.

Escuta `EventTopic.BUTTON_DOWN` (entregue pelo poll loop no futuro — em
W1.2 o loop só publica state.update; em W8.1 consolidamos detecção de
botão via diff de estados consecutivos, mantendo compat com o bus).

Política (V2-4 + V3-2 + FEAT-HOTKEY-STEAM-01):
  - Os combos next/prev (PS + D-pad) estão LIGADOS desde o
    FEAT-HOTKEY-PROFILE-CYCLE-01 — trocam o perfil ativo via
    `ProfileManager.activate` (ver daemon/subsystems/hotkey.py). NÃO há
    leitura de `daemon.toml`; config efetiva vem de env vars + IPC
    daemon.reload.
  - Modo jogo: segurar o botão PS (ps_long_press) suspende a emulação.
  - Buffer de 150ms (V3-2): pressionar PS solo atrasa repasse ao uinput
    pra aguardar possível segundo botão; se passou o buffer, libera.
  - Em modo emulação (uinput gamepad virtual ativo), combo sagrado não
    repassa ao gamepad virtual — evita o combo vazar pro jogo.
  - PS solo (FEAT-HOTKEY-STEAM-01): se PS é pressionado e solto sem
    combo em `buffer_ms`, dispara `on_ps_solo` (default: abrir/focar
    Steam). Detecção: após o release do PS sem combo ter disparado.
  - TETO do toque curto (PS-TOQUE-CURTO-01): o release só é toque se o
    hold couber em `ps_toque_curto_teto_ms` (700 ms). Acima disso é o
    gesto de RELIGAR o controle, não um toque — nada dispara, e o
    journal diz `ps_solo_ignorado_hold_longo`.
  - PS + R3 (FEAT-HOTKEY-PONTE-CYCLE-01): próxima PONTE — a
    forma como o jogo enxerga o controle. Ver
    `daemon/subsystems/hotkey.py:build_next_bridge_callback` para o que o
    gesto pode e o que NÃO pode prometer.

Vocabulário completo dos gestos:
    PS sozinho          abre/foca a Steam (toque de até 700 ms)
    PS + cima / baixo   perfil seguinte / anterior
    PS + L3             próxima máscara (a do cartão de quem faz o gesto)
    PS + R3             próximo modo
    PS + Options        modo jogo
    PS segurado         desligado por padrão (disparava modo-jogo acidental)
`dpad_left` e `dpad_right` seguem livres.

Todos valem em QUALQUER um dos quatro controles (`D-2709-O-PS-R3-EM-QUALQUER-
CONTROLE`, O-MODO-XBOX-NAO-E-QUEDA-02, item 5): cada controle tem o aperto dele
(`observe(..., de=<MAC>)`), e o ato pergunta de quem é o gesto por
`quem_faz_o_gesto`.

Sem hardware físico nesta sprint: manager consome payload genérico
`{"buttons": set[str]}` oriundo do event bus, facilitando testes.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_BUFFER_MS = 150
DEFAULT_COMBO_NEXT = ("ps", "dpad_up")
DEFAULT_COMBO_PREV = ("ps", "dpad_down")
PS_BUTTON = "ps"
DEFAULT_PS_LONG_PRESS_MS = 0
# um DualSense que caiu no rádio abria a Steam** — duas vezes em 45 s na sessão
DEFAULT_PS_TOQUE_CURTO_TETO_MS = 700
ENV_PS_TOQUE_CURTO_TETO_MS = "HEFESTO_DUALSENSE4UNIX_PS_TOQUE_CURTO_TETO_MS"


def _teto_do_toque_curto_do_ambiente() -> int:
    """Resolve o teto do toque curto: env var se legível, senão o default."""
    bruto = os.getenv(ENV_PS_TOQUE_CURTO_TETO_MS)
    if bruto is None:
        return DEFAULT_PS_TOQUE_CURTO_TETO_MS
    try:
        return int(bruto)
    except ValueError:
        logger.warning(
            "ps_toque_curto_teto_ms_ilegivel",
            valor=bruto,
            usando=DEFAULT_PS_TOQUE_CURTO_TETO_MS,
        )
        return DEFAULT_PS_TOQUE_CURTO_TETO_MS


DEFAULT_COMBO_GAMEMODE = ("ps", "options")
# jogo enxerga o controle (máscara DualSense, máscara Xbox, mouse+teclado).
# outros donos fora do combo — clique do meio na emulação de mouse
DEFAULT_COMBO_PONTE = ("ps", "r3")
DEFAULT_COMBO_MASCARA = ("ps", "l3")


_QUEM_FAZ_O_GESTO: ContextVar[str | None] = ContextVar(
    "hefesto_quem_faz_o_gesto", default=None
)


def quem_faz_o_gesto() -> str | None:
    """O MAC do controle que fez o gesto em curso, ou None fora de um gesto."""
    return _QUEM_FAZ_O_GESTO.get()


def _de(uniq: str | None) -> dict[str, str]:
    """O campo `de` do diário: o controle do gesto, quando se sabe qual."""
    return {"de": uniq} if uniq else {}


@dataclass
class _Aperto:
    """O aperto de UM controle: os combos em formação e o ciclo do PS dele."""

    first_seen_at: dict[frozenset[str], float] = field(default_factory=dict)
    last_fired: frozenset[str] | None = None
    ps_pressed_at: float | None = None
    ps_combo_fired: bool = False
    ps_long_press_fired: bool = False


@dataclass
class HotkeyConfig:
    buffer_ms: int = DEFAULT_BUFFER_MS
    next_profile: tuple[str, ...] = DEFAULT_COMBO_NEXT
    prev_profile: tuple[str, ...] = DEFAULT_COMBO_PREV
    passthrough_in_emulation: bool = False
    ps_long_press_ms: int = DEFAULT_PS_LONG_PRESS_MS
    ps_toque_curto_teto_ms: int = field(
        default_factory=_teto_do_toque_curto_do_ambiente
    )
    gamemode_toggle: tuple[str, ...] = DEFAULT_COMBO_GAMEMODE
    next_bridge: tuple[str, ...] = DEFAULT_COMBO_PONTE
    next_mask: tuple[str, ...] = DEFAULT_COMBO_MASCARA


@dataclass
class HotkeyManager:
    """Detecta combos a partir do snapshot atual de botões pressionados."""

    on_next: Any | None = None
    on_prev: Any | None = None
    on_ps_solo: Any | None = None
    on_ps_long_press: Any | None = None
    on_next_bridge: Any | None = None
    on_next_mask: Any | None = None
    config: HotkeyConfig = field(default_factory=HotkeyConfig)

    _apertos: dict[str | None, _Aperto] = field(default_factory=dict)
    _combo_latch: set[str] = field(default_factory=set)

    def _combos_configurados(self) -> dict[str, frozenset[str]]:
        """Mapa nome→botões dos combos LIGADOS. Tupla vazia = combo desligado.

        FONTE ÚNICA dos combos: `observe`, `should_passthrough` e
        `combo_buttons_active` leem daqui. Antes cada um repetia a lista de
        tuplas na mão, e um combo novo entrava num e faltava nos outros — o
        gesto disparava e ainda deixava vazar o membro (dpad→seta, options→Meta)
        para o desktop, que é exatamente o defeito que o FEAT-HOTKEY-COMBO-NO-
        LEAK-01/02 curou para os combos que existiam na época.

        O filtro por tupla não-vazia vale para TODOS: `frozenset()` vazio é
        subconjunto de qualquer coisa e dispararia a cada tick (antes só o
        `gamemode` tinha essa guarda, e `next_profile=()` — o estado
        disabled_until_wired de outrora — disparava sem parar).
        """
        bruto: dict[str, tuple[str, ...]] = {
            "next": self.config.next_profile,
            "prev": self.config.prev_profile,
            # FEAT-EMULATION-GAMEMODE-COMBO-01: default PS+Options.
            "gamemode": self.config.gamemode_toggle,
            # FEAT-HOTKEY-PONTE-CYCLE-01: default PS+R3.
            "ponte": self.config.next_bridge,
            # PS-L3-MASCARA-01: default PS+L3.
            "mascara": self.config.next_mask,
        }
        return {
            nome: frozenset(b.lower() for b in tupla)
            for nome, tupla in bruto.items()
            if tupla
        }

    def observe(
        self,
        pressed: Iterable[str],
        *,
        now: float | None = None,
        de: str | None = None,
    ) -> str | None:
        """Processa snapshot de botões. Retorna nome do evento disparado."""
        t = now if now is not None else time.monotonic()
        aperto = self._apertos.get(de)
        if aperto is None:
            aperto = self._apertos[de] = _Aperto()
        marca = _QUEM_FAZ_O_GESTO.set(de)
        try:
            return self._observe_o_aperto(aperto, pressed, t=t, de=de)
        finally:
            _QUEM_FAZ_O_GESTO.reset(marca)

    def soltar_quem_saiu(self, ficam: Iterable[str | None]) -> None:
        """Esquece o aperto de quem não foi lido neste tique."""
        manter = set(ficam)
        for chave in [c for c in self._apertos if c not in manter]:
            del self._apertos[chave]

    def _observe_o_aperto(
        self, aperto: _Aperto, pressed: Iterable[str], *, t: float, de: str | None
    ) -> str | None:
        """O corpo do :meth:`observe`, sobre o aperto de um controle."""
        buttons = frozenset(str(b).lower() for b in pressed)
        ps_now = PS_BUTTON in buttons

        combos = self._combos_configurados()

        stale = [key for key in aperto.first_seen_at if not key.issubset(buttons)]
        for key in stale:
            del aperto.first_seen_at[key]
        if aperto.last_fired is not None and not aperto.last_fired.issubset(buttons):
            aperto.last_fired = None

        combo_fired: str | None = None
        for name, combo in combos.items():
            if not combo.issubset(buttons):
                continue
            aperto.first_seen_at.setdefault(combo, t)
            held_for = (t - aperto.first_seen_at[combo]) * 1000
            if held_for < self.config.buffer_ms:
                continue
            if aperto.last_fired is not None:
                continue
            self._fire(name, combo, de=de)
            aperto.last_fired = combo
            combo_fired = name
            break

        if combo_fired is not None and PS_BUTTON in combos[combo_fired]:
            aperto.ps_combo_fired = True

        ps_event = self._observe_ps_solo(
            aperto, ps_now=ps_now, buttons=buttons, t=t, combo_fired=combo_fired, de=de
        )

        return combo_fired or ps_event

    def _observe_ps_solo(
        self,
        aperto: _Aperto,
        *,
        ps_now: bool,
        buttons: frozenset[str],
        t: float,
        combo_fired: str | None,
        de: str | None = None,
    ) -> str | None:
        """Detecta o pattern press-then-release do PS sem combo."""
        if ps_now:
            if aperto.ps_pressed_at is None:
                aperto.ps_pressed_at = t
            elif (
                self.config.ps_long_press_ms > 0
                and not aperto.ps_long_press_fired
                and not aperto.ps_combo_fired
                and (t - aperto.ps_pressed_at) * 1000 >= self.config.ps_long_press_ms
            ):
                aperto.ps_long_press_fired = True
                logger.info(
                    "ps_long_press_fired",
                    held_ms=round((t - aperto.ps_pressed_at) * 1000, 1),
                )
                self._fire_ps_long_press()
                return "ps_long_press"
            return None

        if aperto.ps_pressed_at is None:
            aperto.ps_combo_fired = False
            aperto.ps_long_press_fired = False
            return None

        pressed_at = aperto.ps_pressed_at
        fired_during = aperto.ps_combo_fired
        long_press_fired = aperto.ps_long_press_fired
        aperto.ps_pressed_at = None
        aperto.ps_combo_fired = False
        aperto.ps_long_press_fired = False

        if fired_during:
            logger.debug(
                "ps_solo_suppressed_by_combo",
                held_ms=round((t - pressed_at) * 1000, 1),
            )
            return None

        if long_press_fired:
            logger.debug(
                "ps_solo_suppressed_by_long_press",
                held_ms=round((t - pressed_at) * 1000, 1),
            )
            return None

        held_ms = (t - pressed_at) * 1000
        teto_ms = self.config.ps_toque_curto_teto_ms
        if teto_ms > 0 and held_ms > teto_ms:
            logger.info(
                "ps_solo_ignorado_hold_longo",
                held_ms=round(held_ms, 1),
                teto_ms=teto_ms,
            )
            return None

        logger.info("ps_solo_released", held_ms=round(held_ms, 1), **_de(de))
        self._fire_ps_solo()
        return "ps_solo"

    def should_passthrough(
        self, pressed: Iterable[str], *, emulation_active: bool
    ) -> bool:
        """Retorna True se os botões devem ser repassados ao uinput."""
        if not emulation_active or self.config.passthrough_in_emulation:
            return True
        buttons = frozenset(str(b).lower() for b in pressed)
        return all(
            not combo.issubset(buttons)
            for combo in self._combos_configurados().values()
        )

    def combo_buttons_active(self, pressed: Iterable[str]) -> frozenset[str]:
        """Botões a NÃO despachar à emulação por pertencerem a um combo PS+X."""
        buttons = frozenset(str(b).lower() for b in pressed)
        if PS_BUTTON in buttons:
            for combo in self._combos_configurados().values():
                if PS_BUTTON not in combo:
                    continue
                self._combo_latch |= {b for b in combo if b in buttons}
        self._combo_latch &= buttons
        return frozenset(self._combo_latch)

    def _callback_do_combo(self, name: str) -> tuple[bool, Any | None]:
        """Resolve o callback de um combo. Devolve (conhecido, callback).

        DESPACHO POR DICIONÁRIO, e não cadeia de ifs. A cadeia anterior
        terminava num `else: cb = self.on_prev` — ou seja, QUALQUER combo que
        não fosse "gamemode" nem "next" caía no perfil ANTERIOR. Um combo novo
        (o da ponte, por exemplo) trocaria o perfil do usuário para trás no meio da
        partida, silenciosamente. Aqui, nome desconhecido é `(False, None)`:
        não dispara nada e deixa rastro no journal.

        `gamemode` reaproveita o callback do long-press de propósito
        (FEAT-EMULATION-GAMEMODE-COMBO-01): os dois alternam a mesma supressão.
        """
        despacho: dict[str, Any | None] = {
            "next": self.on_next,
            "prev": self.on_prev,
            "gamemode": self.on_ps_long_press,
            "ponte": self.on_next_bridge,
            "mascara": self.on_next_mask,
        }
        if name not in despacho:
            return False, None
        return True, despacho[name]

    def _fire(self, name: str, combo: frozenset[str], *, de: str | None = None) -> None:
        logger.info("hotkey_fired", combo=name, buttons=sorted(combo), **_de(de))
        conhecido, cb = self._callback_do_combo(name)
        if not conhecido:
            logger.warning("hotkey_combo_sem_despacho", combo=name)
            return
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
    "DEFAULT_COMBO_MASCARA",
    "DEFAULT_COMBO_NEXT",
    "DEFAULT_COMBO_PONTE",
    "DEFAULT_COMBO_PREV",
    "DEFAULT_PS_LONG_PRESS_MS",
    "PS_BUTTON",
    "HotkeyConfig",
    "HotkeyManager",
    "quem_faz_o_gesto",
]
