"""Ações puras do teclado e do teclado na tela, sem tela própria.

Os rótulos, na língua de quem usa, dos botões do controle e das teclas (`humanize_button`,
`humanize_binding`) e a frase de quando a máquina não tem o teclado na tela
(`frase_do_teclado_na_tela`). A aba Navegação os lê; nada aqui abre janela nem carrega o GTK.
"""
from __future__ import annotations

# Nomes na língua da usuária, não do kernel.
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
    # O ALTERNADOR é o preset do L3 desde 02/09/2026 (decisão de produto). Sem esta linha, a
    # linha do L3 mostraria `__TOGGLE_OSK__` cru na tela.
    "__TOGGLE_OSK__": "Abrir e fechar teclado na tela",
    "__OPEN_OSK__": "Abrir teclado na tela",
    "__CLOSE_OSK__": "Fechar teclado na tela",
}

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


def frase_do_teclado_na_tela(osk_disponivel: bool | None) -> str:
    """O que ESTA máquina não tem, sobre o teclado na tela; `""` quando tem ou ninguém olhou.

    O dado vem do daemon, no `osk_disponivel` do bloco `keyboard_emulation`: ele enxerga o host,
    e a janela num Flatpak olharia o sandbox. `None` não afirma nada, porque "não sei" mandaria
    instalar um pacote que talvez já esteja lá. A ordem dos pacotes importa: o `onboard` digita
    por XTEST e não alcança cliente Wayland nativo.
    """
    if osk_disponivel is not False:
        return ""
    return (
        "não há teclado na tela instalado neste computador: essa ação não abre nada, e sem "
        "ele, escrever texto com o controle exige mapear as letras uma a uma. Instale o "
        "wvkbd-mobintl (Wayland) ou o onboard (X11)."
    )


__all__ = [
    "frase_do_teclado_na_tela",
]
