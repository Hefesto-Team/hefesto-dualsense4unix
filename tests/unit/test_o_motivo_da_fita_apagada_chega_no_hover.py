"""A fita apagada diz por quê — no hover, e nunca pintada (24/08/2026).

A DECISÃO, e ela tem duas metades que brigam
--------------------------------------------

A Z2-8 fez SEIS abas esmaecerem a fita "Ajustes vão para:" (Início, No jogo,
Perfis, Sistema, Emulação, Navegação), além da Configurações que já esmaecia.
O motivo de cada uma era **guardado e nunca mostrado**: existia só para o
portão da Z2-9 ler. Quem usasse o produto via a fita apagada e não tinha como
saber se aquilo era escolha ou defeito.

A outra metade é a decisão de 23/08/2026, que continua inteira: **o
cabeçalho não ganha um pixel**. A versão que pendurava um rótulo ao lado da
fita empurrava altura e largura, cobria o subtítulo do produto e deixava a aba
visivelmente mais larga que as outras dez — o usuário mandou tirar, e o motivo é
válido para qualquer explicação que ocupe espaço.

Tooltip resolve as duas: aparece só com o ponteiro parado em cima, e ocupa
zero.

A ARMADILHA, medida ANTES de escrever a cura
--------------------------------------------

**No GTK3, um widget insensível não recebe evento de mouse.** Pôr o tooltip na
própria fita (que é quem leva ``set_sensitive(False)``) deixaria a propriedade
posta e a frase nunca exibida:

    >>> caixa.set_tooltip_text("motivo"); caixa.set_sensitive(False)
    >>> caixa.get_property("has-tooltip")   # True  — parece que funcionou
    >>> caixa.is_sensitive()                # False — e por isso nunca dispara

Seria cura escrita e nunca ligada, que é o defeito mais caro desta casa. Por
isso a fita vai dentro de um ``Gtk.EventBox`` que fica SENSÍVEL e carrega o
tooltip; ``set_visible_window(False)`` o mantém sem pintura própria, para o
cabeçalho continuar com o mesmo tamanho de sempre.

AS MORDIDAS
-----------

* Mova o ``set_tooltip_text`` de volta para a fita (``_target_strip``) em vez
  do ``EventBox``: ``test_o_tooltip_mora_em_widget_que_recebe_o_ponteiro``
  reprova, porque o dono do tooltip volta a ser insensível.
* Apague a chamada de ``set_tooltip_text`` de ``set_alvo_inativo``:
  ``test_a_aba_que_nao_le_o_alvo_explica_no_hover`` reprova — é o estado de
  antes desta data, com o motivo guardado e mudo.
* Faça o ``EventBox`` pintar (``set_visible_window(True)``):
  ``test_a_moldura_do_hover_nao_pinta_nada`` reprova, porque o cabeçalho
  passaria a ter um retângulo que ele não tinha.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o tooltip da fita do alvo")


import gi

gi.require_version("Gtk", "3.0")


from gi.repository import Gtk


class _HostDaFita:
    """O mínimo que `set_alvo_inativo` toca: a fita e a moldura do hover."""

    def __init__(self) -> None:
        self._target_strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._target_strip.pack_start(Gtk.Label(label="Ajustes vão para:"), False, False, 0)
        self._target_strip_hover = Gtk.EventBox()
        self._target_strip_hover.set_visible_window(False)
        self._target_strip_hover.add(self._target_strip)


def test_a_moldura_do_hover_nao_pinta_nada() -> None:
    """A decisão de 23/08 continua de pé: o cabeçalho não ganha um pixel."""
    host = _HostDaFita()
    assert host._target_strip_hover.get_visible_window() is False, (
        "o EventBox está pintando: o cabeçalho ganharia um retângulo que não "
        "tinha, que é exatamente o defeito do rótulo que ela mandou tirar"
    )


