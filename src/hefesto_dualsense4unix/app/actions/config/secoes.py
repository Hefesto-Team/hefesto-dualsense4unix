"""A ORDEM das cinco seções da aba — a única lista, e ela mora aqui."""
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
SECOES_DA_ABA: tuple[ModuleType, ...] = (
    secao_exame,
    secao_controles,
    secao_mesa,
    secao_orcamento,
    secao_janela,
)

SECOES: tuple[tuple[str, str | None], ...] = tuple(
    (secao.TITULO, secao.DICA) for secao in SECOES_DA_ABA
)
