"""Aba "Mouse e Teclado" — handlers CRUD de key_bindings por perfil.

FEAT-KEYBOARD-UI-01 (sprint 59.3). Herda `MouseActionsMixin` para reaproveitar
os handlers de mouse existentes e estende com:

- `install_input_tab()` — popula o TreeView com bindings efetivos do perfil
  ativo (DEFAULT_BUTTON_BINDINGS mesclado com `draft.profile.key_bindings`).
- Handlers `on_key_binding_add`, `on_key_binding_remove`,
  `on_key_binding_restore_defaults` — CRUD sobre o ListStore, delegando
  persistência ao `profile.save` via footer.

Rename físico para `input_actions.py` segue o spec, mas `mouse_actions.py`
permanece como submódulo compatibilidade (classe `MouseActionsMixin` não é
removida) para evitar ripple em callers externos e em `main.glade` onde os
handlers de mouse continuam amarrados pelos IDs originais.
"""
from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")


# fronteira (`_dehumanize_binding`). Nomes na língua da usuária, não do kernel.
_BUTTON_LABELS: dict[str, str] = {
    "cross": "X (Cruz)",
    "circle": "Círculo",
    "triangle": "Triângulo",
    "square": "Quadrado",
    "dpad_up": "Direcional ↑",
    "dpad_down": "Direcional ↓",
    "dpad_left": "Direcional ←",
    "dpad_right": "Direcional →",
    "l1": "L1",
    "r1": "R1",
    "l2": "L2 (gatilho esquerdo)",
    "r2": "R2 (gatilho direito)",
    "l3": "L3 (clicar analógico esquerdo)",
    "r3": "R3 (clicar analógico direito)",
    "options": "Options",
    "create": "Share / Create",
    "ps": "Botão PS",
    "touchpad_left_press": "Touchpad — lado esquerdo",
    "touchpad_middle_press": "Touchpad — meio",
    "touchpad_right_press": "Touchpad — lado direito",
}

_KEY_LABELS: dict[str, str] = {
    "KEY_LEFTALT": "Alt",
    "KEY_RIGHTALT": "Alt direito",
    "KEY_LEFTSHIFT": "Shift",
    "KEY_RIGHTSHIFT": "Shift direito",
    "KEY_LEFTCTRL": "Ctrl",
    "KEY_RIGHTCTRL": "Ctrl direito",
    "KEY_LEFTMETA": "Super (tecla Windows)",
    "KEY_TAB": "Tab",
    "KEY_ENTER": "Enter",
    "KEY_ESC": "Esc",
    "KEY_SPACE": "Espaço",
    "KEY_BACKSPACE": "Backspace",
    "KEY_DELETE": "Delete",
    "KEY_SYSRQ": "PrintScreen",
    "KEY_UP": "Seta ↑",
    "KEY_DOWN": "Seta ↓",
    "KEY_LEFT": "Seta ←",
    "KEY_RIGHT": "Seta →",
    # O ALTERNADOR é o preset do L3 desde 02/09/2026 (decisão de produto). Sem esta
    "__TOGGLE_OSK__": "Abrir e fechar teclado na tela",
    "__OPEN_OSK__": "Abrir teclado na tela",
    "__CLOSE_OSK__": "Fechar teclado na tela",
}

_REV_KEY: dict[str, str] = {label.lower(): raw for raw, label in _KEY_LABELS.items()}


def humanize_button(button_id: str) -> str:
    """Rótulo amigável de um botão do controle (fallback: o próprio id)."""
    return _BUTTON_LABELS.get(button_id, button_id)


def humanize_binding(serialized: str) -> str:
    """'KEY_LEFTALT+KEY_TAB' → 'Alt + Tab'; '__OPEN_OSK__' → 'Abrir teclado…'."""
    partes = [tok.strip() for tok in serialized.split("+") if tok.strip()]
    saida = []
    for tok in partes:
        if tok in _KEY_LABELS:
            saida.append(_KEY_LABELS[tok])
        elif tok.startswith("KEY_"):
            saida.append(tok[4:])
        else:
            saida.append(tok)
    return " + ".join(saida)


def _e_nome_de_tecla(tok: str) -> bool:
    """`True` quando `KEY_<TOK>` existe no vocabulário do `evdev`."""
    if not tok or not tok.replace("_", "").isalnum():
        return False
    try:
        from evdev import ecodes
    except Exception:
        return False
    return f"KEY_{tok.upper()}" in getattr(ecodes, "ecodes", {})


def dehumanize_binding(friendly: str) -> str:
    """Inverso de `humanize_binding` — 'Alt + Tab' → 'KEY_LEFTALT+KEY_TAB'."""
    partes = [tok.strip() for tok in friendly.split("+") if tok.strip()]
    saida = []
    for tok in partes:
        chave = tok.lower()
        if chave in _REV_KEY:
            saida.append(_REV_KEY[chave])
        elif tok.startswith("KEY_") or tok.startswith("__"):
            saida.append(tok)
        elif (len(tok) == 1 and tok.isalnum()) or _e_nome_de_tecla(tok):
            saida.append(f"KEY_{tok.upper()}")
        else:
            saida.append(tok)
    return "+".join(saida)


def frase_do_teclado_na_tela(osk_disponivel: bool | None) -> str:
    """O que ESTA máquina tem, sobre o teclado na tela (N12).

    TECLADO-NA-TELA-QUE-A-JANELA-NAO-LE-01. `BINDINGS_LEGEND` diz o que o L3
    PRECISA (`onboard` ou `wvkbd-mobintl` instalados) e nunca disse se algum
    está — e a resposta viaja no fio desde 10/08, no `osk_disponivel` do bloco
    `keyboard_emulation`. Como nenhum atalho de fábrica digita letra, esta é a
    frase que decide se existe ALGUM caminho para escrever texto com o
    controle.

    Aditiva, e não uma reescrita da legenda: com `None` devolve `""` e a tela
    fica exatamente como estava. "Não sei" já está dito no texto fixo, e
    substituí-lo por "não tem" porque ninguém respondeu mandaria ela instalar um
    pacote que talvez já esteja lá.

    Os dois nomes saem com o ambiente ao lado porque a ORDEM importa e a janela
    não a conhece: o `onboard` digita por XTEST e não alcança cliente Wayland
    nativo; o daemon já escolhe pela sessão viva (`_osk_candidatos`), mas quem
    lê a legenda está prestes a instalar à mão.
    """
    if osk_disponivel is None:
        return ""
    if osk_disponivel:
        return (
            "<b>Neste computador:</b> o teclado na tela está instalado — o L3 "
            "abre."
        )
    return (
        "<b>Neste computador:</b> não há teclado na tela instalado, então o L3 "
        "não vai abrir nada — e, como nenhum atalho de fábrica digita letra, "
        "hoje não há como escrever texto com o controle. Instale um: "
        "<tt>wvkbd-mobintl</tt> (Wayland) ou <tt>onboard</tt> (X11)."
    )


__all__ = [
    "frase_do_teclado_na_tela",
]
