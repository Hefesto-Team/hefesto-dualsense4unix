"""Subsystem Gamepad — gamepad virtual (DualSense/Xbox).

FEAT-DSX-GAMEPAD-FLAVOR-01. Integra o bridge — antes um processo CLI avulso
(`emulate xbox360`) que abria um SEGUNDO leitor do mesmo controle e causava
input duplicado/perdido — ao daemon como subsystem. Agora há UM leitor evdev
(o do daemon) que faz fan-out para mouse/teclado/gamepad.

Política:
  - **Mutuamente exclusivo com a emulação de mouse**: ligar o gamepad desliga o
    mouse (jogar = o controle vai pro jogo, não pro cursor do desktop). O poll
    loop, quando o gamepad está ativo, NÃO despacha mouse/teclado.
  - **Máscara (flavor)**: `dualsense` (prompts PlayStation) ou `xbox` (fallback
    p/ jogos XInput-only). Quem escolhe o BACKEND por trás da máscara (uhid ou
    uinput) é `integrations/virtual_pad.make_virtual_pad`, com o fallback e o
    motivo logado num lugar só — este subsystem não sabe em qual está.
  - **Grab do controle físico** (best-effort): enquanto o gamepad virtual está
    ativo, o daemon faz EVIOCGRAB no evdev do controle real para o jogo enxergar
    SÓ o device virtual (senão veria o controle cru + o virtual = input dobrado,
    BUG-DSX-GAMEPAD-DOUBLE-INPUT-01). Liberado ao desligar.
  - **Persistência**: liga/desliga + flavor sobrevivem a restart/reboot via
    `utils.session` (igual ao mouse).
  - **Force-feedback do jogo** (FEAT-VPAD-FF-PASSTHROUGH-01): o vpad do P1
    nasce com um `rumble_sink` que devolve o rumble pedido pelo JOGO ao
    controle físico PRIMÁRIO, passando pela mesma política global de
    intensidade do reassert. `dispatch_gamepad` bombeia o FF a cada tick.
  - **Um controle físico = UM dispositivo de jogo** (JOGO-01): a allowlist do
    Steam Input escolhe QUAL dispositivo o jogo enxerga (nela, o físico), nunca
    QUANTOS. Enquanto um appid da allowlist está em sessão, o vpad é retirado
    de cena (`suspend_vpads_for_steam_input`) e devolvido na saída — sem isso,
    "o Hefesto sai da frente" significava o jogo enumerar o físico E o virtual
    e reparti-los entre dois jogadores.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.virtual_pad import VirtualPad

logger = get_logger(__name__)

#: VPAD-01/VPAD-02: cooldown (s) COMPARTILHADO entre as duas bordas de rebackend
#: do vpad do P1 (uinput→uhid): a promoção do hotplug (`reconnect_loop`) e o
#: "botão de força" da GUI (re-selecionar DualSense). O precheck
#: `uhid_available()` pega o uhid quebrado ANTES do device existir (nó ausente,
#: sem ACL); não pega o que aceita o CREATE2 e nunca faz bind (kernel sem
#: `hid_playstation`, MAC duplicado). Sem a trava, cada reconexão BT (frequente
#: nesta máquina) ou clique repetido na GUI derrubaria e recriaria o vpad
#: uinput que FUNCIONA — input drop em loop no meio do jogo. O apply de
#: perfil/autoswitch nem chega ao cooldown: o latch do BT-04(b) veta a promoção
#: por origem automática em `_deve_promover_backend`.
REBACKEND_COOLDOWN_SEC = 30.0

#: R-04/R-06 (auditoria 23/07): período (s) da reconciliação de LAUNCH que o
#: `dispatch_gamepad` dispara — arming do modo do perfil pelo marker do wrapper
#: e liga/desliga da exceção de Steam Input. Custo por tick sem vencimento: uma
#: comparação de float (o mesmo padrão dos throttles do `_poll_loop`). 1 Hz é a
#: cadência do dreno de pendência do R-03 e é folgada para o que se mede aqui:
#: o wrapper grava o marker segundos antes de o jogo enumerar controles.
LAUNCH_RECONCILE_INTERVAL_SEC = 1.0

#: JOGO-01: período (s) do VIGIA da exceção de Steam Input — a task que assume a
#: reconciliação de launch enquanto o vpad está suspenso. Ela existe porque o
#: tick canônico (`dispatch_gamepad`) é chamado pelo poll loop SÓ quando
#: `daemon._gamepad_device is not None` (`lifecycle._poll_loop`): retirar o vpad
#: apagaria a própria reconciliação que teria de trazê-lo de volta, e a usuária
#: ficaria sem gamepad virtual até reiniciar o daemon. Mesma cadência do
#: `LAUNCH_RECONCILE_INTERVAL_SEC` de propósito — é o MESMO trabalho, só que por
#: outro carregador enquanto o vpad não existe.
STEAM_INPUT_VIGIA_INTERVAL_SEC = 1.0


class GamepadSubsystem:
    """Subsystem que gerencia o gamepad virtual. Espelha MouseSubsystem."""

    name = "gamepad"

    async def start(self, ctx: Any) -> None:
        """Cria o device virtual se gamepad_emulation_enabled=True.

        Idempotente: retorna sem erro se já existe. Lê o flavor da config.
        DEDUP-04: materializa o `launch_env/` também quando a emulação está
        DESLIGADA no boot — sem isso o wrapper leria um `default.env` rançoso
        da sessão anterior (ex.: com IGNORE de um vpad que não existe mais).
        O ramo LIGADO cobre os dois desfechos: sucesso e falha total do start
        regravam o arquivo dentro de `start_gamepad_emulation` — TODO boot
        reescreve o launch_env com o estado real.
        """
        cfg = ctx.config
        daemon = getattr(ctx, "daemon", ctx)
        if not getattr(cfg, "gamepad_emulation_enabled", False):
            _materialize_launch_env(daemon)
            return
        start_gamepad_emulation(daemon, flavor=getattr(cfg, "gamepad_flavor", None))

    async def stop(self) -> None:  # pragma: no cover - simetria de protocolo
        # O teardown real fica a cargo de stop_gamepad_emulation no shutdown do
        # daemon (que tem a referência ao device). Aqui é no-op seguro.
        return

    def is_enabled(self, config: DaemonConfig) -> bool:
        return bool(getattr(config, "gamepad_emulation_enabled", False))


def _materialize_launch_env(daemon: DaemonProtocol) -> None:
    """Regrava as envs de launch do wrapper (DEDUP-04) — sempre best-effort.

    Chamado nas bordas de transição do vpad (start/stop cobrem troca de
    máscara, promoção uhid<->uinput e liga/desliga por perfil). NUNCA pode
    derrubar a emulação: a falha vira log e o wrapper degrada sozinho.
    """
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

        materialize_launch_env(daemon)


def _set_evdev_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Só o EVIOCGRAB do evdev físico, com resultado OBSERVÁVEL.

    Extraído de `_set_controller_grab` (R-06): a exceção de Steam Input por
    appid precisa soltar/retomar o grab SEM passar pela composição
    grab+broker do caller (lá o `restore_all` do broker é chamado com
    `grab=False`, o que é o que queremos ao ENTRAR na exceção mas não ao SAIR
    dela). Nunca propaga exceção: em FAKE mode / sem device / sem suporte, o
    gamepad ainda funciona. Falha de EVIOCGRAB deixa de ser silenciosa
    (BUG-COOP-GRAB-SILENT-FAIL-01): loga warning e conta no store — a
    GUI/doctor podem apontar "input dobrado".
    """
    controller = getattr(daemon, "controller", None)
    evdev = getattr(controller, "_evdev", None)
    setter = getattr(evdev, "set_grab", None)
    if setter is None:
        return
    with contextlib.suppress(Exception):
        ok = setter(grab)
        state = getattr(evdev, "grab_state", None)
        logger.info("gamepad_controller_grab", grab=grab, ok=ok, state=state)
        if grab and ok is False:
            store = getattr(daemon, "store", None)
            if store is not None:
                with contextlib.suppress(Exception):
                    store.bump("gamepad.grab.failed")


