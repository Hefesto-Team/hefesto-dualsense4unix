"""Todo ``handler="..."`` do main.glade tem de estar em ``_signal_handlers()``.

Regressão de BUG-GUI-EMULATION-HANDLERS-UNWIRED-01: os botões novos da aba
Emulação (gamepad/máscara, pausar/retomar, Steam Input, mic) tinham
``<signal name="clicked" handler="on_emulation_..."/>`` no glade, mas as chaves
não foram adicionadas ao dict passado para ``builder.connect_signals()``. Como o
app conecta sinais por um dict explícito (não por ``self``), o GTK não achava o
callback e o clique simplesmente não fazia nada ("clico e não aplica").

O teste é estático (AST do app.py + regex do XML): não importa GTK/PyGObject,
então roda no ``.venv`` e na CI sem display (mesmo motivo dos stubs de ``gi`` nos
demais testes de GUI).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_APP_PY = _ROOT / "src" / "hefesto_dualsense4unix" / "app" / "app.py"
_GLADE = _ROOT / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"


def _glade_handlers() -> set[str]:
    text = _GLADE.read_text(encoding="utf-8")
    return set(re.findall(r'handler="([A-Za-z0-9_]+)"', text))


def _registered_handlers() -> set[str]:
    """Chaves do dict literal retornado por ``HefestoApp._signal_handlers()``."""
    tree = ast.parse(_APP_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_signal_handlers":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                    return {
                        k.value
                        for k in sub.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
    raise AssertionError("_signal_handlers() com dict literal não encontrado em app.py")


def test_todo_handler_do_glade_esta_registrado() -> None:
    faltando = sorted(_glade_handlers() - _registered_handlers())
    assert not faltando, (
        "handlers referenciados no main.glade sem entrada em "
        f"HefestoApp._signal_handlers() (botões mortos): {faltando}"
    )


def test_handlers_de_emulacao_presentes() -> None:
    """Guarda específico do bug: os botões da aba Emulação têm de estar fiados."""
    registered = _registered_handlers()
    esperados = {
        "on_emulation_gamepad_off",
        "on_emulation_gamepad_dualsense",
        "on_emulation_gamepad_xbox",
        "on_emulation_pause",
        "on_emulation_resume",
        "on_emulation_steam_input_check",
        "on_emulation_steam_input_disable",
        "on_emulation_mic_on",
        "on_emulation_mic_off",
    }
    faltando = sorted(esperados - registered)
    assert not faltando, f"handlers da aba Emulação não registrados: {faltando}"
