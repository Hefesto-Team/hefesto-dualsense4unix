"""Funções de conexão, reconexão e shutdown do daemon.

Extrai lógica de ciclo de vida de conexão do IController para funções
puras que recebem o daemon como argumento, mantendo Daemon.run() slim.
"""
from __future__ import annotations

import asyncio
import contextlib
import os

from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch
from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


#: Teto do backoff exponencial em segundos. Evita espera unbounded entre tentativas.
BACKOFF_MAX_SEC: float = 30.0

#: Intervalo entre probes de hot-reconnect quando o controle está desconectado
#: (BUG-DAEMON-NO-DEVICE-FATAL-01). 5s é compromisso entre latência percebida
#: pelo usuário ao plugar o controle e custo (varredura libusb + log).
RECONNECT_PROBE_INTERVAL_SEC: float = 5.0

#: Intervalo entre probes de "ainda conectado?" quando o controle está online.
#: Múltiplo do probe offline para evitar overhead — o poll_loop já detecta
#: desconexão via exceção em read_state e dispara reconnect a parte.
RECONNECT_ONLINE_CHECK_INTERVAL_SEC: float = 30.0

#: Fatia curta do sleep ONLINE do reconnect_loop (FEAT-BACKEND-HOTPLUG-FAST-01).
#: A cada fatia consultamos o `InputDirWatch` (um `os.listdir` de /dev/input,
#: ~µs — custo zero quando nada muda) e SÓ quando o conjunto de nodes mudou
#: antecipamos a reconciliação (`controller.connect()` via executor — o
#: hid_enumerate custa dezenas de ms e NUNCA roda por fatia). Plugar um
#: DualSense novo passa de "até 30s" para ~2s até o backend abrir o handle
#: (describe_controllers/LED/rumble/trigger + throttle adaptativo recalculado).
RECONNECT_HOTPLUG_POLL_INTERVAL_SEC: float = 2.0


async def connect_with_retry(daemon: DaemonProtocol) -> None:
    """Tenta conectar o controller com backoff exponencial. Publica CONTROLLER_CONNECTED.

    AUDIT-FINDING-LOG-EXC-INFO-01:
      - `logger.warning("controller_connect_failed", ..., exc_info=True)` preserva
        traceback completo no log para debug. Só executa no ramo de falha.
      - Backoff dobra após cada falha (`backoff = min(backoff * 2, BACKOFF_MAX_SEC)`).
        Evita hot-loop consumindo CPU se hardware indisponível por período longo.
      - Sleep interrompível via `asyncio.wait_for(stop_event.wait(), ...)`: shutdown
        não precisa esperar o backoff atual terminar. Só ativa se há stop_event
        configurado (via Daemon.run) e no ramo de falha — caminho feliz preserva
        exato comportamento anterior para testes com FakeController.
    """
    backoff = daemon.config.reconnect_backoff_sec
    while True:
        try:
            await daemon._run_blocking(daemon.controller.connect)
            transport = daemon.controller.get_transport()
            daemon.bus.publish(EventTopic.CONTROLLER_CONNECTED, {"transport": transport})
            logger.info("controller_connected", transport=transport)
            return
        except Exception as exc:
            logger.warning("controller_connect_failed", err=str(exc), exc_info=True)
            if not daemon.config.auto_reconnect:
                raise
            stop_event = getattr(daemon, "_stop_event", None)
            if stop_event is not None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=backoff)
                    return  # stop_event sinalizou durante o backoff — aborta.
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(backoff)
            # Backoff exponencial com teto.
            backoff = min(backoff * 2, BACKOFF_MAX_SEC)


