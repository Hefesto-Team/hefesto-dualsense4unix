"""Subsystem Mouse — emulação de mouse+teclado virtual via uinput.

Encapsula a criação, despacho e destruição do dispositivo virtual UinputMouseDevice.
Implementa o protocolo Subsystem e expõe funções utilitárias start_mouse / stop_mouse.

O despacho de eventos (dispatch_mouse) é chamado pelo poll loop a cada tick.
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto.daemon.context import DaemonContext
    from hefesto.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)


class MouseSubsystem:
    """Subsystem que gerencia a emulação de mouse virtual."""

    name = "mouse"
    _device: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Cria o dispositivo uinput se mouse_emulation_enabled=True.

        Idempotente: retorna sem erro se o dispositivo já existe.
        """
        cfg = ctx.config
        if not cfg.mouse_emulation_enabled:
            return
        if self._device is not None:
            return
        try:
            from hefesto.integrations.uinput_mouse import UinputMouseDevice

            device = UinputMouseDevice(
                mouse_speed=cfg.mouse_speed,
                scroll_speed=cfg.mouse_scroll_speed,
            )
        except Exception as exc:
            logger.warning("mouse_subsystem_import_failed", err=str(exc))
            return
        if not device.start():
            logger.warning("mouse_subsystem_start_failed")
            return
        self._device = device
        logger.info(
            "mouse_subsystem_started",
            speed=cfg.mouse_speed,
            scroll_speed=cfg.mouse_scroll_speed,
        )

    async def stop(self) -> None:
        """Para e descarta o dispositivo virtual. Idempotente."""
        if self._device is not None:
            with contextlib.suppress(Exception):
                self._device.stop()
            self._device = None
            logger.info("mouse_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.mouse_emulation_enabled


def start_mouse_emulation(daemon: Any) -> bool:
    """Cria device virtual de mouse+teclado (FEAT-MOUSE-01). Idempotente.

    Retorna True se ativo ao final; False se falhou ao iniciar.
    """
    if daemon._mouse_device is not None:
        return True
    try:
        from hefesto.integrations.uinput_mouse import UinputMouseDevice

        device = UinputMouseDevice(
            mouse_speed=daemon.config.mouse_speed,
            scroll_speed=daemon.config.mouse_scroll_speed,
        )
    except Exception as exc:
        logger.warning("mouse_emulation_import_failed", err=str(exc))
        return False
    if not device.start():
        logger.warning("mouse_emulation_start_failed")
        return False
    daemon._mouse_device = device
    daemon.config.mouse_emulation_enabled = True
    logger.info(
        "mouse_emulation_started",
        speed=daemon.config.mouse_speed,
        scroll_speed=daemon.config.mouse_scroll_speed,
    )
    return True


def stop_mouse_emulation(daemon: Any) -> None:
    """Para e descarta o dispositivo virtual. Idempotente."""
    if daemon._mouse_device is None:
        return
    with contextlib.suppress(Exception):
        daemon._mouse_device.stop()
    daemon._mouse_device = None
    daemon.config.mouse_emulation_enabled = False
    logger.info("mouse_emulation_stopped")


def dispatch_mouse(daemon: Any, state: Any, buttons_pressed: frozenset[str]) -> None:
    """Traduz o estado do controle em eventos de mouse+teclado virtual.

    Chamado pelo poll loop a cada tick se _mouse_device não for None.
    Não relança exceções — falhas são logadas como warning.
    """
    device = daemon._mouse_device
    if device is None:
        return
    try:
        device.dispatch(
            lx=state.raw_lx,
            ly=state.raw_ly,
            rx=state.raw_rx,
            ry=state.raw_ry,
            l2=state.l2_raw,
            r2=state.r2_raw,
            buttons=buttons_pressed,
        )
    except Exception as exc:
        logger.warning("mouse_dispatch_failed", err=str(exc))


__all__ = [
    "MouseSubsystem",
    "dispatch_mouse",
    "start_mouse_emulation",
    "stop_mouse_emulation",
]
