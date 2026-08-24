"""Z6-01 — o vocabulário (`ESCADA`, `DOMINIO_POR_SUFIXO`, `DOMINIO_EXISTE`) tem
um dono só: `scripts/check_paridade_transporte.py`.

A mordida da sprint
(docs/process/sprints/2026-08-24-ONDA0-Z6-COMUNHAO-COM-O-SPECS-01-…md, Z6-01):
"acrescentar um degrau à `ESCADA` e ver o gerador da Z6-02 emitir o degrau
novo **sem edição própria**; tirar o import e ver o teste reprovar."

`scripts/gerar-mapa.py` já importava `ESCADA` de lá antes desta leva — este
arquivo prova que `scripts/gerar-fatos-de-tela.py` (Z6-02, novo) segue a mesma
regra: o domínio de `ate_onde_foi` que ele aceita é `DOMINIO_POR_SUFIXO`, e
`DOMINIO_POR_SUFIXO["ate_onde_foi"]` é DERIVADO de `ESCADA`
(`frozenset({"", *VALORES_DA_ESCADA})`), nunca uma lista redigitada. Um degrau
novo em `ESCADA` alarga esse domínio sozinho — nenhum dos dois geradores
precisa saber o nome do degrau novo.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

import check_paridade_transporte as portao


def test_dominio_de_ate_onde_foi_e_derivado_da_escada_nao_redigitado() -> None:
    """A mordida, sem precisar recompilar a árvore: prova a DERIVAÇÃO.

    Se algum dia `DOMINIO_POR_SUFIXO["ate_onde_foi"]` virar uma lista literal
    escrita à mão (a régua torna a mentir sobre a legenda), este teste
    reprova — é a garantia de que "acrescentar um degrau" de fato alarga o
    domínio sem editar o portão nem o gerador.
    """
    esperado = frozenset({"", *portao.VALORES_DA_ESCADA})
    assert portao.DOMINIO_POR_SUFIXO["ate_onde_foi"] == esperado


def test_gerador_de_fatos_de_tela_nao_redigita_nenhum_degrau() -> None:
    """Nenhum literal de `ESCADA` aparece hardcoded em `gerar-fatos-de-tela.py`.

    ARRANQUE: colar `if valor == "MONTOU": ...` (ou qualquer outro degrau) no
    gerador faz este teste reprovar — é exatamente a redigitação que a Z6-01
    proíbe.
    """
    fonte = (RAIZ / "scripts" / "gerar-fatos-de-tela.py").read_text(encoding="utf-8")
    for degrau in portao.VALORES_DA_ESCADA:
        assert degrau not in fonte, (
            f"gerar-fatos-de-tela.py contém o literal {degrau!r} — o "
            "vocabulário da ESCADA tem um dono só (check_paridade_transporte)"
        )


def test_gerador_de_fatos_de_tela_importa_o_vocabulario_do_portao() -> None:
    """O import é de fato o do portão — não uma cópia local com o mesmo nome."""
    fonte = (RAIZ / "scripts" / "gerar-fatos-de-tela.py").read_text(encoding="utf-8")
    assert "from check_paridade_transporte import" in fonte
    assert "DOMINIO_POR_SUFIXO" in fonte
    assert "DOMINIO_EXISTE" in fonte