def _set_controller_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Grab/ungrab do evdev do controle físico + hide/restore do hidraw.

    Sem isso, o jogo veria o controle cru (js0) + o virtual = input dobrado. O
    grab faz o daemon ser o leitor exclusivo do evdev real (ele já é o leitor),
    escondendo o controle cru dos clientes evdev (SDL2).

    R-06: com a exceção de Steam Input ATIVA (appid da allowlist rodando), o
    grab de entrada é PULADO — a exceção existe justamente para o jogo ver o
    controle físico. O ungrab nunca é pulado: expor nunca é errado (mesma
    assimetria já documentada no `_broker_sync_grab`).
    """
    if grab and steam_input_excecao_ativa(daemon):
        logger.info("gamepad_grab_pulado_steam_input", motivo="excecao_por_appid")
    else:
        _set_evdev_grab(daemon, grab)
    # BROKER-01: hide/restore do hidraw colado ao EVIOCGRAB — fora do
    # suppress acima (falha de grab não silencia o broker) e com o próprio
    # suppress lá dentro. A colocação aqui dá DE GRAÇA a regra da troca de
    # flavor: `release_grab=False` nem passa por esta função ⇒ o físico segue
    # escondido durante a recriação do vpad (sem janela para SDL/winebus).
    _broker_sync_grab(daemon, grab)


def _broker_sync_grab(daemon: DaemonProtocol, grab: bool) -> None:
    """Hide/restore do hidraw do físico colado ao EVIOCGRAB (BROKER-01).

    Best-effort SEMPRE: broker ausente/quebrado ⇒ log debug (no cliente) e a
    emulação segue — o invariante "duplicado > zero controles" proíbe que
    qualquer falha aqui derrube start/stop. Gates: backend com `hidraw_path`
    (só o pydualsense — FakeController do smoke fica fora) e, no hide, fora
    do Modo Nativo. O restore NÃO tem gate de modo: expor nunca é errado.

    Achados Onda S #6/#10: a operação do broker (I/O de socket, até ~4 s com
    broker lento) vai via `broker_call_nonblocking` — os setters de IPC
    (`gamepad.emulation.set`) chamam esta função NA thread do event loop e o
    hide/restore jamais pode congelar o daemon inteiro (§9 do desenho:
    "hide/restore best-effort jamais bloqueiam start/stop da emulação").
    Os gates (nativo, resolução do nó) seguem inline — são leituras baratas.
    """
    with contextlib.suppress(Exception):
        hidraw_fn = getattr(getattr(daemon, "controller", None), "hidraw_path", None)
        if not callable(hidraw_fn):
            return
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_call_nonblocking,
            broker_client_for,
        )

        client = broker_client_for(daemon)
        if grab:
            if daemon.is_native_mode():
                return
            if steam_input_excecao_ativa(daemon):
                # R-06: esconder o hidraw do físico é exatamente o que tornava
                # a allowlist inerte — a Steam precisa LER o hidraw para
                # entregar o DualSense pela API dela (SetDualSenseTriggerEffect).
                logger.info("broker_hide_pulado_steam_input", motivo="excecao_por_appid")
                return
            node = hidraw_fn()
            if isinstance(node, str) and node:
                broker_call_nonblocking(daemon, lambda: client.hide(node))
        else:
            broker_call_nonblocking(daemon, client.restore_all)


def steam_input_excecao_ativa(daemon: Any) -> bool:
    """True enquanto a exceção de Steam Input por appid estiver valendo (R-06).

    Leitura de um flag em memória (`_steam_input_excecao`), NUNCA de disco: esta
    função é gate de caminhos quentes (grab, hide, rehide) e não pode pagar I/O.
    Quem lê o marker/janela e move o flag é `sync_steam_input_exception`, na
    reconciliação throttada de 1 Hz.
    """
    return bool(getattr(daemon, "_steam_input_excecao", False))


def sync_steam_input_exception(
    daemon: DaemonProtocol, *, now: float | None = None
) -> bool:
    """Liga/desliga a exceção de Steam Input por appid. True = ativa (R-06).

    Achado: a allowlist (`steam_input_apps.txt`, com o 2111190 do Mullet Mad
    Jack) era INERTE — o guard de VDF a respeitava, mas o daemon continuava
    fazendo EVIOCGRAB no evdev e mandando o broker esconder o hidraw do
    controle físico. Resultado medido: o jogo cujo suporte a DualSense vem PELA
    Steam não achava controle nenhum da Sony, e a exceção que ela configurou
    não mudava nada.

    A cura é o "Modo Nativo por appid": enquanto um jogo da allowlist está em
    sessão, o físico volta a ficar visível (ungrab + restore do broker) e, ao
    sair, o estado canônico é retomado.

    JOGO-01 (25/07): o R-06 parou no meio do caminho e o preço que ele declarou
    aceitável ("o jogo passa a ver o físico E o vpad") era o defeito, não o
    preço. Com um DualSense no cabo o Mullet Mad Jack enumerava js0=vpad e
    js2=físico, dava jogador 1 a um e jogador 2 ao outro, escrevia a lightbar
    direto no aparelho e metade dos comandos dela ia para o controle que o jogo
    não estava lendo — "ele muda a cor, vai pro player 2 e não funciona". Opt-in
    NÃO significa "dois controles onde existe um": significa trocar QUAL
    dispositivo o jogo vê. Por isso a exceção agora também RETIRA o gamepad
    virtual de cena (`suspend_vpads_for_steam_input`) e o devolve na saída
    (`resume_vpads_after_steam_input`).

    Só age nas BORDAS (o flag em memória guarda o estado anterior): sem borda,
    a função é uma comparação e nada de I/O de grab/broker.
    """
    from hefesto_dualsense4unix.daemon.launch_env import steam_input_exception_appid

    appid = steam_input_exception_appid(daemon, now=now)
    ativa = appid is not None
    anterior = steam_input_excecao_ativa(daemon)
    if ativa == anterior:
        return ativa
    daemon._steam_input_excecao = ativa  # type: ignore[attr-defined]
    if ativa:
        logger.info("steam_input_excecao_ativada", appid=appid)
        _set_evdev_grab(daemon, False)
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                broker_call_nonblocking,
                broker_client_for,
            )

            client = broker_client_for(daemon)
            broker_call_nonblocking(daemon, client.restore_all)
        # JOGO-01: o flag JÁ está de pé quando o vpad cai — é ele que faz o
        # `start_gamepad_emulation` recusar o apply automático que o autoswitch
        # dispara segundos depois, quando a janela do jogo ganha foco.
        with contextlib.suppress(Exception):
            suspend_vpads_for_steam_input(daemon, appid=appid)
        return True
    logger.info("steam_input_excecao_encerrada")
    # JOGO-01: a devolução do vpad vem ANTES dos gates canônicos abaixo — com o
    # vpad suspenso, `gamepad_emulation_enabled` está False em memória (é o que
    # cala os revivedores automáticos durante o jogo) e os gates devolveriam
    # "nada a fazer" para sempre. O start já refaz grab + hide por dentro, então
    # retomar aqui encerra o trabalho desta borda.
    if resume_vpads_after_steam_input(daemon):
        return False
    # Saída da exceção: retoma o estado canônico SÓ se ele valeria agora — os
    # mesmos gates do rehide (emulação ligada, vpad VIVO, fora do Modo Nativo).
    # Sem isso, fechar o jogo da allowlist com a emulação desligada grabaria um
    # controle que ninguém pediu.
    if daemon.is_native_mode():
        return False
    if not getattr(daemon.config, "gamepad_emulation_enabled", False):
        return False
    if not _vpad_vivo(daemon):
        return False
    _set_evdev_grab(daemon, True)
    with contextlib.suppress(Exception):
        rehide_physical_hidraw(daemon)
    return False


def steam_input_vpad_suspenso(daemon: Any) -> bool:
    """True quando o vpad está fora de cena por causa da allowlist (JOGO-01).

    Leitura de flag em memória, como `steam_input_excecao_ativa` — e pelo mesmo
    motivo (é gate de caminho quente). É a resposta honesta para a pergunta que
    a aba Emulação precisa fazer ("por que a emulação aparece desligada com o
    jogo aberto?"): a emulação não foi desligada, ela SAIU DA FRENTE deste jogo.

    Superfície pendente (Entrega 2 da sprint JOGO-01, fora desta frente porque a
    GUI está com outro dono): quem for ligar a frase na aba Emulação lê ISTO
    junto de `steam_input_excecao_ativa` — o par ("exceção ativa", "vpad
    suspenso") distingue os dois estados possíveis do opt-in: o jogo da
    allowlist rodando com o Hefesto fora do caminho (os dois True) e o jogo da
    allowlist rodando com o vpad de pé porque a suspensão não pôde ser armada
    (primeiro True, segundo False — ver `suspend_vpads_for_steam_input`).
    """
    return bool(getattr(daemon, "_steam_input_vpad_suspenso", False))


def steam_input_coop_derrubados(daemon: Any) -> int:
    """Quantos jogadores de co-op a exceção de Steam Input derrubou (0 = nenhum).

    CONTAGEM-E-COOP-01 (29/07). Conta SECUNDÁRIOS (P2, P3, P4) — o P1 não é
    jogador do co-op, ele é o vpad primário, e a queda dele já tem observável
    próprio (`steam_input_vpad_suspenso`). Somar os dois num número só faria
    "co-op de três" virar "4" na tela.

    Leitura de um inteiro em memória, como as duas irmãs deste módulo, e pelo
    mesmo motivo (é consumida pelo `state_full`, que roda a 10 Hz). Vive
    exatamente enquanto a suspensão vive: `suspend_vpads_for_steam_input`
    escreve o valor medido e as DUAS saídas da suspensão (a borda de saída da
    exceção e o gesto manual de religar a emulação) zeram junto com o flag —
    um número pendurado depois de o co-op voltar mandaria a janela avisar de um
    estrago que já acabou.
    """
    valor = getattr(daemon, "_steam_input_coop_derrubados", 0)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else 0


async def _vigia_da_excecao_steam_input(daemon: DaemonProtocol) -> None:
    """Reconciliação de launch a 1 Hz enquanto o vpad está suspenso (JOGO-01).

    O tick canônico (`_reconciliar_launch`, chamado por `dispatch_gamepad`) só
    existe com vpad: `lifecycle._poll_loop` gateia o dispatch em
    `self._gamepad_device is not None`. Suspender o vpad sem esta task seria um
    beco sem saída — nada mais leria o marker do wrapper, a exceção nunca se
    encerraria e o gamepad virtual só voltaria com restart do daemon.

    Roda o MESMO `_reconciliar_launch` (throttle e arming inclusos), na thread
    do event loop, exatamente como o dispatch faria. Termina sozinha na primeira
    volta em que a exceção não estiver mais ativa (a própria reconciliação
    devolve o vpad) ou quando o daemon entra em shutdown; nunca propaga exceção.
    """
    try:
        while not _daemon_parando(daemon):
            await asyncio.sleep(STEAM_INPUT_VIGIA_INTERVAL_SEC)
            if not steam_input_excecao_ativa(daemon):
                return
            with contextlib.suppress(Exception):
                _reconciliar_launch(daemon)
            if not steam_input_excecao_ativa(daemon):
                return
    except asyncio.CancelledError:  # pragma: no cover - shutdown do daemon
        raise
    finally:
        daemon._steam_input_vigia = None  # type: ignore[attr-defined]


def _daemon_parando(daemon: Any) -> bool:
    """True quando o daemon já está em shutdown (tolerante a dublês)."""
    fn = getattr(daemon, "_is_stopping", None)
    if not callable(fn):
        return False
    try:
        return bool(fn())
    except Exception:
        return False


def _armar_vigia_da_excecao(daemon: DaemonProtocol) -> bool:
    """Cria a task-vigia da exceção. False = não há como trazer o vpad de volta.

    JOGO-01 — este é o gate de segurança da Entrega 1: a suspensão do vpad SÓ
    acontece quando existe quem a desfaça. Sem event loop rodando (daemon
    dublado em teste, uso do módulo fora do daemon) a task não nasce, a suspensão
    é abortada e a decisão fica no journal — degradar para o comportamento antigo
    (físico exposto COM o vpad de pé, ou seja, o duplicado) é ruim, mas deixar a
    usuária sem gamepad virtual até reiniciar o daemon é pior e não é reversível
    por ela.

    Idempotente: vigia viva devolve True sem criar outra. A task entra em
    `daemon._tasks` quando a lista existe (mesmo padrão do `start_mic_hotkey`),
    para o shutdown do daemon cancelá-la junto com o resto.
    """
    if getattr(daemon, "_steam_input_vigia", None) is not None:
        return True
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("steam_input_vigia_sem_event_loop")
        return False
    try:
        task = loop.create_task(
            _vigia_da_excecao_steam_input(daemon), name="steam_input_excecao"
        )
    except Exception as exc:  # pragma: no cover - loop fechando no meio
        logger.warning("steam_input_vigia_falhou", err=str(exc))
        return False
    daemon._steam_input_vigia = task  # type: ignore[attr-defined]
    tasks = getattr(daemon, "_tasks", None)
    if isinstance(tasks, list):
        tasks.append(task)
    return True


def suspend_vpads_for_steam_input(
    daemon: DaemonProtocol, *, appid: int | None = None
) -> bool:
    """Retira o gamepad virtual de cena pelo tempo do jogo da allowlist (JOGO-01).

    True = suspendeu de verdade. O princípio da sprint é "um controle físico
    produz exatamente UM dispositivo de jogo": nos appids da allowlist esse
    dispositivo é o FÍSICO (é ele que a Steam entrega ao jogo, com os gatilhos
    adaptativos da API Steamworks), então o vpad — que em qualquer outro jogo é
    o único — aqui é o duplicado que o jogo distribui entre dois jogadores.

    O que cai, e por quê:

    - **jogadores de co-op ANTES do P1**: cada secundário segura o EVIOCGRAB e o
      hide do hidraw do SEU controle, e `CoopManager.disable()` é quem devolve os
      dois. Derrubar o P1 primeiro faria o `should_be_active()` do co-op virar
      False no tick seguinte e o teardown aconteceria de qualquer forma — mas
      até lá o jogo já teria enumerado quatro vpads órfãos;
    - **vpad do P1** por `stop_gamepad_emulation(persist=False,
      release_grab=False)`: `persist=False` porque a PREFERÊNCIA dela não mudou
      (a mesma regra do R-07/HARM-06 — só gesto manual escreve em disco), e
      `release_grab=False` porque a borda de entrada da exceção já soltou o grab
      e restaurou o hidraw; repetir seria I/O de broker à toa.

    O `gamepad_emulation_enabled=False` que o stop deixa em memória não é efeito
    colateral: é ele que cala os revivedores automáticos (o ramo VPAD-09 de
    `upgrade_primary_vpad_to_uhid`) enquanto o jogo roda. O disco continua
    dizendo "ligada", então qualquer desfecho anormal (daemon morto sujo, reboot)
    devolve o vpad no boot seguinte.

    Nunca suspende sem vigia (ver `_armar_vigia_da_excecao`) e nunca suspende o
    que não existe: sem vpad de pé, não há duplicado a remover.

    O ciclo do vpad roda sob `_emu_lock` (RLock), como toda superfície que
    cria/derruba device: a promoção do hotplug (`connection.reconnect_loop`)
    entra pelo executor, numa THREAD diferente desta, e destruir o vpad no meio
    de um `wait_for_bind` alheio deixaria device órfão. `nullcontext` cobre o
    daemon dublado que não tem o lock.
    """
    if steam_input_vpad_suspenso(daemon):
        return False
    device = getattr(daemon, "_gamepad_device", None)
    coop = getattr(daemon, "_coop_manager", None)
    jogadores = getattr(coop, "_players", None) or {}
    if device is None and not jogadores:
        return False
    if not _armar_vigia_da_excecao(daemon):
        logger.warning(
            "steam_input_vpad_mantido_de_pe",
            appid=appid,
            motivo="sem_vigia_para_devolver_o_vpad",
        )
        return False
    flavor = getattr(device, "flavor", None) or getattr(
        daemon.config, "gamepad_flavor", None
    )
    # Contado ANTES do teardown: `CoopManager.disable()` esvazia o MESMO dict a
    # que `jogadores` aponta, e um log de "jogadores_coop=0" na linha que acabou
    # de derrubar quatro jogadores seria uma mentira difícil de perceber.
    n_jogadores = len(jogadores)
    daemon._steam_input_vpad_suspenso = True  # type: ignore[attr-defined]
    # Máscara a devolver — `None` quando não havia vpad do P1 para derrubar (só
    # jogadores de co-op órfãos, estado que o `should_be_active()` do co-op não
    # deveria permitir). A devolução NÃO inventa um vpad que não existia antes.
    daemon._steam_input_flavor_suspenso = (  # type: ignore[attr-defined]
        flavor if device is not None else None
    )
    with getattr(daemon, "_emu_lock", contextlib.nullcontext()):
        if coop is not None:
            with contextlib.suppress(Exception):
                coop.disable()
        if device is not None:
            stop_gamepad_emulation(daemon, persist=False, release_grab=False)
    # CONTAGEM-E-COOP-01 (29/07): o co-op caía EM SILÊNCIO. `coop.disable()`
    # desmonta os secundários três linhas acima e o único vestígio era o campo
    # `jogadores_coop` de um log cujo NOME fala de vpad — entrar na exceção de
    # Steam Input de um jogo desligava dois ou três jogadores e nada, em lugar
    # nenhum, dizia isso a ela. Agora o fato tem nome próprio no journal E sai
    # publicado no `state_full` (`coop.derrubado_por_steam_input`), para a
    # janela poder avisar. A LÓGICA da queda não mudou uma linha: mexer no
    # gatilho encosta na exceção de Steam Input, que é o caminho do defeito do
    # R1 curado na onda 2.
    #
    # Medido pelo RESIDUAL (antes menos o que sobrou), não por `n_jogadores`:
    # `coop.disable()` roda sob `suppress(Exception)` e um teardown que estoura
    # no meio deixa jogadores de pé — declarar "derrubei 3" nesse caso seria a
    # mesma classe de mentira que o log de "jogadores_coop=0".
    restantes = len(getattr(coop, "_players", None) or {}) if coop is not None else 0
    derrubados = max(0, n_jogadores - restantes)
    daemon._steam_input_coop_derrubados = derrubados  # type: ignore[attr-defined]
    logger.info(
        "steam_input_vpad_suspenso",
        appid=appid,
        flavor=flavor,
        jogadores_coop=n_jogadores,
    )
    if derrubados:
        # WARNING, não info: é perda de função que ela não pediu — três
        # jogadores viram um. O `restantes` acusa o teardown parcial.
        logger.warning(
            "coop_derrubado_pela_excecao_steam_input",
            appid=appid,
            secundarios_derrubados=derrubados,
            secundarios_restantes=restantes,
        )
    store = getattr(daemon, "store", None)
    if store is not None:
        with contextlib.suppress(Exception):
            store.bump("gamepad.steam_input.vpad_suspenso")
        if derrubados:
            # `suppress` próprio: um bump que estoura não pode engolir o outro.
            with contextlib.suppress(Exception):
                store.bump("gamepad.steam_input.coop_derrubado")
    return True


def resume_vpads_after_steam_input(daemon: DaemonProtocol) -> bool:
    """Devolve o gamepad virtual quando o jogo da allowlist sai (JOGO-01).

    True = o vpad voltou (ou a suspensão foi encerrada sem ter o que devolver).
    Chamada na borda de SAÍDA da exceção, depois de `_steam_input_excecao` já
    ser False — a ordem importa: o gate de `start_gamepad_emulation` recusa
    apply automático enquanto a exceção estiver de pé, e ele recusaria também
    esta devolução.

    `origin="profile"` de propósito, pela mesma razão do R-07: a preferência em
    disco nunca foi tocada na suspensão, e reescrevê-la agora seria o Hefesto
    "decidindo" por ela um estado que ela não pediu. A máscara restaurada é a
    que estava valendo quando o jogo abriu.

    Modo Nativo entrando no meio da sessão vence: ali o físico é o dispositivo
    por escolha dela, e ressuscitar o vpad recriaria o duplicado do outro lado.
    A suspensão é encerrada mesmo assim (o estado não pode ficar pendurado); o
    caminho canônico do Modo Nativo é quem manda a partir daí.
    """
    if not steam_input_vpad_suspenso(daemon):
        return False
    flavor = getattr(daemon, "_steam_input_flavor_suspenso", None)
    daemon._steam_input_vpad_suspenso = False  # type: ignore[attr-defined]
    daemon._steam_input_flavor_suspenso = None  # type: ignore[attr-defined]
    # CONTAGEM-E-COOP-01: o aviso do co-op derrubado morre com a suspensão, aqui
    # e em TODAS as saídas dela — inclusive nas que devolvem antes do
    # `coop.sync(force=True)` do fim (Modo Nativo, "não havia vpad"). Zerar só no
    # caminho felizmente-completo deixaria a janela avisando de um estrago
    # encerrado. Ver `steam_input_coop_derrubados`.
    derrubados_antes = steam_input_coop_derrubados(daemon)
    daemon._steam_input_coop_derrubados = 0  # type: ignore[attr-defined]
    if derrubados_antes:
        # Nome do fato EXATO: o aviso acabou. "Devolvido" seria mentira nas
        # saídas que não recriam o co-op (Modo Nativo, "não havia vpad") — quem
        # recria é o `coop.sync(force=True)` do fim desta função.
        logger.info(
            "steam_input_coop_aviso_encerrado",
            secundarios_derrubados=derrubados_antes,
        )
    nativo = False
    with contextlib.suppress(Exception):
        nativo = bool(daemon.is_native_mode())
    if nativo:
        logger.info("steam_input_vpad_nao_retomado", motivo="modo_nativo")
        return True
    if not isinstance(flavor, str) or not flavor:
        # Não havia vpad do P1 quando a exceção entrou (ver a máscara gravada na
        # suspensão): devolver aqui seria CRIAR um device que ela não tinha.
        logger.info("steam_input_vpad_nao_retomado", motivo="nao_havia_vpad")
        return True
    logger.info("steam_input_vpad_retomado", flavor=flavor)
    store = getattr(daemon, "store", None)
    if store is not None:
        with contextlib.suppress(Exception):
            store.bump("gamepad.steam_input.vpad_retomado")
    # `_emu_lock` pelo mesmo motivo da suspensão: criar device é operação
    # serializada com as outras superfícies (IPC/GUI/hotplug).
    with getattr(daemon, "_emu_lock", contextlib.nullcontext()):
        start_gamepad_emulation(daemon, flavor=flavor, origin="profile")
        # O conjunto de jogadores foi a zero na suspensão; o ciclo normal do
        # co-op (~2 s no poll loop) recria os secundários sozinho, mas
        # `force=True` faz o P2+ voltar no mesmo instante que o P1 em vez de
        # dois segundos depois — no co-op de quatro, dois segundos são a
        # diferença entre "voltou" e "sumiu".
        coop = getattr(daemon, "_coop_manager", None)
        if coop is not None:
            with contextlib.suppress(Exception):
                coop.sync(force=True)
    return True


def vpad_vivo(device: Any) -> bool:
    """VIDA de UM objeto vpad, não existência (lição 6/#17 da auditoria).

    uhid só conta como vivo com `_started` não-False (o UHID_STOP de um probe
    que recusou derruba o device sem destruir o objeto Python —
    `uhid_gamepad._handle_event`); uinput/fakes sem o atributo contam como
    vivos enquanto o objeto existir; None nunca é vivo. Achado Onda S #1: o
    gate vale para o vpad do P1 E para o de CADA jogador de co-op — esconder
    o físico de quem só tem vpad morto é o caminho direto para ZERO controles.
    """
    if device is None:
        return False
    return getattr(device, "_started", None) is not False


def _vpad_vivo(daemon: DaemonProtocol) -> bool:
    """VIDA do vpad do P1 (gate do rehide/hide do primário) — ver `vpad_vivo`."""
    return vpad_vivo(getattr(daemon, "_gamepad_device", None))


def rehide_physical_hidraw(daemon: DaemonProtocol) -> None:
    """Re-hide de TODOS os hidraw físicos com vpad vivo (P1 + jogadores co-op).

    BROKER-01 §2.2: nó recriado pelo replug/wake BT NASCE VISÍVEL (rule 70 +
    uaccess re-aplicados pelo udev) — o broker re-aplica o fs mesmo para nó
    já rastreado (lição 2: idempotência só em memória mentiria), então chamar
    isto a cada reconciliação online do `reconnect_loop` converge sozinho.
    SEMPRE via executor DEDICADO do broker (`broker_executor_for`, corretor
    final achado #6): o cliente faz I/O de socket com timeout de 2 s por nó —
    nunca no event loop E nunca no pool compartilhado 'hefesto-hid' de
    read_state (o padrão que o HANG-01 baniu). Gates espelham o hide do grab: emulação
    ligada, vpad VIVO (não só existente), fora do Modo Nativo, backend com
    `hidraw_path`. Jogador de co-op sem vpad vivo ou externo (`path:*`) NUNCA
    autoriza hide do próprio nó.
    """
    if daemon.is_native_mode():
        return
    if steam_input_excecao_ativa(daemon):
        # R-06: sem este gate a reconciliação online (a cada ≤30 s) desfaria a
        # exceção sozinha no meio do jogo da allowlist — o físico voltaria a
        # 0600 e a Steam perderia o hidraw que ela acabou de ganhar.
        return
    if not getattr(daemon.config, "gamepad_emulation_enabled", False):
        return
    if not _vpad_vivo(daemon):
        return
    hidraw_fn = getattr(daemon.controller, "hidraw_path", None)
    if not callable(hidraw_fn):
        return
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        broker_client_for,
    )

    client = broker_client_for(daemon)
    nodes: set[str] = set()
    node = hidraw_fn()
    if isinstance(node, str) and node:
        nodes.add(node)
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None) or {}
    # S-6 (auditoria 21/07): snapshot — esta função roda no executor do broker
    # enquanto o coop.sync (event loop) pode mutar o dict; iterar a view viva
    # é RuntimeError engolido pelo suppress do caller = rehide do ciclo perdido.
    for identity, player in list(players.items()):
        # Achado Onda S #1: VIDA do vpad do jogador, não existência — um uhid
        # derrubado por UHID_STOP (`_started=False`) com o objeto Python vivo
        # NÃO autoriza esconder o físico dele (lição 6/#17, agora para P2+).
        if not vpad_vivo(getattr(player, "vpad", None)) or identity.startswith("path:"):
            continue  # jogador sem vpad VIVO nunca autoriza hide
        n = hidraw_fn(identity)
        if isinstance(n, str) and n:
            nodes.add(n)
    for n in sorted(nodes):
        client.hide(n)


def _game_rumble_mult(daemon: DaemonProtocol, now: float) -> float:
    """Multiplicador da política global de rumble para o rumble do JOGO.

    FEAT-VPAD-FF-PASSTHROUGH-01: o FF do vpad passa pela MESMA política
    (economia/balanceado/max/auto/custom) do slider "Intensidade global" —
    espelho fiel de `subsystems.rumble.reassert_rumble` (bateria do snapshot
    do store + `_effective_mult` com o estado de debounce compartilhado do
    daemon). Duplicado aqui de propósito: o reassert é do caminho do rumble
    FIXADO e este é do rumble do jogo; a fonte canônica do cálculo segue
    sendo `core.rumble._effective_mult`.
    """
    from hefesto_dualsense4unix.core.rumble import _effective_mult
    from hefesto_dualsense4unix.daemon.subsystems.rumble import AUTO_DEBOUNCE_SEC

    battery_pct = 50  # fallback neutro (igual ao reassert)
    try:
        ctrl = daemon.store.snapshot().controller
        if ctrl is not None and ctrl.battery_pct is not None:
            battery_pct = int(ctrl.battery_pct)
    except Exception:
        logger.debug("game_rumble_state_read_fallback", exc_info=True)
    mult, daemon._last_auto_mult, daemon._last_auto_change_at = _effective_mult(
        config=daemon.config,
        battery_pct=battery_pct,
        now=now,
        last_auto_mult=daemon._last_auto_mult,
        last_auto_change_at=daemon._last_auto_change_at,
        auto_debounce_sec=AUTO_DEBOUNCE_SEC,
    )
    return mult


def apply_game_rumble(
    daemon: DaemonProtocol,
    weak: int,
    strong: int,
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no controle FÍSICO o rumble vindo do jogo (FF do vpad).

    FEAT-VPAD-FF-PASSTHROUGH-01. Decisões (documentadas):
      - `rumble_active` FIXADO manual VENCE: com rumble fixado (usuária
        testando os motores pela GUI), o FF do jogo é IGNORADO — o reassert
        de 200ms manteria o valor fixado de qualquer forma; ignorar evita
        briga de escrita HID. Em passthrough (`rumble_active is None`) o
        reassert é no-op e o FF do jogo manda sozinho.
      - A política global de intensidade é aplicada AQUI (mesmo multiplicador
        do reassert) — o slider vale também para o rumble do jogo.
      - `target_uniq` (MAC) mira o controle de UM jogador via a API por-uniq
        do backend (`set_rumble_for`, PERFIL-01) — SEM o flip transitório do
        seletor global (`set_output_target`) que existia antes: o flip corria
        com o executor multi-thread (max_workers=2) e, com o estado desejado
        keyed pelo alvo lido na hora, uma escrita da GUI intercalada
        persistiria config no controle errado. O seletor da usuária nunca é
        tocado. Sem a API (ex.: FakeController) ou com MAC que não casa
        nenhum handle, cai no broadcast histórico — limitação documentada:
        TODOS os controles vibram juntos.
    """
    if daemon.config.rumble_active is not None:
        return  # rumble fixado manual vence o FF do jogo
    controller = daemon.controller
    mult = _game_rumble_mult(daemon, time.monotonic())
    weak_eff = max(0, min(255, round(weak * mult)))
    strong_eff = max(0, min(255, round(strong * mult)))

    # Any: o targeting por-uniq é opcional no backend (só o PyDualSense o
    # tem; IController/FakeController não) — o gate é o callable() abaixo.
    rumble_for: Any = getattr(controller, "set_rumble_for", None)
    if target_uniq is not None and callable(rumble_for):
        try:
            if rumble_for(target_uniq, weak_eff, strong_eff):
                return
        except Exception as exc:
            logger.warning("game_rumble_target_failed", err=str(exc), target=target_uniq)
            return
        # MAC não casou nenhum handle → broadcast histórico (documentado).
    try:
        controller.set_rumble(weak=weak_eff, strong=strong_eff)
    except Exception as exc:
        logger.warning("game_rumble_failed", err=str(exc))


def apply_game_trigger(
    daemon: DaemonProtocol,
    side: str,
    block: bytes,
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no físico o trigger effect que o JOGO escreveu no vpad (REPLICA-03).

    Sem broadcast de propósito (diferente do rumble): replicar um efeito de
    gatilho em TODOS os controles pintaria o jogador errado. Sem MAC alvo ou
    sem a API por-uniq no backend (FakeController), a réplica é descartada com
    log — nunca degrada para broadcast.
    """
    fn: Any = getattr(daemon.controller, "set_game_trigger_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_trigger_sem_alvo_descartado", target=target_uniq)
        return
    try:
        fn(target_uniq, side, block)
    except Exception as exc:
        logger.warning("game_trigger_failed", err=str(exc), target=target_uniq)


def apply_game_lightbar(
    daemon: DaemonProtocol,
    rgb: tuple[int, int, int],
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no físico a cor de lightbar que o JOGO pintou no vpad (REPLICA-03)."""
    fn: Any = getattr(daemon.controller, "set_game_output_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_lightbar_sem_alvo_descartado", target=target_uniq)
        return
    try:
        fn(target_uniq, led=rgb)
    except Exception as exc:
        logger.warning("game_lightbar_failed", err=str(exc), target=target_uniq)


def apply_game_player_leds(
    daemon: DaemonProtocol,
    bits: tuple[bool, bool, bool, bool, bool],
    *,
    target_uniq: str | None = None,
) -> None:
    """Aplica no físico os player-LEDs que o JOGO acendeu no vpad (REPLICA-03).

    É a cura do P3 para DualSense por construção: o número NO CONTROLE passa a
    ser o número que o JOGO atribuiu, não o dos nossos registries.
    """
    fn: Any = getattr(daemon.controller, "set_game_output_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_player_leds_sem_alvo_descartado", target=target_uniq)
        return
    try:
        fn(target_uniq, player_leds=bits)
    except Exception as exc:
        logger.warning("game_player_leds_failed", err=str(exc), target=target_uniq)


def end_game_output_session(
    daemon: DaemonProtocol, *, target_uniq: str | None = None
) -> None:
    """Fim da sessão uhid do jogador: devolve perfil/paleta/co-op (REPLICA-03)."""
    fn: Any = getattr(daemon.controller, "end_game_session_for", None)
    if target_uniq is None or not callable(fn):
        logger.debug("game_session_end_sem_alvo", target=target_uniq)
        return
    try:
        fn(target_uniq)
    except Exception as exc:
        logger.warning("game_session_end_failed", err=str(exc), target=target_uniq)


def make_primary_replica_sinks(daemon: DaemonProtocol) -> dict[str, Any]:
    """Sinks de replicação do vpad do P1 → físico PRIMÁRIO (REPLICA-03).

    Espelho de `make_primary_rumble_sink`: o MAC do primário é resolvido NA
    HORA de cada réplica (`primary_uniq` muda em hotplug). As chaves do dict
    casam com os kwargs de `make_virtual_pad`/`UhidDualSense` de propósito —
    o call site desempacota com `**`.

    O CLOSE encerra a sessão de CADA controle que recebeu réplica, não só o
    primário do INSTANTE do CLOSE: o primário pode ter caído/trocado no BT no
    meio do jogo (reconexão BT é frequente nesta máquina), e a camada GAME
    grudou no controle que RECEBEU a cor — não no primário atual. Encerrar só
    o `primary_uniq` corrente vazaria a camada game no controle original, que
    voltaria como TOPO do merge no reconnect (a mesma writer-war/paleta
    corrompida que o REPLICA-03 mata). Por isso lembramos todo uniq replicado
    na sessão e devolvemos CADA um. Tudo roda na thread de poll (sem lock).
    """

    replicados: set[str] = set()

    def _uniq() -> str | None:
        uniq = getattr(daemon.controller, "primary_uniq", None)
        if isinstance(uniq, str) and uniq:
            replicados.add(uniq)
            return uniq
        return None

    def _session_end() -> None:
        alvos = tuple(replicados)
        replicados.clear()
        for uniq in alvos:
            end_game_output_session(daemon, target_uniq=uniq)

    return {
        "trigger_sink": lambda side, block: apply_game_trigger(
            daemon, side, block, target_uniq=_uniq()
        ),
        "lightbar_sink": lambda r, g, b: apply_game_lightbar(
            daemon, (r, g, b), target_uniq=_uniq()
        ),
        "player_led_sink": lambda bits: apply_game_player_leds(
            daemon, bits, target_uniq=_uniq()
        ),
        "session_end_sink": _session_end,
    }


def notify_vpad_degradado(daemon: DaemonProtocol, *, player: int, motivo: str) -> None:
    """Anuncia a TRANSIÇÃO "vpad deste jogador nasceu degradado" (BT-03).

    Duas saídas, ambas best-effort e nunca fatais:

    - log estruturado ``vpad_degradado`` — a fonte de verdade nesta máquina é
      o stdout do daemon (roda ``--foreground`` fora do systemd; ver "Precisão
      de linguagem" do sprint BT: nenhum critério pode depender do journal);
    - ``daemon.bus.publish("vpad.degraded", ...)`` — o EventBus é a infra de
      notificação existente (``core/events.py``). O tópico vai como literal
      documentado porque `EventTopic` está fora da fronteira desta frente
      (promover a constante quando `events.py` entrar em escopo); publicar num
      tópico sem assinantes é no-op barato por construção do bus.

    Chamado SÓ na borda de criação degradada (P1 em `start_gamepad_emulation`;
    secundários em `CoopManager._promote_player`) — nunca no `state_full` a
    10 Hz (seria flood, a mesma regra do `dedup_broken` do DEDUP-06).
    """
    logger.warning("vpad_degradado", player=player, motivo=motivo)
    bus = getattr(daemon, "bus", None)
    if bus is None:
        return
    with contextlib.suppress(Exception):
        bus.publish("vpad.degraded", {"player": player, "motivo": motivo})


def dedup_status(daemon: DaemonProtocol) -> tuple[bool, list[str]]:
    """(dedup_ok, motivos) agregados POR JOGADOR — o guard DEDUP-06.

    `dedup_ok=True` significa: um jogo lançado AGORA com o IGNORE congelado na
    env não deixa NENHUM jogador sem controle utilizável. A agregação é por
    jogador de propósito (exigência da revisão): no co-op cada vpad nasce do
    hidraw daquele controle e cai individualmente em uinput/0ce6 — um único
    jogador degradado com o IGNORE congelado é AQUELE jogador com zero
    controle, e um `dedup_ok` só-do-P1 mentiria.

    Estados:
      - emulação desligada / Modo Nativo: nenhum IGNORE materializado → ok
        (o launch_env já omite o IGNORE nesses estados);
      - máscara xbox: o vpad é uinput 045e POR DESIGN — o IGNORE cirúrgico do
        físico Sony nunca o esconde (invariante VPAD-06) → ok;
      - máscara dualsense: ok SÓ se o vpad do P1 e TODOS os vpads do co-op
        estão em uhid. Motivos: `fallback_motivo` do P1 (ou `sem_uhid`) e
        `jogador_<N>_uinput` por jogador degradado;
      - emulação ligada SEM device (start falhou): `vpad_ausente`.

    Só leitura de atributos — nunca propaga exceção pro `state_full` (getattr
    defensivo em tudo; daemons dublados de teste não têm coop/store).
    """
    cfg = getattr(daemon, "config", None)
    enabled = bool(getattr(cfg, "gamepad_emulation_enabled", False))
    if not enabled:
        return True, []
    with contextlib.suppress(Exception):
        if bool(daemon.is_native_mode()):
            return True, []
    device = getattr(daemon, "_gamepad_device", None)
    if device is None:
        return False, ["vpad_ausente"]
    if getattr(device, "flavor", None) != "dualsense":
        return True, []
    motivos: list[str] = []
    if getattr(device, "backend", None) == "uinput":
        motivo = getattr(device, "fallback_motivo", None)
        motivos.append(motivo if isinstance(motivo, str) and motivo else "sem_uhid")
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None)
    if isinstance(players, dict):
        for player in players.values():
            vpad = getattr(player, "vpad", None)
            if vpad is None or getattr(vpad, "backend", None) != "uinput":
                continue
            indice = getattr(player, "player_index", None)
            rotulo = str(indice) if isinstance(indice, int) else "?"
            motivos.append(f"jogador_{rotulo}_uinput")
    return not motivos, motivos


def controller_allows_uhid(daemon: DaemonProtocol) -> bool:
    """True quando o backend do controle é o real (pydualsense) — uhid liberado.

    VPAD-08: o modo FAKE (`run.sh --fake`, usado em smoke NA MÁQUINA da usuária)
    não pode registrar um DualSense Edge REAL no kernel — a Steam enxergaria um
    controle fantasma. O único backend com `hidraw_path` no repo é o pydualsense
    (`backend_pydualsense.py`); `FakeController`/`IController` não têm o método,
    e essa é a declaração explícita de "sem uhid" que a factory recebe em
    `allow_uhid`. Não confundir com "controle conectado": o blueprint do vpad é
    o canônico embutido (VPAD-03/BT-01) e o uhid sobe mesmo sem físico nenhum —
    este gate é sobre o BACKEND, não sobre o hardware do momento.
    """
    return callable(getattr(daemon.controller, "hidraw_path", None))


def _autoridade_do_jogo(daemon: Any) -> bool:
    """True SÓ quando o sinal STICKY diz que o jogo tem a autoridade (R-04).

    Contradição 3 da §5 do plano — são DOIS sinais para DUAS decisões, e
    fundi-los quebra um dos dois lados:

    - **operação destrutiva** (recriar/parar vpad) lê `display_authority`, que
      é sticky por ~30 s: fail-safe aqui é NÃO destruir, então segurar o gesto
      por mais alguns segundos depois de o jogo perder o foco é exatamente o
      erro que queremos cometer;
    - **reversão de modo para desktop** lê a janela CRUA
      (`lifecycle._janela_de_jogo_em_foco`, R-02): lá o sticky congelaria a
      reversão legítima ao fechar o jogo.

    Ausência do atributo (dublês de teste, daemon antigo) e qualquer leitura
    não-`"game"` NÃO bloqueiam: o risco declarado do R-04 é o gate largo demais
    fazer o perfil não valer NUNCA — que agrava a queixa que ele veio curar.
    """
    return getattr(daemon, "display_authority", "unknown") == "game"


def _recriacao_bloqueada_por_jogo(
    daemon: DaemonProtocol, *, origin: str, motivo: str
) -> bool:
    """True quando destruir/recriar o vpad AGORA arrancaria o controle do jogo.

    R-04 (auditoria 23/07). Medido ao vivo: recriar o vpad com o jogo já
    rodando invalida os handles que ele abriu — a Steam nunca reabre o hidraw
    do vpad do P1 — e o resultado é "abri o jogo e os controles morreram no
    meio da partida". Quem dispara essa recriação sem ela pedir é o caminho
    automático (perfil/autoswitch/hotplug), e é só ele que este gate segura:

    - ``origin == "manual"`` NUNCA é bloqueado. Trocar de máscara com o jogo
      aberto é uma escolha legítima dela (o botão de força do VPAD-02 vive
      disso); a última palavra é sempre da usuária;
    - com o R-04 completo o caso praticamente some: o modo do perfil passa a
      ser armado NO LAUNCH (`launch_env.arm_launch_profile`), antes de o jogo
      executar, e a aplicação tardia vira no-op por idempotência.

    Nunca silencioso: warning no journal + contador no store, para o gesto
    recusado ter rastro (a mesma disciplina do `rebackend_suprimido_por_*`).
    """
    if origin == "manual":
        return False
    if not _autoridade_do_jogo(daemon):
        return False
    logger.warning("vpad_recriacao_bloqueada_por_jogo", motivo=motivo, origem=origin)
    store = getattr(daemon, "store", None)
    if store is not None:
        with contextlib.suppress(Exception):
            store.bump("gamepad.recreate.blocked_by_game")
    return True


def _reconciliar_launch(daemon: DaemonProtocol) -> None:
    """Reconciliação de LAUNCH throttada a 1 Hz (R-04 arming + R-06 exceção).

    Chamada do `dispatch_gamepad` — ou seja, do poll loop, ao lado do dreno de
    pendência do R-03 e com a mesma disciplina de throttle. Duas coisas, ambas
    best-effort e nenhuma delas podendo derrubar o dispatch do controle:

    1. `arm_launch_profile` — aplica o modo do perfil quando o marker do
       wrapper mostra um launch em curso (R-04), idempotente por `(appid,
       epoch)`;
    2. `sync_steam_input_exception` — liga/desliga a exceção por appid (R-06).

    Decisão registrada: o lugar canônico deste par é a cadência do `_poll_loop`
    (`lifecycle.py`), junto de `_drenar_modo_pendente`. Ele mora aqui porque é
    o ponto de 1 Hz alcançável a partir deste subsystem; a semântica é a mesma
    e o custo por tick sem vencimento é uma comparação de float.
    """
    try:
        agora = time.monotonic()
        if agora < getattr(daemon, "_launch_reconcile_next_at", 0.0):
            return
        daemon._launch_reconcile_next_at = (  # type: ignore[attr-defined]
            agora + LAUNCH_RECONCILE_INTERVAL_SEC
        )
    except Exception:
        # Daemon dublado/imutável (ou carimbo corrompido): sem throttle não há
        # reconciliação — e o dispatch do controle, que é a ROTA do jogo, NUNCA
        # pode cair por causa de um extra. Mesma disciplina do `_materialize_
        # launch_env`: falha aqui vira ausência de recurso, nunca input morto.
        logger.debug("launch_reconcile_throttle_indisponivel", exc_info=True)
        return
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.launch_env import arm_launch_profile

        arm_launch_profile(daemon)
    with contextlib.suppress(Exception):
        sync_steam_input_exception(daemon)


def _rebackend_em_cooldown(daemon: DaemonProtocol, now: float) -> bool:
    """True se a última tentativa de rebackend está a menos de um cooldown.

    O carimbo (`daemon._last_rebackend_ts`) é um só para as duas bordas
    (hotplug e re-seleção pela GUI) de propósito: o modo de falha que a trava
    cobre — uhid que aceita o CREATE2 mas nunca faz bind — é o mesmo nos dois
    caminhos, e alternar entre eles não pode burlar o cooldown.
    """
    carimbo = getattr(daemon, "_last_rebackend_ts", float("-inf"))
    return (now - carimbo) < REBACKEND_COOLDOWN_SEC


def upgrade_primary_vpad_to_uhid(daemon: DaemonProtocol) -> bool:
    """Recria em uhid o vpad do P1 que degradou para uinput. True = trocou.

    Pós-VPAD-03/BT-01 o vpad do P1 já NASCE uhid no boot — o blueprint canônico
    embutido não depende de controle conectado, então o caso histórico ("o
    gamepad sobe antes do `controller.connect` e caía no uinput") morreu. Esta
    função virou REDE DE SEGURANÇA: recupera o vpad que caiu no uinput por razão
    transitória (ex.: /dev/uhid ainda sem ACL na primeira sessão pós-install),
    chamada quando o controle conecta (boot em `lifecycle.run`; hotplug tardio
    no `reconnect_loop` — VPAD-01). Conservadora de propósito:

    - só age no vpad do P1 que é uinput com máscara DualSense (a Xbox é uinput
      por design — o `hid_playstation` não faz bind em VID/PID da Microsoft);
    - precheck `uhid_available()` (ressalva do VPAD-01): sem ele, com o uhid
      persistentemente quebrado (permissão do nó, kernel sem `hid_playstation`),
      cada conexão destruiria e recriaria o vpad uinput que ESTÁ funcionando —
      input drop em loop com o jogo aberto;
    - cooldown compartilhado com a re-seleção da GUI (`REBACKEND_COOLDOWN_SEC`):
      o precheck não pega o uhid que aceita o CREATE2 e nunca binda — sem a
      trava, cada reconexão BT viraria o mesmo input drop em loop;
    - backend fake nunca promove (VPAD-08);
    - recria o device, então o jogo aberto PERDE o vpad por um instante. É
      aceitável porque a janela real é a recuperação de uma degradação que já
      tirou a vibração do jogo de qualquer forma.

    VPAD-09 (falha TOTAL): `_gamepad_device is None` com a emulação desejada na
    config = o boot perdeu a corrida da ACL uaccess de /dev/uhid E /dev/uinput
    contra o logind (visto ao vivo em 21/07: daemon de sessão sobe no login,
    logind aplica a ACL instantes depois; sem retry o vpad só voltava com
    restart manual). Aqui a borda de conexão REVIVE a emulação pela factory
    completa (uhid→uinput, flavor da config) — sem precheck `uhid_available()`
    (não há device funcionando para proteger; qualquer backend é melhor que
    nenhum), mas sob o MESMO cooldown (reconexão BT em rajada não vira spam).
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UhidDualSense,
        uhid_available,
    )

    device = getattr(daemon, "_gamepad_device", None)
    if isinstance(device, UhidDualSense):
        return False
    if steam_input_excecao_ativa(daemon):
        # JOGO-01: esta é a REDE DE SEGURANÇA do vpad, e durante a exceção não
        # há vpad a salvar — o dispositivo do jogo é o físico. Sem este gate, o
        # ramo VPAD-09 (device None + emulação desejada) tentaria ressuscitar o
        # vpad na primeira reconexão de controle no meio da partida, que é o
        # cenário mais provável de todos nesta máquina (BT reconectando).
        logger.debug("vpad_revive_pulado_steam_input")
        return False
    if not controller_allows_uhid(daemon):
        return False  # backend fake: nunca registrar um Edge real (VPAD-08)
    if device is None:
        # VPAD-09: sem device NENHUM. Se a emulação está desligada por escolha,
        # não há o que reviver; se está ligada na config, o start do boot
        # falhou inteiro (ex.: EACCES na race da ACL) e ninguém mais tenta.
        if not getattr(daemon.config, "gamepad_emulation_enabled", False):
            return False
        now = time.monotonic()
        if _rebackend_em_cooldown(daemon, now):
            logger.info("rebackend_suprimido_por_cooldown", origem="revive")
            return False
        daemon._last_rebackend_ts = now
        logger.info(
            "vpad_revivendo_pos_falha_total",
            flavor=getattr(daemon.config, "gamepad_flavor", None),
        )
        return start_gamepad_emulation(daemon)
    if getattr(device, "flavor", None) != "dualsense":
        return False
    if not uhid_available():
        return False  # uhid segue quebrado: derrubar o uinput seria só input drop
    # R-04: a promoção abaixo destrói e recria o vpad. A docstring desta função
    # sempre admitiu que "o jogo aberto PERDE o vpad por um instante" e julgou
    # o preço aceitável; a medição de 23/07 mostrou que não é um instante — a
    # Steam não reabre o handle e o jogo fica sem controle o resto da sessão.
    # Com o jogo na autoridade, a recuperação de uma degradação (que no pior
    # caso custa vibração) não pode custar o controle inteiro. Fora do jogo a
    # promoção segue igual, e o hotplug seguinte tenta de novo.
    if _recriacao_bloqueada_por_jogo(daemon, origin="hotplug", motivo="promocao_uhid"):
        return False
    now = time.monotonic()
    if _rebackend_em_cooldown(daemon, now):
        # A tentativa anterior (desta borda OU da re-seleção na GUI — o
        # carimbo é um só) acabou de recriar o device e voltou ao uinput:
        # insistir agora seria o input drop em loop que a ressalva do
        # VPAD-01 proíbe. Nunca silencioso: o motivo fica no journal.
        logger.info("rebackend_suprimido_por_cooldown", origem="hotplug")
        return False
    daemon._last_rebackend_ts = now

    logger.info("vpad_promovendo_para_uhid", motivo="vpad degradado com uhid disponível")
    # `persist=False`: a preferência não mudou, só o backend. `release_grab=False`:
    # soltar o grab aqui devolveria o controle físico ao jogo no meio da troca.
    stop_gamepad_emulation(daemon, persist=False, release_grab=False)
    return start_gamepad_emulation(daemon, flavor="dualsense")


def read_primary_calibration(daemon: DaemonProtocol) -> bytes | None:
    """Feature 0x05 do controle PRIMÁRIO para o vpad do P1 (GYRO-01).

    Best-effort por contrato: backend sem `read_calibration` (FakeController),
    daemon offline (o vpad sobe antes do `controller.connect` no boot) ou
    falha de leitura devolvem None e o vpad fica no 0x05 canônico — o
    invariante "vpad sempre nasce" nunca depende do físico.
    """
    fn: Any = getattr(daemon.controller, "read_calibration", None)
    if not callable(fn):
        return None
    try:
        data = fn()
    except Exception as exc:
        logger.warning("gamepad_calibration_read_failed", err=str(exc))
        return None
    return data if isinstance(data, bytes) else None


def start_motion_reader(daemon: DaemonProtocol, device: Any) -> None:
    """Sobe o espelho de motion do P1 (GYRO-01): hidraw do físico → vpad.

    Só existe no caminho uhid (o uinput não tem `forward_motion` — é evdev
    puro) e só quando o backend expõe `hidraw_path` (o FakeController não tem
    físico para espelhar). O `path_provider` re-resolve o hidraw do PRIMÁRIO
    a cada (re)abertura — hotplug/retarget convergem sem recriar o reader; o
    `attach_motion_reader` do backend fecha o ciclo cutucando o reader na
    troca de primário (`_recompute_primary`).
    """
    stop_motion_reader(daemon)  # idempotência: nunca dois readers no mesmo P1
    if getattr(device, "backend", None) != "uhid":
        return
    hidraw_fn: Any = getattr(daemon.controller, "hidraw_path", None)
    if not callable(hidraw_fn):
        return
    from hefesto_dualsense4unix.core.physical_report_reader import (
        PhysicalReportReader,
    )
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        make_broker_opener,
    )

    def _primary_hidraw() -> str | None:
        try:
            path = hidraw_fn()
        except Exception:
            return None
        return path if isinstance(path, str) else None

    # BROKER-01 §6.3: opener broker-aware — o reader reabre o hidraw via fd
    # do broker root (funciona com o nó ESCONDIDO pelo hide do grab) e cai em
    # os.open por caminho quando o broker está ausente (comportamento de hoje).
    reader = PhysicalReportReader(
        path_provider=_primary_hidraw, vpad=device, opener=make_broker_opener(daemon)
    )
    if not reader.start():  # pragma: no cover - start() atual nunca falha
        return
    daemon._motion_reader = reader
    attach: Any = getattr(daemon.controller, "attach_motion_reader", None)
    if callable(attach):
        with contextlib.suppress(Exception):
            attach(reader)
    logger.info("motion_reader_spawned", player=1)


def stop_motion_reader(daemon: DaemonProtocol) -> None:
    """Para o espelho de motion do P1 (idempotente).

    Chamado ANTES do `device.stop()` em `stop_gamepad_emulation`: o reader
    escreve no /dev/uhid do vpad e não pode sobreviver ao fd do device.
    """
    reader = getattr(daemon, "_motion_reader", None)
    if reader is None:
        return
    daemon._motion_reader = None
    detach: Any = getattr(daemon.controller, "attach_motion_reader", None)
    if callable(detach):
        with contextlib.suppress(Exception):
            detach(None)
    with contextlib.suppress(Exception):
        reader.stop()
    logger.info("motion_reader_stopped", player=1)


def make_primary_rumble_sink(daemon: DaemonProtocol) -> Callable[[int, int], None]:
    """Sink de FF do vpad do P1 → rumble físico do controle PRIMÁRIO.

    FEAT-VPAD-FF-PASSTHROUGH-01: o MAC do primário é resolvido NA HORA do
    rumble (`primary_uniq` muda em hotplug); com o co-op ativo isso garante
    que o rumble do P1 não sacode o controle dos outros jogadores. Backend
    sem `primary_uniq` (ex.: FakeController) cai em broadcast.
    """

    def _sink(weak: int, strong: int) -> None:
        uniq = getattr(daemon.controller, "primary_uniq", None)
        apply_game_rumble(
            daemon,
            weak,
            strong,
            target_uniq=uniq if isinstance(uniq, str) and uniq else None,
        )

    return _sink


def _deve_promover_backend(
    daemon: DaemonProtocol,
    existing: Any,
    key: str,
    origin: Literal["manual", "profile"] = "manual",
) -> bool:
    """True quando um apply de flavor IDÊNTICO deve recriar o vpad (VPAD-02).

    Re-selecionar DualSense na GUI é o "botão de força" da promoção
    uinput→uhid: os dois backends respondem flavor 'dualsense', então o
    early-return que comparava SÓ o flavor fazia da re-seleção um no-op — não
    existia caminho pela interface para recuperar um vpad degradado. A
    comparação agora é (flavor, backend), com os MESMOS gates da promoção do
    hotplug — porque perfis/autoswitch reaplicam a emulação a cada troca de
    janela e um apply idêntico não pode recriar o device à toa:

    - backend já uhid (ou máscara xbox, uinput por design) → no-op de verdade;
    - **latch do BT-04(b)**: `origin != "manual"` NUNCA promove — o botão de
      força é gesto da USUÁRIA (1 clique = 1 tentativa). Perfis/autoswitch
      reaplicam a emulação a cada troca de janela; com o uhid quebrado por
      razão estável que o precheck não enxerga (kernel sem `hid_playstation`:
      `uhid_available()` só testa o acesso ao nó), cada apply automático
      pós-cooldown destruiria o vpad uinput que FUNCIONA e pagaria ~0,5 s de
      `wait_for_bind` com o input congelado — input drop periódico indefinido
      no meio do jogo. A recuperação automática que existe é a do hotplug
      (VPAD-01), em borda física de conexão — não em timer de janela;
    - backend fake veta (VPAD-08): recriar daria só OUTRO uinput (churn);
    - `uhid_available()`: com o uhid quebrado, derrubar o uinput que funciona
      seria input drop sem ganho nenhum;
    - cooldown compartilhado com o VPAD-01 (`REBACKEND_COOLDOWN_SEC`): o uhid
      que aceita o CREATE2 mas nunca binda passa pelo precheck — sem a trava,
      cada apply derrubaria o vpad em loop no meio do jogo. Ressalva do
      VPAD-02: esse no-op devolve True (a GUI mostra sucesso), então NÃO pode
      ser mudo — o motivo vai para o journal ("cliquei e nada" tem rastro).
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import uhid_available

    if key != "dualsense" or getattr(existing, "backend", None) != "uinput":
        return False
    if origin != "manual":
        # BT-04(b): apply automático (perfil/autoswitch) com vpad degradado é
        # no-op SEMPRE. DEBUG de propósito: o autoswitch flapando reaplicaria
        # a cada troca de janela e um INFO viraria spam no journal; o rastro
        # visível para a usuária é o badge de degradação do VPAD-05.
        logger.debug("rebackend_suprimido_por_origem_automatica", origem=origin)
        return False
    if not controller_allows_uhid(daemon):
        return False  # backend fake: nunca registrar um Edge real (VPAD-08)
    if not uhid_available():
        return False  # uhid segue quebrado: derrubar o uinput seria só input drop
    now = time.monotonic()
    if _rebackend_em_cooldown(daemon, now):
        logger.info("rebackend_suprimido_por_cooldown", origem="reselecao_gui")
        return False
    daemon._last_rebackend_ts = now
    logger.info(
        "vpad_promovendo_para_uhid", motivo="re-seleção da máscara DualSense (VPAD-02)"
    )
    return True


def start_gamepad_emulation(
    daemon: DaemonProtocol,
    flavor: str | None = None,
    *,
    origin: Literal["manual", "profile"] = "manual",
) -> bool:
    """Cria o gamepad virtual com a máscara `flavor`. Idempotente.

    Desliga a emulação de mouse (mútua exclusão) e faz grab do controle real.
    Retorna True se ativo ao final; False se falhou ao iniciar. Idempotência
    por (flavor, backend): apply idêntico com backend saudável é no-op; mesma
    máscara DualSense com backend degradado (uinput) recria em uhid (VPAD-02).
    `origin` vem de `set_gamepad_emulation` (BT-04(b)): só o gesto MANUAL da
    usuária destrava a promoção por apply idêntico — perfil/autoswitch nunca
    recriam o vpad degradado (o latch anti-churn; ver `_deve_promover_backend`).

    JOGO-01: com a exceção de Steam Input ATIVA, todo apply AUTOMÁTICO é
    recusado — nos appids da allowlist o dispositivo do jogo é o físico, e o
    autoswitch (que reaplica a emulação a cada troca de janela, ou seja,
    justamente quando o jogo ganha foco) recriaria o vpad que a suspensão
    acabou de retirar. O gesto MANUAL segue passando: a última palavra é dela,
    e um vpad pedido no botão encerra a suspensão em vez de brigar com ela.
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor
    from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

    key = normalize_flavor(
        flavor if flavor is not None else getattr(daemon.config, "gamepad_flavor", None)
    )

    if steam_input_excecao_ativa(daemon):
        if origin != "manual":
            logger.info(
                "gamepad_start_recusado_steam_input", flavor=key, origem=origin
            )
            return False
        if steam_input_vpad_suspenso(daemon):
            # Ela religou a emulação na mão com o jogo da allowlist aberto: o
            # vpad volta AGORA e a suspensão morre aqui (senão a saída da
            # exceção tentaria devolver um vpad que já está de pé). O preço —
            # este jogo volta a ver dois dispositivos — é escolha dela, e fica
            # no journal.
            logger.info("steam_input_vpad_retomado", motivo="gesto_manual")
            daemon._steam_input_vpad_suspenso = False  # type: ignore[attr-defined]
            daemon._steam_input_flavor_suspenso = None  # type: ignore[attr-defined]
            # CONTAGEM-E-COOP-01: a SEGUNDA saída da suspensão. O aviso do co-op
            # derrubado tem de morrer aqui também — senão a janela seguiria
            # avisando depois de ela mesma religar a emulação na mão.
            coop_derrubado_antes = steam_input_coop_derrubados(daemon)
            daemon._steam_input_coop_derrubados = 0  # type: ignore[attr-defined]
            if coop_derrubado_antes:
                logger.info(
                    "steam_input_coop_aviso_encerrado",
                    secundarios_derrubados=coop_derrubado_antes,
                    motivo="gesto_manual",
                )

    existing = daemon._gamepad_device
    if existing is not None:
        if getattr(existing, "flavor", None) == key and not _deve_promover_backend(
            daemon, existing, key, origin
        ):
            return True
        # R-04: daqui para baixo o vpad VIVO seria destruído e recriado. Com o
        # jogo segurando a autoridade de exibição isso arranca o controle da
        # mão dela no meio da partida — e é o desfecho que a queixa "abro o
        # jogo e a config nunca é respeitada" descreve pelo avesso. Vpad já
        # MORTO (uhid derrubado por UHID_STOP) não entra: não há o que perder,
        # e recriar é a única chance de o jogo ter controle.
        if vpad_vivo(existing) and _recriacao_bloqueada_por_jogo(
            daemon,
            origin=origin,
            motivo=f"troca_de_mascara:{getattr(existing, 'flavor', None)}->{key}",
        ):
            # True porque a emulação SEGUE ativa (com a máscara anterior) — o
            # contrato de retorno é "ativo ao final", não "aplicou o pedido".
            return True
        # Flavor mudou — ou mesma máscara com backend degradado e uhid de
        # volta (VPAD-02): recria sem repersistir/regrab intermediário.
        stop_gamepad_emulation(daemon, persist=False, release_grab=False)

    # Mútua exclusão: o controle vai pro jogo, não pro cursor.
    # HARM-06: `persist=False` — a preferência de mouse da usuária sobrevive ao
    # modo jogo. Gravar "off" aqui fazia o round-trip desktop->gamepad->desktop
    # apagá-la e o controle voltava do jogo sem função nenhuma.
    if getattr(daemon, "_mouse_device", None) is not None:
        from hefesto_dualsense4unix.daemon.subsystems.mouse import stop_mouse_emulation

        stop_mouse_emulation(daemon, persist=False)

    # FEAT-VPAD-FF-PASSTHROUGH-01: o rumble que o JOGO pedir no vpad volta
    # para os motores do controle físico primário.
    # SPRINT-UHID-VPAD-01 + VPAD-03/BT-01: a factory prefere o backend uhid
    # (DualSense com hidraw de verdade = vibração in-game na máscara DualSense)
    # e cai no uinput sozinha quando o uhid não sobe. O blueprint é o canônico
    # embutido: o vpad nasce uhid Edge JÁ NO BOOT, mesmo com o
    # `_safe_start("gamepad")` rodando antes do `controller.connect()` e mesmo
    # sem controle nenhum conectado. `allow_uhid` veta o uhid no backend fake
    # (VPAD-08 — o smoke não pode plantar um Edge real no kernel).
    # REPLICA-03: além do rumble, o output completo do jogo (gatilhos
    # adaptativos, lightbar, player-LEDs) volta ao físico do P1 pelos sinks
    # de replicação; o de fim-de-sessão devolve perfil/paleta no UHID_CLOSE.
    # GYRO-01: o 0x05 do físico primário calibra o motion espelhado no vpad
    # (None → canônico; ver `read_primary_calibration`).
    device: VirtualPad | None = make_virtual_pad(
        key,
        rumble_sink=make_primary_rumble_sink(daemon),
        player=1,
        allow_uhid=controller_allows_uhid(daemon),
        calibration_0x05=read_primary_calibration(daemon),
        **make_primary_replica_sinks(daemon),
    )
    if device is None:
        logger.warning("gamepad_emulation_start_failed", flavor=key)
        # DEDUP-04 (achado HIGH da revisão adversarial da Fase 2): a falha
        # TOTAL do start também é uma transição de estado. Sem regravar aqui,
        # um `default.env` rançoso da sessão anterior (com IGNORE) sobrevive a
        # um daemon que morreu SUJO (SIGKILL/OOM) e voltou sem conseguir subir
        # vpad nenhum (ex.: /dev/uhid E /dev/uinput sem ACL — classe já vista
        # nesta máquina pela ordem das regras udev >=73): daemon VIVO passa no
        # gate do wrapper, o IGNORE esconde o físico e não existe vpad = ZERO
        # controles NO LAUNCH. O `_snapshot` com `_gamepad_device=None` compõe
        # o arquivo seguro (só o preload de shaders).
        _materialize_launch_env(daemon)
        return False

    daemon._gamepad_device = device
    if key == "dualsense" and getattr(device, "backend", None) == "uinput":
        # VPAD-05 — fallback NUNCA silencioso: além do motivo que a factory já
        # logou, o degrau vira contador no store (doctor) e o `state_full` expõe
        # `gamepad_emulation.degraded`/`degraded_motivo` para a GUI. getattr
        # defensivo: daemons dublados em teste não têm store.
        store = getattr(daemon, "store", None)
        if store is not None:
            with contextlib.suppress(Exception):
                store.bump("gamepad.uhid.fallback")
        # BT-03: a degradação do P1 é uma transição anunciada (log + bus).
        motivo = getattr(device, "fallback_motivo", None)
        notify_vpad_degradado(
            daemon,
            player=1,
            motivo=motivo if isinstance(motivo, str) and motivo else "sem_uhid",
        )
    # GYRO-01: com o vpad uhid de pé, o gyro/accel/touchpad do físico passa a
    # fluir pelo espelho de report (thread própria; no fallback uinput é no-op).
    start_motion_reader(daemon, device)
    daemon.config.gamepad_emulation_enabled = True
    daemon.config.gamepad_flavor = key
    _set_controller_grab(daemon, True)
    # R-07 (auditoria 23/07): SÓ gesto manual persiste a preferência em disco.
    # A regra já estava escrita em dois lugares deste mesmo módulo/eixo —
    # HARM-06 no mouse ("a preferência da usuária sobrevive ao modo jogo") e
    # FEAT-COOP-DEFAULT-ON-01 no co-op ("perfil ligando/desligando não pode
    # virar opt-out da usuária") — mas o gamepad gravava sem olhar o `origin`.
    # Efeito medido: ela escolhia Xbox, abria o Sackboy (cujo perfil pede
    # dualsense) e a flag em disco virava `dualsense`; a escolha dela sumia sem
    # ela ter tocado em nada, e voltava assim no boot seguinte.
    if origin == "manual":
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

            save_gamepad_emulation(True, key)
    # DEDUP-04: gatilho "transição de backend/máscara" da materialização — o
    # wrapper hefesto-launch decide as envs pelo que fica gravado aqui.
    _materialize_launch_env(daemon)
    logger.info("gamepad_emulation_started", flavor=key)
    return True


def stop_gamepad_emulation(
    daemon: DaemonProtocol, *, persist: bool = True, release_grab: bool = True
) -> None:
    """Para e descarta o gamepad virtual. Idempotente.

    `persist=False` e `release_grab=False` são usados na troca de flavor (a
    recriação imediata reaplica ambos).

    HARM-16: zerar os motores é CONSEQUÊNCIA de parar o vpad, e por isso mora
    aqui. Era responsabilidade de cada caller lembrar, e um esqueceu: o
    `set_mouse_emulation(True)` derruba o gamepad pela exclusão mútua e o
    controle ficava vibrando para sempre (em passthrough o reassert do poll loop
    é no-op — ver `zero_motors_on_mode_exit`). Com o zero aqui, um caller novo
    não tem como esquecer. Vale também para a troca de flavor e o shutdown: o
    dono do FF (o jogo, via vpad) some nos dois, e o motor não pode ficar ligado
    no vácuo — quem tem rumble FIXO pela aba Rumble não é afetado (no-op).
    """
    # GYRO-01: o reader morre ANTES do vpad — ele escreve no /dev/uhid do
    # device e pararia num fd fechado/reciclado se a ordem invertesse.
    stop_motion_reader(daemon)
    tinha_device = daemon._gamepad_device is not None
    if tinha_device:
        with contextlib.suppress(Exception):
            daemon._gamepad_device.stop()
        daemon._gamepad_device = None
    # Sem device (ex.: falha no start) o resto ainda roda: config/flag/grab
    # coerentes valem em qualquer caso.
    daemon.config.gamepad_emulation_enabled = False
    if release_grab:
        _set_controller_grab(daemon, False)
    if persist:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.session import save_gamepad_emulation

            save_gamepad_emulation(False)
    from hefesto_dualsense4unix.daemon.subsystems.rumble import zero_motors_on_mode_exit

    zero_motors_on_mode_exit(daemon)
    # DEDUP-04: sem vpad o wrapper não pode mais anunciar IGNORE — regrava as
    # envs de launch com o estado real (o `persist=False` da troca de flavor
    # regrava de novo no start seguinte; escrever 2x é barato e idempotente).
    _materialize_launch_env(daemon)
    if tinha_device:
        logger.info("gamepad_emulation_stopped")


def dispatch_gamepad(
    daemon: DaemonProtocol, state: Any, buttons_pressed: frozenset[str]
) -> None:
    """Repassa o estado do controle ao gamepad virtual.

    Chamado pelo poll loop a cada tick quando _gamepad_device != None.
    Não relança exceções — falhas viram warning.

    R-04/R-06: a reconciliação de launch roda ANTES do forward e o `device` é
    lido DEPOIS dela de propósito — o arming pode ter recriado o vpad (troca de
    máscara pedida pelo perfil do jogo, ainda sem janela e portanto sem o gate
    destrutivo), e despachar no objeto antigo escreveria num fd já fechado.
    """
    _reconciliar_launch(daemon)
    device = daemon._gamepad_device
    if device is None:
        return
    # UDP-TRIGGER-THRESHOLD-01: a deadzone que um mod DSX pediu na porta 6969
    # (`TriggerThreshold`) vale AQUI — na fronteira entre o controle físico e o
    # pad emulado, o mesmo ponto em que o DSX a aplica. Corte seco, sem
    # reescala: abaixo do limiar o jogo lê zero, no limiar em diante o valor
    # bruto passa intacto. 0/0 (o padrão) é passagem direta, byte a byte igual
    # ao que era antes. getattr defensivo: daemon/store de teste sem o campo
    # degradam para "sem deadzone" em vez de derrubar o dispatch.
    limiar_l, limiar_r = getattr(
        getattr(daemon, "store", None), "udp_trigger_thresholds", (0, 0)
    )
    try:
        device.forward_analog(
            lx=state.raw_lx,
            ly=state.raw_ly,
            rx=state.raw_rx,
            ry=state.raw_ry,
            l2=state.l2_raw if state.l2_raw >= limiar_l else 0,
            r2=state.r2_raw if state.r2_raw >= limiar_r else 0,
        )
        device.forward_buttons(buttons_pressed)
        # FEAT-VPAD-FF-PASSTHROUGH-01: drena o FF (rumble do jogo) do vpad e
        # repassa ao controle físico. getattr defensivo: fakes/devices sem
        # pump_ff degradam sem crash.
        pump = getattr(device, "pump_ff", None)
        if pump is not None:
            pump()
    except Exception as exc:
        logger.warning("gamepad_dispatch_failed", err=str(exc))


__all__ = [
    "LAUNCH_RECONCILE_INTERVAL_SEC",
    "REBACKEND_COOLDOWN_SEC",
    "STEAM_INPUT_VIGIA_INTERVAL_SEC",
    "GamepadSubsystem",
    "apply_game_lightbar",
    "apply_game_player_leds",
    "apply_game_rumble",
    "apply_game_trigger",
    "dedup_status",
    "dispatch_gamepad",
    "end_game_output_session",
    "make_primary_replica_sinks",
    "make_primary_rumble_sink",
    "notify_vpad_degradado",
    "read_primary_calibration",
    "rehide_physical_hidraw",
    "resume_vpads_after_steam_input",
    "start_gamepad_emulation",
    "start_motion_reader",
    "steam_input_coop_derrubados",
    "steam_input_excecao_ativa",
    "steam_input_vpad_suspenso",
    "stop_gamepad_emulation",
    "stop_motion_reader",
    "suspend_vpads_for_steam_input",
    "sync_steam_input_exception",
    "upgrade_primary_vpad_to_uhid",
    "vpad_vivo",
]
