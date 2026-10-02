"""Z2-11 — o contrato, e os dois números errados."""
from __future__ import annotations

import ast
from pathlib import Path

from hefesto_dualsense4unix.app import alvo_de_edicao

_SRC = Path(alvo_de_edicao.__file__).resolve().parents[2]
_ARQUIVO_DONO = Path(alvo_de_edicao.__file__).resolve()


def _leitores_por_getattr_do_campo_legado() -> list[tuple[Path, int]]:
    """Achados de `getattr(<algo>, "_edit_target_uniq", ...)` em `src/`."""
    achados: list[tuple[Path, int]] = []
    for caminho in sorted(_SRC.rglob("*.py")):
        if caminho.resolve() == _ARQUIVO_DONO:
            continue
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            func = no.func
            if not (isinstance(func, ast.Name) and func.id == "getattr"):
                continue
            if len(no.args) < 2:
                continue
            segundo = no.args[1]
            if (
                isinstance(segundo, ast.Constant)
                and segundo.value == "_edit_target_uniq"
            ):
                achados.append((caminho, no.lineno))
    return achados


def test_zero_leitores_por_getattr_fora_do_dono() -> None:
    """A MORDIDA: os sete leitores por `getattr` migraram — hoje são ZERO."""
    achados = _leitores_por_getattr_do_campo_legado()
    assert achados == [], (
        f"getattr do campo legado fora do dono: {achados} — os sete "
        "leitores da P3 tinham migrado nesta leva (ONDA0-Z2)"
    )


def test_a_docstring_do_dono_nao_repete_o_numero_errado() -> None:
    """O número errado ("nove") não pode voltar à docstring."""
    doc = alvo_de_edicao.__doc__ or ""
    assert "nove leitores" not in doc
    assert "nove pontos" not in doc
    assert "sete pontos da janela" in doc, (
        "a docstring perdeu o número medido (7, §2.2 da sprint ONDA0-Z2) — "
        "sem ele ao lado, o próximo agente não tem como saber se está certo"
    )
    assert "seis arquivos" in doc


def test_a_frase_de_outra_leva_ganhou_nota_datada() -> None:
    """"Migrá-los é de outra leva" não pode seguir viva SEM NOTA — a leva"""
    doc = alvo_de_edicao.__doc__ or ""
    assert "a leva foi esta" in doc, (
        "a frase 'migrá-los é de outra leva' precisa da nota datada que diz "
        "que a leva foi esta (ONDA0-Z2) — regra da casa: decisão que caduca "
        "não se apaga, ganha nota"
    )
    assert "ONDA0-Z2" in doc and "24/08/2026" in doc
