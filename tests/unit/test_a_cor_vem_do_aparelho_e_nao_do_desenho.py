#!/usr/bin/env python3
"""A régua do ``check_a_cor_vem_do_aparelho.py`` — e o que ela NÃO pode acusar."""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts/check_a_cor_vem_do_aparelho.py"
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

CRAVADOS_EM_03_09 = 360


def _portao() -> object:
    spec = importlib.util.spec_from_file_location("portao_da_cor", PORTAO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["portao_da_cor"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def portao() -> object:
    return _portao()


@pytest.fixture(scope="module")
def colorways(portao: object) -> set[str]:
    return portao.colorways_do_mapa()


def _conta(portao: object, colorways: set[str], html: str,
           familia: str = "") -> int:
    achados = portao.cravados_no_texto(html, colorways)
    return sum(a[4] for a in achados if not familia or a[1] == familia)


def _folha(colorways: list[str]) -> str:
    """Uma folha de cores como o ``monta.svg()`` a embute, com N modelos."""
    return "<style>" + "".join(
        f'svg[data-colorway="{c}"]{{--z-casca:#ae335a;--z-painel:#1a1a1c}}'
        for c in colorways) + "</style>"


def test_a_folha_com_os_vinte_e_oito_nao_e_divida(portao: object,
                                                  colorways: set[str]) -> None:
    """A folha completa é o MECANISMO CERTO: o produto escolhe por seletor."""
    completa = f'<svg data-colorway="white">{_folha(sorted(colorways))}</svg>'
    assert _conta(portao, colorways, completa, "zona") == 0, (
        "a régua acusou a tabela dela publicada — é o oposto da lei")


def test_a_folha_podada_e_divida(portao: object, colorways: set[str]) -> None:
    """A mesma página com UM modelo: o SVG não tem como virar outro."""
    podada = f'<svg data-colorway="white">{_folha(["white"])}</svg>'
    assert _conta(portao, colorways, podada, "zona") == 2, (
        "a folha de um modelo só é uma escolha cravada, e tinha de ser contada "
        "pelas declarações de zona que ela traz")


def test_o_banco_de_provas_dela_sai_limpo_da_familia_zona(
        portao: object, colorways: set[str]) -> None:
    """O arquivo de verdade em que ela vê as 28 cores clicando."""
    banco = PAGINAS / "mapa-do-controle.html"
    assert banco.is_file(), f"o banco de provas dela sumiu de {banco}"
    assert _conta(portao, colorways,
                  banco.read_text(encoding="utf-8"), "zona") == 0, (
        "o banco de provas das 28 cores foi acusado de cravar cor")


def test_o_comentario_nao_conta(portao: object, colorways: set[str]) -> None:
    """Prosa não é tela.

    Não é hipótese: a ``08-conexoes`` tem um comentário de trinta linhas que
    cita ``#hex`` e ``--plastico`` para EXPLICAR por que o valor não podia
    ficar cravado. Contá-lo faria a régua acusar quem documentou o conserto.
    """
    html = '<!-- style="--plastico:#ae335a" --><i></i>'
    assert _conta(portao, colorways, html) == 0


def test_o_alvo_plastico_cura_a_variavel(portao: object,
                                         colorways: set[str]) -> None:
    cru = '<i data-campo="plastico" style="--plastico:#ae335a"></i>'
    curado = ('<i data-campo="plastico" data-hef-alvo="plastico" '
              'style="--plastico:#ae335a"></i>')
    assert _conta(portao, colorways, cru, "plastico") == 1
    assert _conta(portao, colorways, curado, "plastico") == 0


def test_o_endereco_sem_o_alvo_nao_cura(portao: object,
                                        colorways: set[str]) -> None:
    """Endereço com o alvo errado é o pior dos dois mundos."""
    texto = ('<i data-campo="plastico" data-hef-alvo="texto" '
             'style="--plastico:#ae335a"></i>')
    assert _conta(portao, colorways, texto, "plastico") == 1


def test_o_alvo_de_atributo_cura_o_colorway(portao: object,
                                            colorways: set[str]) -> None:
    cru = '<svg data-colorway="cosmic-red"></svg>'
    curado = ('<svg data-campo="desenho" data-hef-alvo="atributo" '
              'data-hef-atributo="data-colorway" '
              'data-colorway="cosmic-red"></svg>')
    assert _conta(portao, colorways, cru, "colorway") == 1
    assert _conta(portao, colorways, curado, "colorway") == 0


def test_o_alvo_de_atributo_tem_de_nomear_o_colorway(
        portao: object, colorways: set[str]) -> None:
    """Um ``data-hef-atributo`` que aponta para outro atributo não cura nada."""
    quase = ('<svg data-campo="desenho" data-hef-alvo="atributo" '
             'data-hef-atributo="data-modelo" data-colorway="cosmic-red"></svg>')
    assert _conta(portao, colorways, quase, "colorway") == 1


def test_a_mordida_do_alvo_plastico(portao: object,
                                    colorways: set[str]) -> None:
    """A ``05-vibracao`` é a única aba que já curou a família ``plastico``.

    As molduras dos DOIS controles conectados trazem ``data-hef-alvo="plastico"``
    ao lado do ``--plastico`` cravado, e a régua as deixa passar (os outros dois
    lugares da mesa estão vazios no desenho e não trazem cor). Arrancado o alvo,
    ela tem de acusar as duas — senão está passando por outro motivo.
    """
    pagina = (PAGINAS / "05-vibracao.html").read_text(encoding="utf-8")
    assert _conta(portao, colorways, pagina, "plastico") == 0, (
        "a 05-vibracao deixou de estar curada — a mordida não mede mais nada")

    sem_cura, quantos = re.subn(r' data-hef-alvo="plastico"', "", pagina)
    # são quatro DualSense), e as duas vazias já nascem com o alvo posto para o
    molduras = pagina.count('data-campo="plastico"')
    assert quantos == molduras, (
        f"a 05 tem {molduras} molduras e só {quantos} trazem "
        "`data-hef-alvo=\"plastico\"` — uma delas voltou a cravar cor sem alvo")
    assert _conta(portao, colorways, sem_cura, "plastico") == 2, (
        "com o alvo arrancado a régua continuou calada — ela não está medindo "
        "o alvo, está passando por acaso")


def test_a_mordida_da_fita(portao: object, colorways: set[str]) -> None:
    """A ``.fita`` é isenta porque o piloto a TROCA INTEIRA a cada tique."""
    pagina = (PAGINAS / "01-jogar.html").read_text(encoding="utf-8")
    assert _conta(portao, colorways, pagina, "plastico") == 0

    mordida = _portao()
    mordida.TROCADOS_INTEIROS = ()
    achados = mordida.cravados_no_texto(pagina, colorways)
    assert sum(a[4] for a in achados if a[1] == "plastico") == 2, (
        "sem a isenção da fita a régua tinha de acusar os dois chips da mesa "
        "dela — ela está passando por outro motivo")


def test_a_mordida_da_folha_completa(portao: object,
                                     colorways: set[str]) -> None:
    """Poda a folha dos 28 do banco de provas dela e a vê virar dívida."""
    banco = (PAGINAS / "mapa-do-controle.html").read_text(encoding="utf-8")
    antes = _conta(portao, colorways, banco, "zona")
    assert antes == 0

    fora = sorted(colorways - {"white"})
    podado = banco
    for c in fora:
        podado = re.sub(rf'svg\[data-colorway="{re.escape(c)}"\][^\n]*\n', "",
                        podado)
    assert _conta(portao, colorways, podado, "zona") > 0, (
        "a folha podada para um modelo só continuou verde — a régua não mede a "
        "completude da tabela")


def test_os_vinte_e_oito_modelos_vem_do_csv(portao: object,
                                            colorways: set[str]) -> None:
    """A lista de modelos é LIDA, nunca digitada."""
    assert len(colorways) == 28, (
        f"o mapa dela tem 28 modelos e a régua leu {len(colorways)}")
    assert {"white", "cosmic-red", "nova-pink", "ghost-of-yotei"} <= colorways
    fonte = PORTAO.read_text(encoding="utf-8")
    assert "nova-pink" not in fonte, (
        "um nome de colorway foi DIGITADO no portão — a fonte é o CSV")


def test_a_divida_nao_cresce(portao: object, colorways: set[str]) -> None:
    """Uma cor de aparelho nova cravada numa página é dívida NOVA."""
    total = sum(
        sum(a[4] for a in portao.cravados_de(c, colorways))
        for c in sorted(PAGINAS.glob("[0-9][0-9]-*.html"))
    )
    assert total <= CRAVADOS_EM_03_09, (
        f"a dívida de cor cravada subiu de {CRAVADOS_EM_03_09} para {total}. "
        f"Alguma página passou a cravar mais um modelo em vez de seguir o "
        f"aparelho — rode `scripts/check_a_cor_vem_do_aparelho.py` e veja onde")
    if total < CRAVADOS_EM_03_09:
        print(f"[cor-vem-do-aparelho] a dívida caiu para {total}: abaixe o "
              f"CRAVADOS_EM_03_09 e o número do docstring do portão")
