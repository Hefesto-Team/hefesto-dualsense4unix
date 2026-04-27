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
import os
import shutil
import subprocess
from typing import Any

from hefesto_dualsense4unix.core.keyboard_mappings import TOKEN_CLOSE_OSK, TOKEN_OPEN_OSK
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Candidatos de teclado virtual em ordem de preferência. Testados na 1ª vez que
# OSK é solicitado. Cada string aqui é um `shutil.which`-ável; o argv completo
# para spawn fica em `_OSK_SPAWN_ARGS`.
_OSK_CANDIDATES: tuple[str, ...] = ("onboard", "wvkbd-mobintl")
_OSK_SPAWN_ARGS: dict[str, list[str]] = {
    "onboard": ["onboard"],
    # `--layer 0` ancora wvkbd no bottom (padrão); mantém footprint mínimo.
    "wvkbd-mobintl": ["wvkbd-mobintl"],
}


class _OSKController:
    """Gerencia o processo do teclado virtual (onboard/wvkbd-mobintl).

    Detecta o binário disponível apenas 1x (cache em `_resolved_bin`); warning
    é logado uma única vez se nenhum dos candidatos estiver instalado. Abrir
    quando já há processo ativo é no-op (evita stack de janelas sobrepostas).
    Fechar sem processo ativo também é no-op.
    """

    def __init__(self) -> None:
        self._resolved_bin: str | None = None
        self._resolved_checked: bool = False
        self._process: subprocess.Popen[bytes] | None = None
        self._missing_warned: bool = False

    def _resolve(self) -> str | None:
        if self._resolved_checked:
            return self._resolved_bin
        for candidate in _OSK_CANDIDATES:
            path = shutil.which(candidate)
            if path:
                self._resolved_bin = candidate
                self._resolved_checked = True
                return candidate
        self._resolved_bin = None
        self._resolved_checked = True
        return None

    def open(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        resolved = self._resolve()
        if resolved is None:
            if not self._missing_warned:
                logger.warning(
                    "osk_binary_missing",
                    candidates=list(_OSK_CANDIDATES),
                )
                self._missing_warned = True
            return
        args = _OSK_SPAWN_ARGS[resolved]
        try:
            self._process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("osk_opened", binary=resolved, pid=self._process.pid)
        except Exception as exc:
            logger.warning("osk_open_failed", binary=resolved, err=str(exc))
            self._process = None

    def close(self) -> None:
        proc = self._process
        if proc is None:
            return
        if proc.poll() is not None:
            self._process = None
            return
        try:
            proc.terminate()
            logger.info("osk_closed", pid=proc.pid)
        except Exception as exc:
            logger.warning("osk_close_failed", err=str(exc))
        self._process = None

    def dispatch_token(self, token: str, phase: str) -> None:
        """Callback registrado no UinputKeyboardDevice.

        Só atua em press (edge-triggered pull-to-focus). Release é no-op para
        evitar fechar no release de L3 logo após o press abrir.
        """
        if phase != "press":
            return
        if token == TOKEN_OPEN_OSK:
            self.open()
        elif token == TOKEN_CLOSE_OSK:
            self.close()
        else:
            logger.warning("osk_token_desconhecido", token=token)


def start_keyboard_emulation(daemon: Any) -> bool:
    """Cria device virtual de teclado + touchpad reader. Idempotente.

    Retorna True se ativo ao final; False se falhou ao iniciar o device
    principal. O `TouchpadReader` é best-effort: se o device evdev do
    touchpad não existir (controle BT, kernel velho), não quebra o fluxo.
    """
    if getattr(daemon, "_keyboard_device", None) is not None:
        return True
    try:
        from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice

        device = UinputKeyboardDevice()
    except Exception as exc:
        logger.warning("keyboard_emulation_import_failed", err=str(exc))
        return False
    # OSK controller vive 1x por daemon; callback é registrado na inicialização
    # para que L3/R3 já funcionem antes do primeiro switch de perfil.
    osk = getattr(daemon, "_osk_controller", None)
    if osk is None:
        osk = _OSKController()
        daemon._osk_controller = osk
    device.virtual_token_callback = osk.dispatch_token
    if not device.start():
        logger.warning("keyboard_emulation_start_failed")
        return False
    daemon._keyboard_device = device
    # TouchpadReader best-effort: emite 3 strings virtuais (touchpad_*_press)
    # que o dispatcher mescla ao frozenset de botões. Bindings default
    # mapeiam para KEY_BACKSPACE/ENTER/DELETE.
    _start_touchpad_reader(daemon)
    logger.info("keyboard_emulation_started")
    return True


def _start_touchpad_reader(daemon: Any) -> None:
    """Inicia TouchpadReader se device evdev disponível; no-op caso contrário.

    Em modo FAKE (testes, CI, smoke runs) o reader é pulado pois
    `find_dualsense_touchpad_evdev()` pode demorar >60ms enumerando evdev
    em ambiente com muitos devices, o que compete com janelas de teste
    curtas do poll loop.
    """
    if getattr(daemon, "_touchpad_reader", None) is not None:
        return
    if os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE"):
        logger.debug("touchpad_reader_desativado_em_fake_mode")
        return
    try:
        from hefesto_dualsense4unix.core.evdev_reader import TouchpadReader
    except Exception as exc:
        logger.warning("touchpad_reader_import_failed", err=str(exc))
        return
    reader = TouchpadReader()
    if not reader.is_available():
        logger.debug("touchpad_reader_ausente")
        return
    if reader.start():
        daemon._touchpad_reader = reader
        logger.info("touchpad_reader_iniciado")


def stop_keyboard_emulation(daemon: Any) -> None:
    """Para device + reader + OSK. Idempotente."""
    device = getattr(daemon, "_keyboard_device", None)
    if device is not None:
        with contextlib.suppress(Exception):
            device.stop()
        daemon._keyboard_device = None
    reader = getattr(daemon, "_touchpad_reader", None)
    if reader is not None:
        with contextlib.suppress(Exception):
            reader.stop()
        daemon._touchpad_reader = None
    osk = getattr(daemon, "_osk_controller", None)
    if osk is not None:
        with contextlib.suppress(Exception):
            osk.close()
        daemon._osk_controller = None
    logger.info("keyboard_emulation_stopped")


def dispatch_keyboard(daemon: Any, buttons_pressed: frozenset[str]) -> None:
    """Traduz o set de botões pressionados em eventos de teclado virtual.

    Chamado pelo poll loop a cada tick. Reusa `buttons_pressed` já obtido
    via `_evdev_buttons_once` (armadilha A-09). Mescla as 3 regiões do
    `TouchpadReader` (`touchpad_{left,middle,right}_press`) ao frozenset
    antes de passar ao device — regiões são tratadas como "botões virtuais"
    com os bindings default KEY_BACKSPACE/ENTER/DELETE. Não relança
    exceções — falhas são logadas como warning.
    """
    device = getattr(daemon, "_keyboard_device", None)
    if device is None:
        return
    reader = getattr(daemon, "_touchpad_reader", None)
    if reader is not None:
        try:
            regions = reader.regions_pressed()
        except Exception as exc:
            logger.warning("touchpad_regions_read_failed", err=str(exc))
            regions = frozenset()
        combined = buttons_pressed | regions
    else:
        combined = buttons_pressed
    try:
        device.dispatch(combined)
    except Exception as exc:
        logger.warning("keyboard_dispatch_failed", err=str(exc))


__all__ = [
    "_OSKController",
    "dispatch_keyboard",
    "start_keyboard_emulation",
    "stop_keyboard_emulation",
]

# "A natureza nada faz em vão." — Aristóteles
