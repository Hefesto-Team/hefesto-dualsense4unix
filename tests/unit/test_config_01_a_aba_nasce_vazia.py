"""CONFIG-01 — a décima primeira aba existe, nasce vazia e não custa largura."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("aba configurações")


import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import SECOES

ROTULO_DA_ABA = "Configurações"


def _titulo_da_moldura(frame: Gtk.Widget) -> str | None:
    """O texto do `label_widget` de uma moldura de seção, ou `None`."""
    rotulo = frame.get_label_widget()
    return None if rotulo is None else rotulo.get_text()


def test_nenhum_titulo_promete_numero() -> None:
    """Rótulo estático é honesto; valor inventado não é."""
    for titulo, dica in SECOES:
        assert not any(caractere.isdigit() for caractere in titulo), (
            f"o título {titulo!r} promete um número que ninguém mediu"
        )
        if dica is not None:
            assert not any(caractere.isdigit() for caractere in dica), (
                f"a dica de {titulo!r} promete um número que ninguém mediu"
            )


