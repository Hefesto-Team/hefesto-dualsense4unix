"""Entry do daemon: monta dependências e chama `Daemon.run()`.

Controlado pela CLI (`hefesto daemon start`). Suporta backend fake via
env `HEFESTO_FAKE=1` — útil para smoke tests runtime (meta-regra 9.8)
sem hardware.
"""
from __future__ import annotations

import asyncio
import os

from hefesto.core.controller import IController
from hefesto.daemon.lifecycle import Daemon, DaemonConfig
from hefesto.utils.logging_config import configure_logging, get_logger


def build_controller() -> IController:
    if os.getenv("HEFESTO_FAKE") == "1":
        from hefesto.testing import FakeController

        transport = os.getenv("HEFESTO_FAKE_TRANSPORT", "usb")
        if transport not in ("usb", "bt"):
            transport = "usb"
        fc = FakeController(transport=transport)  # type: ignore[arg-type]
        return fc

    from hefesto.core.backend_pydualsense import PyDualSenseController

    return PyDualSenseController()


def run_daemon(poll_hz: int | None = None, auto_reconnect: bool = True) -> int:
    configure_logging()
    logger = get_logger(__name__)

    # BUG-MULTI-INSTANCE-01: "última vence" — encerra daemon predecessor
    # (SIGTERM grace 2s, depois SIGKILL) antes de subir. Evita dois daemons
    # disputando /dev/hidraw* e criando uinput duplicado. Ver armadilha A-10.
    from hefesto.utils.single_instance import acquire_or_takeover

    acquire_or_takeover("daemon")

    controller = build_controller()
    config = DaemonConfig(
        poll_hz=poll_hz or int(os.getenv("HEFESTO_POLL_HZ", "60")),
        auto_reconnect=auto_reconnect,
    )
    daemon = Daemon(controller=controller, config=config)

    logger.info("daemon_main", fake=os.getenv("HEFESTO_FAKE") == "1")
    try:
        asyncio.run(daemon.run())
        return 0
    except KeyboardInterrupt:
        logger.info("daemon_interrupted")
        return 130


__all__ = ["build_controller", "run_daemon"]
