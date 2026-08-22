"""Seção 1 da aba Configurações — um card por controle da mesa.

Aqui entra o que o aparelho não anuncia e o produto não deduz: o modo em que um
controle não-Sony foi ligado, o rótulo dos botões, e a cor do plástico quando a
leitura falha. Todo campo nasce em "não sei", e "não sei" é resposta válida.

TERRITÓRIO DE CONFIG-06. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

from typing import Any

#: O título como ela o lê na tela.
TITULO = "Os controles"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "A borda de cada card é a cor do plástico daquele controle. O anel roxo "
    "por dentro marca qual está selecionado no cabeçalho da janela."
)


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
