"""A moldura de uma seção da aba Configurações — o molde único das cinco.

Por que existe um módulo só para isto: em 22/08/2026 a aba Configurações foi
posta lado a lado com as outras dez, e foi a única que leu como quebrada. As
dez seguem a mesma gramática visual desde sempre — cada seção é um
``Gtk.Frame`` com o título no canto, borda fina e conteúdo recuado
(``home_actions.py:1500``, ``:1712``, ``:1756``). A Configurações tinha cinco
``Gtk.Label`` soltos, colados na borda esquerda, sem moldura nenhuma.

O defeito não era de gosto: sem a moldura não há onde o conteúdo morar, e cada
seção nova ficaria à deriva na página. Esta função é a resposta, e é ela que
todas as cinco seções usam — nenhuma monta a própria caixa.

Os números vêm do molde da aba Início, medidos lá e copiados aqui: margem
interna 10 em cima e embaixo, 12 nos lados, e 8 de espaçamento entre filhos.
"""
from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.utils.i18n import _

#: Margens internas do conteúdo de uma seção, em pixels. Cópia do molde da aba
#: Início (`home_actions.py:1501-1505`) — não são valores novos.
MARGEM_VERTICAL = 10
MARGEM_HORIZONTAL = 12
#: Espaçamento entre filhos diretos do conteúdo de uma seção.
ESPACAMENTO = 8


def moldura_de_secao(titulo: str, dica: str | None = None) -> tuple[Any, Any]:
    """Devolve ``(frame, caixa)`` — a moldura e a caixa onde a seção monta.

    O título vai num ``label_widget`` próprio, e não na propriedade ``label``
    do frame, por um motivo prático: assim a dica pousa no TÍTULO e não na
    moldura inteira. Dica em moldura inteira dispara ao passar o mouse em
    qualquer canto da seção, inclusive sobre um botão que tem dica própria — e
    a dica errada aparece por cima da certa.

    Quem chama empacota o ``frame`` na página e monta dentro do ``caixa``.
    """
    from gi.repository import Gtk

    frame = Gtk.Frame()
    rotulo = Gtk.Label(label=_(titulo))
    with contextlib.suppress(Exception):
        rotulo.get_style_context().add_class("hefesto-titulo-secao")
    if dica is not None:
        rotulo.set_tooltip_text(_(dica))
    rotulo.show()
    frame.set_label_widget(rotulo)

    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=ESPACAMENTO)
    caixa.set_margin_top(MARGEM_VERTICAL)
    caixa.set_margin_bottom(MARGEM_VERTICAL)
    caixa.set_margin_start(MARGEM_HORIZONTAL)
    caixa.set_margin_end(MARGEM_HORIZONTAL)
    frame.add(caixa)
    return frame, caixa


def rotulo_de_apoio(texto: str, *, largura_max: int = 92) -> Any:
    """Rótulo explicativo no padrão da casa: alinhado à esquerda e com quebra.

    As três chamadas de ``set_``  são a regra 5 do roteiro da leva, e ela nasceu
    de um defeito medido: um título de 198 caracteres sem quebra pediu 1295px
    numa janela que abre com 1180 e não tem rolagem horizontal.
    """
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    rotulo.set_line_wrap(True)
    rotulo.set_max_width_chars(largura_max)
    with contextlib.suppress(Exception):
        rotulo.get_style_context().add_class("dim-label")
    return rotulo
