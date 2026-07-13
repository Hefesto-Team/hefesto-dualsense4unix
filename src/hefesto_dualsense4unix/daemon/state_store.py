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

from hefesto_dualsense4unix.core.controller import ControllerState

# CLUSTER-IPC-STATE-PROFILE-01 (Bug C): janela de supressão do autoswitch após
# escolha manual via IPC `profile.switch`. Quando o usuário ativa um perfil
# explicitamente (CLI/GUI/IPC), o autoswitch deve respeitar a escolha por
# `MANUAL_PROFILE_LOCK_SEC` segundos antes de voltar a aplicar perfil pelo
# wm_class da janela ativa. Valor canônico fixo: 30s — curto o bastante para
# não frustrar troca legítima de janela, longo o bastante para a UX "ativei
# manualmente, ele respeitou". Não-objetivo desta sprint torná-lo configurável.
MANUAL_PROFILE_LOCK_SEC: float = 30.0


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
        # CLUSTER-IPC-STATE-PROFILE-01 (Bug C): timestamp absoluto
        # (`time.monotonic`) até quando o autoswitch deve suspender por
        # escolha manual de perfil. 0.0 → lock inativo. Setado pelo handler
        # IPC `profile.switch`; consultado em `AutoSwitcher._activate`.
        self._manual_profile_lock_until: float = 0.0
        # FEAT-NATIVE-MODE-01: Modo Nativo ("release total" do controle). Enquanto
        # ativo, o AutoSwitcher NÃO ativa perfil por foco de janela e o hotkey de
        # ciclo NÃO troca de perfil — nada re-escreve gatilhos/rumble por cima do
        # jogo nativo (Sackboy & cia). Setado por `Daemon.set_native_mode`.
        self._native_mode_active: bool = False
        # FEAT-PROFILE-MODE-01: origem do nativo ativo ("manual" congela o
        # autoswitch; "profile" o mantém observando para reverter ao sair).
        self._native_mode_origin: str | None = None
        # FEAT-WINDOW-DETECT-DIAG-01: diagnóstico do detector de janela do
        # autoswitch. `backend` é o nome do backend efetivamente ativo
        # ("xlib" | "portal" | "wlrctl" | "null"); `healthy` segue a semântica
        # documentada em `record_window_detect_read`; `last_class` é a última
        # wm_class ÚTIL (!= "unknown") vista — permite capturar o wm_class de
        # um jogo direto do estado do daemon, sem garimpar o journal.
        self._window_detect_backend: str | None = None
        self._window_detect_healthy: bool = False
        self._window_detect_last_class: str | None = None

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

    def set_native_mode_active(
        self, active: bool, origin: str | None = None
    ) -> None:
        """Liga/desliga o gate do Modo Nativo (FEAT-NATIVE-MODE-01).

        Enquanto ativo com origem MANUAL, autoswitch e hotkey de ciclo NÃO
        re-aplicam perfil — o controle fica "solto" para o jogo nativo até a
        usuária desligar. Com origem "profile" (FEAT-PROFILE-MODE-01) o
        autoswitch CONTINUA observando a janela: ao focar outro app, o perfil
        seguinte reverte o nativo (senão o modo por-perfil nunca sairia).
        Setado por `Daemon.set_native_mode`.
        """
        with self._lock:
            self._native_mode_active = bool(active)
            self._native_mode_origin = origin if active else None

    # --- diagnóstico do detector de janela (FEAT-WINDOW-DETECT-DIAG-01) --

    def set_window_detect_backend(self, backend: str | None, healthy: bool) -> None:
        """Semeia o diagnóstico do detector na partida do autoswitch.

        `backend` é o nome do backend escolhido ("xlib" | "portal" | "wlrctl"
        | "null"). `healthy` inicial usa a presunção do chamador (subsystem
        autoswitch): backend "xlib" nasce saudável — ele só é escolhido com
        DISPLAY presente e cobre XWayland/Proton, o caso de uso principal;
        os demais nascem não-saudáveis até a primeira leitura útil (ver
        `record_window_detect_read`). Zera `last_class` (novo boot do
        detector = novo episódio de observação).
        """
        with self._lock:
            self._window_detect_backend = backend
            self._window_detect_healthy = healthy
            self._window_detect_last_class = None

    def record_window_detect_read(
        self, backend: str | None, wm_class: str | None
    ) -> None:
        """Registra uma leitura do detector de janela (poll do autoswitch).

        Semântica de `window_detect_healthy` (documentada de propósito):
        saudável = houve ao menos UMA leitura útil (wm_class != "unknown" e
        não-vazia) desde o boot do autoswitch, OU a presunção inicial do
        backend xlib (ver `set_window_detect_backend`). Leitura "unknown"
        NÃO derruba a flag: desktop vazio também produz "unknown", então
        unknown persistente não distingue "detector cego" de "nenhuma janela
        focada" — o veredito fino de ambiente fica no doctor.sh. `backend` é
        re-gravado a cada leitura porque a cascata Wayland pode migrar em
        runtime (portal -> wlrctl -> null).
        """
        useful = bool(wm_class) and wm_class != "unknown"
        with self._lock:
            self._window_detect_backend = backend
            if useful:
                self._window_detect_healthy = True
                self._window_detect_last_class = wm_class

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
        """Retorna True se o lock manual ainda está ativo em `now`.

        `now` deve ser obtido via `time.monotonic()` (mesmo relógio usado em
        `mark_manual_profile_lock`). Após o instante de expiração, o
        autoswitch volta a operar normalmente sem precisar de reset.
        """
        with self._lock:
            return now < self._manual_profile_lock_until

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

    @property
    def native_mode_active(self) -> bool:
        with self._lock:
            return self._native_mode_active

    @property
    def native_mode_origin(self) -> str | None:
        """Origem do Modo Nativo ativo: "manual" | "profile" | None (inativo)."""
        with self._lock:
            return self._native_mode_origin

    @property
    def window_detect_backend(self) -> str | None:
        """Backend ativo do detector de janela (FEAT-WINDOW-DETECT-DIAG-01).

        "xlib" | "portal" | "wlrctl" | "null"; None = autoswitch nunca subiu.
        """
        with self._lock:
            return self._window_detect_backend

    @property
    def window_detect_healthy(self) -> bool:
        """Detecção de janela saudável? (FEAT-WINDOW-DETECT-DIAG-01).

        True = ao menos 1 leitura útil desde o boot do autoswitch OU presunção
        do backend xlib (semântica completa em `record_window_detect_read`).
        """
        with self._lock:
            return self._window_detect_healthy

    @property
    def window_detect_last_class(self) -> str | None:
        """Última wm_class ÚTIL vista pelo detector (FEAT-WINDOW-DETECT-DIAG-01).

        None = nenhuma leitura útil ainda. Serve para capturar o wm_class de
        um jogo (ex.: Sackboy) direto do estado, sem ler o journal.
        """
        with self._lock:
            return self._window_detect_last_class

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


__all__ = [
    "MANUAL_PROFILE_LOCK_SEC",
    "StateStore",
    "StoreSnapshot",
]
