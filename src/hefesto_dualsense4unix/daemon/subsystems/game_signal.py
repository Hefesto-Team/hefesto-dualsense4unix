"""NUMA-01 — sinal de 3 estados "jogo real ativo": `game` / `daemon` / `unknown`."""
from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from typing import Any, Literal

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
       máquina do usuário, o jogo NÃO passa pelo wrapper — sobrava uma perna só, e
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


def outro_jogo_vivo(inputs: dict[str, Any], appid_do_lancamento: int) -> bool:
    """Há, nas leituras de `classify`, evidência de um jogo que NÃO é o lançamento?

    Quem pergunta é o arme de um lançamento novo (`launch_env`), com a autoridade
    ainda `game`: se nenhum outro jogo está vivo, o que a segura é só a histerese
    do jogo que acabou, e o lançamento a encerra (`GameSignal.encerrar`). As
    evidências são as de `classify`, menos as duas que não dizem «outro»: o marcador
    do próprio lançamento e a idade da última janela de jogo (`window_seen_age`),
    que é o resíduo da histerese que se quer encerrar. O processo ou a janela do
    próprio `appid_do_lancamento` também não contam.
    """
    vivo = inputs.get("appid_de_jogo_vivo")
    if isinstance(vivo, int) and vivo > 0 and vivo != appid_do_lancamento:
        return True
    marker = inputs.get("marker")
    if (
        marker is not None
        and int(marker[0]) != appid_do_lancamento
        and wrapper_game_running(
            marker=marker,
            exit_marker=inputs.get("exit_marker"),
            pid_alive=bool(inputs.get("marker_pid_alive")),
            marker_pid=inputs.get("marker_pid"),
            exit_pid=inputs.get("exit_pid"),
            now=float(inputs.get("now") or time.time()),
        )
    ):
        return True
    classe = inputs.get("window_class_current")
    da_janela = steam_appid_from_wm_class(classe) if classe is not None else None
    if da_janela is not None:
        return da_janela != appid_do_lancamento
    return bool(inputs.get("profile_rule_match"))


#: A decisão do arme do próprio jogo (O-ARME-NAO-ENCERRA-A-AUTORIDADE-DO-PROPRIO-JOGO-01).
DECISAO_ARME_DO_PROPRIO_JOGO = "D-2310-O-ARME-NAO-ENCERRA-A-AUTORIDADE-DO-PROPRIO-JOGO"

#: O appid do arme que está recriando o pad e a marca dele, enquanto `o_arme_do_proprio_jogo`
#: está aberto. A marca só vale em `_ARMES_EM_CURSO`: a tarefa que nasce no arme copia o
#: contexto (`asyncio.create_task`) e roda DEPOIS dele, com o jogo já no pad.
_ARME_DO_PROPRIO_JOGO: ContextVar[tuple[int, object] | None] = ContextVar(
    "hefesto_arme_do_proprio_jogo", default=None
)
_ARMES_EM_CURSO: set[object] = set()


@contextlib.contextmanager
def o_arme_do_proprio_jogo(appid: int | None) -> Iterator[None]:
    """O arme de `appid` pede recriações com a autoridade `game` que é DESSE jogo.

    Só o arme (`launch_env.arm_launch_profile`) abre isto, e só quando a autoridade é do
    appid dele e nenhum outro jogo está vivo. O contexto é da chamada (``ContextVar``): a
    soltura do pad (`lifecycle._soltar_o_pad_do_lancamento`) e o tique de outra tarefa
    não herdam a passagem, e a tarefa que nasce dentro dele a perde quando ele acaba.
    ``None`` não abre passagem nenhuma.
    """
    if appid is None:
        yield
        return
    marca = object()
    token = _ARME_DO_PROPRIO_JOGO.set((appid, marca))
    _ARMES_EM_CURSO.add(marca)
    try:
        yield
    finally:
        _ARMES_EM_CURSO.discard(marca)
        _ARME_DO_PROPRIO_JOGO.reset(token)


def appid_da_autoridade(daemon: Any) -> int | None:
    """De quem é a autoridade `game` do daemon: o appid da evidência que a pôs, ou ``None``.

    O sticky da casca (`GameSignal.appid`), que atravessa a histerese do jogo que fechou;
    não é a leitura do tique corrente (`Daemon.appid_em_cena`).
    """
    appid = getattr(getattr(daemon, "_game_signal", None), "appid", None)
    return appid if isinstance(appid, int) else None