async def restore_last_profile(daemon: DaemonProtocol) -> None:
    """Reativa o último perfil salvo pelo usuário (FEAT-PERSIST-SESSION-01).

    PERFIL-03: o nome vem de `resolve_boot_profile` — session.json (canônico,
    manual-only pós-fix) com o seed de migração do `active_profile.txt`
    (quando divergem, o marker carrega a intenção manual herdada de versões
    em que o autoswitch clobberava o session.json). A ativação vai com
    `origin="system"`: restore de boot não é gesto novo da usuária e NÃO
    regrava a intenção manual.

    Fix do review (2026-07-16, MED): o marker vence na divergência SEM
    verificar se o perfil ainda carrega — um marker órfão (perfil renomeado/
    apagado/corrompido) suprimia o restore INTEIRO em todo boot, mesmo com o
    session.json apontando um perfil carregável. Quando a ativação do nome
    resolvido falha, tentamos o session.json como fallback, com o log
    `last_profile_seed_marker_invalido` (recusa do marker ≠ boot sem perfil).
    """
    from functools import partial

    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.utils.session import (
        load_last_profile,
        resolve_boot_profile,
    )

    name = resolve_boot_profile()
    if not name:
        return
    # FEAT-NATIVE-MODE-01: em Modo Nativo o controle fica SOLTO para o jogo — não
    # re-aplica o perfil (que re-escreveria gatilhos/emulação por cima).
    if getattr(daemon, "_native_mode", False):
        logger.info("last_profile_restore_skipped_native_mode", name=name)
        return
    # FEAT-POINT-AND-CLICK-01 (fix A-06/A8): provider lazy + appliers — o
    # restore pode rodar antes/depois do keyboard subir e após reconexão
    # (device recriado); resolver na ativação cobre todos os casos.
    #
    # BUG-BOOT-RESTORE-FLIPS-EMULATION-01: mouse_applier=None no restore de
    # propósito. O estado de emulação (mouse/gamepad) no boot é governado
    # pelos FLAGS persistidos (lifecycle.py restaura antes desta chamada),
    # não pela seção mouse do perfil. Com o applier injetado, um last_profile
    # com mouse.enabled (ex.: point_and_click, que vira last_profile por mero
    # autoswitch) rodava set_mouse_emulation(True) DEPOIS do gamepad já
    # restaurado — matava o gamepad, apagava gamepad_emulation.flag e invertia
    # a escolha persistida da usuária a cada boot. O perfil ainda aplica
    # triggers/LEDs/teclado; só a emulação fica com os flags.
    manager = ProfileManager(
        controller=daemon.controller,
        store=daemon.store,
        keyboard_device_provider=lambda: getattr(
            daemon, "_keyboard_device", None
        ),
        mouse_applier=None,
        suppression_applier=getattr(daemon, "apply_profile_suppression", None),
        # FEAT-PROFILE-MODE-01: mode_applier=None no restore pela MESMA
        # razão do mouse — gamepad/nativo/co-op no boot vêm dos flags
        # persistidos (utils.session), não do perfil.
        mode_applier=None,
        # FEAT-RUMBLE-POLICY-PROFILE-01: aqui o applier VAI injetado —
        # diferente de mouse/mode, a política de rumble NÃO tem flag
        # persistido próprio (reseta a "balanceado" a cada boot), então o
        # perfil é a única fonte para restaurá-la; aplicá-la só ajusta a
        # config (não cria/destrói devices — sem o risco do
        # BUG-BOOT-RESTORE-FLIPS-EMULATION-01).
        rumble_policy_applier=getattr(
            daemon, "apply_profile_rumble_policy", None
        ),
        rumble_passthrough_applier=getattr(
            daemon, "apply_profile_rumble_passthrough", None
        ),
    )
    try:
        await daemon._run_blocking(
            partial(manager.activate, name, origin="system")
        )
        logger.info("last_profile_restored", name=name)
    except Exception as exc:
        # Sem `exc_info=True`: este warning dispara normalmente quando o perfil
        # persistido na sessão foi deletado/renomeado — err=str(exc) já dá o
        # diagnóstico; traceback completo seria ruído e atrasaria o boot.
        logger.warning("last_profile_restore_failed", name=name, err=str(exc))
        # Fix do review (2026-07-16, MED): o nome resolvido pode ter vindo do
        # marker (que vence na divergência) e o marker pode estar órfão —
        # cair no session.json preserva o restore em vez de deixar o boot
        # sem perfil nenhum.
        fallback = load_last_profile()
        if not fallback or fallback == name:
            return
        logger.info(
            "last_profile_seed_marker_invalido", marker=name, fallback=fallback
        )
        try:
            await daemon._run_blocking(
                partial(manager.activate, fallback, origin="system")
            )
            logger.info("last_profile_restored", name=fallback)
        except Exception as exc2:
            logger.warning(
                "last_profile_restore_failed", name=fallback, err=str(exc2)
            )


