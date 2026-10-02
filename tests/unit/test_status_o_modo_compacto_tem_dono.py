"""STATUS-DIZ-O-QUE-VÊ-01/T5 — o modo compacto do card tem de ter um dono."""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


def _chamadas_com_compact_verdadeiro() -> list[str]:
    """Toda chamada de produção que passa ``compact=True``, com o endereço."""
    achados: list[str] = []
    for arquivo in sorted(_SRC.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — arquivo quebrado é outro erro
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            for palavra in no.keywords:
                if (
                    palavra.arg == "compact"
                    and isinstance(palavra.value, ast.Constant)
                    and palavra.value.value is True
                ):
                    relativo = arquivo.relative_to(_SRC.parents[1])
                    achados.append(f"{relativo}:{no.lineno}")
    return achados


def test_o_modo_compacto_tem_dono() -> None:
    """Ou nenhum código de produção pede o card compacto, ou alguém o pede."""
    chamadas = _chamadas_com_compact_verdadeiro()
    assert not chamadas, (
        "código de produção voltou a construir o card COMPACTO: "
        f"{chamadas}. Desde a EMPILHA-02 (02/08/2026) a aba dá a largura "
        "inteira a todo card — se a volta é intencional, escreva aqui quem "
        "constrói o modo compacto e quando"
    )


