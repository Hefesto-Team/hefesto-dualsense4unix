"""Aba Triggers: dropdown de 19 presets + sliders dinâmicos + aplicar via IPC."""
from __future__ import annotations

import re
from typing import Any

import gi

gi.require_version("Gtk", "3.0")


# HARM-19: formatos de recusa que `core/trigger_effects` levanta (ValueError ->
_RE_ERRO_ORDEM = re.compile(r"(\w+) \((-?\d+)\) deve ser > (\w+) \((-?\d+)\)")
_RE_ERRO_RANGE = re.compile(r"(\w+) fora do range (-?\d+)-(-?\d+): (-?\d+)")


def _rotulo_do_param(spec: Any, nome: str) -> str:
    """Rótulo do slider para o parâmetro `nome` do preset (ex.: end -> "Fim")."""
    for param in getattr(spec, "params", ()):
        if param.name == nome:
            return str(param.label)
    return nome


def humanizar_erro_gatilho(motivo: str, spec: Any = None) -> str | None:
    """Traduz a recusa do daemon para português simples (HARM-19)."""
    m = _RE_ERRO_ORDEM.search(motivo)
    if m:
        maior, v_maior, menor, v_menor = m.groups()
        return (
            f"{_rotulo_do_param(spec, maior)} ({v_maior}) precisa ser maior que "
            f"{_rotulo_do_param(spec, menor)} ({v_menor})"
        )
    m = _RE_ERRO_RANGE.search(motivo)
    if m:
        nome, lo, hi, valor = m.groups()
        return (
            f"{_rotulo_do_param(spec, nome)} precisa estar entre {lo} e {hi} "
            f"(você pediu {valor})"
        )
    return None