def _broker_restore_for_recovery(daemon: DaemonProtocol) -> list[str]:
    """Restaura hidraws escondidos pelo broker cujo nó AINDA EXISTE no disco.

    S-2 (auditoria 21/07, viola "duplicado > zero controles"): o backend
    pydualsense reabre por CAMINHO (hidapi não abre por fd) — se um handle
    morreu sem re-enumeração do nó (EIO transitório, hiccup USB), o reopen
    encontra o nó ainda 0600 do hide e leva PermissionError para TODOS os
    controles, em backoff eterno (a lease está viva, o rehide só re-esconde e
    ninguém restaurava). Este helper roda SÓ no caminho de recuperação: expõe
    o físico pelo tempo de um reconnect (o rehide da reconciliação online
    re-esconde) — duplicado transitório > zero controles, que é lei. Nó
    escondido que NÃO existe mais (unplug real) é pulado: restaurar seria
    no-op barulhento a cada probe de 5s. Best-effort como todo o cliente.
    """
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        broker_client_for,
    )

    client = broker_client_for(daemon)
    response = client.status()
    hidden = response.get("hidden") if isinstance(response, dict) else None
    restored: list[str] = []
    for node in hidden or []:
        if not isinstance(node, str) or not os.path.exists(node):
            continue
        if client.restore(node):
            restored.append(node)
    return restored


async def _restore_hidden_before_reopen(daemon: DaemonProtocol) -> None:
    """Agenda o `_broker_restore_for_recovery` no executor DEDICADO do broker.

    Mesma disciplina do rehide (HANG-01): I/O de socket com timeout de 2s por
    chamada nunca roda no event loop nem no pool compartilhado 'hefesto-hid'.
    Falha nunca derruba o caminho de reconexão (best-effort).
    """
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_executor_for,
        )

        restored = await asyncio.get_running_loop().run_in_executor(
            broker_executor_for(daemon), _broker_restore_for_recovery, daemon
        )
        if restored:
            logger.info("hidraw_broker_restore_recovery", nodes=restored)


async def reconnect(daemon: DaemonProtocol) -> None:
    """Desconecta e tenta reconectar com backoff."""
    with contextlib.suppress(Exception):
        await daemon._run_blocking(daemon.controller.disconnect)
    await asyncio.sleep(daemon.config.reconnect_backoff_sec)
    # S-2: handles fechados; se algum nó físico segue escondido pelo broker,
    # o reopen por caminho falharia com PermissionError para TODOS — restaura
    # antes (o rehide pós-reconexão re-esconde).
    await _restore_hidden_before_reopen(daemon)
    await connect_with_retry(daemon)
    # BUG-DAEMON-CONNECT-GHOST-INPUT-01: rearma o settling assim que
    # reconectamos. Cobre a janela em que o poll loop chama reconnect()
    # diretamente (read_state levantou) e volta a ler estado no próximo tick
    # — o estado inicial pós-replug (HID-raw cru + snapshot evdev populando)
    # não deve gerar mute/teclas fantasma.
    daemon._arm_input_grace()


