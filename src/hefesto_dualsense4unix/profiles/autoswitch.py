"""Auto-switch de perfil conforme janela X11 ativa."""
from __future__ import annotations

import asyncio
import contextlib
import math
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import (
    MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    MOTIVO_SEM_CANDIDATO,
    ProfileManager,
    _estado_da_secao,
    o_freestyle_manda,
    soltar_a_trava_da_mao,
)
from hefesto_dualsense4unix.profiles.schema import (
    Profile,
    e_endereco_de_jogo,
    perfil_declara_modo_de_jogo,
    perfil_e_regra_de_jogo,
)
from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class
from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL_SEC = 0.5
DEFAULT_DEBOUNCE_SEC = 0.5

DEFAULT_DEBOUNCE_SAIDA_SEC = 12.0

OWN_GUI_WM_CLASSES: frozenset[str] = frozenset(
    {
        "main.py",
        "com.vitoriamaria.hefestodualsense4unix",
    }
    | {
        nome.casefold()
        for nome in (
            identidade.HEFESTO.wm_instance,
            identidade.HEFESTO.wm_class,
            identidade.HEFESTO.entrypoint_gui,
        )
    }
)


WindowReader = Callable[[], dict[str, Any]]


def _cmdline_confirma_appid(
    pid: int, appid: int, proc_dir: Path | None = None
) -> bool:
    """A linha de comando de `pid` anuncia `AppId=<appid>`? (FOCO-ERRANTE-01)"""
    base = proc_dir if proc_dir is not None else Path("/proc")
    try:
        bruto = (base / str(pid) / "cmdline").read_bytes()
    except OSError:
        return False
    except Exception:  # defensivo: sondar /proc jamais derruba o tique
        logger.debug("cmdline_do_jogo_ilegivel", exc_info=True)
        return False
    texto = bruto.decode("utf-8", "replace").replace("\0", " ")
    return (
        re.search(
            rf"(?<![0-9A-Za-z_])appid={appid}(?![0-9])", texto, re.IGNORECASE
        )
        is not None
    )


def jogo_do_wrapper_vivo(
    *,
    base_dir: Path | None = None,
    proc_dir: Path | None = None,
    now: float | None = None,
) -> int | None:
    """Appid do jogo do wrapper que ainda está RODANDO agora, ou None."""
    from hefesto_dualsense4unix.daemon.launch_env import (
        pid_is_alive,
        read_last_exit_marker,
        read_last_exit_pid,
        read_last_run_marker,
        read_last_run_pid,
        wrapper_game_running,
    )

    marker = read_last_run_marker(base_dir)
    if marker is None:
        return None
    marker_pid = read_last_run_pid(base_dir)
    if marker_pid is None:
        return None
    vivo = wrapper_game_running(
        marker=marker,
        exit_marker=read_last_exit_marker(base_dir),
        pid_alive=pid_is_alive(marker_pid),
        marker_pid=marker_pid,
        exit_pid=read_last_exit_pid(base_dir),
        now=now,
        window_sec=math.inf,
    )
    if not vivo:
        return None
    appid = marker[0]
    if not _cmdline_confirma_appid(marker_pid, appid, proc_dir):
        return None
    return appid


def _appids_de_jogo_do_perfil(profile: object) -> frozenset[int]:
    """Os appids de que este perfil é a regra PRÓPRIA (FOCO-ERRANTE-01)."""
    match = getattr(profile, "match", None)
    classes = getattr(match, "window_class", None)
    if not isinstance(classes, (list, tuple, set, frozenset)):
        return frozenset()
    achados = set()
    for classe in classes:
        appid = steam_appid_from_wm_class(classe if isinstance(classe, str) else None)
        if appid is not None:
            achados.add(appid)
    return frozenset(achados)


