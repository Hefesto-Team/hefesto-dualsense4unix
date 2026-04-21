"""Estado atual do daemon, compartilhado entre threads (poll) e loop (consumers).

`StateStore` guarda uma snapshot consistente do controle + perfil ativo +
contadores runtime. Todas as leituras retornam cópias imutáveis
(`ControllerState` já é `frozen=True`, dicionários são copiados rasos);
escrita usa `threading.RLock` para evitar write-tearing entre poll
(executor) e reload (CLI/IPC).

Consumo típico:
    store = StateStore()
    store.update_controller_state(state)       # chamado do executor
    snap = store.snapshot()                    # chamado do loop ou CLI
    active = store.active_profile              # propriedade read-only
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from hefesto.core.controller import ControllerState


@dataclass(frozen=True)
class StoreSnapshot:
    """Snapshot consistente do estado do daemon num instante."""

    controller: ControllerState | None
    active_profile: str | None
    last_battery_pct: int | None
    counters: dict[str, int]
    manual_trigger_active: bool = False


class StateStore:
    """Repositório thread-safe do estado do daemon.

    Escritas usam `RLock`; leituras retornam cópias. RLock (reentrante)
    evita deadlock se um callback dentro de `with self._lock` chamar
    outro método que também adquire o lock (ex: logging).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._controller_state: ControllerState | None = None
        self._active_profile: str | None = None
        self._last_battery_pct: int | None = None
        self._counters: dict[str, int] = {}
        # BUG-MOUSE-TRIGGERS-01: quando o usuário aplica um efeito de gatilho
        # manualmente (via aba Gatilhos ou IPC trigger.set), marcamos override
        # ativo. Enquanto estiver ativo, o AutoSwitcher NÃO reaplica perfis
        # por mudança de janela — evita que o fallback pise no trigger manual
        # ao ligar o mouse (cursor move → foco muda → autoswitch reavalia).
        # Flag só zera em: trigger.reset, profile.switch explícito, ou
        # clear_manual_trigger_active() programático.
        self._manual_trigger_active: bool = False

    # --- escritas ------------------------------------------------------

    def update_controller_state(self, state: ControllerState) -> None:
        with self._lock:
            self._controller_state = state
            if state.battery_pct != self._last_battery_pct:
                self._last_battery_pct = state.battery_pct

    def set_active_profile(self, name: str | None) -> None:
        with self._lock:
            self._active_profile = name

    def bump(self, counter: str, delta: int = 1) -> int:
        with self._lock:
            value = self._counters.get(counter, 0) + delta
            self._counters[counter] = value
            return value

    def reset_counters(self) -> None:
        with self._lock:
            self._counters.clear()

    def mark_manual_trigger_active(self) -> None:
        """Sinaliza que o usuário aplicou um trigger manualmente.

        Usado pelo `IpcServer` quando processa `trigger.set`. Enquanto este
        flag estiver ligado, o `AutoSwitcher` NÃO reaplica perfil por mudança
        de janela (respeita override do usuário).
        """
        with self._lock:
            self._manual_trigger_active = True

    def clear_manual_trigger_active(self) -> None:
        """Limpa o override manual de trigger.

        Chamado em `trigger.reset` e `profile.switch` (usuário escolheu um
        perfil explícito, recuperando controle ao autoswitch).
        """
        with self._lock:
            self._manual_trigger_active = False

    # --- leituras ------------------------------------------------------

    @property
    def controller_state(self) -> ControllerState | None:
        with self._lock:
            return self._controller_state

    @property
    def active_profile(self) -> str | None:
        with self._lock:
            return self._active_profile

    @property
    def last_battery_pct(self) -> int | None:
        with self._lock:
            return self._last_battery_pct

    @property
    def manual_trigger_active(self) -> bool:
        with self._lock:
            return self._manual_trigger_active

    def counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def snapshot(self) -> StoreSnapshot:
        with self._lock:
            return StoreSnapshot(
                controller=self._controller_state,
                active_profile=self._active_profile,
                last_battery_pct=self._last_battery_pct,
                counters=dict(self._counters),
                manual_trigger_active=self._manual_trigger_active,
            )


__all__ = ["StateStore", "StoreSnapshot"]
