"""NUMA-01 — sinal de 3 estados "jogo real ativo": `game` / `daemon` / `unknown`."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

from hefesto_dualsense4unix.daemon.launch_env import (
    steam_appid_from_wm_class,
    wrapper_game_running,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

Authority = Literal["game", "daemon", "unknown"]

HYSTERESIS_SEC: float = 30.0


def classify(
    *,
    window_healthy: bool,
    window_class_current: str | None,
    window_seen_age: float | None,
    profile_rule_match: bool,
    marker: tuple[int, int] | None,
    marker_pid_alive: bool,
    exit_marker: int | None,
    session_open: bool,
    now: float,
    marker_pid: int | None = None,
    exit_pid: int | None = None,
    appid_de_jogo_vivo: int | None = None,
) -> Authority:
    """Classifica a autoridade de exibição num instante — 100% pura, sem I/O.

    Evidência de `game` (qualquer uma ⇒ `game` imediato):

    1. `window_class_current` (a leitura CORRENTE do tick — NUNCA o sticky
       `window_detect_last_class`) casa `steam_app_\\d+`; OU a idade de
       `game_window_seen_at` (`window_seen_age`, já em segundos) ainda cabe
       em `HYSTERESIS_SEC` — tolera um hiccup momentâneo do detector
       (leitura "unknown" isolada) sem recorrer ao sticky vetado.
    2. `profile_rule_match`: a janela corrente casou uma regra de
       perfil-por-jogo do autoswitch (`mode.kind == "gamepad"` com match
       ESPECÍFICO, não o `MatchAny` catch-all) — cobre GOG/Heroic fora da
       Steam.
    3. `wrapper_game_running(marker, exit_marker, marker_pid_alive, now,
       marker_pid, exit_pid)`: marker `last_run` do wrapper fresco + pid
       vivo + sem `last_exit` mais novo — cobre a janela launch→janela
       (shaders/AAA) e Wayland puro COM wrapper (o detector de janela pode
       estar são mas cego a XWayland ausente; o marker não depende dele).
       `marker_pid`/`exit_pid` (opcionais, ver `wrapper_game_running`)
       correlacionam um `last_exit` global ao launch CERTO — sem eles, um
       `last_exit` de outro launch concorrente pode invalidar este marker
       (achado da auditoria da Onda N).
    4. `appid_de_jogo_vivo`: há PROCESSO de jogo vivo agora — a evidência E4
       da SINAL-DE-JOGO-01, e a única das quatro que **não depende nem do
       detector de janela nem do wrapper**. Quem responde é a varredura
       canônica da casa (`steam_launch_options.steam_game_running_appid`,
       agulha `SteamLaunch AppId=<dígitos>` na cmdline), lida pelo
       `lifecycle._gather_game_signal_inputs`.

       **Por que ela é a cura, e não mais uma perna:** as evidências 1 e 2
       exigem o detector enxergando e a 3 exige o wrapper. Medido em 31/07 na
       máquina dela, o jogo NÃO passa pelo wrapper — sobrava uma perna só, e
       o detector cegar no meio da partida derrubava a autoridade sem nada ter
       acontecido no jogo.

       **E é ela que tira do `WRAPPER_MARKER_WINDOW_SEC` (900 s) o poder de
       matar um jogo vivo.** A evidência 3 avalia o teto de frescor ANTES de
       olhar o pid (`launch_env.wrapper_game_running`), então uma partida mais
       longa que 15 min deixava de ser evidência com o pid de pé. A varredura
       não tem teto: enquanto o processo do jogo estiver vivo, ele é evidência.
       O que o teto cobria era o PID RECICLADO, e a varredura não corre esse
       risco — ela lê a cmdline do processo de AGORA, não um número gravado em
       arquivo (o mesmo raciocínio que `autoswitch.jogo_do_wrapper_vivo` já
       tinha registrado por outra porta).

       **O que NÃO conta, e é o incidente das 14:42 escrito como contrato:**
       `steam`, `steamwebhelper` e `reaper` vivos são a ÁRVORE da Steam, não
       um jogo — o cliente sem jogo nenhum já escreveu lightbar e player-LEDs
       com o daemon defendendo a cor dele. A agulha exige `SteamLaunch
       AppId=<dígitos>`, que a Steam põe no launch de um jogo E no avaliador
       do install script dele (`reaper SteamLaunch AppId=<id> Install=1`); a
       varredura devolve None para o avaliador
       (`steam_launch_options.e_avaliador_do_install_script`). E `appid <= 0`
       é recusado aqui, porque um appid zero não identifica jogo nenhum.

       NOTA DATADA — 13/09/2026 (JOGO-SEM-EXCLUSIVIDADE-01): esta frase dizia
       que `SteamLaunch AppId=` «só existe no launch de um jogo». O log da
       Steam e o journal derrubaram o fato: o avaliador rodou antes do wrapper
       e pôs a autoridade em `game` 4 a 5 s cedo, em 6 de 6 aberturas de um
       jogo com install script.

    Sem NENHUMA evidência: `daemon` exige `window_healthy` (evidência
    POSITIVA de detector são — desktop vazio/alt-tab observado, não
    "não sei"); detector não-saudável sem evidência degrada para `unknown`
    (fail-safe — nunca pior que hoje). `session_open` é aceito e IGNORADO
    aqui de propósito (veto: sessão uhid jamais é evidência de jogo) — é
    consumido só por `GameSignal.evaluate` para modular a histerese.
    """
    ev_janela = (
        window_class_current is not None
        and steam_appid_from_wm_class(window_class_current) is not None
    ) or (window_seen_age is not None and window_seen_age <= HYSTERESIS_SEC)
    ev_perfil = bool(profile_rule_match)
    ev_marker = wrapper_game_running(
        marker=marker,
        exit_marker=exit_marker,
        pid_alive=marker_pid_alive,
        marker_pid=marker_pid,
        exit_pid=exit_pid,
        now=now,
    )
    ev_processo = appid_de_jogo_vivo is not None and appid_de_jogo_vivo > 0
    if ev_janela or ev_perfil or ev_marker or ev_processo:
        return "game"
    if window_healthy:
        return "daemon"
    return "unknown"


class GameSignal:
    """Casca com histerese (30s) + telemetria de transição sobre `classify`."""

    def __init__(
        self,
        *,
        time_fn: Callable[[], float] = time.monotonic,
        hysteresis_sec: float = HYSTERESIS_SEC,
    ) -> None:
        self._time_fn = time_fn
        self._hysteresis_sec = hysteresis_sec
        self._authority: Authority = "unknown"
        self._non_game_since: float | None = None

    @property
    def authority(self) -> Authority:
        """Autoridade de exibição CORRENTE (contrato lido pelo provider)."""
        return self._authority

    def evaluate(self, raw: Authority, *, session_open: bool) -> Authority:
        """Aplica a histerese sobre um veredito CRU de `classify()` (1 tick)."""
        if raw != "daemon":
            self._non_game_since = None
            self._transition(raw, evidencia=raw)
            return self._authority
        if not session_open:
            self._non_game_since = None
            self._transition("daemon", evidencia="daemon_sem_sessao")
            return self._authority
        now = self._time_fn()
        if self._non_game_since is None:
            self._non_game_since = now
        if (now - self._non_game_since) >= self._hysteresis_sec:
            self._transition("daemon", evidencia="daemon_histerese_expirada")
        return self._authority

    def mark_degraded(self, motivo: str) -> Authority:
        """Força `unknown` (fail-safe) e loga a causa — leitura de I/O falhou."""
        self._non_game_since = None
        self._transition("unknown", evidencia=f"degradado:{motivo}")
        return self._authority

    def _transition(self, novo: Authority, *, evidencia: str) -> None:
        anterior = self._authority
        if novo == anterior:
            return
        self._authority = novo
        logger.info("game_signal_transition", de=anterior, para=novo, evidencia=evidencia)


__all__ = [
    "HYSTERESIS_SEC",
    "Authority",
    "GameSignal",
    "classify",
]
