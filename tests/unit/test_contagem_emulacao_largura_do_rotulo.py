"""CONTAGEM-E-COOP-01 (E2) — a frase honesta não pode inflar a largura da aba.

A contagem por aparelho trocou "6 controles detectados pelo sistema" (34 chars)
por uma frase de ~125. O rótulo do glade quebra linha, e um GtkLabel que quebra
pede como largura NATURAL a linha inteira — medido no `Gtk.OffscreenWindow`
com o glade real, 799px contra os 220px do texto antigo. Numa janela larga o
GTK entrega o natural, e o cartão de diagnóstico ficaria com quase o dobro da
largura que o grid inteiro pedia antes.

É a LARGURA-01 desta casa, e o comentário do próprio glade sobre esta linha
registra que foi espremer os blocos desta aba que forçou rolagem em TODAS as
páginas do notebook.

A asserção é RELATIVA de propósito: comparar o pedido com e sem o teto não
depende de fonte nenhuma. A CI mede com outras fontes que a máquina dela — a
lição dos 12px de folga de 29/07 — e um número absoluto aqui reprovaria lá.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("contagem emulacao: largura do rotulo de gamepads")

import inspect

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS,
    EmulationActionsMixin,
    rotulo_gamepads,
)
from hefesto_dualsense4unix.app.constants import MAIN_GLADE

FRASE_LONGA = rotulo_gamepads(1, 1, 2, 6)


def _pedido_do_rotulo(com_teto: bool) -> tuple[int, int]:
    """`(mínimo, natural)` que o rótulo pede dentro do glade REAL."""
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    construtor = Gtk.Builder()
    construtor.add_from_file(str(MAIN_GLADE))
    rotulo = construtor.get_object("emulation_js_label")
    caixa = construtor.get_object("emulation_box")
    caixa.get_parent().remove(caixa)
    janela = Gtk.OffscreenWindow()
    janela.add(caixa)
    janela.show_all()
    rotulo.set_text(FRASE_LONGA)
    if com_teto:
        rotulo.set_line_wrap(True)
        rotulo.set_max_width_chars(LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS)
    while Gtk.events_pending():
        Gtk.main_iteration()
    return rotulo.get_preferred_width()


class TestOTetoDeQuebra:
    def test_o_teto_encolhe_o_pedido_natural(self) -> None:
        _, sem_teto = _pedido_do_rotulo(com_teto=False)
        _, com_teto = _pedido_do_rotulo(com_teto=True)
        assert com_teto < sem_teto

    def test_o_teto_nao_mexe_no_minimo_da_aba(self) -> None:
        """O mínimo é a maior palavra, e é ele que decide a rolagem do notebook.

        Se algum dia alguém "curar" o espremido com `set_width_chars`, este
        teste é o que denuncia: o mínimo subiria e a aba voltaria a empurrar
        todas as páginas.
        """
        minimo_sem, _ = _pedido_do_rotulo(com_teto=False)
        minimo_com, _ = _pedido_do_rotulo(com_teto=True)
        assert minimo_com == minimo_sem

    def test_a_aba_aplica_o_teto(self) -> None:
        """Sem esta chamada a constante existiria e não protegeria nada."""
        fonte = inspect.getsource(EmulationActionsMixin._refresh_emulation_view)
        assert "set_max_width_chars(LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS)" in fonte
