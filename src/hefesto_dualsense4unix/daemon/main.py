"""Entry do daemon: monta dependências e chama `Daemon.run()`."""
from __future__ import annotations

import asyncio
import os
import sys

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig, IpcIndisponivel
from hefesto_dualsense4unix.utils.logging_config import configure_logging, get_logger


def build_controller() -> IController:
    if os.getenv("HEFESTO_DUALSENSE4UNIX_FAKE") == "1":
        from hefesto_dualsense4unix.testing import FakeController

        transport = os.getenv("HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT", "usb")
        if transport not in ("usb", "bt"):
            transport = "usb"
        fc = FakeController(transport=transport)  # type: ignore[arg-type]
        return fc

    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    return PyDualSenseController()


def single_instance_name() -> str:
    """Nome do lock de instância única do daemon, derivado do socket IPC.

    BUG-MULTI-INSTANCE-ISOLATED-SOCKET-01: um daemon com socket ISOLADO (fake via
    `run.sh --fake`, smoke, ou socket custom) NÃO deve brigar pelo mesmo pid-lock
    do daemon de PRODUÇÃO. Antes o lock era sempre "daemon": um fake fazia
    takeover (SIGTERM) do real, o systemd ressuscitava o real, e podiam sobrar
    daemons órfãos disputando o socket (GUI/applet falando com o daemon errado).
    Atando o lock ao socket, cada namespace de socket tem seu próprio
    single-instance: dois daemons de PRODUÇÃO (socket default) ainda se substituem
    corretamente; fake/smoke/custom nunca matam o real.

    BUG-FAKE-SOCKET-SYNC-01: o nome-base vem de `ipc_socket_name()` (fake-aware), a
    MESMA fonte que `ipc_socket_path()`. Assim o lock e o socket derivam do mesmo
    switch de fake — um daemon fake (mesmo iniciado como `daemon start` cru) tem
    socket E lock isolados, e nunca sequestra/mata o daemon de produção.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import (
        IPC_SOCKET_DEFAULT_NAME,
        ipc_socket_name,
    )

    sock = ipc_socket_name()
    if sock == IPC_SOCKET_DEFAULT_NAME:
        return "daemon"
    return "daemon-" + sock.removesuffix(".sock")


def run_daemon(poll_hz: int | None = None) -> int:
    from hefesto_dualsense4unix.utils import sd_notify

    sd_notify.guardar_o_soquete()
    configure_logging()
    logger = get_logger(__name__)

    from hefesto_dualsense4unix.utils import chave

    try:
        motivo = chave.motivo_do_desligamento()
    except chave.PastaIlegivel as exc:
        logger.error("daemon_pasta_ilegivel", pasta=str(exc.pasta), err=str(exc.erro))
        print(exc.recado(), file=sys.stderr)
        return 1
    if motivo is not None:
        logger.warning("daemon_recusado_pela_chave", motivo=motivo)
        print(chave.recado_da_recusa(motivo), file=sys.stderr)
        return 0

    from hefesto_dualsense4unix.utils.migrate_legacy_paths import migrate_legacy_paths

    migrate_legacy_paths()

    from hefesto_dualsense4unix.utils.single_instance import acquire_or_takeover

    acquire_or_takeover(single_instance_name())

    try:
        nice_level = int(os.getenv("HEFESTO_DUALSENSE4UNIX_NICE", "5"))
        if nice_level > 0:
            os.nice(nice_level)
    except (OSError, ValueError):
        logger.warning("daemon_nice_unavailable")

    from hefesto_dualsense4unix.utils import session
    from hefesto_dualsense4unix.utils.maquina import servidor_dsu_declarado

    controller = build_controller()
    servidor_dsu = servidor_dsu_declarado()
    config = DaemonConfig(
        poll_hz=poll_hz or int(os.getenv("HEFESTO_DUALSENSE4UNIX_POLL_HZ", "60")),
        ps_long_press_ms=int(
            os.getenv("HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS", "0")
        ),
        keyboard_emulation_enabled=(
            os.getenv("HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION", "1") != "0"
        ),
        plugins_enabled=session.load_plugins_enabled(),
        metrics_enabled=session.load_metrics_enabled(),
    )
    config.dsu_enabled = servidor_dsu.ligado
    config.dsu_port = servidor_dsu.porta
    daemon = Daemon(controller=controller, config=config)

    logger.info("daemon_main", fake=os.getenv("HEFESTO_DUALSENSE4UNIX_FAKE") == "1")
    from hefesto_dualsense4unix.daemon.subsystems.vigia_do_laco import vigiado

    try:
        asyncio.run(vigiado(daemon.run()))
        return 0
    except IpcIndisponivel as exc:
        print(exc.recado(), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        logger.info("daemon_interrupted")
        return 130


__all__ = ["build_controller", "run_daemon", "single_instance_name"]