async def reconnect_loop(
    daemon: DaemonProtocol, *, input_watch: InputDirWatch | None = None
) -> None:
    """Probe não-bloqueante de conexão com o DualSense (BUG-DAEMON-NO-DEVICE-FATAL-01).

    Diferente de `connect_with_retry` (legado, bloqueante e reusado pela CLI):
      - Nunca bloqueia o boot — `Daemon.run()` cria esta task em background.
      - Respeita `daemon._stop_event` durante todos os waits.
      - Loga transições offline→online e online→offline em INFO; tentativas
        falhadas em DEBUG (evita inundar journal a cada 5s).
      - Restaura último perfil exatamente uma vez na primeira conexão bem-sucedida.

    O loop coopera com o poll_loop: quando `read_state` levanta após perda de
    conexão, o poll loop dispara `reconnect()` (legado) e o probe deste loop
    detectará a transição back-online no próximo tick.

    FEAT-BACKEND-HOTPLUG-FAST-01: quando ONLINE, o sleep de 30s é fatiado em
    `RECONNECT_HOTPLUG_POLL_INTERVAL_SEC` consultando um `InputDirWatch`
    (mudança em /dev/input = hotplug/unplug de controle). Mudou → reconcilia já
    (`controller.connect()` no executor); sem mudança, o custo por fatia é um
    listdir (~µs) e o check de 30s permanece como fallback. Reentrância segura:
    `connect()` é idempotente e tem a guarda `_opening` sob `_io_lock` no
    backend — um `reconnect()` concorrente do poll loop não duplica abertura.
    `input_watch` é injetável para testes; None cria o watch real.
    """
    from hefesto_dualsense4unix.daemon.connection import (
        restore_last_profile as _restore_last_profile,
    )

    watch = input_watch if input_watch is not None else InputDirWatch()
    # Baseline do watch: a 1ª chamada de poll() devolve True por construção
    # (não havia snapshot anterior). Consumimos aqui para que só mudança REAL
    # de /dev/input dispare reconciliação antecipada — o connect() do boot já
    # cobriu o estado inicial.
    watch.poll()

    # Se o boot já conectou e restaurou o perfil, não re-publica
    # CONTROLLER_CONNECTED nem reaplica o perfil — apenas monitora transições.
    initial_connected = bool(daemon.controller.is_connected())
    restored = initial_connected
    was_connected = initial_connected
    while not daemon._is_stopping():
        try:
            await daemon._run_blocking(daemon.controller.connect)
        except Exception as exc:
            # Backend real só levanta para erros não-"No device detected"
            # (permissão hidraw, USB transitório). Loga em DEBUG para não
            # poluir; próxima iteração tenta de novo.
            logger.debug("reconnect_probe_failed", err=str(exc), exc_info=True)
            # S-2: a classe "permissão hidraw" inclui o nó AINDA ESCONDIDO
            # pelo broker após um handle morrer sem re-enumeração — sem o
            # restore aqui o probe falharia para sempre (zero controles).
            await _restore_hidden_before_reopen(daemon)
            await _wait_or_stop(daemon, RECONNECT_PROBE_INTERVAL_SEC)
            continue

        is_connected = bool(daemon.controller.is_connected())
        if is_connected and not was_connected:
            # BUG-DAEMON-CONNECT-GHOST-INPUT-01: transição offline→online
            # detectada pelo probe. Rearma o settling antes de qualquer outra
            # coisa para que o poll loop suprima o input emulado do estado
            # inicial cru (mute fantasma + teclas aleatórias). O poll loop
            # também arma o grace na própria borda; aqui cobrimos o caso em
            # que o probe chega primeiro / reconecta sem o loop ver offline.
            daemon._arm_input_grace()
            transport = daemon.controller.get_transport()
            daemon.bus.publish(
                EventTopic.CONTROLLER_CONNECTED, {"transport": transport}
            )
            logger.info("controller_connected", transport=transport)
            # VPAD-01: hotplug tardio promove o vpad degradado — espelha o
            # gancho do boot (`lifecycle.run`). Antes, o único caller era o
            # connect inicial: quem ligasse o controle DEPOIS do boot ficava
            # com o vpad uinput até reiniciar o daemon. Roda no executor
            # (`_run_blocking`): este loop divide o event loop com o poll
            # loop e a promoção é síncrona (pior caso ~0,5 s no
            # `UHID_BIND_TIMEOUT_S`) — bloquear aqui congelaria o input. O
            # `_emu_lock` (RLock) serializa com set_gamepad_emulation/
            # set_mouse_emulation das outras superfícies (IPC/GUI/hotkey);
            # os gates internos do upgrade (já-uhid, precheck
            # `uhid_available()`, cooldown compartilhado com o VPAD-02)
            # garantem zero churn nas reconexões normais.
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    upgrade_primary_vpad_to_uhid,
                )

                def _promover_vpad() -> bool:
                    with getattr(daemon, "_emu_lock", contextlib.nullcontext()):
                        return upgrade_primary_vpad_to_uhid(daemon)

                await daemon._run_blocking(_promover_vpad)
            # FEAT-COSMIC-NOTIFICATIONS-01: opt-in via env var.
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.integrations.desktop_notifications import (
                    notify_controller_connected,
                )
                notify_controller_connected(transport or "usb")
            if not restored:
                with contextlib.suppress(Exception):
                    await _restore_last_profile(daemon)
                restored = True
            was_connected = True
        elif not is_connected and was_connected:
            # Transição online→offline detectada pelo probe (poll_loop também
            # pode detectar via exceção em read_state e disparar reconnect()
            # legado; logamos aqui só se chegamos primeiro).
            daemon.bus.publish(
                EventTopic.CONTROLLER_DISCONNECTED, {"reason": "probe_offline"}
            )
            logger.info("controller_disconnected", reason="probe_offline")
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.integrations.desktop_notifications import (
                    notify_controller_disconnected,
                )
                notify_controller_disconnected("probe offline")
            was_connected = False

        if is_connected:
            # BROKER-01 §2.2: re-hide do físico a cada reconciliação online —
            # nó recriado pelo replug/wake BT nasce VISÍVEL (rule 70/uaccess do
            # udev) e é re-escondido aqui (o broker re-aplica o fs mesmo para
            # nó já rastreado, lição 2). Corretor final (interação S x HANG-01,
            # achado #6): no executor DEDICADO do broker ('hefesto-broker',
            # 1 worker FIFO), NUNCA no pool compartilhado 'hefesto-hid' de
            # `_run_blocking` — o cliente do broker faz I/O de socket com
            # timeout de 2 s por chamada (até ~8s com 4 nós de co-op e broker
            # degradado), e ocupar 1 dos 2 workers de 'hefesto-hid' enfileira
            # read_state/_gather_game_signal_inputs/heal atrás dele (o padrão
            # que o HANG-01 baniu ao isolar `_sync_external_leds`). O await
            # preserva o backpressure: um broker travado atrasa só ESTE loop,
            # sem acumular rehides na fila. Best-effort: falha nunca derruba
            # o probe.
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    rehide_physical_hidraw,
                )
                from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                    broker_executor_for,
                )

                await asyncio.get_running_loop().run_in_executor(
                    broker_executor_for(daemon), rehide_physical_hidraw, daemon
                )
            # FEAT-BACKEND-HOTPLUG-FAST-01: online, espera em fatias curtas
            # observando /dev/input — hotplug antecipa a reconciliação (o
            # connect() da próxima iteração) sem esperar o fallback de 30s.
            if await _wait_online_or_hotplug(daemon, watch):
                logger.info(
                    "backend_hotplug_reconcile", trigger="input_dir_change"
                )
        else:
            # Offline o probe já é curto (5s) e cada iteração reconcilia —
            # o watch não acrescentaria nada aqui.
            await _wait_or_stop(daemon, RECONNECT_PROBE_INTERVAL_SEC)


