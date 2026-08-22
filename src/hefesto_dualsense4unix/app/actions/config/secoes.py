"""A ORDEM das cinco seções da aba — a única lista, e ela mora aqui.

Separada do `mixin.py` de propósito: o montador importa esta lista, e as
seções importam a moldura. Sem este arquivo no meio, `mixin` importaria os
cinco módulos e qualquer um deles que quisesse uma constante do montador
fecharia um ciclo de importação.

Acrescentar uma seção é acrescentar uma linha aqui. Trocar a ordem da tela é
trocar a ordem aqui — e nada mais em lugar nenhum.
"""
from __future__ import annotations

from types import ModuleType

from hefesto_dualsense4unix.app.actions.config import (
    secao_controles,
    secao_exame,
    secao_janela,
    secao_mesa,
    secao_orcamento,
)

#: As cinco, na ordem do desenho aprovado. Cada módulo declara `TITULO`,
#: `DICA` e `montar(host, caixa)`.
SECOES_DA_ABA: tuple[ModuleType, ...] = (
    secao_exame,
    secao_controles,
    secao_mesa,
    secao_orcamento,
    secao_janela,
)

#: `(título, dica)` de cada seção, derivado da lista acima.
#:
#: Existe porque os portões de tela e a suíte leem os títulos sem querer saber
#: de módulo nenhum — e porque derivar impede a divergência clássica: uma lista
#: de títulos que envelhece ao lado dos títulos de verdade.
SECOES: tuple[tuple[str, str | None], ...] = tuple(
    (secao.TITULO, secao.DICA) for secao in SECOES_DA_ABA
)
