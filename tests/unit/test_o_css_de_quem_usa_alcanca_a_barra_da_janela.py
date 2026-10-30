"""O CSS de quem usa alcança a barra da janela, que é GTK e fica fora da página.

A regra que começa por ``headerbar`` vale na barra; a régua não deixa ela esconder nem empurrar
os botões, a declaração que o GTK não entende fica de fora sozinha, e o CSS desligado devolve a
barra ao padrão.

Mordidas:
- o ``vestir_a_barra_de_quem_usa`` que carrega vazio reprova
  ``test_o_css_pinta_o_botao_e_desligar_devolve_o_padrao``;
- o ``_conferir_na_janela`` que não confere reprova ``test_a_regua_nao_deixa_a_barra_sem_saida``;
- o ``_VAR`` que não troca reprova
  ``test_o_token_do_tema_vira_a_cor_e_o_que_o_gtk_nao_entende_sai``;
- o ``trocar_o_tema`` sem o ``vestir_a_barra_de_quem_usa`` reprova
  ``test_ligar_e_desligar_o_css_repinta_a_barra_sem_reabrir``.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.janela`, que carrega o GTK")

from gi.repository import Gtk

from hefesto_dualsense4unix.interface import janela as ponte_da_tela
from hefesto_dualsense4unix.mods import meu_css

EXEMPLO = """\
.quadro { opacity: 0.5; }
headerbar button.fechar { background: #ff0000; border-radius: 50%; }
headerbar .title { font-weight: bold !important; }
@media (min-width: 1px) { headerbar .subtitle { color: #00ff00; } }
"""


@pytest.mark.parametrize(("css", "curta"), [
    ("headerbar { opacity: 0; }", "Linha 1: opacity na barra"),
    ("headerbar .title { color: transparent; }", "Linha 1: letra invisível"),
    ("headerbar button { margin: -30px; }", "Linha 1: medida negativa"),
    ("\nheaderbar { min-height: 200px; }", "Linha 2: grande demais"),
])
def test_a_regua_nao_deixa_a_barra_sem_saida(css: str, curta: str) -> None:
    """A prova da D-3010-O-CSS-DE-QUEM-USA-ALCANCA-A-JANELA-INTEIRA."""
    with pytest.raises(meu_css.CssRecusadoError) as recusa:
        meu_css.aplicar(css)
    assert recusa.value.curta == curta


def test_so_as_regras_headerbar_do_topo_vao_para_a_barra() -> None:
    folha = meu_css.aplicar(EXEMPLO)
    assert meu_css.regras_da_janela(folha) == (
        ("headerbar button.fechar", "background:#ff0000"),
        ("headerbar button.fechar", "border-radius:50%"),
        ("headerbar .title", "font-weight:bold"),
    )


def test_o_token_do_tema_vira_a_cor_e_o_que_o_gtk_nao_entende_sai() -> None:
    folha = meu_css.aplicar(
        "headerbar button.fechar { background: var(--red); color: banana; }")
    texto = ponte_da_tela.css_da_barra_de_quem_usa(folha, ":root{--red:#123456 !important;}")
    assert texto == "headerbar button.fechar { background:#123456; }"


@pytest.fixture
def barra() -> Iterator[tuple[object, dict[str, object], object]]:
    provedor = Gtk.CssProvider()
    barra, botoes = ponte_da_tela.montar_a_barra("Hefesto", "", lambda *_: None)
    janela = Gtk.OffscreenWindow()
    janela.add(barra)
    janela.show_all()
    tela = barra.get_screen()
    Gtk.StyleContext.add_provider_for_screen(tela, provedor, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    try:
        yield barra, botoes, provedor
    finally:
        Gtk.StyleContext.remove_provider_for_screen(tela, provedor)
        janela.destroy()


def _fundo(botao: object) -> str:
    fim = time.monotonic() + 0.3
    while time.monotonic() < fim:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.01)
    contexto = botao.get_style_context()  # type: ignore[attr-defined]
    return contexto.get_property("background-color", contexto.get_state()).to_string()


def test_o_css_pinta_o_botao_e_desligar_devolve_o_padrao(barra: tuple) -> None:
    """A prova da D-3010-O-CSS-DE-QUEM-USA-ALCANCA-A-JANELA-INTEIRA."""
    _barra, botoes, provedor = barra
    fechar, minimizar = botoes["fechar"], botoes["minimizar"]
    assert fechar.get_style_context().has_class("fechar")
    padrao = _fundo(fechar)
    ponte_da_tela.vestir_a_barra_de_quem_usa(provedor, meu_css.aplicar(EXEMPLO))
    assert _fundo(fechar) == "rgb(255,0,0)"
    assert _fundo(minimizar) == padrao
    ponte_da_tela.vestir_a_barra_de_quem_usa(provedor, "")
    assert _fundo(fechar) == padrao


def test_ligar_e_desligar_o_css_repinta_a_barra_sem_reabrir() -> None:
    from types import SimpleNamespace

    class PonteDeMentira:
        meu_css = ""

        def trocar_o_tema(self, _folha: str, meu: str | None = None) -> None:
            if meu is not None:
                self.meu_css = meu

    vista = SimpleNamespace(ponte=PonteDeMentira(), _cor_da_barra=Gtk.CssProvider(),
                            _barra_de_quem_usa=Gtk.CssProvider())
    ponte_da_tela.JanelaDaAba.trocar_o_tema(vista, "", meu_css.aplicar(EXEMPLO))
    assert "button.fechar" in vista._barra_de_quem_usa.to_string()
    ponte_da_tela.JanelaDaAba.trocar_o_tema(vista, "", "")
    assert vista._barra_de_quem_usa.to_string().strip() == ""
