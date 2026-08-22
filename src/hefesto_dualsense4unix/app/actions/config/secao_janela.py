"""Seção 4 da aba Configurações — ajustes do programa, não dos controles.

Tamanho do texto, ambiente da área de trabalho, ícone na barra do sistema e o
espelho de "Ligar junto com o computador", que mora na aba Sistema.

O ambiente detectado informa a MENSAGEM DE AJUDA, nunca o comportamento:
`XDG_CURRENT_DESKTOP` pode vir vazia ou composta, e a aba abre igual nos três
casos.

TERRITÓRIO DE CONFIG-07. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

from typing import Any

#: O título como ela o lê na tela.
TITULO = "A janela"

#: Sem dica, e de propósito: no desenho aprovado esta seção também não tem.
#: Os rótulos dela se explicam sozinhos, e inventar uma explicação aqui seria
#: pôr na tela uma frase que ninguém aprovou.
DICA: str | None = None


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.
    """