def decisao_do_arme(daemon: Any) -> str | None:
    """A decisão que deixa o arme em curso recriar o pad, ou ``None`` (a recusa fica).

    Vale só com o arme ainda em curso e a autoridade `game` do MESMO appid que ele abriu.
    """
    arme = _ARME_DO_PROPRIO_JOGO.get()
    if arme is None or arme[1] not in _ARMES_EM_CURSO:
        return None
    appid = arme[0]
    if getattr(daemon, "display_authority", "unknown") != "game":
        return None
    return DECISAO_ARME_DO_PROPRIO_JOGO if appid_da_autoridade(daemon) == appid else None


def _sem_derrubar_o_tique(nome: str, acao: Callable[[], None]) -> None:
    """Roda um passo da borda; se falhar, o tique segue e o diário diz qual caiu."""
    try:
        acao()
    except Exception as exc:
        logger.warning("game_signal_borda_falhou", passo=nome, err=str(exc))


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
        self._appid: int | None = None

    @property
    def authority(self) -> Authority:
        """Autoridade de exibição CORRENTE (contrato lido pelo provider)."""
        return self._authority

    @property
    def appid(self) -> int | None:
        """O appid da evidência que pôs (ou mantém) a autoridade em `game`; fora dela, ``None``.

        Quem pergunta é o arme de um lançamento (`launch_env`): a autoridade que é do
        PRÓPRIO jogo que está abrindo não é o resíduo de um jogo que acabou. Evidência só
        de janela ou de regra de perfil não traz appid e deixa o anterior; a histerese
        segura o appid junto com o jogo, e a saída de `game` o apaga.
        """
        return self._appid if self._authority == "game" else None

    def evaluate(
        self, raw: Authority, *, session_open: bool, appid: int | None = None
    ) -> Authority:
        """Aplica a histerese sobre um veredito CRU de `classify()` (1 tick).

        `appid` é o da evidência do tique (`lifecycle._o_appid_da_evidencia`, o dono
        dessa leitura); só vale com o veredito `game`.
        """
        if raw != "daemon":
            self._non_game_since = None
            self._transition(raw, evidencia=raw)
            if raw == "game" and appid is not None and appid > 0:
                self._appid = appid
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

    def encerrar(self, evidencia: str) -> bool:
        """Encerra a autoridade `game` na hora, sem esperar a histerese. ``True`` se havia.

        O lançamento de outro jogo, sem nenhum outro vivo (`outro_jogo_vivo`), é a
        prova de que o anterior acabou. A histerese de 30 s é da janela que pisca
        dentro do MESMO jogo, e segue valendo para ela. O tique seguinte reavalia o
        veredito cru como sempre, e o jogo novo volta a `game` pela evidência dele.
        """
        if self._authority != "game":
            return False
        self._non_game_since = None
        self._transition("daemon", evidencia=evidencia)
        return True

    def na_borda(self, daemon: Any, anterior: str, novo: str) -> None:
        """O que a troca de autoridade `anterior -> novo` faz com a cor e as saídas retidas.

        Quem troca é o tique do sinal (`Daemon._sync_game_signal`) e o encerramento pelo
        lançamento novo (`Daemon.encerrar_a_autoridade_do_jogo`): a mesma borda, uma só vez.
        """
        def cor() -> None:
            from hefesto_dualsense4unix.daemon.connection import armar_gatilho_da_cor_por_evento

            armar_gatilho_da_cor_por_evento(daemon, f"game_signal:{anterior}->{novo}")

        def saida(nome: str) -> None:
            def chama() -> None:
                acao = getattr(daemon.controller, nome, None)
                if callable(acao):
                    acao()

            _sem_derrubar_o_tique(nome, chama)

        _sem_derrubar_o_tique("cor", cor)
        if novo == "daemon":
            saida("defend_display")
        elif anterior == "daemon":
            saida("replay_retained_game_outputs")

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
        if novo != "game":
            self._appid = None
        logger.info("game_signal_transition", de=anterior, para=novo, evidencia=evidencia)


__all__ = [
    "DECISAO_ARME_DO_PROPRIO_JOGO",
    "HYSTERESIS_SEC",
    "Authority",
    "GameSignal",
    "appid_da_autoridade",
    "classify",
    "decisao_do_arme",
    "o_arme_do_proprio_jogo",
    "outro_jogo_vivo",
]