async def _wait_online_or_hotplug(
    daemon: DaemonProtocol, watch: InputDirWatch
) -> bool:
    """Espera o intervalo online em fatias, sondando o watch de /dev/input.

    FEAT-BACKEND-HOTPLUG-FAST-01: dorme `RECONNECT_HOTPLUG_POLL_INTERVAL_SEC`
    por fatia (respeitando `_stop_event`) e consulta `watch.poll()` entre elas
    (listdir ~µs — custo zero quando nada muda). Retorna:
      - True  → /dev/input mudou (controle plugado/removido); o chamador deve
                reconciliar imediatamente;
      - False → o fallback `RECONNECT_ONLINE_CHECK_INTERVAL_SEC` expirou sem
                mudança (reconciliação periódica normal) ou o daemon está
                parando.
    """
    elapsed = 0.0
    while elapsed < RECONNECT_ONLINE_CHECK_INTERVAL_SEC:
        step = min(
            RECONNECT_HOTPLUG_POLL_INTERVAL_SEC,
            RECONNECT_ONLINE_CHECK_INTERVAL_SEC - elapsed,
        )
        await _wait_or_stop(daemon, step)
        if daemon._is_stopping():
            return False
        elapsed += step
        if watch.poll():
            return True
    return False


async def _wait_or_stop(daemon: DaemonProtocol, timeout: float) -> None:
    """Dorme `timeout` segundos respeitando `_stop_event`.

    Retorna logo se o stop_event for sinalizado durante a espera. Não levanta
    em timeout — só interrompe o sleep.
    """
    stop_event = getattr(daemon, "_stop_event", None)
    if stop_event is None:
        await asyncio.sleep(timeout)
        return
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)


