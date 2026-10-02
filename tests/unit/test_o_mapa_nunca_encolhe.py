"""O mapa de canais NUNCA encolhe, e o piso é dado, não palpite."""
from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

PISO_DE_LINHAS = 308

COLUNAS_DO_GRAO = ("chave", "controle", "cabo_de_onde_sei", "radio_de_onde_sei")


def _mapa() -> tuple[list[str], list[dict]]:
    with open(MAPA, encoding="utf-8", newline="") as fh:
        leitor = csv.DictReader(fh)
        return list(leitor.fieldnames or []), list(leitor)


def test_o_mapa_nao_encolheu():
    _, linhas = _mapa()
    assert len(linhas) >= PISO_DE_LINHAS, (
        f"o mapa tem {len(linhas)} linhas e o piso é {PISO_DE_LINHAS}. "
        "Alguém regenerou por cima do trabalho dos agentes. NÃO baixe este "
        "número para ficar verde: descubra o que apagou as linhas."
    )


def test_o_grao_continua_sendo_chave_por_controle():
    cabecalho, _ = _mapa()
    faltando = [c for c in COLUNAS_DO_GRAO if c not in cabecalho]
    assert not faltando, (
        f"o mapa perdeu as colunas {faltando}: o formato regrediu para um "
        "anterior ao de 11/08/2026"
    )
    assert cabecalho[0] == "chave", (
        f"a primeira coluna é {cabecalho[0]!r} e devia ser 'chave' — no formato "
        "antigo ela era 'id', então isto é um mapa de antes da migração"
    )


def test_o_trabalho_dos_agentes_continua_no_mapa():
    """As referências de código que eles preencheram são o lastro das inferências."""
    _, linhas = _mapa()
    com_ref = sum(
        1
        for lin in linhas
        for lado in ("cabo", "radio")
        if (lin.get(f"{lado}_codigo_ref") or "").strip()
    )
    assert com_ref >= 500, (
        f"só {com_ref} células citam arquivo em `codigo_ref`, e eram 507 em "
        "05/09/2026. É por essa coluna que o `specs.html` conta quantas "
        "inferências o driver do kernel sustenta — perdê-la é desconsiderar o "
        "trabalho dos agentes de novo."
    )


def test_o_migrador_de_uma_vez_so_nao_voltou():
    """Ele apagava 104 linhas num comando. Se alguém o recriar, esta régua avisa."""
    morto = RAIZ / "scripts" / "migrar-mapa-v2.py"
    assert not morto.exists(), (
        "`scripts/migrar-mapa-v2.py` voltou ao disco. Ele é um migrador de uma "
        "vez só que JÁ RODOU em 11/08/2026, e rodá-lo de novo escreve o retrato "
        "daquele dia por cima do mapa de hoje. Se a intenção é outra migração, "
        "ela precisa de nome próprio e de ler o mapa de HOJE como fonte."
    )
