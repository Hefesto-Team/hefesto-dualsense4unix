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
  em `src/hefesto/core/evdev_reader.py` linha 89).
- cross/circle/triangle/square — reservados para mouse (FEAT-MOUSE-01/02);
  serão reconfiguráveis via UI em FEAT-KEYBOARD-UI-01.
- dpad_* — reservados para mouse (setas); mesma razão.
- L2/R2 inversão — pertence à sub-sprint UI (depende de persistência).

Persistência por perfil e UI de edição entram em sub-sprints filhas.
"""
from __future__ import annotations

KeyBinding = tuple[str, ...]

# Tokens virtuais reservados (FEAT-KEYBOARD-UI-01). Não são teclas reais:
# o `UinputKeyboardDevice` reconhece o prefixo `__`/sufixo `__` e delega ao
# callback do subsystem em vez de emitir via uinput. Mantê-los em constantes
# evita literais mágicos espalhados pelo código.
TOKEN_OPEN_OSK = "__OPEN_OSK__"
TOKEN_CLOSE_OSK = "__CLOSE_OSK__"

DEFAULT_BUTTON_BINDINGS: dict[str, KeyBinding] = {
    "options": ("KEY_LEFTMETA",),
    "create": ("KEY_SYSRQ",),
    "l1": ("KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB"),
    "r1": ("KEY_LEFTALT", "KEY_TAB"),
    # L3/R3 abrem/fecham teclado virtual do sistema (onboard/wvkbd-mobintl).
    # O token virtual é interceptado pelo UinputKeyboardDevice e delegado ao
    # keyboard subsystem — não emite evento real de tecla. Previne colisão
    # com R3=BTN_MIDDLE do mouse porque este último só atua quando
    # `mouse_emulation_enabled=True`. Quem habilita mouse+teclado juntos
    # pode sobrescrever l3/r3 via UI (FEAT-KEYBOARD-UI-01) removendo o
    # conflito explicitamente.
    "l3": (TOKEN_OPEN_OSK,),
    "r3": (TOKEN_CLOSE_OSK,),
    # Regiões do touchpad (click firme, não toque leve) — emitidas pelo
    # `TouchpadReader` no device separado expose pelo kernel hid_playstation.
    # O dispatcher (`dispatch_keyboard`) mescla `regions_pressed()` ao
    # frozenset de botões antes de passar ao device, permitindo que as 3
    # regiões sejam tratadas como "botões" virtuais aqui — API uniforme.
    "touchpad_left_press": ("KEY_BACKSPACE",),
    "touchpad_middle_press": ("KEY_ENTER",),
    "touchpad_right_press": ("KEY_DELETE",),
}


def is_virtual_token(token: str) -> bool:
    """True se `token` é um marcador `__XXX__` (delegado ao callback)."""
    return len(token) >= 4 and token.startswith("__") and token.endswith("__")


def parse_binding(spec: str) -> KeyBinding:
    """Converte `"KEY_LEFTALT+KEY_TAB"` em `("KEY_LEFTALT", "KEY_TAB")`.

    Formato aceito:
    - Tecla única: `"KEY_ENTER"`.
    - Combo: `"KEY_LEFTALT+KEY_TAB"`, `"KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T"`.

    Tokens são stripped e uppercased. Vazio retorna tupla vazia. Strings
    fora do padrão `KEY_*` levantam `ValueError` — validação completa contra
    `evdev.ecodes` fica a cargo do loader de perfil (sub-sprint 2).
    """
    if not spec or not spec.strip():
        return ()
    tokens = [tok.strip().upper() for tok in spec.split("+") if tok.strip()]
    for tok in tokens:
        if not tok.startswith("KEY_"):
            raise ValueError(
                f"token {tok!r} fora do padrão 'KEY_*' "
                f"(binding recebido: {spec!r})"
            )
    return tuple(tokens)


def format_binding(binding: KeyBinding) -> str:
    """Inverso de `parse_binding`. Útil para serialização e UI."""
    return "+".join(binding)


__all__ = [
    "DEFAULT_BUTTON_BINDINGS",
    "TOKEN_CLOSE_OSK",
    "TOKEN_OPEN_OSK",
    "KeyBinding",
    "format_binding",
    "is_virtual_token",
    "parse_binding",
]

# "O homem é a medida de todas as coisas." — Protágoras
