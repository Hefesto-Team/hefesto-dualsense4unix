"""Auto-switch de perfil conforme janela X11 ativa.

Poll a 2Hz (`poll_interval_sec=0.5`), debounce ASSIMÉTRICO (UX-04): 500ms para
ENTRAR num perfil específico, `DEFAULT_DEBOUNCE_SAIDA_SEC` para SAIR dele rumo
a um catch-all. Aplica via ProfileManager.activate quando a escolha muda.

UX-01 (SPRINT-UX-AUTOSWITCH-01): histerese — leitura SEM INFORMAÇÃO
("não sei qual janela está em foco") pula o tick inteiro e retém o perfil
corrente. Antes, o backend cego virava `wm_class='unknown'`, o `MatchAny`
do perfil padrão casava com tudo e a emulação caía no meio do jogo
(provado ao vivo: journal 03:40:29 e 13:07:18 de 2026-07-16).

FOCO-ERRANTE-01 (18/08/2026): a janela do CLIENTE Steam não tira o perfil de um
jogo VIVO. A histerese UX-01 cobre a AUSÊNCIA de dado; nada cobria o dado
ERRADO — e sob XWayland uma janela invisível do `steamwebhelper` (classe
`steam`) rouba o foco do X no meio da partida. Ver `jogo_do_wrapper_vivo` e
`AutoSwitcher._recusa_a_janela_do_cliente_steam`.

Desligável via env `HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT=1` (usado pelo unit headless,
V2-4 / Patch 8).
"""
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

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import (
    MOTIVO_JOGO_SEM_PERFIL_PROPRIO,
    MOTIVO_SEM_CANDIDATO,
    ProfileManager,
    _estado_da_secao,
)
from hefesto_dualsense4unix.profiles.schema import (
    Profile,
    perfil_declara_modo_de_jogo,
    perfil_e_regra_de_jogo,
)
from hefesto_dualsense4unix.profiles.steam_app import (
    e_janela_do_cliente_steam,
    steam_appid_from_wm_class,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_POLL_INTERVAL_SEC = 0.5
DEFAULT_DEBOUNCE_SEC = 0.5

#: UX-04 (auditoria 24/07): debounce ASSIMÉTRICO. ENTRAR num perfil específico
#: (a regra do jogo que ela abriu) continua custando ~0,5 s — é o que faz o
#: modo/lightbar/gatilhos valerem desde o começo da partida. SAIR de um perfil
#: específico rumo a um CATCH-ALL custa isto aqui.
#:
#: O porquê está medido: com poll de 0,5 s e debounce de 0,5 s, DOIS ticks
#: bastavam para trocar de perfil, e a histerese UX-01 só cobre leitura SEM
#: informação — entre duas janelas CONHECIDAS não havia cooldown nenhum. No
#: journal de 22-23/07 isso virou `vitoria``Navegação` a cada 18-28 s, com o
#: controle mudando de cor e de comportamento no meio do jogo ("controles
#: malucos"). A assimetria é a forma certa: uma pausa de 12 s no jogo (overlay
#: da Steam, navegador para ver um guia, notificação que rouba o foco) não é
#: "ela saiu do jogo", e o custo de errar para o lado de ficar é zero — o
#: perfil só volta ao genérico quando ela REALMENTE ficou fora.
DEFAULT_DEBOUNCE_SAIDA_SEC = 12.0

#: MISC-08 item 2 (2026-07-18): wm_class da PRÓPRIA GUI/applet do hefesto.
#: Focar a nossa janela não é evidência de "saiu do jogo" — ao vivo (journal
#: 20:15:40-51) cada alt-tab jogoGUI flipava vitoriasackboy_nativo, mexendo
#: em política de rumble/modo no meio da partida. Valores provados no journal
#: (`Main.py`, `Hefesto-Dualsense4Unix`) + o instance do WM_CLASS e o prgname
#: ("hefesto-dualsense4unix", app/app.py + app/main.py), o entrypoint da GUI
#: ("hefesto-dualsense4unix-gui", app/main.py) e o APP_ID do applet COSMIC
#: (packaging/cosmic-applet/src/app.rs). Comparação case-insensitive.
#: Tradeoff aceito: "Main.py" é genérico (outro app GTK rodando um Main.py
#: também seria retido) — é o valor que a nossa GUI de fato reporta sob
#: XWayland, então precisa estar coberto.
OWN_GUI_WM_CLASSES: frozenset[str] = frozenset(
    {
        "main.py",
        "hefesto-dualsense4unix",
        "hefesto-dualsense4unix-gui",
        "com.vitoriamaria.hefestodualsense4unix",
    }
)


WindowReader = Callable[[], dict[str, Any]]


def _cmdline_confirma_appid(
    pid: int, appid: int, proc_dir: Path | None = None
) -> bool:
    """A linha de comando de `pid` anuncia `AppId=<appid>`? (FOCO-ERRANTE-01)

    É a corroboração que SUBSTITUI a janela de frescor de 15 min do
    `wrapper_game_running` — ver `jogo_do_wrapper_vivo`. O que a janela de
    tempo cobria era o PID RECICLADO: um marker velho apontando para um número
    que o núcleo já entregou a outro processo. A linha de comando responde a
    mesma pergunta sem prazo de validade, porque o processo do marker é o
    `reaper` da Steam e ele carrega o appid na própria `argv`, medido na
    máquina dela em 18/08 (`.../reaper SteamLaunch AppId=2497900 -- ...`).

    Consequência declarada: jogo lançado pelo wrapper FORA da Steam não tem
    `AppId=` na `argv` e não é reconhecido aqui. É o lado seguro do erro — sem
    corroboração, sem guarda, e o autoswitch segue como sempre seguiu.

    `proc_dir` existe pela mesma razão do `base_dir` das funções de marker do
    `launch_env`: dar costura de teste hermético. Nunca levanta — leitura de
    `/proc` que falha vira "não confirmei".
    """
    base = proc_dir if proc_dir is not None else Path("/proc")
    try:
        bruto = (base / str(pid) / "cmdline").read_bytes()
    except OSError:
        return False
    except Exception:  # defensivo: sondar /proc jamais derruba o tique
        logger.debug("cmdline_do_jogo_ilegivel", exc_info=True)
        return False
    # `/proc/<pid>/cmdline` separa os argumentos por NUL; virar espaço mantém a
    # fronteira entre eles, que é o que o lookbehind abaixo usa.
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
    """Appid do jogo do wrapper que ainda está RODANDO agora, ou None.

    FOCO-ERRANTE-01 (18/08/2026). Irmã de `launch_env.launch_session_appid`,
    e a diferença entre as duas é a única razão de esta existir: aquela exige
    que o marker `last_run` seja FRESCO (`WRAPPER_MARKER_WINDOW_SEC`, 900 s), e
    a partida dela dura mais que isso. **Medido:** o marker tinha 1296 s de
    idade no instante em que o perfil do jogo foi roubado pela janela do
    cliente Steam (marker de 00:31:38, roubo às 00:53:14). Uma guarda montada
    sobre `launch_session_appid` teria respondido `None` e não teria evitado o
    defeito — por isso a janela de frescor SAI, e só ela.

    Tudo o mais é a MESMA decisão pura de sempre: `wrapper_game_running`
    (NUMA-01) é reusada com `window_sec=inf`, então a correlação por pid entre
    `last_run` e `last_exit` — a correção pós-auditoria da Onda N — continua
    valendo byte a byte. Reinventar o critério aqui reabriria a divergência
    entre predicados que o `profiles/steam_app.py` existe para fechar.

    O que ENTRA no lugar da janela de tempo é a corroboração por `AppId=` na
    linha de comando do processo (`_cmdline_confirma_appid`): sem prazo de
    validade e imune a PID reciclado, que era o risco real que os 900 s
    cobriam. Nunca levanta.
    """
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
        # Sem `pid=` no marker não há vitalidade nenhuma para atestar (marker
        # gravado por um wrapper anterior ao NUMA-01) — e sem PID também não há
        # linha de comando para corroborar. Recusar é o lado seguro.
        return None
    vivo = wrapper_game_running(
        marker=marker,
        exit_marker=read_last_exit_marker(base_dir),
        pid_alive=pid_is_alive(marker_pid),
        marker_pid=marker_pid,
        exit_pid=read_last_exit_pid(base_dir),
        now=now,
        # A ÚNICA diferença para `launch_session_appid`, e ela é o assunto
        # inteiro desta função (ver docstring).
        window_sec=math.inf,
    )
    if not vivo:
        return None
    appid = marker[0]
    if not _cmdline_confirma_appid(marker_pid, appid, proc_dir):
        return None
    return appid


def _appids_de_jogo_do_perfil(profile: object) -> frozenset[int]:
    """Os appids de que este perfil é a regra PRÓPRIA (FOCO-ERRANTE-01).

    Lê as `window_class` do `match` e as passa pelo predicado ÚNICO
    (`steam_app.steam_appid_from_wm_class`) — nada de um sexto predicado de
    "isto é janela de jogo da Steam", que é a armadilha nº 5 da sprint.

    Vazio quando o perfil não é regra de jogo da Steam (catch-all, regra por
    título/processo, dublê de teste sem `match`): a guarda que consome isto
    fica inerte, que é o comportamento histórico.
    """
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
    # UX-04: o lado LENTO do debounce assimétrico (ver DEFAULT_DEBOUNCE_SAIDA_SEC).
    # Só vale para SAIR de um perfil específico rumo a um catch-all; qualquer
    # outra transição usa `debounce_sec`.
    debounce_saida_sec: float = DEFAULT_DEBOUNCE_SAIDA_SEC
    # BUG-MOUSE-TRIGGERS-01: opcional para permitir testes legados que
    # instanciam AutoSwitcher sem store. Em produção, o Daemon injeta o
    # store compartilhado para respeitar override de trigger manual.
    store: StateStore | None = None
    # MODO-01/B3: par de callables do daemon para o MODO JOGO PADRÃO — o modo
    # que liga quando é um jogo e NENHUM perfil específico opina sobre ele. Os
    # callsites injetam `daemon.aplicar_modo_jogo_padrao` /
    # `daemon.reverter_modo_jogo_padrao` (assinatura `(*, wm_class: str)`).
    # None = sem daemon (CLI/testes legados): o autoswitch segue byte-idêntico
    # ao comportamento anterior. O autoswitch só reporta o FATO ("é jogo e
    # ninguém opina" / "não é mais isso"); toda a política — autoridade de
    # exibição, lock de gesto manual de 30 s, idempotência — mora no daemon.
    modo_jogo_padrao_applier: Callable[..., object] | None = None
    modo_jogo_padrao_reverter: Callable[..., object] | None = None
    # FOCO-ERRANTE-01: quem responde "que jogo do wrapper está VIVO agora?".
    # None = `jogo_do_wrapper_vivo()` com os diretórios reais, que é o que o
    # daemon usa (nenhuma rota de subida precisa ligar fio nenhum). O campo
    # existe para o teste apontar a leitura para um `tmp_path` — o mesmo motivo
    # do `base_dir` das funções de marker do `launch_env`.
    jogo_vivo_reader: Callable[[], int | None] | None = None

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
    # curso (inclui foco na própria GUI/applet — MISC-08 item 2). Serve para
    # (a) logar `autoswitch_window_info_unavailable` (ou
    # `autoswitch_janela_propria_ignorada`) 1x por episódio (padrão do
    # `_log_suppressed_once` — sem flood a 2 Hz) e (b)
    # resetar o relógio do debounce na PRIMEIRA leitura útil após o gap (o
    # debounce é wall-time: sem o reset, o tempo pulado contaria como
    # estabilidade e um glitch idêntico ao de antes do gap ativaria na hora).
    _info_gap_active: bool = False
    # UX-04: o perfil CORRENTE é uma regra específica (não catch-all)? É o que
    # arma o lado lento do debounce assimétrico. Guardado no commit da ativação
    # porque `_current_profile` é só o NOME — reconsultar o disco a cada tick
    # para descobrir a especificidade do que já está ativo seria I/O a 2 Hz.
    _current_especifico: bool = False
    # FEAT-AUTOSWITCH-LOCK-01: chave (evento, candidato) do último log do
    # cadeado. Mesmo motivo do `_suppress_log_key` — o cadeado é avaliado a
    # 2 Hz e ficou LIGADO por 90 min na máquina dela.
    _cadeado_log_key: tuple[str, str] | None = None
    # PERFIL-REESCRITO-NA-PARTIDA-01 (leva de 05/08), item 4: último estado
    # devolvido pelo par do MODO JOGO PADRÃO (`aplicar_modo_jogo_padrao` /
    # `reverter_modo_jogo_padrao`), no vocabulário `aplicado`/`adiado_*`/
    # `ignorado_*` dos outros appliers. O retorno era DESCARTADO: o eixo mexia
    # (ou recusava mexer) no gamepad da usuária a cada tique e nada disso
    # entrava no relatório da ativação — a janela não tinha como lhe dizer o que
    # não entrou. Vazio = o par não foi chamado nesta instância.
    _estado_modo_jogo_padrao: str = ""
    # FOCO-ERRANTE-01: chave (candidato, perfil corrente) da última recusa
    # logada. Mesma razão — e o mesmo padrão — do `_cadeado_log_key`: a recusa
    # é avaliada a 2 Hz e o episódio medido no journal dela durou minutos; sem
    # dedup seriam 7 200 linhas por hora.
    _recusa_log_key: tuple[str, str] | None = None
    # FOCO-ERRANTE-01: cache de `_appids_de_jogo_do_perfil` para o perfil
    # CORRENTE, chaveado pelo nome. `ProfileManager.get` lê o JSON do disco (e
    # varre o diretório quando o arquivo não bate com o slug); a guarda roda a
    # 2 Hz enquanto a janela da Steam está na frente. A chave é o NOME, então o
    # cache se invalida sozinho em toda troca de perfil — inclusive na
    # sincronização de crença. Custo declarado: editar o `match` do perfil ATIVO
    # em disco só é visto na próxima troca, e o efeito se limita à guarda.
    _appids_do_perfil_nome: str | None = None
    _appids_do_perfil_valor: frozenset[int] = frozenset()

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

    def travado(self) -> bool:
        """True quando a troca automática de perfil está CONGELADA pela usuária.

        FEAT-AUTOSWITCH-LOCK-01 (pedido da mantenedora, 23/07: "no sackboy a
        ideia era ficar a seleção que eu marquei na interface... deixar na
        interface a opção de escolha", e o mesmo para o Mullet Mad Jack).

        É diferente de tudo que já existia:
        - do PAUSE do daemon (`_paused`): aquele para TODA a emulação; este só
          congela a DECISÃO de perfil — gamepad, co-op, rumble seguem vivos;
        - da trava manual por categoria (`manual_override_categories`): aquela é
          por-seção e some quando ela troca de perfil; esta é a escolha
          explícita de "não troca de perfil sozinho, ponto".

        Estado no StateStore (persistido pelo handler IPC), lido a cada tick —
        ligar/desligar vale na hora. Sem store (testes legados) = nunca travado,
        o comportamento histórico.

        LOCK-CEDE-01 (decisão da mantenedora, 24/07): travado NÃO é mais "não
        acontece nada". Ver o gate em `_tick` — o cadeado cede para a regra
        PRÓPRIA do jogo. Este predicado segue respondendo só "o cadeado está
        ligado?"; a política de quem fura mora no chamador.
        """
        store = self.store
        return store is not None and bool(getattr(store, "autoswitch_locked", False))

    def _store_de_estado(self) -> Any | None:
        """O store onde mora o perfil REALMENTE ativo (nunca `None` em produção).

        PERFIL-REESCRITO-NA-PARTIDA-01, item 1. Prefere o store injetado pelo
        daemon; cai no store do próprio `ProfileManager` (que é o MESMO objeto
        em produção — as duas rotas de subida do autoswitch injetam `ctx.store`
        nos dois) para que a sincronização também valha nas construções legadas
        `AutoSwitcher(manager=..., window_reader=...)` sem `store`, usadas por
        boa parte da suíte. Sem esse fallback a cura ficaria sem cobertura
        justamente onde ela é mais fácil de testar.
        """
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
            self._current_profile = ativo
            self._current_especifico = True
            logger.info(
                "autoswitch_crenca_sincronizada",
                de=anterior or "",
                para=ativo,
            )
        return self._current_profile

    def _tick(self, info: dict[str, Any], now: float) -> None:
        """Um ciclo de decisão do autoswitch (leitura já feita pelo caller).

        Separado do run-loop para os testes dirigirem o relógio: o debounce é
        wall-time e o buraco-do-debounce da UX-01 só é testável com `now`
        controlado.
        """
        # PERFIL-REESCRITO-NA-PARTIDA-01, item 1: a PRIMEIRA coisa do tique é
        # adotar o perfil realmente ativo. Tem de vir antes de tudo — antes da
        # histerese (que loga `current=`), antes do select, antes do debounce —
        # senão o resto do tique decide contra uma crença que pode estar horas
        # atrasada em relação ao que ela escolheu na mão.
        self._perfil_corrente()
        # UX-01 (SPRINT-UX-AUTOSWITCH-01): histerese. Leitura sem informação
        # (backend cego: janela X morta, foco em janela Wayland nativa) NÃO
        # significa "é o desktop" — pula o tick INTEIRO: não mexe no candidato,
        # não reinicia o debounce, não ativa nada. O perfil corrente fica
        # retido até evidência POSITIVA de outra janela. Sem TTL de propósito:
        # o EIO de BT já mediu 5,1 s e loading screens duram minutos — TTL
        # re-introduziria o drop no meio do jogo.
        # MISC-08 item 2 (2026-07-18): a PRÓPRIA GUI/applet em foco entra no
        # MESMO caminho — olhar o hefesto não é sair do jogo; tratar como
        # janela comum fazia o fallback MatchAny flipar o perfil a cada
        # alt-tab jogoGUI (journal 20:15:40-51).
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
            # BUG-AUTOSWITCH-LOG-KEY-STUCK-01: o reset da chave de supressão
            # NÃO pode ser pulado junto com o tick — um episódio de supressão
            # que termina durante o gap deduplicaria o seguinte em silêncio.
            if not self._suppression_active():
                self._suppress_log_key = None
            return

        resumed = self._info_gap_active
        self._info_gap_active = False

        profile, motivo = self._selecionar_com_motivo(info)
        candidate = profile.name if profile else None

        # PERFIL-REESCRITO-NA-PARTIDA-01, item 1: quando o candidato É o perfil
        # corrente, a especificidade sai de GRAÇA do objeto recém-selecionado —
        # sem disco e sem custo a 2 Hz. É o que corrige o palpite conservador
        # que a sincronização acima deixa após uma troca manual dela.
        if candidate is not None and candidate == self._current_profile:
            self._current_especifico = not bool(getattr(profile, "e_catch_all", True))

        # MODO-01/B3: ANTES do cadeado, de propósito — o cadeado congela a
        # decisão de PERFIL, não a de MODO. Ela deixou `autoswitch_locked.flag`
        # ligado desde 24/07 e AINDA ASSIM quer que o modo jogo ligue sozinho;
        # eram duas perguntas diferentes respondidas pelo mesmo `return`.
        self._sincronizar_modo_jogo_padrao(motivo, info)

        # FEAT-AUTOSWITCH-LOCK-01 + LOCK-CEDE-01 (decisão da mantenedora,
        # 24/07): o cadeado saiu da PRIMEIRA linha do tick para cá, DEPOIS do
        # select. O motivo é medido: com a flag ligada (mtime 24/07 20:42) o
        # `return` na entrada matava tudo — inclusive a regra própria do jogo —
        # e o modo jogo nunca ligava (zero `profile_autoswitch` em 90 min).
        #
        # A política nova é a que ela pediu, sem perder o que ela pediu antes:
        # continua NÃO trocando de perfil por janela comum de desktop (é o
        # "não troca sozinho"), mas CEDE quando o perfil casado é a regra
        # ESPECÍFICA do jogo em foco. É a mesma exceção, pelo mesmo predicado
        # (`perfil_e_regra_de_jogo`), que o override manual já tinha em
        # `_activate` (F2/R-01): um genérico de desktop nunca fura, a regra do
        # jogo sempre fura.
        if self.travado():
            # MODO-01/B2: o cadeado cede à regra própria do jogo (LOCK-CEDE-01,
            # inalterado) E também ao perfil que DECLARA ser de jogo — não
            # catch-all, com `mode.kind` em {gamepad, native}. Sem a segunda
            # metade, o preset `coop_local` (que tem `mode: gamepad` e casa por
            # TÍTULO de janela) e todo jogo fora da Steam ficavam congelados por
            # um cadeado que só prometia não trocar de perfil "ao abrir um jogo".
            if not (
                perfil_e_regra_de_jogo(profile, info)
                or perfil_declara_modo_de_jogo(profile)
            ):
                self._log_cadeado_uma_vez(
                    "autoswitch_congelado_pelo_cadeado", candidate, info
                )
                # Zera o candidato: enquanto o cadeado segura, o relógio do
                # debounce não pode acumular "estabilidade". Sem isto, destravar
                # depois de horas na mesma janela ativaria o perfil no MESMO
                # tick — a mesma armadilha do buraco-do-debounce da UX-01.
                self._last_candidate = None
                # Idem BUG-AUTOSWITCH-LOG-KEY-STUCK-01: o retorno antecipado não
                # pode deixar a chave de supressão presa.
                if not self._suppression_active():
                    self._suppress_log_key = None
                return
            self._log_cadeado_uma_vez(
                "autoswitch_cadeado_cedeu_a_regra_de_jogo", candidate, info
            )
        else:
            self._cadeado_log_key = None

        # FOCO-ERRANTE-01 (18/08/2026): a janela do CLIENTE Steam não tira o
        # perfil de um jogo que ainda está VIVO. Medido no journal dela: treze
        # trocas entre 00:15 e 01:09, todas com `wm_class=steam`, uma delas
        # cinco segundos depois da anterior — gatilhos e lightbar do jogo
        # reescritos pelos do desktop no meio da partida, porque uma janela
        # INVISÍVEL do `steamwebhelper` (instância `steamwebhelper`, classe
        # `steam`, `WM_NAME` vazio) rouba o foco do X sob XWayland.
        #
        # A ironia que originou esta guarda: `lifecycle._janela_de_jogo_em_foco`
        # (VPAD-NA-JANELA-DA-STEAM-01, 17/08) já sabia que "a janela da Steam
        # durante a partida não autoriza voltar ao desktop" — e era consultada
        # DEPOIS da troca, para salvar o modo e a política de rumble. Ninguém a
        # consultava ANTES, para não trocar.
        #
        # A guarda vem aqui, ANTES do bloco de estabilidade, pelo mesmo motivo
        # do cadeado: zerando o candidato, a espera não acumula. Quando o jogo
        # morre, o candidato renasce e a troca sai no debounce normal (~1 s) —
        # é o ensaio E-4 da sprint, e é o que separa esta cura de um cadeado.
        if self._recusa_a_janela_do_cliente_steam(candidate, info):
            self._last_candidate = None
            if not self._suppression_active():
                self._suppress_log_key = None
            return
        self._recusa_log_key = None

        if candidate != self._last_candidate or resumed:
            # `resumed`: primeira leitura útil após um gap reinicia o relógio
            # do debounce — o tempo pulado não conta como estabilidade
            # (armadilha 1 da UX-01: sem isso, duas leituras-glitch idênticas
            # separadas por minutos ativariam instantaneamente).
            self._last_candidate = candidate
            self._candidate_since = now

        # UX-04: debounce assimétrico — barato para ENTRAR, caro para SAIR
        # rumo a um genérico (ver DEFAULT_DEBOUNCE_SAIDA_SEC).
        limite = self.debounce_sec
        if self._saida_para_catch_all(profile):
            limite = max(self.debounce_sec, self.debounce_saida_sec)
        stable = now - self._candidate_since >= limite
        # BUG-AUTOSWITCH-LOG-KEY-STUCK-01: reabre o log de supressão assim que
        # a supressão CESSA, independente de haver ativação. Antes a chave só
        # zerava dentro de `_activate` (que só roda com candidate != current),
        # então um episódio que terminava com o candidato estável == perfil
        # corrente (ex.: trigger.reset com a janela do jogo em foco) deixava a
        # chave presa e deduplicava em silêncio o episódio seguinte.
        if not self._suppression_active():
            self._suppress_log_key = None
        if stable and candidate and candidate != self._current_profile:
            # R-01: o objeto Profile já está aqui — propagá-lo evita que o
            # `_activate` tenha de adivinhar POR QUE o candidato casou.
            self._activate(candidate, info, profile)

    def _selecionar_com_motivo(
        self, info: dict[str, Any]
    ) -> tuple[Profile | None, str]:
        """Seleciona o perfil da janela e traz junto o MOTIVO (MODO-01/B3).

        Prefere `ProfileManager.select_for_window_ex`, que responde o par
        `(perfil, motivo)`. A leitura do motivo é OPCIONAL por construção: um
        `manager` que não tenha o método novo — ou que devolva outra coisa
        (dublê de teste, `MagicMock`, integração de terceiros) — cai no
        `select_for_window` histórico e o motivo vira `MOTIVO_SEM_CANDIDATO`,
        que não dispara nada. Nunca vale derrubar o tick por causa do motivo:
        ele é informação EXTRA, e sem ele o autoswitch precisa seguir exatamente
        como seguia antes desta sprint.
        """
        seletor = getattr(self.manager, "select_for_window_ex", None)
        if callable(seletor):
            resultado = seletor(info)
            if isinstance(resultado, tuple) and len(resultado) == 2:
                perfil, motivo = resultado
                return perfil, str(motivo)
        perfil_legado = self.manager.select_for_window(info)
        return perfil_legado, MOTIVO_SEM_CANDIDATO

    def _sincronizar_modo_jogo_padrao(
        self, motivo: str, info: dict[str, Any]
    ) -> None:
        """Liga/solta o MODO JOGO PADRÃO conforme o motivo da seleção (B3).

        MODO-01. O daemon já SABIA que havia um jogo (registrou
        `game_signal_transition de=daemon para=game` com o Mullet Mad Jack
        aberto) e não fazia nada com isso em termos de modo: todo o automatismo
        dependia de ela ter criado, à mão, um perfil com seção `mode` para
        AQUELE jogo. Aqui o fato vira ação.

        Só o FATO mora neste método, e ele é lido do motivo da seleção:

        - `MOTIVO_JOGO_SEM_PERFIL_PROPRIO` → "é um jogo e ninguém opina": pede o
          modo jogo padrão. Chamado a cada tique de propósito — o applier do
          daemon é idempotente e barato (checa autoridade de exibição, lock de
          gesto manual e se já aplicou), e é ele que sabe quando o pedido pode
          finalmente ser honrado (a autoridade demora até ~2 s para virar
          `game`, e um gesto manual dela adia por 30 s);
        - qualquer outro motivo → há EVIDÊNCIA POSITIVA de outra janela (o tick
          sem informação já saiu lá em cima, pela histerese UX-01): solta o
          modo jogo padrão. O gatilho é a janela lida, não a queda do sinal
          sticky — o sinal cai sozinho 30 s depois com o jogo ainda aberto
          (defeito B4, registrado e NÃO corrigido nesta sprint), e desligar o
          vpad no meio da partida por causa disso seria o pior desfecho
          possível.

        Best-effort dos dois lados: falha do daemon vira log e o tick segue.

        PERFIL-REESCRITO-NA-PARTIDA-01, item 4: o estado devolvido pelo par
        deixa de ser descartado — fica em `_estado_modo_jogo_padrao` e entra no
        relatório da ativação seguinte. O daemon já respondia no vocabulário dos
        outros appliers (`aplicado`, `adiado_lock_manual`, `ignorado_sem_jogo`,
        `ignorado_gesto_dela`); era o autoswitch que jogava a resposta fora.
        """
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

    def _saida_para_catch_all(self, profile: Profile | None) -> bool:
        """True quando a troca é SAÍDA de um perfil específico rumo a um genérico.

        UX-04: é o único caso que paga o debounce lento. Exige as três coisas —
        há perfil corrente, ele é ESPECÍFICO (casou por regra de verdade) e o
        candidato é OUTRO perfil, catch-all. Entrar num específico, trocar entre
        específicos e reentrar no mesmo perfil seguem no debounce curto: só a
        volta ao genérico é a decisão cara de desfazer no meio da partida.

        `getattr` com default True (= "trate como catch-all") mantém o predicado
        tolerante a dublês de teste sem inventar atrito: na dúvida, o debounce
        que vale é o curto de sempre — dúvida não pode virar regressão de UX.
        """
        if profile is None or not self._current_especifico:
            return False
        if self._current_profile is None or profile.name == self._current_profile:
            return False
        return bool(getattr(profile, "e_catch_all", True))

    def _recusa_a_janela_do_cliente_steam(
        self, candidate: str | None, info: dict[str, Any]
    ) -> bool:
        """A troca de perfil tem de ser RECUSADA neste tique? (FOCO-ERRANTE-01)

        Três termos, e os três são obrigatórios — tirar qualquer um deles é o
        que transforma a cura em defeito:

        1. **a janela em foco é o CLIENTE Steam** (loja, biblioteca, Big
           Picture, `steamwebhelper`), pelo predicado ÚNICO da casa
           (`steam_app.e_janela_do_cliente_steam`). Sem este termo, a guarda
           valeria para o Firefox e mataria a política de 23/07;
        2. **o perfil CORRENTE é a regra própria de um jogo da Steam** — é o
           que impede o marker do jogo A de segurar o perfil do jogo B;
        3. **esse jogo está VIVO agora** (`jogo_do_wrapper_vivo`). Sem o termo
           de vitalidade, ela fecharia o jogo, ficaria na biblioteca da Steam e
           o perfil do jogo ficaria PRESO PARA SEMPRE — um cadeado permanente é
           pior que o defeito que ele cura.

        Só recusa uma troca que ia acontecer: candidato ausente, ou candidato
        que já É o perfil corrente, seguem pelo caminho de sempre.
        """
        corrente = self._current_profile
        if candidate is None or corrente is None or candidate == corrente:
            return False
        if not e_janela_do_cliente_steam(info.get("wm_class")):
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
        """Appid do jogo do wrapper vivo agora, pelo leitor injetado ou o real.

        FOCO-ERRANTE-01. Best-effort declarado: leitor que levanta vira "não
        sei", e "não sei" NÃO recusa a troca — a guarda é a exceção, e uma
        exceção que falha tem de devolver o comportamento histórico.
        """
        leitor = self.jogo_vivo_reader
        try:
            return jogo_do_wrapper_vivo() if leitor is None else leitor()
        except Exception as exc:
            logger.debug("jogo_vivo_indisponivel", err=str(exc))
            return None

    def _appids_do_perfil_corrente(self, nome: str) -> frozenset[int]:
        """Appids de que o perfil CORRENTE é a regra própria, com cache por nome.

        FOCO-ERRANTE-01 — ver `_appids_do_perfil_nome` para o porquê do cache.
        Manager sem `get` (dublê de teste) ou perfil que não abre devolvem o
        conjunto vazio, e conjunto vazio desliga a guarda.
        """
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
        """Loga a recusa 1x por episódio (candidato, perfil corrente).

        FOCO-ERRANTE-01, passo 5 da sprint. O poll é 2 Hz e o episódio medido
        durou minutos: sem a chave seriam ~7 200 linhas por hora. Mesmo padrão
        (e mesma razão) do `_log_cadeado_uma_vez` e do `_log_suppressed_once`.
        A chave é zerada no `_tick` assim que a recusa deixa de valer, para o
        episódio SEGUINTE voltar a aparecer no journal.
        """
        key = (candidate, corrente)
        if self._recusa_log_key == key:
            return
        self._recusa_log_key = key
        logger.info(
            "autoswitch_recusou_a_janela_da_steam",
            candidato=candidate,
            perfil_corrente=corrente,
            appid=appid,
            wm_class=str(info.get("wm_class") or ""),
        )

    def _log_cadeado_uma_vez(
        self, evento: str, candidate: str | None, info: dict[str, Any]
    ) -> None:
        """Loga o estado do cadeado 1x por (motivo, candidato).

        FEAT-AUTOSWITCH-LOCK-01: o cadeado é avaliado a 2 Hz e na máquina dela
        ficou ligado por 90 min — sem dedup seriam ~650 mil linhas. Mesmo padrão
        (e mesma razão) do `_log_suppressed_once`.
        """
        key = (evento, candidate or "")
        if self._cadeado_log_key == key:
            return
        self._cadeado_log_key = key
        logger.info(
            evento,
            candidate=candidate or "",
            wm_class=info.get("wm_class", ""),
            current=self._current_profile or "",
        )

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

    @staticmethod
    def _janela_propria(info: dict[str, Any]) -> bool:
        """True quando a janela em foco é a própria GUI/applet do hefesto.

        MISC-08 item 2: match por `wm_class` normalizado (case-insensitive)
        contra `OWN_GUI_WM_CLASSES`. Só o wm_class decide — título/processo
        não entram: a GUI reporta wm_class estável ("Main.py" ou
        "Hefesto-Dualsense4Unix" conforme o momento do set_wmclass sob
        XWayland) e é isso que o journal provou.
        """
        wm_class = str(info.get("wm_class") or "").strip().casefold()
        return wm_class in OWN_GUI_WM_CLASSES

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

    def _activate(
        self, name: str, info: dict[str, Any], profile: Profile | None = None
    ) -> None:
        # PERFIL-REESCRITO-NA-PARTIDA-01, item 1: sincroniza a crença também
        # aqui — `_tick` já o faz, mas `_activate` é chamado direto por outros
        # caminhos (e pela suíte), e `from_=` no journal mentia exatamente
        # quando mais importava: `from_=None to=sackboy_nativo` com outro perfil
        # ativo havia horas. Custa um `getattr` quando não há divergência.
        self._perfil_corrente()
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
        # BUG-MOUSE-TRIGGERS-01: se o usuário tem um override manual aplicado
        # (gatilho/LED/rumble), autoswitch suspende até o override ser limpo
        # por trigger.reset ou profile.switch explícito. Sem isso, ao ligar a
        # aba Mouse (que move o cursor e muda o foco de janela), o autoswitch
        # reaplicaria o fallback e zeraria o trigger recém-aplicado.
        # F2 (auditoria 21/07): EXCEÇÃO única — perfil de JOGO. A janela em
        # foco casando `steam_app_*` com perfil PRÓPRIO (candidato diferente
        # do perfil ativo) vence o override: a trava não pode silenciar a
        # troca de perfil por jogo para sempre (um `led.set` de manhã
        # bloqueava o perfil do jogo à noite, sem indicador). Ao ceder, as
        # categorias são limpas — o perfil do jogo reescreve tudo mesmo.
        # Reaplicação do perfil ATIVO (o "perfil eterno" da Causa A) e
        # regras de janela comuns seguem suprimidas como sempre.
        # R-01 (auditoria 23/07): a exceção só vale para a regra PRÓPRIA do
        # jogo. Antes bastava "a janela em foco é steam_app_*", sem checar se o
        # perfil candidato casou POR CAUSA dela — e com três catch-all no disco
        # e nenhum perfil para o Mullet Mad Jack, quem entrava era o `vitoria`
        # (genérico de desktop). A trava manual era apagada e o genérico pisava
        # na configuração recém-feita: exatamente o "nunca é respeitado".
        if self.store is not None and self.store.manual_trigger_active:
            candidato_de_jogo = perfil_e_regra_de_jogo(profile, info)
            if candidato_de_jogo and name != self.store.active_profile:
                self.store.clear_manual_trigger_active()
                logger.info(
                    "autoswitch_manual_override_cedeu_ao_jogo",
                    candidate=name,
                    wm_class=info.get("wm_class", ""),
                )
            else:
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
        # R-03 (auditoria 23/07): o relatório da ativação diz QUAIS seções o lock
        # de gesto manual adiou. O perfil segue COMMITADO (`_current_profile`
        # abaixo) mesmo assim — a variante "não commitar para tentar de novo no
        # próximo tick" foi rejeitada: com o poll de 2 Hz ela reescreveria
        # gatilhos/LEDs ~60x em 30 s. O retry mora na pendência de `mode` do
        # daemon, drenada UMA vez pelo poll loop.
        relatorio: dict[str, str] = {}
        try:
            # PERFIL-03: troca AUTOMÁTICA por janela — origin="autoswitch" NÃO
            # grava session.json. Era o bug provado do autoload: o autoswitch
            # reescrevia a intenção manual da usuária a cada troca de janela e
            # o boot restaurava "Navegação" em vez do perfil que ela escolheu.
            self.manager.activate(name, origin="autoswitch", relatorio=relatorio)
        except Exception as exc:
            logger.warning("autoswitch_activate_failed", name=name, err=str(exc))
            return
        self._current_profile = name
        # FOCO-ERRANTE-01: o objeto do perfil que ACABOU de entrar já está aqui
        # — carimbar os appids dele agora é de graça e poupa a guarda de reler
        # o disco a 2 Hz enquanto a janela da Steam segura o foco. Sem o objeto
        # (chamada direta com só o nome), o cache é INVALIDADO em vez de
        # carimbado com vazio: vazio desliga a guarda, e desligar a guarda por
        # falta de dado seria o defeito de volta.
        if profile is not None:
            self._appids_do_perfil_nome = name
            self._appids_do_perfil_valor = _appids_de_jogo_do_perfil(profile)
        else:
            self._appids_do_perfil_nome = None
        # UX-04: carimba a especificidade do que ACABOU de entrar — é o que
        # decide, na próxima troca, se o debounce de saída se aplica.
        self._current_especifico = profile is not None and not bool(
            getattr(profile, "e_catch_all", True)
        )
        # PERFIL-REESCRITO-NA-PARTIDA-01, item 4: o MODO JOGO PADRÃO é o único
        # eixo que o tique mexe FORA do `ProfileManager` (o daemon liga o vpad
        # quando é jogo e ninguém opina). Entra no relatório como seção própria,
        # com o mesmo vocabulário, para a janela poder contar essa metade também.
        if self._estado_modo_jogo_padrao:
            relatorio["modo_jogo_padrao"] = self._estado_modo_jogo_padrao
        logger.info(
            "profile_autoswitch",
            from_=from_profile,
            to=name,
            wm_class=info.get("wm_class", ""),
            wm_name=info.get("wm_name", ""),
            # Sem isto, "perfil trocou mas a máscara não" não tinha rastro
            # nenhum no journal — era preciso adivinhar.
            adiado=sorted(
                secao
                for secao, estado in relatorio.items()
                if estado.startswith("adiado")
            ),
            # PERFIL-REESCRITO-NA-PARTIDA-01, item 5: o filtro acima escondia
            # METADE do relatório. `ignorado_catch_all`, `ignorado_janela_de_jogo`,
            # `ignorado_trava_manual` e `falhou` NUNCA apareciam no journal — e
            # são justamente os estados em que a ativação "deu certo" sem aplicar
            # a seção. `adiado=` fica onde estava (é o campo que a leitura do
            # journal já procura); `secoes=` diz a verdade INTEIRA, uma entrada
            # por seção, ordenada para o diff entre dois tiques ser legível.
            secoes=sorted(
                f"{secao}={estado}" for secao, estado in relatorio.items()
            ),
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
    "DEFAULT_DEBOUNCE_SAIDA_SEC",
    "DEFAULT_DEBOUNCE_SEC",
    "DEFAULT_POLL_INTERVAL_SEC",
    "OWN_GUI_WM_CLASSES",
    "AutoSwitcher",
    "WindowReader",
    "jogo_do_wrapper_vivo",
]
