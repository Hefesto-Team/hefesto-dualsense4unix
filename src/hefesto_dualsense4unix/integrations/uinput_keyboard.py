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

from hefesto_dualsense4unix.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    KeyBinding,
    is_virtual_token,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEVICE_NAME = "Hefesto - Dualsense4Unix Virtual Keyboard"

CODIGO_MAXIMO_DE_TECLA = 255
_NAO_E_TECLA = frozenset({"KEY_RESERVED", "KEY_UNKNOWN"})


def _teclas_do_teclado() -> tuple[str, ...]:
    """Toda tecla de teclado e de mídia que o `evdev.ecodes` nomeia, de `KEY_ESC` a `KEY_MICMUTE`.

    É o dono único da lista: o nó nasce com todas, e o perfil só aceita as que ele emite.
    """
    from evdev import ecodes

    codigos = {
        nome: codigo for nome, codigo in ecodes.ecodes.items()
        if nome.startswith("KEY_") and nome not in _NAO_E_TECLA
        and isinstance(codigo, int) and 1 <= codigo <= CODIGO_MAXIMO_DE_TECLA
    }
    return tuple(sorted(codigos, key=lambda nome: (codigos[nome], nome)))


SUPPORTED_KEYS: tuple[str, ...] = _teclas_do_teclado()


def tecla_aceita(nome: str) -> bool:
    """O nó emite a tecla `nome`? Vale para `button_actions` e para `key_bindings`."""
    return nome in SUPPORTED_KEYS


def _eventos_do_no(uinput: Any) -> dict[str, Any]:
    """`{nome: evento}` de cada tecla do nó: o do módulo `uinput` ou o `EV_KEY` do código."""
    from evdev import ecodes

    eventos: dict[str, Any] = {}
    for nome in SUPPORTED_KEYS:
        ev = getattr(uinput, nome, None)
        if ev is None:
            ev = (ecodes.EV_KEY, ecodes.ecodes[nome])
        eventos[nome] = ev
    return eventos


def _build_capabilities() -> list[Any]:
    """Lista de eventos que o uinput device expõe. Import lazy."""
    import uinput

    caps: list[Any] = []
    for ev in _eventos_do_no(uinput).values():
        if ev not in caps:
            caps.append(ev)
    return caps


