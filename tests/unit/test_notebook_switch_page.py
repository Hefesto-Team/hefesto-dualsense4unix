"""Refresh por aba: identificação pelo WIDGET, nunca pelo índice da página.

O mapa `page_num -> refresher` era por número. Fundir "Mouse" e "Teclado" na aba
"Navegação DSX" renumerou as páginas seguintes, e um mapa por índice passaria a
chamar o refresher errado **em silêncio** — sem exceção, sem log, só a aba
mostrando dado velho. Estes testes trancam o contrato novo.
"""
from __future__ import annotations

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from hefesto_dualsense4unix.app.app import HefestoApp  # noqa: E402


class _AppFalso:
    """Só o suficiente para exercitar `_on_notebook_switch_page` sem GUI real."""

    _REFRESH_POR_ABA = HefestoApp._REFRESH_POR_ABA
    _on_notebook_switch_page = HefestoApp._on_notebook_switch_page

    def __init__(self) -> None:
        self.chamados: list[str] = []
        for nomes in self._REFRESH_POR_ABA.values():
            for nome in nomes:
                setattr(self, nome, lambda n=nome: self.chamados.append(n))


def _pagina(nome: str) -> Gtk.Widget:
    page = Gtk.Box()
    Gtk.Buildable.set_name(page, nome)
    return page


def test_aba_unificada_roda_os_dois_refreshers() -> None:
    """"Navegação DSX" herda o refresh que era de Mouse E o que era de Teclado."""
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("tab_navegacao_dsx"), 8)

    assert app.chamados == ["_refresh_mouse_tab", "_refresh_key_bindings_from_draft"]


def test_pagina_dentro_de_scrolledwindow_ainda_e_reconhecida() -> None:
    """`_wrap_notebook_pages_in_scroll` embrulha cada página; o id fica no filho.

    Sem desembrulhar, NENHUMA aba dispararia refresh — o widget que chega no
    handler seria o scroller anônimo.
    """
    app = _AppFalso()
    scroller = Gtk.ScrolledWindow()
    scroller.add(_pagina("tab_triggers_box"))

    app._on_notebook_switch_page(None, scroller, 2)

    assert app.chamados == ["_refresh_triggers_from_draft"]


def test_aba_sem_refresher_nao_quebra() -> None:
    """Status não tem refresher no mapa (ele roda por polling próprio)."""
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("tab_status_box"), 1)

    assert app.chamados == []


def test_todo_id_do_mapa_existe_no_glade() -> None:
    """Um id errado no mapa falha em SILÊNCIO — é o bug que isto previne."""
    import xml.etree.ElementTree as ET

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    arvore = ET.parse(str(MAIN_GLADE))
    ids_no_glade = {
        obj.get("id") for obj in arvore.iter("object") if obj.get("id")
    }

    faltando = set(HefestoApp._REFRESH_POR_ABA) - ids_no_glade
    assert not faltando, (
        f"ids no mapa de refresh que não existem no glade: {sorted(faltando)}"
    )
