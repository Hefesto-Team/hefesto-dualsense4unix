"""Seção 2 da aba Configurações — os adaptadores, a vizinhança e o rádio.

O que a máquina responde sozinha (adaptadores, rádios vizinhos, hub, topologia
USB) é LIDO; o que nenhum barramento sabe (altura da antena, linha de visada) é
declarado. A ordem importa: onde a leitura acerta, ela pré-preenche.

TERRITÓRIO DE CONFIG-02, e do medidor de rádio de CONFIG-04. Quem trabalha
nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

from typing import Any

#: O título como ela o lê na tela.
TITULO = "A mesa"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "O Hefesto enxerga os adaptadores, mas não enxerga onde eles estão. Cabo, "
    "hub e altura mudam o alcance e não aparecem em lugar nenhum do sistema."
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
