"""Entry do daemon: monta dependências e chama `Daemon.run()`.

Controlado pela CLI (`hefesto-dualsense4unix daemon start`). Suporta backend fake via
env `HEFESTO_DUALSENSE4UNIX_FAKE=1` — útil para smoke tests runtime (meta-regra 9.8)
sem hardware.
"""
from __future__ import annotations

import asyncio
import os

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
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


def run_daemon(poll_hz: int | None = None, auto_reconnect: bool = True) -> int:
    configure_logging()
    logger = get_logger(__name__)

    # CHORE-CONFIG-MIGRATE-LEGACY-SHORT-PATH-01: traz perfis/sessão/prefs do
    # layout curto legado (~/.config/hefesto) para o atual, se necessário.
    # Idempotente e não-destrutivo; roda antes de qualquer leitura de config.
    from hefesto_dualsense4unix.utils.migrate_legacy_paths import migrate_legacy_paths

    migrate_legacy_paths()

    # BUG-MULTI-INSTANCE-01: "última vence" — encerra daemon predecessor
    # (SIGTERM grace 2s, depois SIGKILL) antes de subir. Evita dois daemons
    # disputando /dev/hidraw* e criando uinput duplicado. Ver armadilha A-10.
    from hefesto_dualsense4unix.utils.single_instance import acquire_or_takeover

    acquire_or_takeover(single_instance_name())

    controller = build_controller()
    config = DaemonConfig(
        poll_hz=poll_hz or int(os.getenv("HEFESTO_DUALSENSE4UNIX_POLL_HZ", "60")),
        auto_reconnect=auto_reconnect,
        # FEAT-EMULATION-GAMEMODE-COMBO-01: modo jogo e' so pelo combo PS+Options.
        # Default 0 = long-press DESLIGADO (evita o modo-jogo acidental); quem
        # quiser o gesto seta HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS>0.
        ps_long_press_ms=int(
            os.getenv("HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS", "0")
        ),
    )
    daemon = Daemon(controller=controller, config=config)

    logger.info("daemon_main", fake=os.getenv("HEFESTO_DUALSENSE4UNIX_FAKE") == "1")
    try:
        asyncio.run(daemon.run())
        return 0
    except KeyboardInterrupt:
        logger.info("daemon_interrupted")
        return 130


__all__ = ["build_controller", "run_daemon", "single_instance_name"]