@dataclass
class AutoSwitcher:
    manager: ProfileManager
    window_reader: WindowReader
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC
    debounce_sec: float = DEFAULT_DEBOUNCE_SEC
    debounce_saida_sec: float = DEFAULT_DEBOUNCE_SAIDA_SEC
    store: StateStore | None = None
    modo_jogo_padrao_applier: Callable[..., object] | None = None
    modo_jogo_padrao_reverter: Callable[..., object] | None = None
    jogo_vivo_reader: Callable[[], int | None] | None = None
    exclusao_applier: Callable[..., object] | None = None
    exclusao_reverter: Callable[..., object] | None = None
    exclusao_reader: Callable[[str], bool] | None = None

    _last_candidate: str | None = None
    _candidate_since: float = 0.0
    _current_profile: str | None = None
    _stop_event: asyncio.Event | None = None
    _task: asyncio.Task[Any] | None = None
    _suppress_log_key: tuple[str, str] | None = None
    _info_gap_active: bool = False
    _current_especifico: bool = False
    _freestyle_log_key: str | None = None
    _estado_modo_jogo_padrao: str = ""
    _exclusao_em_foco: str | None = None
    _recusa_log_key: tuple[str, str] | None = None
    _appids_do_perfil_nome: str | None = None
    _appids_do_perfil_valor: frozenset[int] = frozenset()
    _foco_do_negativo: tuple[object, str] | None = None
    _escolha_nome: str | None = None
    _escolha_perfil: Profile | None = None
    _trava_vista: bool = False
    _jogo_da_trava: str | None = None
    _appids_da_trava: frozenset[int] = frozenset()
    _antes_da_mao: str | None = None
    _ativo_da_trava: str | None = None
    _jogo_da_trava_visto_vivo: bool = False
    _ultima_janela: str = ""

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

    def freestyle_ligado(self) -> bool:
        """True quando o Modo Freestyle está ligado: o tique não casa a janela."""
        return o_freestyle_manda(self._store_de_estado())

    def _store_de_estado(self) -> Any | None:
        """O store onde mora o perfil REALMENTE ativo (nunca `None` em produção)."""
        if self.store is not None:
            return self.store
        return getattr(self.manager, "store", None)

    def _perfil_corrente(self) -> str | None:
        """Nome do perfil ATIVO de verdade, sincronizando a crença do autoswitch.

        PERFIL-REESCRITO-NA-PARTIDA-01, item 1 (o de maior alcance da leva).
        `_current_profile` era escrito num único lugar — o commit do próprio
        `_activate` — e NADA o sincronizava com `store.active_profile`. Um
        `profile.switch` dela (janela, CLI, PS+D-pad) trocava o perfil de
        verdade e o autoswitch seguia acreditando no que ELE tinha ativado por
        último. A prova está no journal dela: `profile_autoswitch from_=None
        to=sackboy_nativo` com outro perfil ativo havia horas — o autoswitch
        "entrando" num perfil que já era o ativo, reescrevendo gatilhos, LEDs,
        modo e política de rumble por cima do que ela tinha escolhido na mão.

        A decisão passa a ser tomada contra o estado REAL: `ProfileManager
        .activate` publica `store.set_active_profile(...)` em TODA ativação, de
        qualquer origem, então o store já era a única fonte honesta — faltava
        lê-lo.

        Quando a crença diverge, a especificidade (`_current_especifico`, que
        arma o lado lento do debounce assimétrico UX-04) vira `True` —
        "trate como perfil específico" — porque um nome novo com a
        especificidade do perfil ANTIGO seria uma terceira crença errada.
        `True` é o palpite seguro e o único gratuito: ele apenas torna mais
        CARO sair do perfil rumo a um genérico (12 s em vez de 0,5 s), e depois
        de um gesto explícito dela ficar tem custo zero, enquanto sair rápido
        reabre o flap que a UX-04 fechou. Nada de reler o disco aqui: o
        `ProfileManager.get` varre o diretório de perfis, e a docstring do
        `_current_especifico` já proíbe I/O nesta decisão. O palpite é
        corrigido de graça no próprio tique — ver `_tick`, quando o candidato
        selecionado é o perfil corrente.

        `active_profile` vazio/ausente/não-string (store parcial, dublê
        `MagicMock`) NÃO derruba a crença: sem evidência positiva, vale o
        comportamento histórico.

        O EFEITO COLATERAL, declarado porque é real: o restore de boot também
        publica em `store.active_profile`, então o autoswitch deixa de "entrar"
        no perfil que o boot acabou de restaurar (antes, a crença `None` fazia
        o primeiro tique re-ativá-lo ~1 s depois). Isso não é perda — é o
        `BUG-BOOT-RESTORE-FLIPS-EMULATION-01` sendo respeitado: o restore de
        boot monta o manager com `mouse_applier=None` e `mode_applier=None` de
        propósito, porque no boot quem governa a emulação são os FLAGS
        PERSISTIDOS, não o perfil (com o applier ligado, um `point_and_click`
        como last_profile matava o gamepad restaurado e invertia a escolha dela
        a cada boot). A re-ativação pelo autoswitch reintroduzia por acidente
        exatamente o que aquela cura removeu.
        """
        store = self._store_de_estado()
        if store is None:
            return self._current_profile
        ativo = getattr(store, "active_profile", None)
        if not isinstance(ativo, str) or not ativo:
            return self._current_profile
        if ativo != self._current_profile:
            anterior = self._current_profile
            self._antes_da_mao = anterior
            self._current_profile = ativo
            self._current_especifico = True
            logger.info(
                "autoswitch_crenca_sincronizada",
                de=anterior or "",
                para=ativo,
            )
        return self._current_profile

    def _outra_janela_invalida_o_negativo(self, info: dict[str, Any]) -> None:
        """Outra janela em foco joga fora o «não há jogo» da varredura de `/proc`."""
        if not _ode.armado():
            return
        wm_class = str(info.get("wm_class") or "")
        pid = info.get("pid") or None
        if not pid and wm_class in ("", "unknown"):
            return
        chave = (pid, wm_class)
        if chave == self._foco_do_negativo:
            return
        self._foco_do_negativo = chave
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            invalidar_varredura_de_proc,
        )

        invalidar_varredura_de_proc()

    def _tick(self, info: dict[str, Any], now: float) -> None:
        """Um ciclo de decisão do autoswitch (leitura já feita pelo caller)."""
        self._perfil_corrente()
        self._acompanhar_a_trava_da_mao()
        self._outra_janela_invalida_o_negativo(info)
        eh_propria = self._janela_propria(info)
        if eh_propria or self._tick_sem_informacao(info):
            if not self._info_gap_active:
                self._info_gap_active = True
                logger.info(
                    "autoswitch_janela_propria_ignorada"
                    if eh_propria
                    else "autoswitch_window_info_unavailable",
                    wm_class=str(info.get("wm_class", "")),
                    current=self._current_profile or "",
                )
            if not self._suppression_active():
                self._suppress_log_key = None
            return

        resumed = self._info_gap_active
        self._info_gap_active = False
        self._ultima_janela = str(info.get("wm_class") or "")

        if self._na_exclusao(info):
            self._last_candidate = None
            if not self._suppression_active():
                self._suppress_log_key = None
            return

        if self.freestyle_ligado():
            self._log_freestyle_uma_vez(info)
            self._modo_jogo_padrao_sob_o_freestyle(info)
            self._last_candidate = None
            if not self._suppression_active():
                self._suppress_log_key = None
            return
        self._freestyle_log_key = None

        profile, motivo = self._selecionar_com_motivo(info)
        veio_da_escolha = False
        if profile is None and motivo == MOTIVO_SEM_CANDIDATO:
            profile = self._perfil_da_escolha()
            veio_da_escolha = profile is not None
        candidate = profile.name if profile else None

        if candidate is not None and candidate == self._current_profile:
            self._current_especifico = not bool(getattr(profile, "e_catch_all", True))

        self._sincronizar_modo_jogo_padrao(motivo, info)

        if self._recusa_a_troca_com_o_jogo_vivo(
            candidate, profile, info, veio_da_escolha=veio_da_escolha
        ):
            self._last_candidate = None
            if not self._suppression_active():
                self._suppress_log_key = None
            return
        self._recusa_log_key = None

        if candidate != self._last_candidate or resumed:
            self._last_candidate = candidate
            self._candidate_since = now

        limite = self.debounce_sec
        if self._saida_para_a_escolha(profile, veio_da_escolha):
            limite = max(self.debounce_sec, self.debounce_saida_sec)
        stable = now - self._candidate_since >= limite
        # corrente (ex.: trigger.reset com a janela do jogo em foco) deixava a
        if not self._suppression_active():
            self._suppress_log_key = None
        if stable and candidate and candidate != self._current_profile:
            self._activate(candidate, info, profile, veio_da_escolha=veio_da_escolha)

    def _selecionar_com_motivo(
        self, info: dict[str, Any]
    ) -> tuple[Profile | None, str]:
        """Seleciona o perfil da janela e traz junto o MOTIVO (MODO-01/B3)."""
        seletor = getattr(self.manager, "select_for_window_ex", None)
        if callable(seletor):
            resultado = seletor(info)
            if isinstance(resultado, tuple) and len(resultado) == 2:
                perfil, motivo = resultado
                return perfil, str(motivo)
        perfil_legado = self.manager.select_for_window(info)
        return perfil_legado, MOTIVO_SEM_CANDIDATO

    def _na_exclusao(self, info: dict[str, Any]) -> bool:
        """A janela em foco está na lista de exclusão? Aplica ou solta (E3)."""
        wm_class = str(info.get("wm_class") or "").strip()
        reader = self.exclusao_reader
        excluida = False
        if wm_class and reader is not None:
            try:
                excluida = bool(reader(wm_class))
            except Exception as exc:
                logger.warning("exclusao_leitura_falhou", err=str(exc))
        if excluida:
            if self._exclusao_em_foco != wm_class:
                logger.info("autoswitch_janela_excluida", wm_class=wm_class)
            self._exclusao_em_foco = wm_class
            applier = self.exclusao_applier
            if applier is not None:
                try:
                    applier(chave=wm_class)
                except Exception as exc:
                    logger.warning("exclusao_falhou", err=str(exc))
            return True
        if self._exclusao_em_foco is not None:
            reverter = self.exclusao_reverter
            if reverter is not None:
                try:
                    reverter()
                except Exception as exc:
                    logger.warning("exclusao_revert_falhou", err=str(exc))
            self._exclusao_em_foco = None
        return False

    def _sincronizar_modo_jogo_padrao(
        self, motivo: str, info: dict[str, Any]
    ) -> None:
        """Liga/solta o MODO JOGO PADRÃO conforme o motivo da seleção (B3)."""
        wm_class = str(info.get("wm_class") or "")
        if motivo == MOTIVO_JOGO_SEM_PERFIL_PROPRIO:
            applier = self.modo_jogo_padrao_applier
            if applier is None:
                return
            try:
                self._estado_modo_jogo_padrao = _estado_da_secao(
                    applier(wm_class=wm_class)
                )
            except Exception as exc:
                self._estado_modo_jogo_padrao = "falhou"
                logger.warning("modo_jogo_padrao_falhou", err=str(exc))
            return
        reverter = self.modo_jogo_padrao_reverter
        if reverter is None:
            return
        try:
            self._estado_modo_jogo_padrao = _estado_da_secao(
                reverter(wm_class=wm_class)
            )
        except Exception as exc:
            self._estado_modo_jogo_padrao = "falhou"
            logger.warning("modo_jogo_padrao_revert_falhou", err=str(exc))

    def _modo_jogo_padrao_sob_o_freestyle(self, info: dict[str, Any]) -> None:
        """O modo jogo padrão com o Freestyle ligado: só quando ele não diz o modo."""
        if self._o_freestyle_diz_o_modo():
            return
        motivo = (
            MOTIVO_JOGO_SEM_PERFIL_PROPRIO
            if e_endereco_de_jogo(info.get("wm_class"))
            else MOTIVO_SEM_CANDIDATO
        )
        self._sincronizar_modo_jogo_padrao(motivo, info)

    @staticmethod
    def _o_freestyle_diz_o_modo() -> bool:
        """O Freestyle do disco tem a seção `mode`? Sem o arquivo, não diz."""
        from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO, perfil_em_disco

        freestyle = perfil_em_disco(NOME_DO_PADRAO)
        return freestyle is not None and freestyle.mode is not None

    def _saida_para_a_escolha(
        self, profile: Profile | None, veio_da_escolha: bool
    ) -> bool:
        """True quando a troca é SAÍDA de um perfil específico rumo à escolha dela."""
        if profile is None or not veio_da_escolha or not self._current_especifico:
            return False
        return self._current_profile is not None and profile.name != self._current_profile

    def _perfil_da_escolha(self) -> Profile | None:
        """O perfil da escolha dela, pelo dono (`a_escolha_dela`). Nunca levanta."""
        from hefesto_dualsense4unix.utils.session import a_escolha_dela

        nome = a_escolha_dela(freestyle_ligado=self.freestyle_ligado())
        if not nome:
            self._escolha_nome = None
            self._escolha_perfil = None
            return None
        if nome == self._escolha_nome and self._escolha_perfil is not None:
            return self._escolha_perfil
        getter = getattr(self.manager, "get", None)
        if not callable(getter):
            return None
        try:
            perfil = getter(nome)
        except Exception as exc:
            logger.debug("escolha_ilegivel", name=nome, err=str(exc))
            return None
        if not isinstance(perfil, Profile):
            return None
        self._escolha_nome = nome
        self._escolha_perfil = perfil
        return perfil

    def _recusa_a_troca_com_o_jogo_vivo(
        self,
        candidate: str | None,
        profile: Profile | None,
        info: dict[str, Any],
        *,
        veio_da_escolha: bool = False,
    ) -> bool:
        """A troca de perfil tem de ser RECUSADA neste tique? (FOCO-ERRANTE-01)"""
        corrente = self._current_profile
        if candidate is None or corrente is None or candidate == corrente:
            return False
        if not veio_da_escolha and (
            perfil_e_regra_de_jogo(profile, info) or perfil_declara_modo_de_jogo(profile)
        ):
            return False
        appids = self._appids_do_perfil_corrente(corrente)
        if not appids:
            return False
        appid_vivo = self._appid_do_jogo_vivo()
        if appid_vivo is None or appid_vivo not in appids:
            return False
        self._log_recusa_uma_vez(candidate, corrente, appid_vivo, info)
        return True

    def _appid_do_jogo_vivo(self) -> int | None:
        """Appid do jogo do wrapper vivo agora, pelo leitor injetado ou o real."""
        leitor = self.jogo_vivo_reader
        try:
            return jogo_do_wrapper_vivo() if leitor is None else leitor()
        except Exception as exc:
            logger.debug("jogo_vivo_indisponivel", err=str(exc))
            return None

    def _appids_do_perfil_corrente(self, nome: str) -> frozenset[int]:
        """Appids de que o perfil CORRENTE é a regra própria, com cache por nome."""
        if self._appids_do_perfil_nome == nome:
            return self._appids_do_perfil_valor
        getter = getattr(self.manager, "get", None)
        appids: frozenset[int] = frozenset()
        if callable(getter):
            try:
                appids = _appids_de_jogo_do_perfil(getter(nome))
            except Exception as exc:
                logger.debug("perfil_corrente_ilegivel", name=nome, err=str(exc))
                appids = frozenset()
        self._appids_do_perfil_nome = nome
        self._appids_do_perfil_valor = appids
        return appids

    def _log_recusa_uma_vez(
        self, candidate: str, corrente: str, appid: int, info: dict[str, Any]
    ) -> None:
        """Loga a recusa 1x por episódio (candidato, perfil corrente)."""
        key = (candidate, corrente)
        if self._recusa_log_key == key:
            return
        self._recusa_log_key = key
        logger.info(
            "autoswitch_recusou_a_troca_com_o_jogo_vivo",
            candidato=candidate,
            perfil_corrente=corrente,
            appid=appid,
            wm_class=str(info.get("wm_class") or ""),
        )

    def _log_freestyle_uma_vez(self, info: dict[str, Any]) -> None:
        """Loga a parada pelo Freestyle 1x por janela em foco."""
        chave = str(info.get("wm_class") or "")
        if self._freestyle_log_key == chave:
            return
        self._freestyle_log_key = chave
        logger.info(
            "autoswitch_parado_pelo_freestyle",
            wm_class=chave,
            current=self._current_profile or "",
        )

    @staticmethod
    def _tick_sem_informacao(info: dict[str, Any]) -> bool:
        """True quando a leitura de janela não carrega NENHUMA evidência."""
        if not info:
            return True
        wm_class = str(info.get("wm_class") or "")
        if wm_class not in ("", "unknown"):
            return False
        wm_name = str(info.get("wm_name") or "")
        exe_basename = str(info.get("exe_basename") or "")
        return not wm_name and not exe_basename

    @staticmethod
    def _janela_propria(info: dict[str, Any]) -> bool:
        """True quando a janela em foco é a própria GUI/applet do hefesto."""
        wm_class = str(info.get("wm_class") or "").strip().casefold()
        return wm_class in OWN_GUI_WM_CLASSES

    def start(self) -> asyncio.Task[Any]:
        self._task = asyncio.create_task(self.run(), name="autoswitch")
        return self._task

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def _acompanhar_a_trava_da_mao(self) -> None:
        """Guarda, a cada troca à mão, o jogo em cena; e solta a trava quando ele fecha."""
        store = self.store
        if store is None:
            return
        try:
            armada = bool(store.manual_profile_lock_active(time.monotonic()))
        except Exception:
            armada = False
        if not armada:
            self._esquecer_o_jogo_da_trava()
            return
        if not self._trava_vista or self._current_profile != self._ativo_da_trava:
            self._trava_vista = True
            self._ativo_da_trava = self._current_profile
            if self._jogo_da_trava is None:
                self._guardar_o_jogo_em_cena(self._antes_da_mao)
            return
        if not (self._appids_da_trava and self._jogo_da_trava_visto_vivo):
            return
        vivo = self._appid_do_jogo_vivo()
        if vivo is not None and vivo in self._appids_da_trava:
            return
        jogo = self._jogo_da_trava or ""
        self._esquecer_o_jogo_da_trava()
        soltar_a_trava_da_mao(store, "o_jogo_em_cena_fechou", jogo=jogo, candidato="")

    def _guardar_o_jogo_em_cena(self, jogo: str | None) -> None:
        """O perfil que a mão tirou é o de um jogo ABERTO? Só então ele é guardado."""
        appids = self._appids_do_perfil_corrente(jogo) if jogo else frozenset()
        if not appids:
            return
        vivo = self._appid_do_jogo_vivo()
        visto_vivo = vivo is not None and vivo in appids
        em_foco = self._ultima_janela in {f"steam_app_{a}" for a in appids}
        if not (visto_vivo or (vivo is None and em_foco)):
            return
        self._jogo_da_trava = jogo
        self._appids_da_trava = appids
        self._jogo_da_trava_visto_vivo = visto_vivo

    def _esquecer_o_jogo_da_trava(self) -> None:
        self._trava_vista = False
        self._ativo_da_trava = None
        self._jogo_da_trava = None
        self._appids_da_trava = frozenset()
        self._jogo_da_trava_visto_vivo = False

    def _a_trava_da_mao_segura(
        self,
        name: str,
        profile: Profile | None,
        info: dict[str, Any],
        veio_da_escolha: bool,
    ) -> bool:
        """A trava da troca à mão segura ESTA troca? Solta-a no evento, com a linha."""
        store = self.store
        if store is None or not store.manual_profile_lock_active(time.monotonic()):
            return False
        jogo = self._jogo_da_trava
        if self._appids_da_trava and name != jogo:
            vivo = self._appid_do_jogo_vivo()
            if vivo is None or vivo not in self._appids_da_trava:
                self._esquecer_o_jogo_da_trava()
                soltar_a_trava_da_mao(
                    store, "o_jogo_em_cena_fechou", jogo=jogo or "", candidato=name
                )
                return False
        e_outro_jogo = (
            not veio_da_escolha
            and profile is not None
            and name != jogo
            and (perfil_e_regra_de_jogo(profile, info) or perfil_declara_modo_de_jogo(profile))
        )
        if e_outro_jogo:
            soltar_a_trava_da_mao(
                store, "jogo_com_perfil_em_foco", candidato=name, jogo=jogo or "",
                wm_class=str(info.get("wm_class") or ""),
            )
            return False
        return True

    def _suppression_active(self) -> bool:
        """True se alguma fonte de supressão do autoswitch está ativa agora."""
        if self.store is None:
            return False
        return self.store.manual_profile_lock_active(time.monotonic())

    def _activate(
        self,
        name: str,
        info: dict[str, Any],
        profile: Profile | None = None,
        *,
        veio_da_escolha: bool = False,
    ) -> None:
        self._perfil_corrente()
        if (
            self.store is not None
            and self.store.native_mode_active
            and getattr(self.store, "native_mode_origin", None) != "profile"
        ):
            return
        # por trigger.reset ou profile.switch explícito. Sem isso, ao ligar a
        # *"isso nao faz sentido mais."*  # (noqa-acento): citação literal
        if self._a_trava_da_mao_segura(name, profile, info, veio_da_escolha):
            self._log_suppressed_once(
                "autoswitch_suppressed_by_manual_profile_lock", name, info
            )
            return
        self._suppress_log_key = None
        from_profile = self._current_profile
        relatorio: dict[str, str] = {}
        try:
            self.manager.activate(name, origin="autoswitch", relatorio=relatorio)
        except Exception as exc:
            logger.warning("autoswitch_activate_failed", name=name, err=str(exc))
            return
        self._current_profile = name
        if profile is not None:
            self._appids_do_perfil_nome = name
            self._appids_do_perfil_valor = _appids_de_jogo_do_perfil(profile)
        else:
            self._appids_do_perfil_nome = None
        self._current_especifico = profile is not None and not bool(
            getattr(profile, "e_catch_all", True)
        )
        if self._estado_modo_jogo_padrao:
            relatorio["modo_jogo_padrao"] = self._estado_modo_jogo_padrao
        logger.info(
            "profile_autoswitch",
            from_=from_profile,
            to=name,
            wm_class=info.get("wm_class", ""),
            wm_name=info.get("wm_name", ""),
            adiado=sorted(
                secao
                for secao, estado in relatorio.items()
                if estado.startswith("adiado")
            ),
            secoes=sorted(
                f"{secao}={estado}" for secao, estado in relatorio.items()
            ),
        )

    def _log_suppressed_once(
        self, event: str, name: str, info: dict[str, Any]
    ) -> None:
        """Loga a supressão do autoswitch 1x por (motivo, candidato)."""
        key = (event, name)
        if self._suppress_log_key == key:
            return
        self._suppress_log_key = key
        logger.info(event, candidate=name, wm_class=info.get("wm_class", ""))


__all__ = [
    "DEFAULT_DEBOUNCE_SAIDA_SEC",
    "DEFAULT_DEBOUNCE_SEC",
    "DEFAULT_POLL_INTERVAL_SEC",
    "OWN_GUI_WM_CLASSES",
    "AutoSwitcher",
    "WindowReader",
    "jogo_do_wrapper_vivo",
]
