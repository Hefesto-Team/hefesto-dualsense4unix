#!/usr/bin/env python3
"""A borda do cartão da aba Jogar é a cor do controle DELA, não a do mockup.

A LEI, e ela é dela (03/09/2026, IDENTIDADE-VEM-DE-CIMA-01):

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado.  (noqa-acento: palavra dela)
    Por isso temos o mapa pra servir como variável de identificação"

O QUE ESTAVA NA TELA, fotografado em 03/09 com os dois controles dela na mesa e
a página publicada de hoje:

    rótulo do cartão do P1     White · USB          ← o pacote já escrevia certo
    BORDA do cartão do P1      Cosmic Red           ← o mockup, cravado
    rótulo do cartão do P2     Não sei · BT
    BORDA do cartão do P2      Starlight Blue       ← cor INVENTADA: não se leu

O cartão discordava de si mesmo, com quatro pixels entre uma coisa e outra.

O QUE ESTA RÉGUA COBRA, e cada item é uma forma de a cura morrer calada:

1. o cartão não traz mais `--plastico` cravado nem `title` com nome de
   colorway — os dois são identidade que o produto **não pode** reescrever
   (o piloto tem sete alvos e nenhum escreve custom property nem atributo);
2. cada cartão CONECTADO tem a pele endereçada, e o lugar VAZIO não tem;
3. o pacote ESCREVE aquele endereço com o hex do mapa — *dar endereço não é
   entregar*: um `data-campo` que ninguém escreve zera a régua e deixa a tela
   igualmente errada;
4. sem leitura de cor o pacote manda VAZIO, e não o nome do desenho — regra
   dela: campo sem informação não mostra nada;
5. a pele NÃO é o `.cartao`: o desenho grande tem 16 traços em `currentColor`
   (`ds_limpo.svg`), e pintar a cor no cartão repintaria o controle inteiro.

A BANCADA É O ALVO, e não a página publicada: publicar é ato dela
(`check_o_desenho_aprovado.py --publicar 01`), e este trabalho entrega a
bancada. Apontar para o publicado daria VERMELHO sobre uma página que ninguém
podia mudar — a outra metade da armadilha do `COMO-OLHAR-A-TELA.md`.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O `--plastico` escrito à mão, na forma que a régua nova procura. Ele é a
#: cor que o produto NÃO alcança: nenhum dos sete alvos do `escrever()` do
#: piloto escreve uma custom property.
PLASTICO_CRAVADO = re.compile(r"--plastico\s*:\s*#[0-9a-fA-F]{3,8}")

#: A fileira de cartões, do `<div class="pecas"` até o fim do quadro. Cobrar a
#: página inteira misturaria o cartão com a FITA, que é do `monta.py` e não
#: desta aba — e faria esta régua acusar quem não pode consertar.
INICIO_DA_FILEIRA = '<div class="pecas" data-lista="cartoes">'
FIM_DA_FILEIRA = '<div class="col-atencao"'


def bancada() -> str:
    return onde.pagina("01-jogar.html").read_text(encoding="utf-8")


def fileira_de_cartoes() -> str:
    doc = bancada()
    i = doc.index(INICIO_DA_FILEIRA)
    return doc[i:doc.index(FIM_DA_FILEIRA, i)]


def nomes_de_colorway() -> list[str]:
    """Os 28 nomes, lidos do CSV que é dono deles — nunca digitados aqui.

    Uma lista escrita à mão neste arquivo envelheceria sozinha, e é o defeito
    que o `cores-do-dualsense.csv` existe para não ter.
    """
    caminho = RAIZ / "docs/data/cores-do-dualsense.csv"
    linhas = [
        linha
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    nomes = {(linha.get("nome") or "").strip() for linha in csv.DictReader(linhas)}
    return sorted(n for n in nomes if len(n) >= 4)


# ---------------------------------------------------------------------------
# 1. O cartão parou de trazer a identidade cravada
# ---------------------------------------------------------------------------
def test_o_cartao_nao_traz_mais_plastico_cravado() -> None:
    """A borda vinha de `style="--plastico:#ae335a"`, e o produto não a alcança."""
    achados = PLASTICO_CRAVADO.findall(fileira_de_cartoes())
    assert achados == [], (
        f"a fileira de cartões voltou a cravar a cor do plástico: {achados}. "
        f"Nenhum dos sete alvos do piloto escreve uma custom property, então "
        f"esse hex é, por construção, a cor do MOCKUP na tela dela para sempre."
    )


def test_o_cartao_nao_tem_dica_com_nome_de_colorway() -> None:
    """O `title` do cartão dizia `Sony • Player 1 • Cosmic Red • USB`.

    `title` é ATRIBUTO, e o piloto não tem alvo de pintura para atributo — a
    razão já estava escrita na `aba04.py`, na dica que saiu de lá pelo mesmo
    motivo. Ele repetia o rótulo palavra por palavra, quatro pixels ao lado.
    """
    fileira = fileira_de_cartoes()
    for atributo in re.findall(r'title="([^"]*)"', fileira):
        for nome in nomes_de_colorway():
            assert nome not in atributo, (
                f"uma dica do cartão voltou a nomear o plástico: {atributo!r}. "
                f"Ela fica congelada no que o gerador soube, e o gerador só "
                f"sabe o mockup."
            )


def test_a_prosa_da_legenda_nao_nomeia_um_colorway() -> None:
    """A legenda citava a fita com um exemplo: `[P1 · Cosmic Red · USB]`.

    Nome de plástico em prosa é nome que contradiz a fita três centímetros
    acima. E o rótulo da fita tem DONO (`monta.ROTULO_DA_FITA`): a prosa dizia
    `Ajustes vão para:`, que ela trocou em 31/08.
    """
    doc = bancada()
    legenda = doc[doc.index('<div class="nota">'):]
    for nome in nomes_de_colorway():
        assert nome not in legenda, (
            f"a legenda voltou a nomear o plástico {nome!r} — a prosa passa a "
            f"discordar da fita no primeiro controle que ela ligar"
        )
    assert monta.ROTULO_DA_FITA in legenda, (
        "a legenda deixou de citar o rótulo da fita pelo dono "
        "(`monta.ROTULO_DA_FITA`) — escrito à mão, ele volta a envelhecer"
    )


# ---------------------------------------------------------------------------
# 2. A pele existe, e está no lugar certo
# ---------------------------------------------------------------------------
def test_cada_cartao_conectado_tem_a_pele_enderecada() -> None:
    """Um por controle da mesa que está na mesa, e nenhuma no lugar vazio."""
    fileira = fileira_de_cartoes()
    peles = re.findall(
        r'<i class="pele" data-campo="plastico" data-hef-alvo="cor"', fileira)
    assert len(peles) == len(monta.CONECTADOS), (
        f"são {len(peles)} peles para {len(monta.CONECTADOS)} controles na "
        f"mesa — sem a pele, a borda do cartão volta a ser a do desenho"
    )
    vazios = fileira.split('class="cartao off"')[1:]
    for pedaco in vazios:
        assert 'class="pele"' not in pedaco.split("</div>\n              </div>")[0], (
            "um LUGAR VAZIO ganhou pele. Sem controle não há plástico a "
            "mostrar, e a borda dele é a do `.cartao.off`"
        )


def test_a_pele_nao_e_o_cartao() -> None:
    """Pintar a cor no `.cartao` repintaria o desenho inteiro.

    `ds_limpo.svg` tem 16 traços em `currentColor` — é como o glifo herda a cor
    da linha em que está. O alvo `cor` escreve `style.color`, e `color` HERDA:
    posto no cartão, ele desceria até o SVG. A pele é um elemento vazio, e é o
    que permite trocar a borda sem tocar no controle desenhado.
    """
    assert "currentColor" in (INTERFACE / "ds_limpo.svg").read_text(encoding="utf-8"), (
        "o desenho deixou de usar `currentColor` — a razão da pele mudou, e "
        "esta régua tem de ser relida antes de qualquer simplificação"
    )
    for tag in re.findall(r'<div class="cartao[^>]*>', fileira_de_cartoes()):
        assert "data-hef-alvo" not in tag, (
            f"o `.cartao` ganhou alvo de pintura: {tag!r}. Com o alvo `cor` "
            f"ali, o desenho do controle seria repintado junto."
        )


# ---------------------------------------------------------------------------
# 3. O PACOTE ESCREVE — dar endereço não é entregar
# ---------------------------------------------------------------------------
def _ctx(cor: str, nome: str) -> Contexto:
    """Um controle no cabo, com a cor que o argumento disser."""
    uniq = "aa:bb:cc:00:00:01"
    cru = {"uniq": uniq, "connected": True, "player_slot": 1,
           "transport": "usb", "battery_pct": 95}
    da_mesa = {"uniq": uniq, "pref": "p1", "jogador": 1,
               "nome": nome, "cor": cor, "via": "USB"}
    return Contexto(state={"controllers": [cru]}, mesa=[da_mesa],
                    conectados=[cru], estados={})


def cartao(ctx: Contexto) -> dict[str, Any]:
    return next(iter(aba.pacote(ctx)["cartoes"].values()))


def test_o_pacote_escreve_a_cor_do_plastico_lida() -> None:
    """Com o White no cabo, o pacote manda o hex do White — não o do desenho.

    O hex NÃO está digitado aqui: ele sai de `monta.cor_da_zona`, que lê a
    folha que pinta o SVG. Digitá-lo criaria a segunda verdade que o
    `check_cores_do_dualsense.py` existe para matar.
    """
    esperado = monta.cor_da_zona("white")
    assert cartao(_ctx("white", "White"))["plastico"] == esperado, (
        "o pacote parou de escrever a cor do plástico. Sem esta chave o "
        "endereço fica MUDO, a pele nasce no `#ae335a` do desenho e lá fica — "
        "que é trocar um congelado por um vazio"
    )


def test_o_hex_nao_e_o_do_mockup() -> None:
    """A régua acima passaria se o pacote copiasse o desenho. Esta não passa.

    `#ae335a` é o Cosmic Red do cartão do P1 no mockup. Com o White na mesa, o
    pacote que devolvesse aquele hex estaria pintando o mockup por cima do
    mockup — verde sobre nada.
    """
    assert cartao(_ctx("white", "White"))["plastico"] != monta.cor_da_zona("cosmic-red")


def test_sem_leitura_de_cor_o_pacote_nao_inventa() -> None:
    """A cor só vem pelo CABO. Pelo rádio ela não vem, e é para não mostrar nada.

    Regra dela: campo sem informação não mostra nada. O vazio faz o alvo `cor`
    apagar o `style.color`, e a pele volta ao neutro do CSS — em vez de manter
    aceso o `#7eb8d4` que o desenho deixou no cartão do P2.
    """
    assert cartao(_ctx("", "Não sei"))["plastico"] == "", (
        "o pacote inventou uma cor para um controle cuja cor ninguém leu"
    )


def test_um_modelo_que_o_desenho_nao_conhece_nao_derruba_a_aba() -> None:
    """`monta.cor_da_zona` levanta `SystemExit` — e ele não é `Exception`.

    Um modelo novo derrubaria a pintura da aba INTEIRA: trocaríamos uma borda
    que falta por uma tela congelada. Esta régua morde a guarda: com
    `except Exception` no lugar de `except BaseException`, ela reprova.
    """
    assert cartao(_ctx("cor-que-nao-existe", "Novo"))["plastico"] == ""


def test_a_cobertura_conta_o_campo_novo() -> None:
    """O contador é O instrumento com que esta casa prova que um endereço existe.

    Ele diz quantos valores a aba promete pintar. Deixá-lo em três por cartão
    depois de acrescentar o quarto é o começo de um contador que mente.
    """
    fora = aba.pacote(_ctx("white", "White"))
    por_cartao = {len(c) for c in fora["cartoes"].values()}
    assert por_cartao == {4}, f"o cartão passou a ter {por_cartao} campos"
    # A CONTA SAI DA FORMA DO PACOTE, E NÃO DE UM NÚMERO DIGITADO — 03/09/2026.
    # Ela era `3 + cartoes * 4`, e o 3 era a quantidade de endereços de PÁGINA
    # daquele dia. A aba ganhou os endereços que faltavam (a posição do
    # interruptor, o chip aceso, a máscara viva, as linhas da coluna Atenção) e
    # a régua reprovou a ENTREGA em vez do defeito — é a forma exata que esta
    # casa já pagou onze vezes numa tarde só.
    #
    # ELA CONTINUA MORDENDO, e agora pela pergunta certa: o contador tem de
    # bater com o que o pacote EMITE. Emitir uma chave e esquecê-la em
    # `DA_PAGINA` deixa o número menor que o dicionário, e é aqui que aparece.
    da_pagina = [k for k in fora if k not in {"cartoes", "cobertura", "sem_dono", "blocos"}]
    esperado = len(da_pagina) + sum(len(c) for c in fora["cartoes"].values())
    assert fora["cobertura"]["pintados"] == esperado, (
        f"a cobertura diz {fora['cobertura']['pintados']} e o pacote emite "
        f"{len(da_pagina)} endereços de página + "
        f"{sum(len(c) for c in fora['cartoes'].values())} de cartão — "
        f"o contador e o pacote discordam"
    )
