"""A régua do portão `nada novo aponta para a janela` — sprint GTK-1, 06/09/2026."""

from __future__ import annotations

import importlib.util
from pathlib import Path


RAIZ_DE_VERDADE = Path(__file__).resolve().parents[2]
PORTAO = RAIZ_DE_VERDADE / "scripts" / "check_nada_aponta_para_a_janela.py"


def _carregar_portao():
    """Importa o portão como módulo próprio, sem poluir `sys.modules` de ninguém."""
    espec = importlib.util.spec_from_file_location(
        "portao_nada_aponta_para_a_janela", PORTAO
    )
    assert espec and espec.loader
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


_CABECALHO = "# inventário de mentira, só para a régua\n"
_COLUNAS = (
    "arquivo,linhas,alvo,natureza,ocorrencias,pergunta_respondida,veredito,razao\n"
)


def test_o_portao_nao_se_varre_a_si_mesmo():
    """O script, o CSV e este arquivo citam os alvos porque SÃO o instrumento."""
    modulo = _carregar_portao()
    assert "scripts/check_nada_aponta_para_a_janela.py" in modulo._NAO_SE_VARRE
    assert "tests/unit/test_nada_novo_aponta_para_a_janela.py" in modulo._NAO_SE_VARRE
    assert "docs/data/o-que-ainda-aponta-para-a-janela.csv" in modulo._NAO_SE_VARRE


def test_a_prosa_nao_e_chamada():
    """`tokenize`, não `grep`: a sprint avisa que a maioria das citações é comentário."""
    modulo = _carregar_portao()
    fonte = (
        "import os\n"
        "# o texto vem de main.glade, em prosa\n"
        'CAMINHO = "main.glade"\n'
        '"""docstring que cita main.glade também."""\n'
    )
    prosa = modulo._prosa_do_python(fonte)
    natureza = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        for _, coluna in modulo._alvos_da_linha(linha):
            natureza.append(modulo._natureza(linha, coluna, numero, ".py", prosa))
    assert natureza == ["prosa", "código", "prosa"], natureza


def test_os_tres_vereditos_sao_os_do_plano():
    modulo = _carregar_portao()
    assert {
        "SAI-COM-A-JANELA",
        "MOTOR-MUDA-DE-CASA",
        "NUNCA-DEVIA-CITAR",
    } == modulo.VEREDITOS


def test_o_inventario_de_verdade_existe_e_esta_declarado_por_inteiro():
    """A árvore de verdade passa no portão, e o inventário não está vazio."""
    modulo = _carregar_portao()
    inventario = modulo.ler_o_inventario()
    assert inventario, "o inventário da GTK-1 não pode nascer vazio"
    for linha in inventario:
        assert linha["veredito"] in modulo.VEREDITOS, linha
        assert linha["pergunta_respondida"].strip(), linha
        assert linha["razao"].strip(), linha
