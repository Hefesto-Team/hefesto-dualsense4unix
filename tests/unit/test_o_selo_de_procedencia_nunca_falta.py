"""Nenhuma linha de ordem existe sem dizer de onde ela veio.

Três selos, e o terceiro **exige nomear o terceiro**: autoridade anônima é
exatamente como raciocínio se veste de medição, e é o motivo de o selo existir.

POR QUE POR AST, E NÃO CHAMANDO AS REGRAS
------------------------------------------

Chamar as seis regras só alcança as `Linha` que a bancada faz nascer. Uma linha
dentro de um ramo que nenhuma fixture cobre passaria em branco — e é justamente
o ramo raro que ninguém revisa. A varredura por AST lê o ARQUIVO e alcança
todas as construções de `Linha`, disparem elas ou não.

O molde é `scripts/validar-fala-de-tela.py`, que lê `NUMEROS_MEDIDOS_NO_MAPA`
sem importar o módulo.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import ordens_da_mesa

#: A raiz da árvore — três níveis acima de `tests/unit/<este arquivo>`.
RAIZ = Path(__file__).resolve().parents[2]

#: O arquivo que a varredura lê. Lido como TEXTO, nunca importado: o ponto do
#: portão é alcançar o ramo que não roda.
FONTE = Path(ordens_da_mesa.__file__)


def _construcoes_de_linha() -> list[ast.Call]:
    """Toda chamada `Linha(...)` do módulo, ache ela um caminho de execução ou não."""
    arvore = ast.parse(FONTE.read_text(encoding="utf-8"))
    return [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "Linha"
    ]


def _argumento(chamada: ast.Call, nome: str) -> ast.expr | None:
    return next(
        (kw.value for kw in chamada.keywords if kw.arg == nome), None
    )


def _constante_do_modulo(no: ast.expr | None) -> object:
    """O valor de `SELO` ou `"texto"` — resolvendo o nome contra o módulo.

    Os selos são escritos como `MEDIDO_AQUI`, não como a string crua. Resolver
    o nome contra o módulo é o que deixa o portão ler o VALOR sem executar o
    arquivo.
    """
    if isinstance(no, ast.Constant):
        return no.value
    if isinstance(no, ast.Name):
        return getattr(ordens_da_mesa, no.id, None)
    return None


def test_ha_linhas_para_varrer() -> None:
    """Um portão que não acha nada para conferir é um portão que mente de verde."""
    assert len(_construcoes_de_linha()) >= 15


def test_toda_linha_declara_um_dos_tres_selos() -> None:
    """Selo é DADO, e só há três. Um quarto valor não existe."""
    for chamada in _construcoes_de_linha():
        selo = _constante_do_modulo(_argumento(chamada, "selo"))
        assert selo in ordens_da_mesa.SELOS, (
            f"linha {chamada.lineno}: selo {selo!r} não é um dos três"
        )


def test_selo_de_terceiro_sem_fonte_nao_existe() -> None:
    """A regra que o portão guarda: terceiro anônimo não é terceiro.

    Tirar o `fonte=` da linha do USB 3.0 reprova aqui.
    """
    for chamada in _construcoes_de_linha():
        selo = _constante_do_modulo(_argumento(chamada, "selo"))
        if selo != ordens_da_mesa.ESPECIFICACAO_DE_TERCEIRO:
            continue
        fonte = _constante_do_modulo(_argumento(chamada, "fonte"))
        assert isinstance(fonte, str) and fonte.strip(), (
            f"linha {chamada.lineno}: selo de terceiro sem nomear o terceiro"
        )


def test_a_fonte_do_selo_existe_em_disco() -> None:
    """A MORDIDA DA ORDEM-7: a fonte é um caminho desta árvore, não um nome solto.

    "Intel" numa string não é uma fonte: ninguém consegue ir conferir. Apagar
    `docs/protocol/por-que-usb3-atrapalha-24ghz.md` reprova aqui.
    """
    conferidas = 0
    for chamada in _construcoes_de_linha():
        selo = _constante_do_modulo(_argumento(chamada, "selo"))
        if selo != ordens_da_mesa.ESPECIFICACAO_DE_TERCEIRO:
            continue
        fonte = _constante_do_modulo(_argumento(chamada, "fonte"))
        assert isinstance(fonte, str)
        assert (RAIZ / fonte).is_file(), (
            f"linha {chamada.lineno}: a fonte {fonte!r} não existe em disco"
        )
        conferidas += 1
    assert conferidas >= 1, "nenhum selo de terceiro foi conferido"


def test_toda_linha_tem_texto_nao_vazio() -> None:
    """Linha muda é o F7 em miniatura: um campo vazio parecendo resposta."""
    for chamada in _construcoes_de_linha():
        texto = _argumento(chamada, "texto")
        assert texto is not None, f"linha {chamada.lineno}: sem texto"
        if isinstance(texto, ast.Constant):
            assert str(texto.value).strip(), f"linha {chamada.lineno}: texto vazio"


def test_o_texto_de_tela_de_cada_selo_existe_e_e_distinto() -> None:
    """Chave de máquina é contrato; texto de tela é da frente do léxico."""
    assert set(ordens_da_mesa.TEXTO_DO_SELO) == set(ordens_da_mesa.SELOS)
    palavras = list(ordens_da_mesa.TEXTO_DO_SELO.values())
    assert len(set(palavras)) == len(palavras)


def test_a_chave_do_selo_e_ascii_com_hifen() -> None:
    """A convenção do `de_onde_sei` do mapa de canais: chave estável, sem acento."""
    for selo in ordens_da_mesa.SELOS:
        assert selo.isascii()
        assert selo == selo.lower()
        assert " " not in selo
        assert "_" not in selo


@pytest.mark.parametrize("selo", ordens_da_mesa.SELOS)
def test_nenhum_selo_promete_medicao_que_nao_houve(selo: str) -> None:
    """`derivado-da-conta` e `especificacao-de-terceiro` não dizem "medido"."""
    if selo == ordens_da_mesa.MEDIDO_AQUI:
        return
    assert "medido" not in selo
