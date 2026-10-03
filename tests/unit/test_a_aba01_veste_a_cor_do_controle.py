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

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O `--plastico` escrito à mão, na forma que a régua nova procura. Ele é a
PLASTICO_CRAVADO = re.compile(r"--plastico\s*:\s*#[0-9a-fA-F]{3,8}")

INICIO_DA_FILEIRA = '<div class="pecas" data-lista="cartoes">'
FIM_DA_FILEIRA = '<div class="faixa-final'


def bancada() -> str:
    return onde.pagina("01-jogar.html").read_text(encoding="utf-8")


def fileira_de_cartoes() -> str:
    doc = bancada()
    i = doc.index(INICIO_DA_FILEIRA)
    return doc[i:doc.index(FIM_DA_FILEIRA, i)]


def nomes_de_colorway() -> list[str]:
    """Os 28 nomes, lidos do CSV que é dono deles — nunca digitados aqui."""
    caminho = RAIZ / "docs/data/cores-do-dualsense.csv"
    linhas = [
        linha
        for linha in caminho.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    nomes = {(linha.get("nome") or "").strip() for linha in csv.DictReader(linhas)}
    return sorted(n for n in nomes if len(n) >= 4)


def test_o_cartao_nao_traz_mais_plastico_cravado() -> None:
    """A borda vinha de `style="--plastico:#ae335a"`, e o produto não a alcança."""
    achados = PLASTICO_CRAVADO.findall(fileira_de_cartoes())
    assert achados == [], (
        f"a fileira de cartões voltou a cravar a cor do plástico: {achados}. "
        f"Nenhum dos sete alvos do piloto escreve uma custom property, então "
        f"esse hex é, por construção, a cor do MOCKUP na tela dela para sempre."
    )


def test_o_cartao_nao_tem_dica_com_nome_de_colorway() -> None:
    """O `title` do cartão dizia `Sony • Player 1 • Cosmic Red • USB`."""
    fileira = fileira_de_cartoes()
    for atributo in re.findall(r'title="([^"]*)"', fileira):
        for nome in nomes_de_colorway():
            assert nome not in atributo, (
                f"uma dica do cartão voltou a nomear o plástico: {atributo!r}. "
                f"Ela fica congelada no que o gerador soube, e o gerador só "
                f"sabe o mockup."
            )


def test_a_prosa_da_legenda_nao_nomeia_um_colorway() -> None:
    """A legenda citava a fita com um exemplo: `[P1 · Cosmic Red · USB]`."""
    import aba01

    legenda = aba01.LEGENDA
    for nome in nomes_de_colorway():
        assert nome not in legenda, (
            f"a legenda voltou a nomear o plástico {nome!r} — a prosa passa a "
            f"discordar da fita no primeiro controle que ela ligar"
        )
    assert monta.ROTULO_DA_FITA in legenda, (
        "a legenda deixou de citar o rótulo da fita pelo dono "
        "(`monta.ROTULO_DA_FITA`) — escrito à mão, ele volta a envelhecer"
    )


def test_cada_lugar_da_mesa_tem_a_pele_enderecada() -> None:
    """Uma por LUGAR da mesa — os quatro, e não só os conectados.

    ERA `len(monta.CONECTADOS)` E O LUGAR VAZIO ERA PROIBIDO DE TER PELE, até
    07/09/2026 (QUATRO-NA-MESA-01). A régua era a do mundo de ontem, e a
    proibição era o próprio defeito escrito como requisito: no produto a página
    é ESTÁTICA, e quando um terceiro controle chega o cartão do P3 REABRE (passo
    `1c` do piloto, que tira a classe `off`). Sem `data-campo="plastico"` lá
    dentro, o `achar(raiz, 'plastico')` do piloto devolvia lista vazia e a borda
    do P3 ficava na cor neutra para sempre — com a cor certa chegando do daemon
    a cada tique e caindo no vazio.

    O LUGAR VAZIO CONTINUA SEM PELE NA TELA, e é isso que esta régua ainda
    protege — só que por CSS e não por ausência de HTML: `.cartao.off > .pele`
    é `display:none`, e a regra já existia desde 03/09 exatamente para o cartão
    que vira `off` em tempo de execução. A cena que ela aprovou não muda um
    pixel; o que muda é haver onde a cor pousar.
    """
    fileira = fileira_de_cartoes()
    peles = re.findall(
        r'<i class="pele" data-campo="plastico" data-hef-alvo="cor"', fileira)
    assert len(peles) == len(monta.MESA), (
        f"são {len(peles)} peles para {len(monta.MESA)} LUGARES na mesa — sem a "
        f"pele, o cartão que reabre fica com a borda do desenho"
    )
    folha = bancada()
    assert ".cartao.off > .pele{display:none}" in folha, (
        "a regra que esconde a pele do lugar vazio saiu da folha — o cartão "
        "apagado voltaria a mostrar a cor de um controle que não está lá"
    )


def test_a_pele_nao_e_o_cartao() -> None:
    """Pintar a cor no `.cartao` repintaria o desenho inteiro."""
    assert "currentColor" in (INTERFACE / "ds_limpo.svg").read_text(encoding="utf-8"), (
        "o desenho deixou de usar `currentColor` — a razão da pele mudou, e "
        "esta régua tem de ser relida antes de qualquer simplificação"
    )
    for tag in re.findall(r'<div class="cartao[^>]*>', fileira_de_cartoes()):
        assert "data-hef-alvo" not in tag, (
            f"o `.cartao` ganhou alvo de pintura: {tag!r}. Com o alvo `cor` "
            f"ali, o desenho do controle seria repintado junto."
        )


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
    """Com o White no cabo, o pacote manda o hex do White — não o do desenho."""
    esperado = monta.cor_da_zona("white")
    assert cartao(_ctx("white", "White"))["plastico"] == esperado, (
        "o pacote parou de escrever a cor do plástico. Sem esta chave o "
        "endereço fica MUDO, a pele nasce no `#ae335a` do desenho e lá fica — "
        "que é trocar um congelado por um vazio"
    )


def test_o_hex_nao_e_o_do_mockup() -> None:
    """A régua acima passaria se o pacote copiasse o desenho. Esta não passa."""
    assert cartao(_ctx("white", "White"))["plastico"] != monta.cor_da_zona("cosmic-red")


def test_sem_leitura_de_cor_o_pacote_nao_inventa() -> None:
    """A cor só vem pelo CABO. Pelo rádio ela não vem, e é para não mostrar nada."""
    assert cartao(_ctx("", "Não sei"))["plastico"] == "", (
        "o pacote inventou uma cor para um controle cuja cor ninguém leu"
    )


def test_um_modelo_que_o_desenho_nao_conhece_nao_derruba_a_aba() -> None:
    """`monta.cor_da_zona` levanta `SystemExit` — e ele não é `Exception`."""
    assert cartao(_ctx("cor-que-nao-existe", "Novo"))["plastico"] == ""


def test_a_cobertura_conta_o_campo_novo() -> None:
    """O contador é O instrumento com que esta casa prova que um endereço existe."""
    fora = aba.pacote(_ctx("white", "White"))
    por_cartao = {len(c) for c in fora["cartoes"].values()}
    assert por_cartao == {len(aba.POR_CARTAO)}, (
        f"o cartão emite {por_cartao} campos e `POR_CARTAO` promete "
        f"{len(aba.POR_CARTAO)}: {aba.POR_CARTAO}")
    assert set(next(iter(fora["cartoes"].values()))) == set(aba.POR_CARTAO), (
        "o pacote emite um campo de cartão que `POR_CARTAO` não lista — a "
        "cobertura contaria menos do que a aba pinta")
    da_pagina = [k for k in fora if k not in {"cartoes", "cobertura", "sem_dono", "blocos"}]
    esperado = len(da_pagina) + sum(len(c) for c in fora["cartoes"].values())
    assert fora["cobertura"]["pintados"] == esperado, (
        f"a cobertura diz {fora['cobertura']['pintados']} e o pacote emite "
        f"{len(da_pagina)} endereços de página + "
        f"{sum(len(c) for c in fora['cartoes'].values())} de cartão — "
        f"o contador e o pacote discordam"
    )
