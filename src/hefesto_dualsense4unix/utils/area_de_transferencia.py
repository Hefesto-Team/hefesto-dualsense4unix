"""A área de transferência que a moldura entrega à lógica.

O «Copiar» da aba Sistema precisa da área de transferência, que é do GTK e mora na moldura
(`interface/janela.por_na_area_de_transferencia`). A lógica não importa a moldura: a moldura que
nasce entrega a sua função aqui (`receber`), e o «Copiar» pede por `por`
(A-LISTA-DO-WEBKIT-DA-SUITE-VOLTA-AO-TAMANHO-REAL-01).
Sem moldura (um teste, a bandeja, um python sem `gi`), `por` diz `False`, e a aba diz que não deu.
"""
from __future__ import annotations

from collections.abc import Callable

_A_DA_MOLDURA: list[Callable[[str], bool]] = []


def receber(por_o_texto: Callable[[str], bool]) -> None:
    """A moldura entrega a função que põe o texto na área de transferência (a última vale)."""
    _A_DA_MOLDURA[:] = [por_o_texto]


def por(texto: str) -> bool:
    """O texto na área de transferência da moldura. `False` = não há moldura, ou não deu."""
    if not _A_DA_MOLDURA:
        return False
    try:
        return bool(_A_DA_MOLDURA[0](texto))
    except Exception:
        return False
