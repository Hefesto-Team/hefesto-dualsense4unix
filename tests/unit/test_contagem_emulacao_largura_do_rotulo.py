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
    EmulationActionsMixin,
    rotulo_gamepads,
)

FRASE_LONGA = rotulo_gamepads(1, 1, 2, 6)

class TestOTetoDeQuebra:
    """06/09/2026 (`GTK-3`): os DOIS testes de medição saíram com a janela.

    `test_o_teto_encolhe_o_pedido_natural` e `test_o_teto_nao_mexe_no_minimo_da_aba`
    montavam o `emulation_js_label` do `gui/main.glade` numa
    `Gtk.OffscreenWindow` e comparavam o pedido de largura com e sem o teto —
    a aba Emulação da janela GTK, aposentada por decisão dela
    (`D-0609-GTK-LEVA-INTEIRA`). O que fica é a única asserção que não precisa
    da janela: que o mixin CHAMA o teto. **O que se perde é a prova do efeito**,
    e a frase honesta que a inflava hoje é escrita em HTML —
    `interface/paginas/09-sistema.html` —, onde a largura é CSS e não pedido de
    widget.
    """

    def test_a_aba_aplica_o_teto(self) -> None:
        """Sem esta chamada a constante existiria e não protegeria nada."""
        fonte = inspect.getsource(EmulationActionsMixin._refresh_emulation_view)
        assert "set_max_width_chars(LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS)" in fonte