@dataclass
class UinputKeyboardDevice:
    """Wrapper do device virtual de teclado. Lazy-creates no `start()`."""

    name: str = DEVICE_NAME
    bindings: dict[str, KeyBinding] = field(
        default_factory=lambda: dict(DEFAULT_BUTTON_BINDINGS)
    )
    virtual_token_callback: Callable[[str, str], None] | None = None

    _device: Any = None
    _uinput_mod: Any = None
    _eventos: dict[str, Any] = field(default_factory=dict)
    _capacidades: frozenset[str] | None = None
    _pressed_buttons: frozenset[str] = field(default_factory=frozenset)
    _quem_segura: dict[str, int] = field(default_factory=dict)
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
            self._eventos = _eventos_do_no(uinput)
            caps = _build_capabilities()
            self._device = uinput.Device(caps, name=self.name)
            self._capacidades = frozenset(self._eventos)
            self._uinput_mod = uinput
            logger.info("keyboard_emulator_opened", name=self.name)
            return True
        except Exception as exc:
            logger.warning("uinput_keyboard_create_failed", err=str(exc))
            return False

    def stop(self) -> None:
        if self._device is None:
            return
        self._release_all()
        with contextlib.suppress(Exception):
            self._device.destroy()
        self._device = None
        self._uinput_mod = None
        self._eventos = {}
        self._capacidades = None
        self._pressed_buttons = frozenset()
        self._quem_segura = {}

    def is_active(self) -> bool:
        return self._device is not None

    def set_bindings(self, bindings: dict[str, KeyBinding]) -> None:
        """Substitui mapeamentos em runtime. Usado por `daemon.reload_config`
        e pela UI quando o usuário edita bindings.

        Não recria o device; capabilities são superset fixo.
        """
        self._release_all()
        self.bindings = dict(bindings)

    def dispatch(self, buttons_pressed: frozenset[str]) -> None:
        """Aplica snapshot de botões pressionados no device virtual."""
        if self._device is None or self._uinput_mod is None:
            return

        now_mapped = frozenset(b for b in buttons_pressed if b in self.bindings)
        newly_pressed = now_mapped - self._pressed_buttons
        newly_released = self._pressed_buttons - now_mapped

        for button in sorted(newly_pressed):
            self._emit_sequence_press(button)
        for button in sorted(newly_released):
            self._emit_sequence_release(button)

        self._pressed_buttons = now_mapped

    def prime(self, buttons_pressed: frozenset[str]) -> None:
        """Semeia o edge-tracker com `buttons_pressed` SEM apertar nada.

        As teclas dos botões semeados entram na conta de quem segura: o soltar
        deles emite o key up, e o de outro botão não derruba a tecla que eles seguram.
        A tecla que a conta antiga segurava e a nova esquece recebe o key up aqui.
        """
        if self._device is None or self._uinput_mod is None:
            return
        antes = self._quem_segura
        self._pressed_buttons = frozenset(
            b for b in buttons_pressed if b in self.bindings
        )
        self._quem_segura = {}
        for button in self._pressed_buttons:
            seq = self.bindings.get(button) or ()
            if any(is_virtual_token(tok) for tok in seq):
                continue
            for key_name in seq:
                if self._evento(key_name) is not None:
                    self._quem_segura[key_name] = self._quem_segura.get(key_name, 0) + 1
        esquecidas = sorted(set(antes) - set(self._quem_segura))
        for key_name in esquecidas:
            ev = self._evento(key_name)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)
        if esquecidas:
            self._device.syn()


    def _evento(self, key_name: str) -> Any:
        """O evento da tecla, ou None quando o nó não a tem entre as capacidades."""
        capacidades = self._capacidades
        if capacidades is not None and key_name not in capacidades:
            return None
        ev = self._eventos.get(key_name)
        if ev is None:
            ev = getattr(self._uinput_mod, key_name, None)
        return ev

    def _emit_sequence_press(self, button: str) -> None:
        seq = self.bindings.get(button)
        if not seq:
            return
        if self._delegate_virtual_tokens(button, seq, phase="press"):
            return
        any_emitted = False
        for key_name in seq:
            ev = self._evento(key_name)
            if ev is None:
                logger.warning(
                    "keyboard_key_unknown", button=button, key=key_name
                )
                continue
            seguram = self._quem_segura.get(key_name, 0)
            self._quem_segura[key_name] = seguram + 1
            if seguram:
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
        any_emitted = False
        for key_name in reversed(seq):
            ev = self._evento(key_name)
            seguram = self._quem_segura.get(key_name, 0)
            if ev is None or seguram == 0:
                continue
            if seguram > 1:
                self._quem_segura[key_name] = seguram - 1
                continue
            del self._quem_segura[key_name]
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
        """Se `seq` for inteiramente tokens virtuais `__*__`, delega ao callback."""
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
        """Libera todas as teclas ainda pressionadas, uma vez cada, e zera a conta."""
        if self._device is None or self._uinput_mod is None:
            self._quem_segura = {}
            return
        for button in sorted(self._pressed_buttons):
            self._emit_sequence_release(button)
        sobra = sorted(self._quem_segura)
        for key_name in sobra:
            ev = self._evento(key_name)
            if ev is not None:
                self._device.emit(ev, 0, syn=False)
        if sobra:
            self._device.syn()
        self._pressed_buttons = frozenset()
        self._quem_segura = {}


__all__ = [
    "CODIGO_MAXIMO_DE_TECLA",
    "DEVICE_NAME",
    "SUPPORTED_KEYS",
    "UinputKeyboardDevice",
    "tecla_aceita",
]

