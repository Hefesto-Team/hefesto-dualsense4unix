"""Escape de markup do Pango, sem depender de o GLib estar completo."""

from __future__ import annotations

_TROCAS = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ("'", "&#39;"),
    ('"', "&quot;"),
)


def escapar_markup(texto: str) -> str:
    """``texto`` seguro para ``set_markup``, com ou sem GLib completo."""
    try:
        from gi.repository import GLib
    except Exception:  # pragma: no cover - sem gi nenhum, o piso já resolve
        pass
    else:
        escapar = getattr(GLib, "markup_escape_text", None)
        if callable(escapar):
            resultado = escapar(texto)
            return str(resultado)

    for cru, escapado in _TROCAS:
        texto = texto.replace(cru, escapado)
    return texto
