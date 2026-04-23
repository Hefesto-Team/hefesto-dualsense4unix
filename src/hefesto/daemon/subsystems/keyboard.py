"""Subsystem Keyboard — emulação de teclado virtual via uinput.

Introduzido em FEAT-KEYBOARD-EMULATOR-01. Encapsula criação, despacho e
destruição do `UinputKeyboardDevice`. Ativado por padrão (não depende de
toggle explícito como `mouse_emulation_enabled`): a instalação do daemon já
espera que os 4 botões default (Options/Share/L1/R1) emitam teclas
correspondentes assim que o serviço sobe.

Wire-up no Daemon (armadilha A-07 — 3 pontos):
  1. Slot `_keyboard_device: Any = None` em `Daemon` (lifecycle.py).
  2. `start_keyboard_emulation(daemon)` chamado em `Daemon.run()` antes de
     `_stop_event.wait()`, quando `config.keyboard_emulation_enabled` for True.
  3. `dispatch_keyboard(daemon, buttons_pressed)` chamado no `_poll_loop`
     reusando o mesmo `buttons_pressed` já obtido via `_evdev_buttons_once()`
     (armadilha A-09 — snapshot único por tick).
  4. `shutdown` em `connection.py` zera o slot e chama `stop()` para liberar
     teclas pressionadas antes do destroy (evita ghost-keys).
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto.daemon.context import DaemonContext
    from hefesto.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)


class KeyboardSubsystem:
    """Subsystem que gerencia a emulação de teclado virtual."""

    name = "keyboard"
    _device: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Cria o dispositivo uinput se keyboard_emulation_enabled=True."""
        cfg = ctx.config
        if not cfg.keyboard_emulation_enabled:
            return
        if self._device is not None:
            return
        try:
            from hefesto.integrations.uinput_keyboard import UinputKeyboardDevice

            device = UinputKeyboardDevice()
        except Exception as exc:
            logger.warning("keyboard_subsystem_import_failed", err=str(exc))
            return
        if not device.start():
            logger.warning("keyboard_subsystem_start_failed")
            return
        self._device = device
        logger.info("keyboard_subsystem_started")

    async def stop(self) -> None:
        """Para e descarta o dispositivo virtual. Idempotente."""
        if self._device is not None:
            with contextlib.suppress(Exception):
                self._device.stop()
            self._device = None
            logger.info("keyboard_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.keyboard_emulation_enabled


def start_keyboard_emulation(daemon: Any) -> bool:
    """Cria device virtual de teclado. Idempotente.

    Retorna True se ativo ao final; False se falhou ao iniciar.
    """
    if getattr(daemon, "_keyboard_device", None) is not None:
        return True
    try:
        from hefesto.integrations.uinput_keyboard import UinputKeyboardDevice

        device = UinputKeyboardDevice()
    except Exception as exc:
        logger.warning("keyboard_emulation_import_failed", err=str(exc))
        return False
    if not device.start():
        logger.warning("keyboard_emulation_start_failed")
        return False
    daemon._keyboard_device = device
    logger.info("keyboard_emulation_started")
    return True


def stop_keyboard_emulation(daemon: Any) -> None:
    """Para e descarta o dispositivo virtual. Idempotente."""
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    with contextlib.suppress(Exception):
        device.stop()
    daemon._keyboard_device = None
    logger.info("keyboard_emulation_stopped")


def dispatch_keyboard(daemon: Any, buttons_pressed: frozenset[str]) -> None:
    """Traduz o set de botões pressionados em eventos de teclado virtual.

    Chamado pelo poll loop a cada tick. Reusa `buttons_pressed` já obtido
    via `_evdev_buttons_once` (armadilha A-09). Não relança exceções —
    falhas são logadas como warning.
    """
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    try:
        device.dispatch(buttons_pressed)
    except Exception as exc:
        logger.warning("keyboard_dispatch_failed", err=str(exc))


__all__ = [
    "KeyboardSubsystem",
    "dispatch_keyboard",
    "start_keyboard_emulation",
    "stop_keyboard_emulation",
]

# "A natureza nada faz em vão." — Aristóteles
