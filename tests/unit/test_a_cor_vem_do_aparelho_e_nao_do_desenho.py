#!/usr/bin/env python3
"""A régua do ``check_a_cor_vem_do_aparelho.py`` — e o que ela NÃO pode acusar.

A LEI é dela, 03/09/2026: *"eu mapeei as cores, glifos, controles, id e tudo
mais. É pro projeto usar esse meu trabalho (…) nada hardcoded"*. Vinte e oito
modelos no ``docs/data/cores-do-dualsense.csv``; o produto usa quatro, cravados.

**O PERIGO DESTA RÉGUA EM PARTICULAR, e é por isso que metade deste arquivo
mede o que ela deixa passar**: um CSS que declara os 28 modelos e escolhe por
seletor **é a tabela dela, publicada** — o mecanismo certo. Uma régua que não
distinguisse isso de uma escolha cravada mandaria apagar o trabalho dela, que é
o oposto da lei. O caso
:func:`test_o_banco_de_provas_dela_sai_limpo_da_familia_zona` roda sobre o
arquivo de verdade que ela usa para ver as 28 cores clicando.

AS MORDIDAS, e elas rodam — cada uma arranca uma cura REAL, do disco, e exige
ver a acusação voltar:

* :func:`test_a_mordida_do_alvo_plastico` tira o ``data-hef-alvo="plastico"``
  das molduras da ``05-vibracao`` — a única aba que já curou essa família — e as
  vê serem acusadas;
* :func:`test_a_mordida_da_fita` tira a ``.fita`` de ``TROCADOS_INTEIROS`` e vê
  os chips da ``01-jogar`` serem acusados;
* :func:`test_a_mordida_da_folha_completa` poda a folha dos 28 do banco de
  provas dela e a vê virar dívida.

Nenhuma delas mexe em arquivo: a régua recebe TEXTO, e a mutilação acontece em
memória.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts/check_a_cor_vem_do_aparelho.py"
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

#: O NÚMERO DE ONDE AS ONDAS PARTEM, medido em 03/09/2026 e declarado no
#: docstring do portão. Ele não é um teto a perseguir — é o retrato do dia. O
#: que este arquivo cobra é que ele **não cresça**: uma cor de aparelho nova
#: cravada numa página é dívida nova, e o portão está vermelho demais para
#: acusá-la sozinho.
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


# ---------------------------------------------------------------------------
# 1. o que ela NÃO pode acusar: a tabela dela, publicada
# ---------------------------------------------------------------------------
def test_a_folha_com_os_vinte_e_oito_nao_e_divida(portao: object,
                                                  colorways: set[str]) -> None:
    """A folha completa é o MECANISMO CERTO: o produto escolhe por seletor.

    Trocar o ``data-colorway`` do ``<svg>`` passa a bastar para o desenho virar
    outro modelo — que é exatamente o que a lei pede.
    """
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
    """O arquivo de verdade em que ela vê as 28 cores clicando.

    Ele publica a folha inteira, e é a prova em disco de que a régua distingue
    a TABELA da ESCOLHA. Se este caso reprovar, a régua passou a mandar apagar
    o trabalho dela.
    """
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


# ---------------------------------------------------------------------------
# 2. o que cura, e o que NÃO cura
# ---------------------------------------------------------------------------
def test_o_alvo_plastico_cura_a_variavel(portao: object,
                                         colorways: set[str]) -> None:
    cru = '<i data-campo="plastico" style="--plastico:#ae335a"></i>'
    curado = ('<i data-campo="plastico" data-hef-alvo="plastico" '
              'style="--plastico:#ae335a"></i>')
    assert _conta(portao, colorways, cru, "plastico") == 1
    assert _conta(portao, colorways, curado, "plastico") == 0


def test_o_endereco_sem_o_alvo_nao_cura(portao: object,
                                        colorways: set[str]) -> None:
    """Endereço com o alvo errado é o pior dos dois mundos.

    O ``escrever()`` ACHA o elemento e cai no ramo padrão: escreve a cor como
    TEXTO, por cima do desenho. A cor cravada continua na tela e a página ainda
    ganha um ``#hex`` escrito em letras.
    """
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
    """Um ``data-hef-atributo`` que aponta para outro atributo não cura nada.

    O alvo escreveria o ``data-modelo`` e deixaria o ``data-colorway`` como o
    desenho o cravou — a tela continuaria Cosmic Red. Sem esta exigência a régua
    daria por curado quem só pôs a palavra certa no lugar errado, que é o
    defeito-mãe desta casa: *presença de string não é funcionamento*.
    """
    quase = ('<svg data-campo="desenho" data-hef-alvo="atributo" '
             'data-hef-atributo="data-modelo" data-colorway="cosmic-red"></svg>')
    assert _conta(portao, colorways, quase, "colorway") == 1


# ---------------------------------------------------------------------------
# 3. AS TRÊS MORDIDAS — cada uma arranca uma cura REAL
# ---------------------------------------------------------------------------
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
    # A RÉGUA MEDIA O MUNDO DE ONTEM — 08/09/2026. Aqui estava `quantos == 2`,
    # e ela achou 4: a bancada passou a desenhar as QUATRO colunas (o foco dela
    # são quatro DualSense), e as duas vazias já nascem com o alvo posto para o
    # dia em que o controle chegar. O número que a mordida precisa não é "dois"
    # — é "TODA moldura tem o alvo", e isso se LÊ da página.
    molduras = pagina.count('data-campo="plastico"')
    assert quantos == molduras, (
        f"a 05 tem {molduras} molduras e só {quantos} trazem "
        "`data-hef-alvo=\"plastico\"` — uma delas voltou a cravar cor sem alvo")
    # E O NÚMERO ACUSADO CONTINUA DOIS, medido: arrancados os quatro alvos, a
    # régua acusa só as duas molduras que de fato CRAVAM uma cor. As outras
    # duas são lugares vazios e não trazem cor nenhuma — é o que a docstring
    # acima afirma, e é por isso que "alvos arrancados" e "molduras acusadas"
    # são dois números diferentes de propósito.
    assert _conta(portao, colorways, sem_cura, "plastico") == 2, (
        "com o alvo arrancado a régua continuou calada — ela não está medindo "
        "o alvo, está passando por acaso")


def test_a_mordida_da_fita(portao: object, colorways: set[str]) -> None:
    """A ``.fita`` é isenta porque o piloto a TROCA INTEIRA a cada tique.

    ``hefesto_vivo.pintar`` substitui o ``outerHTML`` de
    ``document.querySelector('.fita')`` com o que ``monta.fita(mesa=…)`` monta
    da mesa VIVA. Tirada a isenção, os chips da ``01-jogar`` viram dívida — e é
    isso que prova que a isenção está segurando alguma coisa, e não decorando.
    """
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
    """Poda a folha dos 28 do banco de provas dela e a vê virar dívida.

    É a mordida do caso mais perigoso desta régua: se ela não acusasse a folha
    podada, a família ``zona`` inteira seria verde sobre 324 hexes cravados.
    """
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


# ---------------------------------------------------------------------------
# 4. o dado é dela, e o número não cresce
# ---------------------------------------------------------------------------
def test_os_vinte_e_oito_modelos_vem_do_csv(portao: object,
                                            colorways: set[str]) -> None:
    """A lista de modelos é LIDA, nunca digitada.

    Digitá-la aqui criaria a segunda lista que envelhece sozinha — o defeito que
    o ``cores-do-dualsense.csv`` existe para não ter.
    """
    assert len(colorways) == 28, (
        f"o mapa dela tem 28 modelos e a régua leu {len(colorways)}")
    assert {"white", "cosmic-red", "nova-pink", "ghost-of-yotei"} <= colorways
    fonte = PORTAO.read_text(encoding="utf-8")
    assert "nova-pink" not in fonte, (
        "um nome de colorway foi DIGITADO no portão — a fonte é o CSV")


def test_a_divida_nao_cresce(portao: object, colorways: set[str]) -> None:
    """Uma cor de aparelho nova cravada numa página é dívida NOVA.

    O portão está vermelho enquanto as dez abas fecham, e um portão vermelho não
    distingue 360 de 361. Este caso distingue.
    """
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
