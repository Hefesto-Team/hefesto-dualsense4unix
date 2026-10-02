"""Seção 4 da aba Configurações — ajustes do programa, não dos controles."""
from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "A janela"

DICA: str | None = None

_ESPACAMENTO_DA_FILEIRA = 8


def _recibo(host: Any, linha: Any) -> Any:
    """Um rótulo VAZIO no fim da fileira, e o registro dele na lista do host."""
    from gi.repository import Gtk

    rotulo = Gtk.Label(label="")
    rotulo.set_xalign(0.0)
    linha.pack_start(rotulo, False, False, 0)
    with contextlib.suppress(Exception):
        host._config_recibos.append(rotulo)
    return rotulo


# `_abrir_a_aba_sistema` VIVEU AQUI e saiu com o botão dela (LEX-4, 25/08/2026).


def _fileira(titulo: str, *, dica: str | None = None) -> tuple[Any, Any]:
    """Uma fileira "rótulo + controle", devolvida como `(caixa, rótulo)`."""
    from gi.repository import Gtk

    caixa = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL, spacing=_ESPACAMENTO_DA_FILEIRA
    )
    rotulo = _rotulo_simples(titulo)
    if dica is not None:
        rotulo.set_tooltip_text(_(dica))
    caixa.pack_start(rotulo, False, False, 0)
    return caixa, rotulo


def _rotulo_simples(texto: str) -> Any:
    """Rótulo curto de fileira: alinhado à esquerda, sem quebra."""
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    return rotulo
