"""Funções de conexão, reconexão e shutdown do daemon.

Extrai lógica de ciclo de vida de conexão do IController para funções
puras que recebem o daemon como argumento, mantendo Daemon.run() slim.
"""
from __future__ import annotations

import asyncio
import contextlib

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
    """Reativa o último perfil salvo pelo usuário (FEAT-PERSIST-SESSION-01)."""
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.utils.session import load_last_profile

    name = load_last_profile()
    if not name:
        return
    try:
        manager = ProfileManager(
            controller=daemon.controller,
            store=daemon.store,
            keyboard_device=getattr(daemon, "_keyboard_device", None),
        )
        await daemon._run_blocking(manager.activate, name)
        logger.info("last_profile_restored", name=name)
    except Exception as exc:
        # Sem `exc_info=True`: este warning dispara normalmente quando o perfil
        # persistido na sessão foi deletado/renomeado — err=str(exc) já dá o
        # diagnóstico; traceback completo seria ruído e atrasaria o boot.
        logger.warning("last_profile_restore_failed", name=name, err=str(exc))


async def reconnect(daemon: DaemonProtocol) -> None:
    """Desconecta e tenta reconectar com backoff."""
    with contextlib.suppress(Exception):
        await daemon._run_blocking(daemon.controller.disconnect)
    await asyncio.sleep(daemon.config.reconnect_backoff_sec)
    await connect_with_retry(daemon)
    # BUG-DAEMON-CONNECT-GHOST-INPUT-01: rearma o settling assim que
    # reconectamos. Cobre a janela em que o poll loop chama reconnect()
    # diretamente (read_state levantou) e volta a ler estado no próximo tick
    # — o estado inicial pós-replug (HID-raw cru + snapshot evdev populando)
    # não deve gerar mute/teclas fantasma.
    daemon._arm_input_grace()


async def reconnect_loop(daemon: DaemonProtocol) -> None:
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
    """
    from hefesto_dualsense4unix.daemon.connection import (
        restore_last_profile as _restore_last_profile,
    )

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

        # Quando online, dorme intervalo maior; quando offline, dorme curto.
        timeout = (
            RECONNECT_ONLINE_CHECK_INTERVAL_SEC
            if is_connected
            else RECONNECT_PROBE_INTERVAL_SEC
        )
        await _wait_or_stop(daemon, timeout)


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
    daemon._tasks.clear()
    logger.info("daemon_stopped")


__all__ = [
    "BACKOFF_MAX_SEC",
    "RECONNECT_ONLINE_CHECK_INTERVAL_SEC",
    "RECONNECT_PROBE_INTERVAL_SEC",
    "connect_with_retry",
    "reconnect",
    "reconnect_loop",
    "restore_last_profile",
    "shutdown",
]
