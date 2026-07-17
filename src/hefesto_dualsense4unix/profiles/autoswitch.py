"""Auto-switch de perfil conforme janela X11 ativa.

Poll a 2Hz (`poll_interval_sec=0.5`), debounce de 500ms para evitar flicker
em alt-tab, aplica via ProfileManager.activate quando escolha muda.

UX-01 (SPRINT-UX-AUTOSWITCH-01): histerese — leitura SEM INFORMAÇÃO
("não sei qual janela está em foco") pula o tick inteiro e retém o perfil
corrente. Antes, o backend cego virava `wm_class='unknown'`, o `MatchAny`
do perfil padrão casava com tudo e a emulação caía no meio do jogo
(provado ao vivo: journal 03:40:29 e 13:07:18 de 2026-07-16).

Desligável via env `HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT=1` (usado pelo unit headless,
V2-4 / Patch 8).
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL_SEC = 0.5
DEFAULT_DEBOUNCE_SEC = 0.5


WindowReader = Callable[[], dict[str, Any]]


@dataclass
class AutoSwitcher:
    manager: ProfileManager
    window_reader: WindowReader
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC
    debounce_sec: float = DEFAULT_DEBOUNCE_SEC
    # BUG-MOUSE-TRIGGERS-01: opcional para permitir testes legados que
    # instanciam AutoSwitcher sem store. Em produção, o Daemon injeta o
    # store compartilhado para respeitar override de trigger manual.
    store: StateStore | None = None

    _last_candidate: str | None = None
    _candidate_since: float = 0.0
    _current_profile: str | None = None
    _stop_event: asyncio.Event | None = None
    _task: asyncio.Task[Any] | None = None
    # FEAT-POINT-AND-CLICK-01 (rate-limit): chave (evento, candidato) do último
    # log de supressão emitido. O poll de 2 Hz chamava `_activate` a cada tick
    # enquanto suprimido e inundava o journal (~1074 linhas/2h). Loga 1x por
    # (motivo, candidato); re-loga quando o candidato ou o motivo muda, ou
    # quando a supressão termina (chave zerada em `_activate` não-suprimido) e
    # um novo episódio começa. Estado por instância — nada global.
    _suppress_log_key: tuple[str, str] | None = None
    # UX-01 (SPRINT-UX-AUTOSWITCH-01): episódio de leituras sem informação em
    # curso. Serve para (a) logar `autoswitch_window_info_unavailable` 1x por
    # episódio (padrão do `_log_suppressed_once` — sem flood a 2 Hz) e (b)
    # resetar o relógio do debounce na PRIMEIRA leitura útil após o gap (o
    # debounce é wall-time: sem o reset, o tempo pulado contaria como
    # estabilidade e um glitch idêntico ao de antes do gap ativaria na hora).
    _info_gap_active: bool = False

    def disabled(self) -> bool:
        return os.environ.get("HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT") == "1"

    async def run(self) -> None:
        if self.disabled():
            logger.info("autoswitch_disabled_via_env")
            return

        self._stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        while not self._stop_event.is_set():
            try:
                info = self.window_reader()
            except Exception as exc:
                logger.warning("autoswitch_window_read_failed", err=str(exc))
                info = {}

            self._tick(info, loop.time())

            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval_sec
                )

    def _tick(self, info: dict[str, Any], now: float) -> None:
        """Um ciclo de decisão do autoswitch (leitura já feita pelo caller).

        Separado do run-loop para os testes dirigirem o relógio: o debounce é
        wall-time e o buraco-do-debounce da UX-01 só é testável com `now`
        controlado.
        """
        # UX-01 (SPRINT-UX-AUTOSWITCH-01): histerese. Leitura sem informação
        # (backend cego: janela X morta, foco em janela Wayland nativa) NÃO
        # significa "é o desktop" — pula o tick INTEIRO: não mexe no candidato,
        # não reinicia o debounce, não ativa nada. O perfil corrente fica
        # retido até evidência POSITIVA de outra janela. Sem TTL de propósito:
        # o EIO de BT já mediu 5,1 s e loading screens duram minutos — TTL
        # re-introduziria o drop no meio do jogo.
        if self._tick_sem_informacao(info):
            if not self._info_gap_active:
                self._info_gap_active = True
                logger.info(
                    "autoswitch_window_info_unavailable",
                    wm_class=str(info.get("wm_class", "")),
                    current=self._current_profile or "",
                )
            # BUG-AUTOSWITCH-LOG-KEY-STUCK-01: o reset da chave de supressão
            # NÃO pode ser pulado junto com o tick — um episódio de supressão
            # que termina durante o gap deduplicaria o seguinte em silêncio.
            if not self._suppression_active():
                self._suppress_log_key = None
            return

        resumed = self._info_gap_active
        self._info_gap_active = False

        profile = self.manager.select_for_window(info)
        candidate = profile.name if profile else None

        if candidate != self._last_candidate or resumed:
            # `resumed`: primeira leitura útil após um gap reinicia o relógio
            # do debounce — o tempo pulado não conta como estabilidade
            # (armadilha 1 da UX-01: sem isso, duas leituras-glitch idênticas
            # separadas por minutos ativariam instantaneamente).
            self._last_candidate = candidate
            self._candidate_since = now

        stable = now - self._candidate_since >= self.debounce_sec
        # BUG-AUTOSWITCH-LOG-KEY-STUCK-01: reabre o log de supressão assim que
        # a supressão CESSA, independente de haver ativação. Antes a chave só
        # zerava dentro de `_activate` (que só roda com candidate != current),
        # então um episódio que terminava com o candidato estável == perfil
        # corrente (ex.: trigger.reset com a janela do jogo em foco) deixava a
        # chave presa e deduplicava em silêncio o episódio seguinte.
        if not self._suppression_active():
            self._suppress_log_key = None
        if stable and candidate and candidate != self._current_profile:
            self._activate(candidate, info)

    @staticmethod
    def _tick_sem_informacao(info: dict[str, Any]) -> bool:
        """True quando a leitura de janela não carrega NENHUMA evidência.

        UX-01: info vazio OU (`wm_class` vazio/'unknown' E `wm_name` vazio E
        `exe_basename` vazio). A condição é estrita de propósito: janela X com
        título ou processo preenchidos AINDA entra no select (preserva perfis
        por `window_title_regex`/`process_name`). Tradeoff residual aceito e
        coberto por teste: janela X sem WM_CLASS mas com título ativa o
        fallback MatchAny depois do debounce.
        """
        if not info:
            return True
        wm_class = str(info.get("wm_class") or "")
        if wm_class not in ("", "unknown"):
            return False
        wm_name = str(info.get("wm_name") or "")
        exe_basename = str(info.get("exe_basename") or "")
        return not wm_name and not exe_basename

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.create_task(self.run(), name="autoswitch")
        return self._task

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def _suppression_active(self) -> bool:
        """True se alguma fonte de supressão do autoswitch está ativa agora
        (override de trigger manual ou lock de perfil manual). Espelha os gates
        de `_activate`; usado pelo run-loop para saber quando o episódio de
        supressão terminou e reabrir o log (BUG-AUTOSWITCH-LOG-KEY-STUCK-01)."""
        if self.store is None:
            return False
        if self.store.manual_trigger_active:
            return True
        return self.store.manual_profile_lock_active(time.monotonic())

    def _activate(self, name: str, info: dict[str, Any]) -> None:
        # FEAT-NATIVE-MODE-01: em Modo Nativo MANUAL o controle está SOLTO para
        # o jogo — o autoswitch NÃO ativa perfil (que re-escreveria gatilhos por
        # cima) até a usuária desligar. Silencioso (estado estável).
        # FEAT-PROFILE-MODE-01: nativo ligado POR PERFIL não congela — o
        # autoswitch continua observando a janela para que, ao focar outro app,
        # o perfil seguinte reverta o nativo (senão o modo por-perfil nunca
        # sairia do jogo).
        if (
            self.store is not None
            and self.store.native_mode_active
            and getattr(self.store, "native_mode_origin", None) != "profile"
        ):
            return
        # BUG-MOUSE-TRIGGERS-01: se o usuário tem um trigger manual aplicado
        # via aba Gatilhos, autoswitch suspende até o override ser limpo por
        # trigger.reset ou profile.switch explícito. Sem isso, ao ligar a aba
        # Mouse (que move o cursor e muda o foco de janela), o autoswitch
        # reaplicaria o fallback e zeraria o trigger recém-aplicado.
        if self.store is not None and self.store.manual_trigger_active:
            self._log_suppressed_once(
                "autoswitch_suppressed_by_manual_override", name, info
            )
            return
        # CLUSTER-IPC-STATE-PROFILE-01 (Bug C): respeita lock manual armado
        # por `profile.switch` IPC. Lock dura `MANUAL_PROFILE_LOCK_SEC` (30s)
        # e expira sozinho — não exige reset.
        if self.store is not None and self.store.manual_profile_lock_active(
            time.monotonic()
        ):
            self._log_suppressed_once(
                "autoswitch_suppressed_by_manual_profile_lock", name, info
            )
            return
        # Chegou aqui = sem supressão: zera a chave (reabre o log do próximo
        # episódio). O run-loop faz o MESMO reset a cada tick — necessário para o
        # caso candidate == current, em que _activate nem roda
        # (BUG-AUTOSWITCH-LOG-KEY-STUCK-01). Manter ambos cobre chamadas diretas.
        self._suppress_log_key = None
        from_profile = self._current_profile
        try:
            # PERFIL-03: troca AUTOMÁTICA por janela — origin="autoswitch" NÃO
            # grava session.json. Era o bug provado do autoload: o autoswitch
            # reescrevia a intenção manual da usuária a cada troca de janela e
            # o boot restaurava "Navegação" em vez do perfil que ela escolheu.
            self.manager.activate(name, origin="autoswitch")
        except Exception as exc:
            logger.warning("autoswitch_activate_failed", name=name, err=str(exc))
            return
        self._current_profile = name
        logger.info(
            "profile_autoswitch",
            from_=from_profile,
            to=name,
            wm_class=info.get("wm_class", ""),
            wm_name=info.get("wm_name", ""),
        )

    def _log_suppressed_once(
        self, event: str, name: str, info: dict[str, Any]
    ) -> None:
        """Loga a supressão do autoswitch 1x por (motivo, candidato).

        FEAT-POINT-AND-CLICK-01: o tick de 0,5s repetia o mesmo log enquanto o
        override manual durasse — journal inundado a ~2 Hz. Deduplica pela
        chave (evento, candidato); a chave é zerada quando `_activate` roda
        sem supressão, reabrindo o log para o episódio seguinte.
        """
        key = (event, name)
        if self._suppress_log_key == key:
            return
        self._suppress_log_key = key
        logger.info(event, candidate=name, wm_class=info.get("wm_class", ""))


__all__ = [
    "DEFAULT_DEBOUNCE_SEC",
    "DEFAULT_POLL_INTERVAL_SEC",
    "AutoSwitcher",
    "WindowReader",
]