async def shutdown(daemon: DaemonProtocol) -> None:
    """Encerra todos os recursos do daemon de forma limpa."""
    logger.info("daemon_shutting_down")
    # Plugins: stop antes dos outros subsystems (on_unload pode usar controller).
    if daemon._plugins_subsystem is not None:
        with contextlib.suppress(Exception):
            await daemon._plugins_subsystem.stop()
        daemon._plugins_subsystem = None
    daemon._hotkey_manager = None
    daemon._audio = None
    # FEAT-DSX-COOP-LOCAL-01: desmonta os jogadores secundários (solta o grab e
    # fecha os uinput) — senão os controles secundários ficariam "sequestrados".
    if getattr(daemon, "_coop_manager", None) is not None:
        with contextlib.suppress(Exception):
            daemon._coop_manager.stop_all()
        daemon._coop_manager = None
    if daemon._mouse_device is not None:
        with contextlib.suppress(Exception):
            daemon._mouse_device.stop()
        daemon._mouse_device = None
    # FEAT-DSX-GAMEPAD-FLAVOR-01: para o gamepad virtual e LIBERA o grab do
    # controle físico (senão o controle ficaria "sequestrado" após o shutdown).
    if getattr(daemon, "_gamepad_device", None) is not None:
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                stop_gamepad_emulation,
            )

            stop_gamepad_emulation(daemon, persist=False)
    # Achados Onda S #5/#6/#10: desliga o executor dedicado do broker ANTES do
    # close da lease — operações ainda na fila (o restore_all que o stop acima
    # agendou, hides atrasados) são canceladas: o EOF do close abaixo restaura
    # TUDO de uma vez, e um hide tardio pós-close reabriria uma lease órfã.
    broker_executor = getattr(daemon, "_hidraw_broker_executor", None)
    if broker_executor is not None:
        with contextlib.suppress(Exception):
            broker_executor.shutdown(wait=False, cancel_futures=True)
        daemon._hidraw_broker_executor = None
    # BROKER-01: fecha a lease do broker explicitamente (belt) — o
    # `stop_gamepad_emulation` acima já pediu restore_all; o close derruba a
    # conexão AGORA (EOF imediato ⇒ o broker restaura o que restou) sem
    # esperar o kernel varrer os fds do processo. Morte suja (SIGKILL/OOM)
    # segue coberta pelo EOF automático.
    client = getattr(daemon, "_hidraw_broker_client", None)
    if client is not None:
        with contextlib.suppress(Exception):
            client.close()
        daemon._hidraw_broker_client = None
    if getattr(daemon, "_keyboard_device", None) is not None:
        with contextlib.suppress(Exception):
            daemon._keyboard_device.stop()
        daemon._keyboard_device = None
    # FEAT-DAEMON-GRACEFUL-SHUTDOWN-01: fecha IPC/UDP com timeout — um stop() que
    # trave (ex.: cliente em voo) não pode pendurar o shutdown indefinidamente.
    if daemon._ipc_server is not None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(daemon._ipc_server.stop(), timeout=2.0)
        daemon._ipc_server = None
    if daemon._udp_server is not None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(daemon._udp_server.stop(), timeout=2.0)
        daemon._udp_server = None
    if daemon._autoswitch is not None:
        with contextlib.suppress(Exception):
            daemon._autoswitch.stop()
        daemon._autoswitch = None
    # CLUSTER-IPC-STATE-PROFILE-01 (Bug A): limpa cache de último state.
    daemon._last_state = None
    for task in daemon._tasks:
        task.cancel()
    for task in daemon._tasks:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    # BUG-DAEMON-NO-DEVICE-FATAL-01: reconnect_task é parte de `_tasks`,
    # já cancelada acima — só zera a referência nomeada.
    daemon._reconnect_task = None
    try:
        await daemon._run_blocking(daemon.controller.disconnect)
    except Exception as exc:
        logger.warning("controller_disconnect_failed", err=str(exc))
    if daemon._executor is not None:
        daemon._executor.shutdown(wait=False, cancel_futures=True)
        daemon._executor = None
    # HANG-01: pool DEDICADO do tick de externos (isolado de `_executor`
    # desde a correção pós-auditoria 20/07) — mesmo trade-off de shutdown
    # não-bloqueante (uma thread wedged não impede o processo de encerrar).
    if daemon._external_executor is not None:
        daemon._external_executor.shutdown(wait=False, cancel_futures=True)
        daemon._external_executor = None
    daemon._tasks.clear()
    logger.info("daemon_stopped")


__all__ = [
    "BACKOFF_MAX_SEC",
    "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC",
    "RECONNECT_ONLINE_CHECK_INTERVAL_SEC",
    "RECONNECT_PROBE_INTERVAL_SEC",
    "connect_with_retry",
    "reconnect",
    "reconnect_loop",
    "restore_last_profile",
    "shutdown",
]
