"""Mapeamentos default de botão do DualSense para sequência de teclas.

Introduzido em FEAT-KEYBOARD-EMULATOR-01 (sub-sprint 1 de
FEAT-MOUSE-TECLADO-COMPLETO-01). Define `DEFAULT_BUTTON_BINDINGS` hardcoded
cobrindo Options, Share/Create, L1, R1, L3, R3.

Formato de binding: `tuple[str, ...]` com nomes canônicos `KEY_*` do
`evdev.ecodes`. Uma tupla com 1 elemento é tecla única; múltiplos elementos
representam combo (todos os modificadores pressionados junto com a tecla
final, emitidos em ordem de press e liberados em ordem reversa).

Exemplos:
- `("KEY_LEFTMETA",)` — tecla Super.
- `("KEY_LEFTALT", "KEY_TAB")` — Alt+Tab.
- `("KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB")` — Alt+Shift+Tab.

Botões cobertos nesta sprint (baseados em `evdev_reader._BUTTONS`):
    options, create (Share), l1, r1, l3, r3.

Fora desta sprint-1:
- touchpad_press — evdev ainda não expõe keycode consistente (ver comentário
  em `src/hefesto_dualsense4unix/core/evdev_reader.py` linha 89).
- cross/circle/triangle/square — reservados para mouse (FEAT-MOUSE-01/02);
  serão reconfiguráveis via UI em FEAT-KEYBOARD-UI-01.
- dpad_* — reservados para mouse (setas); mesma razão.
- L2/R2 inversão — pertence à sub-sprint UI (depende de persistência).

Persistência por perfil e UI de edição entram em sub-sprints filhas.
"""
from __future__ import annotations

KeyBinding = tuple[str, ...]

TOKEN_OPEN_OSK = "__OPEN_OSK__"
TOKEN_CLOSE_OSK = "__CLOSE_OSK__"
TOKEN_TOGGLE_OSK = "__TOGGLE_OSK__"

DEFAULT_BUTTON_BINDINGS: dict[str, KeyBinding] = {
    "options": ("KEY_LEFTMETA",),
    "create": ("KEY_SYSRQ",),
    "l1": ("KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB"),
    "r1": ("KEY_LEFTALT", "KEY_TAB"),
    "l3": (TOKEN_TOGGLE_OSK,),
    "r3": (TOKEN_CLOSE_OSK,),
    "touchpad_left_press": ("KEY_BACKSPACE",),
    "touchpad_middle_press": ("KEY_ENTER",),
    "touchpad_right_press": ("KEY_DELETE",),
}

PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ: dict[str, tuple[str, str]] = {}


def is_virtual_token(token: str) -> bool:
    """True se `token` é um marcador `__XXX__` (delegado ao callback)."""
    return len(token) >= 4 and token.startswith("__") and token.endswith("__")


__all__ = [
    "DEFAULT_BUTTON_BINDINGS",
    "PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ",
    "TOKEN_CLOSE_OSK",
    "TOKEN_OPEN_OSK",
    "TOKEN_TOGGLE_OSK",
    "KeyBinding",
    "is_virtual_token",
]

