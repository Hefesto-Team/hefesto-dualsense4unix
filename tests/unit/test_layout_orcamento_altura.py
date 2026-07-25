"""Orçamento de altura da janela: o conteúdo tem de caber sem barra de rolagem.

O `GtkNotebook` pede como altura mínima o MAIOR mínimo entre todas as páginas —
uma aba gorda vira o piso de todas as outras. Estes testes medem o layout com
`GtkOffscreenWindow` (renderiza de verdade, sem aparecer na tela) e falham se
alguém reintroduzir um bloco que estoure o orçamento.

Histórico do que já custou caro aqui:
  - o `GtkFlowBox` dos 19 modos de gatilho reportava 606px (tudo empilhado);
  - a aba Emulação empilhava 9 blocos e pedia 674px;
  - o scroller de parâmetros reservava 220px fixos mesmo vazio.
"""
from __future__ import annotations

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from hefesto_dualsense4unix.app.constants import GUI_DIR, MAIN_GLADE  # noqa: E402

#: Altura default da janela (`default-height` do glade).
ALTURA_JANELA = 680
#: Teto para o conteúdo. Abaixo disso a barra de rolagem não precisa aparecer.
TETO_CONTEUDO = ALTURA_JANELA
#: Largura de referência — a janela abre com 1100px.
LARGURA = 1100


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


def _montar() -> tuple[Gtk.Builder, Gtk.Widget]:
    """Carrega o glade com o tema aplicado, dentro de uma janela offscreen."""
    provider = Gtk.CssProvider()
    provider.load_from_path(str(GUI_DIR / "theme.css"))
    tela = Gdk.Screen.get_default()
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    root = builder.get_object("root_box")
    pai = root.get_parent()
    if pai is not None:
        pai.remove(root)
    win = Gtk.OffscreenWindow()
    win.get_style_context().add_class("hefesto-dualsense4unix-window")
    win.add(root)
    win.set_size_request(LARGURA, -1)
    win.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    return builder, root


def test_janela_cabe_sem_rolagem() -> None:
    """Header + abas + rodapé têm de caber nos 680px que a janela abre."""
    _builder, root = _montar()

    altura, _ = root.get_preferred_height_for_width(LARGURA)

    assert altura <= TETO_CONTEUDO, (
        f"o conteúdo pede {altura}px e a janela abre com {ALTURA_JANELA}px "
        f"({altura - ALTURA_JANELA}px a mais): a barra de rolagem volta a "
        "aparecer em TODAS as abas, não só na que cresceu"
    )


def test_nenhuma_aba_isolada_estoura_o_orcamento() -> None:
    """Aponta QUAL aba estourou — o teste acima só diz que a soma não cabe.

    Header (~70px) e rodapé (~50px) ficam fora do notebook, então o teto por
    aba é menor que o da janela.
    """
    builder, _root = _montar()
    notebook = builder.get_object("main_notebook")
    teto_por_aba = 520

    gordas = []
    for i in range(notebook.get_n_pages()):
        page = notebook.get_nth_page(i)
        rotulo = notebook.get_tab_label_text(page) or f"#{i}"
        altura, _ = page.get_preferred_height_for_width(LARGURA - 20)
        if altura > teto_por_aba:
            gordas.append(f"{rotulo} ({altura}px)")

    assert not gordas, (
        f"abas acima do teto de {teto_por_aba}px: {', '.join(gordas)}. "
        "Lembre que o notebook adota o MAIOR mínimo — uma aba gorda empurra "
        "todas as outras para a rolagem."
    )
