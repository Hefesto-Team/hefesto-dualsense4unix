"""Seção 3 da aba Configurações — o teto de recursos da mesa inteira.

Economia, Balanceado, Máximo e Auto: o mesmo vocabulário que a aba Rumble já
mostra, porque `RumbleConfig.policy` já grava esses valores e renomear
quebraria os perfis gravados no disco.

Teto, não troca: escolher Economia não desliga nada e não apaga ajuste nenhum.

TERRITÓRIO DE CONFIG-05. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

from typing import Any

#: O título como ela o lê na tela.
TITULO = "Orçamento"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "Um teto para a mesa inteira. As abas continuam mandando no que fazem — "
    "só não passam daqui. Nenhum ajuste seu é apagado."
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
