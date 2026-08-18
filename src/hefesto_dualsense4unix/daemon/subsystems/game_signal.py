"""NUMA-01 — sinal de 3 estados "jogo real ativo": `game` / `daemon` / `unknown`.

Núcleo do gate de posse de EXIBIÇÃO da Onda N (síntese em
`docs/process/sprints/2026-07-19-sprint-numeracao-una.md`). Antes deste
sinal, "sessão uhid aberta" era tratada como "jogo" — e o cliente Steam
TAMBÉM abre sessão uhid nos vpads (incidente de 14:42: o cliente sem NENHUM
jogo rodando escreveu lightbar/player_leds e o reassert do backend passou a
DEFENDER a cor do cliente). O sinal daqui vira o provider que
`backend_pydualsense.set_game_authority_provider` consulta (NUMA-02/03, já
no tree e dormentes até este módulo ser fiado pelo lifecycle).

Duas peças:

- `classify(...)` — função PURA, tabela-verdade, SEM estado e SEM I/O: dado
  um instantâneo de evidências já resolvidas, devolve o veredito CRU do
  tick. Testável isoladamente (branch a branch).
- `GameSignal` — casca com estado: aplica a histerese de 30s na QUEDA para
  `daemon` (subir para `game` — ou cair para `unknown`, fail-safe — é
  sempre imediato, ≤1 tick) e emite telemetria INFO
  `game_signal_transition {de, para, evidencia}` a cada mudança real de
  autoridade. `time_fn` injetado (convenção do módulo — mesmo padrão de
  `integrations.uhid_gamepad.time_fn`), monotonic por default.

Vetos permanentes (unânimes dos 3 juízes da síntese, NUNCA violar):
  - "sessão uhid aberta" (`session_open`) JAMAIS é evidência de jogo — ela
    só entra em `GameSignal.evaluate` para modular a histerese da queda
    (sem sessão aberta não há réplica de exibição a proteger, então a queda
    dispensa espera).
  - `window_detect_last_class` (o STICKY do autoswitch) JAMAIS é evidência
    — prenderia a autoridade em `game` para sempre após o jogo fechar.
    Usamos `window_class_current` (a leitura CRUA do tick) e a IDADE de
    `game_window_seen_at` (que DECAI — ver `classify`), nunca o sticky.
  - Fail-safe sempre assimétrico para o lado do jogo: qualquer ambiguidade
    (detector não-saudável, I/O ilegível, exceção no cômputo) vira
    `unknown`, nunca `daemon` — bloquear réplica/repintar exige evidência
    POSITIVA de não-jogo.
"""
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

#: Histerese da queda `*→daemon` (síntese da Onda N, NUMA-01): 30s contínuos
#: sem NENHUMA evidência de jogo antes de honrar a queda — cobre alt-tab
#: curto sem derrubar a posse (o merge-gate do NUMA-02 torna a volta barata:
#: a camada GAME persiste e o reassert re-honra sozinho). O MESMO valor
#: também tolera, em `classify`, um hiccup momentâneo do detector de janela
#: (leitura "unknown" isolada) sem cair no sticky vetado — a idade de
#: `game_window_seen_at` decai neste teto, diferente do
#: `window_detect_last_class`, que NUNCA decai.
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
    if ev_janela or ev_perfil or ev_marker:
        return "game"
    if window_healthy:
        return "daemon"
    return "unknown"


class GameSignal:
    """Casca com histerese (30s) + telemetria de transição sobre `classify`.

    `classify()` é pura e memoryless; esta casca decide QUANDO honrar uma
    queda para `daemon`. Subir para `game` (evidência positiva) e cair para
    `unknown` (fail-safe) são SEMPRE imediatos — só a queda `*→daemon`
    espera. `time_fn` injetado, monotonic por convenção (não confundir com
    o `now` epoch que `classify` usa para o marker do wrapper — são
    relógios independentes, um para a histerese local, outro para a
    freshness do arquivo).
    """

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
        """Aplica a histerese sobre um veredito CRU de `classify()` (1 tick).

        `raw='game'`/`raw='unknown'`: honra IMEDIATO (subir nunca espera;
        `unknown` é fail-safe — represar seria pior que hoje). Só
        `raw='daemon'` passa pela histerese: sem sessão uhid aberta
        (`session_open=False`) não há réplica de exibição a proteger e a
        queda é imediata; com sessão aberta, exige `hysteresis_sec`
        contínuos de `raw='daemon'` antes de honrar.
        """
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
        """Força `unknown` (fail-safe) e loga a causa — leitura de I/O falhou.

        Chamado pelo lifecycle quando o gather de evidências (marker/perfil/
        disco) levanta exceção: NUNCA propaga o erro, sempre degrada para o
        lado seguro (jogo vence, daemon não disputa).
        """
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
