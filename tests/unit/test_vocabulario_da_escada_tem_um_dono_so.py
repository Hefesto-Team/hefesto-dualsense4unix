"""Z6-01 — o vocabulário (`ESCADA`, `DOMINIO_POR_SUFIXO`, `DOMINIO_EXISTE`) tem"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

import check_paridade_transporte as portao


def test_dominio_de_ate_onde_foi_e_derivado_da_escada_nao_redigitado() -> None:
    """A mordida, sem precisar recompilar a árvore: prova a DERIVAÇÃO."""
    esperado = frozenset({"", *portao.VALORES_DA_ESCADA})
    assert portao.DOMINIO_POR_SUFIXO["ate_onde_foi"] == esperado


def test_gerador_de_fatos_de_tela_nao_redigita_nenhum_degrau() -> None:
    """Nenhum literal de `ESCADA` aparece hardcoded em `gerar-fatos-de-tela.py`."""
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
