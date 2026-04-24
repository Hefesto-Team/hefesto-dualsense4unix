"""Emulação de teclado virtual via python-uinput (FEAT-KEYBOARD-EMULATOR-01).

Análogo a `uinput_mouse.py`, cria um device virtual dedicado para teclas que
NÃO conflitam com o device de mouse (mouse device já expõe algumas teclas
como KEY_ENTER/KEY_ESC/KEY_UP). Separar o device evita ambiguidade de
roteamento e mantém a convenção de 1 subsystem → 1 /dev/uinput próprio.

Responsabilidades:
- Abrir /dev/uinput com capabilities EV_KEY cobrindo as teclas usadas pelos
  mapeamentos default (`DEFAULT_BUTTON_BINDINGS`) + espaço para overrides
  futuros.
- Expor `dispatch(buttons_pressed)` chamado a cada tick do poll loop.
- Emitir press+release edge-triggered: cada transição False→True de um botão
  mapeado emite a sequência completa (modificadores+tecla final), mantém
  pressionados enquanto o botão físico está pressionado e libera na ordem
  reversa ao soltar.
- Zero conflito com o mouse: o set de botões aqui tratado é disjunto do set
  tratado por `UinputMouseDevice` (cross/triangle/r3/dpad_*/circle/square).

Política para sprints futuras:
- Suporte a bindings dinâmicos via `set_bindings(mapping)` já incluído para
  destravar FEAT-KEYBOARD-PERSISTENCE-01 sem tocar nesta classe.
- Capabilities são fixas no `start()`: cobrem um superset de teclas comuns
  (letras, modificadores, função, números, Alt+Tab etc.) para que overrides
  de UI não exijam recriar o device.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hefesto.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    KeyBinding,
    is_virtual_token,
)
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

DEVICE_NAME = "Hefesto Virtual Keyboard"

# Superset de teclas que o device expõe. Cobre DEFAULT_BUTTON_BINDINGS mais
# letras/números/funções que o usuário poderá atribuir via UI futura.
# Manter em ordem alfabética facilita diff.
SUPPORTED_KEYS: tuple[str, ...] = (
    # Modificadores
    "KEY_LEFTALT", "KEY_RIGHTALT",
    "KEY_LEFTCTRL", "KEY_RIGHTCTRL",
    "KEY_LEFTSHIFT", "KEY_RIGHTSHIFT",
    "KEY_LEFTMETA", "KEY_RIGHTMETA",
    # Controle e navegação
    "KEY_BACKSPACE", "KEY_DELETE", "KEY_ENTER", "KEY_ESC",
    "KEY_HOME", "KEY_END", "KEY_INSERT", "KEY_PAGEUP", "KEY_PAGEDOWN",
    "KEY_SPACE", "KEY_TAB",
    "KEY_SYSRQ",  # PrintScreen
    # Setas
    "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    # Letras
    "KEY_A", "KEY_B", "KEY_C", "KEY_D", "KEY_E", "KEY_F", "KEY_G",
    "KEY_H", "KEY_I", "KEY_J", "KEY_K", "KEY_L", "KEY_M", "KEY_N",
    "KEY_O", "KEY_P", "KEY_Q", "KEY_R", "KEY_S", "KEY_T", "KEY_U",
    "KEY_V", "KEY_W", "KEY_X", "KEY_Y", "KEY_Z",
    # Números (linha principal)
    "KEY_0", "KEY_1", "KEY_2", "KEY_3", "KEY_4",
    "KEY_5", "KEY_6", "KEY_7", "KEY_8", "KEY_9",
    # Função
    "KEY_F1", "KEY_F2", "KEY_F3", "KEY_F4", "KEY_F5", "KEY_F6",
    "KEY_F7", "KEY_F8", "KEY_F9", "KEY_F10", "KEY_F11", "KEY_F12",
    # Volume (para handlers futuros)
    "KEY_VOLUMEUP", "KEY_VOLUMEDOWN", "KEY_MUTE",
)


def _build_capabilities() -> list[Any]:
    """Lista de eventos que o uinput device expõe. Import lazy.

    Filtra teclas que o módulo `uinput` não conhece (versões antigas podem
    faltar KEY_SYSRQ etc.) com log de aviso; não quebra o start por tecla
    faltante — apenas pula.
    """
    import uinput

    caps: list[Any] = []
    for key_name in SUPPORTED_KEYS:
        ev = getattr(uinput, key_name, None)
        if ev is None:
            logger.warning("keyboard_capability_missing", key=key_name)
            continue
        caps.append(ev)
    return caps


@dataclass
class UinputKeyboardDevice:
    """Wrapper do device virtual de teclado. Lazy-creates no `start()`."""

    name: str = DEVICE_NAME
    bindings: dict[str, KeyBinding] = field(
        default_factory=lambda: dict(DEFAULT_BUTTON_BINDINGS)
    )
    # Callback para tokens virtuais `__*__` (FEAT-KEYBOARD-UI-01). Recebe
    # `(token, phase)` onde phase é "press" ou "release". Quando None, tokens
    # virtuais são ignorados (log warning uma vez). Ver keyboard subsystem
    # para o binding típico: `__OPEN_OSK__` → abrir onboard/wvkbd.
    virtual_token_callback: Callable[[str, str], None] | None = None

    _device: Any = None
    _uinput_mod: Any = None
    # Botões canônicos (do DualSense) atualmente pressionados e já emitidos.
    _pressed_buttons: frozenset[str] = field(default_factory=frozenset)
    _virtual_token_warned: bool = False

    def start(self) -> bool:
        """Cria o device. Retorna False se /dev/uinput indisponível."""
        if self._device is not None:
            return True
        try:
            import uinput
        except ImportError:
            logger.warning(
                "python-uinput não instalado — emulação de teclado indisponível"
            )
            return False
        try:
            caps = _build_capabilities()
            self._device = uinput.Device(caps, name=self.name)
            self._uinput_mod = uinput
            logger.info("keyboard_emulator_opened", name=self.name)
            return True
        except Exception as exc:
            logger.warning("uinput_keyboard_create_failed", err=str(exc))
            return False

    def stop(self) -> None:
        if self._device is None:
            return
        # Solta tudo que ainda estiver pressionado antes de destruir o device
        # para evitar ghost-keys no sistema do usuário.
        self._release_all()
        with contextlib.suppress(Exception):
            self._device.destroy()
        self._device = None
        self._uinput_mod = None
        self._pressed_buttons = frozenset()

    def is_active(self) -> bool:
        return self._device is not None

    def set_bindings(self, bindings: dict[str, KeyBinding]) -> None:
        """Substitui mapeamentos em runtime. Usado por `daemon.reload_config`
        e pela UI quando o usuário edita bindings.

        Não recria o device; capabilities são superset fixo.
        """
        # Antes de trocar, libera tudo que estava pressionado sob o mapping antigo
        # para evitar tecla "colada".
        self._release_all()
        self.bindings = dict(bindings)

    def dispatch(self, buttons_pressed: frozenset[str]) -> None:
        """Aplica snapshot de botões pressionados no device virtual.

        Edge-triggered: emite press da sequência (modificadores+tecla) ao
        detectar transição False→True de um botão mapeado; emite release
        ao detectar True→False.
        """
        if self._device is None or self._uinput_mod is None:
            return

        # Considera apenas os botões que tenham binding ativo.
        now_mapped = frozenset(b for b in buttons_pressed if b in self.bindings)
        newly_pressed = now_mapped - self._pressed_buttons
        newly_released = self._pressed_buttons - now_mapped

        for button in sorted(newly_pressed):
            self._emit_sequence_press(button)
        for button in sorted(newly_released):
            self._emit_sequence_release(button)

        self._pressed_buttons = now_mapped

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _emit_sequence_press(self, button: str) -> None:
        seq = self.bindings.get(button)
        if not seq:
            return
        if self._delegate_virtual_tokens(button, seq, phase="press"):
            return
        u = self._uinput_mod
        any_emitted = False
        for key_name in seq:
            ev = getattr(u, key_name, None)
            if ev is None:
                logger.warning(
                    "keyboard_key_unknown", button=button, key=key_name
                )
                continue
            self._device.emit(ev, 1, syn=False)
            any_emitted = True
        if any_emitted:
            self._device.syn()
            logger.info(
                "key_binding_emit",
                button=button,
                keys=list(seq),
                phase="press",
            )

    def _emit_sequence_release(self, button: str) -> None:
        seq = self.bindings.get(button)
        if not seq:
            return
        if self._delegate_virtual_tokens(button, seq, phase="release"):
            return
        u = self._uinput_mod
        any_emitted = False
        # Libera em ordem reversa ao press (modificadores por último saem).
        for key_name in reversed(seq):
            ev = getattr(u, key_name, None)
            if ev is None:
                continue
            self._device.emit(ev, 0, syn=False)
            any_emitted = True
        if any_emitted:
            self._device.syn()
            logger.info(
                "key_binding_emit",
                button=button,
                keys=list(seq),
                phase="release",
            )

    def _delegate_virtual_tokens(
        self, button: str, seq: KeyBinding, phase: str
    ) -> bool:
        """Se `seq` for inteiramente tokens virtuais `__*__`, delega ao callback.

        Retorna True quando o binding foi tratado como virtual (caller deve
        sair sem emitir pelo uinput). False quando é um binding normal com
        `KEY_*`. Binding misto (`__OPEN_OSK__` + `KEY_TAB`) é rejeitado com
        warning — semântica mista seria confusa e a UI futura impede.
        """
        virtual = [tok for tok in seq if is_virtual_token(tok)]
        if not virtual:
            return False
        if len(virtual) != len(seq):
            logger.warning(
                "keyboard_binding_misto_rejeitado",
                button=button,
                keys=list(seq),
            )
            return True
        cb = self.virtual_token_callback
        if cb is None:
            if not self._virtual_token_warned:
                logger.warning(
                    "keyboard_virtual_token_sem_callback",
                    button=button,
                    keys=list(seq),
                )
                self._virtual_token_warned = True
            return True
        for tok in seq:
            try:
                cb(tok, phase)
            except Exception as exc:
                logger.warning(
                    "keyboard_virtual_token_callback_failed",
                    button=button,
                    token=tok,
                    phase=phase,
                    err=str(exc),
                )
        logger.info(
            "key_binding_virtual_emit",
            button=button,
            tokens=list(seq),
            phase=phase,
        )
        return True

    def _release_all(self) -> None:
        """Libera todas as teclas ainda pressionadas sob os bindings atuais."""
        if self._device is None or self._uinput_mod is None:
            return
        for button in sorted(self._pressed_buttons):
            self._emit_sequence_release(button)
        self._pressed_buttons = frozenset()


__all__ = [
    "DEVICE_NAME",
    "SUPPORTED_KEYS",
    "UinputKeyboardDevice",
]

# "Não há mau maior para o homem do que ignorar o bem." — Platão
