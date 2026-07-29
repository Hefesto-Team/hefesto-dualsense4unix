"""Refresh por aba: identificação pelo WIDGET, nunca pelo índice da página.

O mapa `page_num -> refresher` era por número. Fundir "Mouse" e "Teclado" na aba
"Navegação DSX" renumerou as páginas seguintes, e um mapa por índice passaria a
chamar o refresher errado **em silêncio** — sem exceção, sem log, só a aba
mostrando dado velho. Estes testes trancam o contrato novo.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("notebook switch page")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
# CI-TYPELIB-PARCIAL-01: `importorskip("gi")` não basta. O módulo `gi` pode
# existir sem as TYPELIBS que o app usa — é o estado do runner do GitHub, onde
# `import gi` funciona e `from gi.repository import GdkPixbuf` estoura
# `ImportError: unknown location`. Como o erro acontece na COLETA, ele não vira
# skip: derruba a suíte inteira com "errors during collection" e reprovou o
# release da v0.1.1. Pular exige checar a typelib que este módulo puxa de
# verdade, e `app.py` importa GdkPixbuf.
pytest.importorskip(
    "gi.repository.GdkPixbuf", reason="precisa da typelib GdkPixbuf"
)
from gi.repository import Gtk

from hefesto_dualsense4unix.app.app import HefestoApp



class _AppFalso:
    """Só o suficiente para exercitar `_on_notebook_switch_page` sem GUI real."""

    _REFRESH_POR_ABA = HefestoApp._REFRESH_POR_ABA
    _ABA_STATUS = HefestoApp._ABA_STATUS
    _on_notebook_switch_page = HefestoApp._on_notebook_switch_page

    def __init__(self) -> None:
        self.chamados: list[str] = []
        self.status_visivel: list[bool] = []
        for nomes in self._REFRESH_POR_ABA.values():
            for nome in nomes:
                setattr(self, nome, lambda n=nome: self.chamados.append(n))

    def set_status_tab_visivel(self, visivel: bool) -> None:
        self.status_visivel.append(visivel)


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


def test_entrar_no_status_liga_a_captura_do_microfone() -> None:
    """S2: o medidor de mic só captura com a aba Status à vista."""
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("tab_status_box"), 1)

    assert app.status_visivel == [True]


def test_sair_do_status_desliga_a_captura() -> None:
    """Sem isto, um `parec` por controle seguiria segurando o microfone da
    usuária com a janela em qualquer outra aba — o incidente de busy-loop da
    v3.8.1 com outra roupa."""
    app = _AppFalso()
    app._on_notebook_switch_page(None, _pagina("tab_status_box"), 1)

    app._on_notebook_switch_page(None, _pagina("tab_triggers_box"), 2)

    assert app.status_visivel == [True, False]


def test_id_da_aba_status_existe_no_glade() -> None:
    """O gate do microfone casa por id de Glade; id errado erra em silêncio."""
    import xml.etree.ElementTree as ET

    from hefesto_dualsense4unix.app.constants import MAIN_GLADE

    arvore = ET.parse(str(MAIN_GLADE))
    ids = {obj.get("id") for obj in arvore.iter("object") if obj.get("id")}

    assert HefestoApp._ABA_STATUS in ids


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
