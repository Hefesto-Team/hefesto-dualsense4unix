"""Estado atual do daemon, compartilhado entre threads (poll) e loop (consumers)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.launch_env import steam_appid_from_wm_class

# escolha manual via IPC `profile.switch`. Quando o usuário ativa um perfil
MANUAL_PROFILE_LOCK_SEC: float = 30.0

WINDOW_DETECT_BLIND_AFTER_SEC: float = 300.0


@dataclass(frozen=True)
class StoreSnapshot:
    """Snapshot consistente do estado do daemon num instante."""

    controller: ControllerState | None
    active_profile: str | None
    last_battery_pct: int | None
    counters: dict[str, int]


class StateStore:
    """Repositório thread-safe do estado do daemon."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._controller_state: ControllerState | None = None
        self._active_profile: str | None = None
        self._last_battery_pct: int | None = None
        self._counters: dict[str, int] = {}
        # Limpeza: profile.switch explícito limpa TUDO; rumble.passthrough
        # limpa SÓ "rumble"; trigger.reset limpa SÓ "trigger" (ABAS-05, 25/07 —
        self._freestyle_ligado: bool = False
        # IPC `profile.switch`; consultado em `AutoSwitcher._activate`.
        self._manual_profile_lock_until: float = 0.0
        self._native_mode_active: bool = False
        self._native_mode_origin: str | None = None
        self._window_detect_backend: str | None = None
        self._window_detect_healthy: bool = False
        self._window_detect_last_class: str | None = None
        self._window_detect_current_class: str | None = None
        self._window_detect_read_monotonic: float | None = None
        self._game_window_seen_at: float | None = None
        self._window_detect_current_name: str | None = None
        self._window_detect_current_exe: str | None = None
        self._window_detect_last_useful_monotonic: float | None = None
        self._window_detect_reason: str | None = None
        self._udp_trigger_thresholds: dict[str, int] = {"left": 0, "right": 0}
        self._steam_jogo_appid: int | None = None
        self._steam_jogo_lido: bool = False


    def update_controller_state(self, state: ControllerState) -> None:
        with self._lock:
            self._controller_state = state
            if state.battery_pct != self._last_battery_pct:
                self._last_battery_pct = state.battery_pct

    def clear_controller_state(self) -> None:
        """Limpa `controller` — mesa vazia, sem repetir a última leitura boa.

        ONDA0-Z5/T1: chamado pelo `lifecycle` na BORDA de queda
        (conectado → desconectado), uma vez por borda, nunca a cada tick.
        Antes desta chamada existir, `_controller_state` guardava a última
        `ControllerState` para sempre — sem escrita nenhuma na queda — e a
        bateria/transporte de um controle que já saiu da mesa continuavam
        respondendo como se ele estivesse lá (medido: `connected: true,
        transport: "bt", battery_pct: 75` com ZERO controles na bancada,
        ONDA0-Z5 §2.2-2.3). `None` aqui é o "não sei" honesto — diferente de
        escrever um `ControllerState` com campos obrigatórios (`battery_pct`,
        `transport`) sem valor honesto para "sem controle" (§3 da sprint).
        `_last_battery_pct` (debounce de `BATTERY_CHANGE`) fica de fora: é
        estado interno do detector de delta, não o fato publicado.
        """
        with self._lock:
            self._controller_state = None

    def set_active_profile(self, name: str | None) -> None:
        """Publica o perfil ativo, de qualquer origem (`ProfileManager.activate`)."""
        with self._lock:
            self._active_profile = name

    def set_steam_jogo_appid(self, appid: int | None) -> None:
        """Publica o resultado de UMA sonda por jogo da Steam aberto.

        ABA-DO-JOGO-01. `appid` inteiro = há jogo, e é este; `None` = **sondei e
        não há jogo**. Os dois marcam `_lido`, e é essa marcação que transforma o
        `None` de "ainda não sei" em resposta — quem não conseguiu sondar
        simplesmente NÃO chama isto (`lifecycle._sync_steam_jogo_aberto` engole a
        falha), e o último fato conhecido continua valendo.

        Quem escreve é o tique lento do daemon, quem lê é o `state_full` a 10 Hz —
        duas threads que só se encontram pelo store, então a escrita é sob lock.
        """
        with self._lock:
            self._steam_jogo_appid = (
                int(appid) if isinstance(appid, int) and not isinstance(appid, bool)
                else None
            )
            self._steam_jogo_lido = True

    def bump(self, counter: str, delta: int = 1) -> int:
        with self._lock:
            value = self._counters.get(counter, 0) + delta
            self._counters[counter] = value
            return value

    def reset_counters(self) -> None:
        with self._lock:
            self._counters.clear()


    def set_udp_trigger_threshold(self, side: str, value: int) -> None:
        """Grava o limiar do lado `side` ("left"|"right"), clampado em 0-255."""
        if side not in ("left", "right"):
            raise ValueError(f"lado de gatilho desconhecido: {side!r}")
        with self._lock:
            self._udp_trigger_thresholds[side] = max(0, min(255, int(value)))

    def clear_udp_trigger_thresholds(self) -> None:
        """Volta os dois lados ao padrão "sem deadzone"."""
        with self._lock:
            self._udp_trigger_thresholds = {"left": 0, "right": 0}

    @property
    def udp_trigger_thresholds(self) -> tuple[int, int]:
        """Par `(esquerdo, direito)` dos limiares vigentes. Lido a cada tick."""
        with self._lock:
            atual = self._udp_trigger_thresholds
            return (atual["left"], atual["right"])

    # *"isso nao faz sentido mais."*  # (noqa-acento): citação literal

    def set_window_detect_backend(self, backend: str | None, healthy: bool) -> None:
        """Semeia o diagnóstico do detector na partida do autoswitch."""
        with self._lock:
            self._window_detect_backend = backend
            self._window_detect_healthy = healthy
            self._window_detect_last_class = None
            self._window_detect_current_class = None
            self._window_detect_current_name = None
            self._window_detect_current_exe = None
            self._window_detect_read_monotonic = None
            self._game_window_seen_at = None
            self._window_detect_last_useful_monotonic = None
            self._window_detect_reason = None

    def record_window_detect_read(
        self,
        backend: str | None,
        wm_class: str | None,
        *,
        now: float | None = None,
        reason: str | None = None,
        wm_name: str | None = None,
        exe_basename: str | None = None,
    ) -> None:
        """Registra uma leitura do detector de janela (poll do autoswitch)."""
        moment = now if now is not None else time.monotonic()
        useful = bool(wm_class) and wm_class != "unknown"
        entra_no_sticky = False
        if useful:
            from hefesto_dualsense4unix.profiles.autoswitch import (
                OWN_GUI_WM_CLASSES,
            )

            entra_no_sticky = str(wm_class).strip().casefold() not in (
                OWN_GUI_WM_CLASSES
            )
        with self._lock:
            self._window_detect_backend = backend
            self._window_detect_current_class = (
                wm_class if isinstance(wm_class, str) else None
            )
            self._window_detect_current_name = (
                wm_name if isinstance(wm_name, str) and wm_name else None
            )
            self._window_detect_current_exe = (
                exe_basename
                if isinstance(exe_basename, str) and exe_basename
                else None
            )
            self._window_detect_read_monotonic = moment
            if useful:
                self._window_detect_healthy = True
                self._window_detect_reason = None
                self._window_detect_last_useful_monotonic = moment
                if entra_no_sticky:
                    self._window_detect_last_class = wm_class
            else:
                self._window_detect_reason = reason
            if steam_appid_from_wm_class(
                wm_class if isinstance(wm_class, str) else None
            ) is not None:
                self._game_window_seen_at = moment


    # --- lock manual de profile.switch (Bug C) ------------------------

    def mark_manual_profile_lock(self, until: float) -> None:
        """Arma o lock de supressão do autoswitch até `until` (monotonic).

        Setado pelo handler IPC `profile.switch` com
        `time.monotonic() + MANUAL_PROFILE_LOCK_SEC`. Renovado a cada chamada
        (escolha mais recente vence; não acumula). NÃO é setado por
        autoswitch interno (recursão evitada), `daemon.reload`, nem
        `restore_last_profile` no boot — apenas entrada manual do usuário.
        """
        with self._lock:
            self._manual_profile_lock_until = until

    def manual_profile_lock_active(self, now: float) -> bool:
        """Retorna True se o lock manual ainda está ativo em `now`."""
        with self._lock:
            return now < self._manual_profile_lock_until


    @property
    def controller_state(self) -> ControllerState | None:
        with self._lock:
            return self._controller_state

    @property
    def active_profile(self) -> str | None:
        """O perfil EM VIGOR agora, no daemon vivo."""
        with self._lock:
            return self._active_profile

    @property
    def steam_jogo_appid(self) -> int | None:
        """Appid do jogo da Steam aberto AGORA. Só vale com `steam_jogo_lido`."""
        with self._lock:
            return self._steam_jogo_appid

    @property
    def steam_jogo_lido(self) -> bool:
        """True depois da PRIMEIRA sonda bem-sucedida por jogo da Steam."""
        with self._lock:
            return self._steam_jogo_lido

    @property
    def last_battery_pct(self) -> int | None:
        with self._lock:
            return self._last_battery_pct

    @property
    def freestyle_ligado(self) -> bool:
        """True quando o Modo Freestyle está ligado: o Freestyle manda em tudo."""
        with self._lock:
            return self._freestyle_ligado

    def set_freestyle_ligado(self, ligado: bool) -> None:
        """Só a memória. O escritor é `profiles.manager.ligar_o_freestyle`."""
        with self._lock:
            self._freestyle_ligado = bool(ligado)

    @property
    def native_mode_active(self) -> bool:
        with self._lock:
            return self._native_mode_active

    @property
    def native_mode_origin(self) -> str | None:
        """Origem do Modo Nativo ativo: "manual" | "profile" | None (inativo)."""
        with self._lock:
            return self._native_mode_origin

    def set_native_mode_active(
        self, active: bool, origin: str | None = None
    ) -> None:
        """Liga/desliga o gate do Modo Nativo (FEAT-NATIVE-MODE-01)."""
        with self._lock:
            self._native_mode_active = bool(active)
            self._native_mode_origin = origin if active else None

    @property
    def window_detect_backend(self) -> str | None:
        """Backend ativo do detector de janela (FEAT-WINDOW-DETECT-DIAG-01)."""
        with self._lock:
            return self._window_detect_backend

    @property
    def window_detect_healthy(self) -> bool:
        """Detecção de janela saudável? (FEAT-WINDOW-DETECT-DIAG-01)."""
        with self._lock:
            return self._window_detect_healthy

    def window_detect_useful_age(self, now: float | None = None) -> float | None:
        """Idade, em segundos, da última leitura ÚTIL — None se nunca houve."""
        with self._lock:
            carimbo = self._window_detect_last_useful_monotonic
        if carimbo is None:
            return None
        momento = now if now is not None else time.monotonic()
        return max(0.0, momento - carimbo)

    def window_detect_seeing(self, now: float | None = None) -> bool:
        """O detector enxergou janela nos últimos `WINDOW_DETECT_BLIND_AFTER_SEC`?"""
        idade = self.window_detect_useful_age(now)
        if idade is None:
            return False
        return idade < WINDOW_DETECT_BLIND_AFTER_SEC

    @property
    def window_detect_reason(self) -> str | None:
        """Motivo da última leitura NÃO-útil do detector (JANELA-CEGA-01)."""
        with self._lock:
            return self._window_detect_reason

    @property
    def window_detect_last_class(self) -> str | None:
        """Última wm_class ÚTIL vista pelo detector (FEAT-WINDOW-DETECT-DIAG-01)."""
        with self._lock:
            return self._window_detect_last_class

    @property
    def window_detect_current_class(self) -> str | None:
        """wm_class CRUA da ÚLTIMA leitura (NUMA-01) — inclusive "unknown"/None."""
        with self._lock:
            return self._window_detect_current_class

    @property
    def window_detect_current_name(self) -> str | None:
        """Título CRU da última leitura (SINAL-DE-JOGO-01) — None se vazio."""
        with self._lock:
            return self._window_detect_current_name

    @property
    def window_detect_current_exe(self) -> str | None:
        """Basename do executável da última leitura (SINAL-DE-JOGO-01)."""
        with self._lock:
            return self._window_detect_current_exe

    @property
    def game_window_seen_at(self) -> float | None:
        """Monotonic da ÚLTIMA leitura cuja classe casou `steam_app_\\d+`."""
        with self._lock:
            return self._game_window_seen_at

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
            )


__all__ = [
    "MANUAL_PROFILE_LOCK_SEC",
    "WINDOW_DETECT_BLIND_AFTER_SEC",
    "StateStore",
    "StoreSnapshot",
]
