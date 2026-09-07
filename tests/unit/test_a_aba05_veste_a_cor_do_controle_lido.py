#!/usr/bin/env python3
"""A ABA 05 VESTE A COR DO CONTROLE LIDO — a identidade vem da fita, não do desenho.

A LEI, e ela é dela (03/09/2026):

    "se no topo tá mostrando controle white player 1, então cada aba vai usar os
    controles lá de cima. Não mistura com a info dos mockups. Cada feature faz
    referencia ao controle conectado."   (noqa-acento: citação literal dela)

O QUE ESTA RÉGUA VIGIA, e o defeito estava FOTOGRAFADO antes dela existir. Com
os dois controles dela na mesa — um White no cabo, um sem cor legível no rádio —
a `05-vibracao` mostrava, com três centímetros entre uma coisa e outra:

    rótulo da coluna (lido do aparelho)   P1 · White · USB
    borda da moldura (do MOCKUP)          #ae335a  ← Cosmic Red

E a fita do topo, que devia ser a fonte da identidade, dizia
`P1 · Cosmic Red · USB` / `P2 · Starlight Blue · BT`: os dois controles do
desenho, nenhum dos dois na mesa.

AS QUATRO METADES DE UM CONSERTO DE VERDADE, e é por isso que são quatro
funções e não uma:

1. o ENDEREÇO existe na página, e o valor congelado saiu de onde ninguém o
   alcançava (`_ctrl` → `.moldura`);
2. o PACOTE escreve aquele endereço com o que leu, e **cala** quando não leu;
3. o CHIP da fita tem dono, e também cala a cor que não veio;
4. o alvo que a página PEDE é um que o pintor SABE escrever — sem isto o
   endereço existe, a régua da identidade fica verde e a tela continua com a
   cor do mockup. *Dar endereço não é entregar.*

NENHUMA DELAS DIGITA O QUE DEVIA LER: o hexadecimal esperado sai de
`monta.cor_da_zona`, que lê o `<style>` do SVG; os alvos do pintor saem do
próprio `hefesto_vivo.py`; e o HTML sai do gerador, nunca de uma cópia colada
aqui.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# O import do PACOTE é o que põe `interface/` no `sys.path` (`pacotes/__init__`
# faz o `insert`), e é o que deixa `import monta` funcionar logo abaixo — a
# mesma porta pela qual o piloto entra.
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao

import monta

BANCADA = RAIZ / "mockup/05-vibracao.html"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: O colorway de um controle que o cabo respondeu, e o de um que ninguém leu.
#: `""` NÃO é descuido: é o que `mesa_viva.mesa_do_estado` põe quando o mapa de
#: canais diz que aquele transporte não entrega a cor — o caso do rádio, que é
#: metade da mesa dela.
LIDO = "white"
SEM_LEITURA = ""

#: O valor do `data-conectado` num lugar sem controle — chave de máquina,
#: e por isso sem acento.
SEM_CONTROLE = "nao"  # (noqa-acento) valor de atributo


class _Elementos(HTMLParser):
    """Os elementos da página com os atributos de cada um, em ordem."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.achados: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.achados.append((tag, {k: (v or "") for k, v in attrs}))

    handle_startendtag = handle_starttag


def _elementos(caminho: pathlib.Path) -> list[tuple[str, dict[str, str]]]:
    leitor = _Elementos()
    leitor.feed(caminho.read_text(encoding="utf-8"))
    return leitor.achados


def _mesa(*cores: str) -> list[dict[str, Any]]:
    """Uma mesa de mentira, na forma que `mesa_viva.mesa_do_estado` devolve."""
    return [
        {
            "pref": f"p{i}",
            "uniq": f"{i}" * 12,
            "jogador": i,
            "cor": cor,
            "nome": "White" if cor else "Não sei",
            "via": "USB" if i == 1 else "BT",
            "transporte": "usb" if i == 1 else "bt",
            "alvo": i == 1,
            "mascara": "DualSense",
        }
        for i, cor in enumerate(cores, start=1)
    ]


# ---------------------------------------------------------------------------
# 1. O ENDEREÇO — a cor saiu de onde o pintor não alcança
# ---------------------------------------------------------------------------
def test_a_cor_do_plastico_mora_onde_o_pintor_alcanca() -> None:
    """Todo `--plastico` da bancada está num elemento com `data-campo`.

    E ELE NÃO PODE ESTAR NO `<div class="ctrl">`, que é a RAIZ da coluna: o
    pintor procura os campos com `raiz.querySelectorAll` (`hefesto_vivo.achar`),
    e um `querySelectorAll` **não devolve a própria raiz**. Escrita ali, a cor
    ficava congelada no que o desenho soube — que é exatamente o que a foto de
    03/09/2026 mostrava, com a moldura em Cosmic Red e o rótulo dizendo White.

    A MORDIDA: devolver o `style="--plastico:…"` ao `.ctrl` faz esta função
    reprovar, e faz o `check_identidade_vem_de_cima --bancada --aba 05` voltar
    de 0 para 2.
    """
    sem_dono = []
    no_ctrl = []
    for tag, attrs in _elementos(BANCADA):
        if "--plastico" not in attrs.get("style", ""):
            continue
        classes = (attrs.get("class") or "").split()
        if "ctrl" in classes:
            no_ctrl.append((tag, attrs.get("class")))
        if "data-campo" not in attrs and "data-papel" not in attrs:
            sem_dono.append((tag, attrs.get("class")))

    assert not no_ctrl, (
        "a cor do plástico voltou para o `<div class=\"ctrl\">`, que é a raiz "
        f"da coluna e o pintor não a visita: {no_ctrl}")
    assert not sem_dono, (
        f"há `--plastico` cravado em elemento sem endereço nenhum: {sem_dono}")


def test_a_moldura_pede_o_alvo_da_cor_uma_vez_por_coluna_conectada() -> None:
    """TODAS as molduras pedem `data-hef-alvo="plastico"` — e só as vivas trazem cor.

    A CONTA SAI DA PÁGINA, e não de um número digitado: cada `.ctrl` tem UMA
    moldura. Assim, no dia em que a mesa do desenho mudar de tamanho, esta régua
    acompanha em vez de reprovar a mudança.

    **INVERTEU EM 07/09/2026, E É O PONTO INTEIRO DA CURA.** Esta régua dizia
    *"o lugar vazio NÃO ganha o endereço… ele não desenha controle nenhum, logo
    não tem plástico que vestir"* — e essa ausência era o defeito, medido com os
    quatro DualSense dela na mesa: o daemon publicava os quatro, o pacote
    mandava as quatro colunas e o P3 e o P4 ficavam no travessão, porque o
    piloto pinta procurando `data-campo` DENTRO do bloco daquele
    `data-controle`. Sem endereço, o dado dela chega e não tem onde pousar.

    O QUE SEPARA OS DOIS ESTADOS PASSOU A SER O VALOR, e não o endereço: o
    `style="--plastico:…"` só nasce em quem tem aparelho. Um lugar vazio não tem
    plástico para AFIRMAR — mas tem, agora, onde receber o do controle que
    chegar. É a mesma divisão que o `data-colorway` do `<svg>` já fazia.
    """
    elementos = _elementos(BANCADA)
    colunas = [
        a for _t, a in elementos
        if "ctrl" in (a.get("class") or "").split()
    ]
    vivas = [a for a in colunas if a.get("data-conectado") != SEM_CONTROLE]
    enderecadas = [
        a for t, a in elementos
        if a.get("data-campo") == "plastico"
        and a.get("data-hef-alvo") == "plastico"
    ]
    vestem = [a for a in enderecadas if "--plastico" in a.get("style", "")]
    assert colunas, "a bancada da 05 não tem uma coluna de controle sequer"
    assert vivas and len(vivas) < len(colunas), (
        f"a mesa do desenho deixou de ter lugar vivo E lugar vazio "
        f"({len(vivas)} de {len(colunas)}) — esta régua compara os dois")
    assert len(enderecadas) == len(colunas), (
        f"{len(colunas)} lugares e {len(enderecadas)} molduras com o endereço "
        "da cor — um lugar sem endereço é dado dela chegando sem onde pousar")
    assert len(vestem) == len(vivas), (
        f"{len(vivas)} colunas conectadas e {len(vestem)} molduras com a cor "
        "cravada — o lugar vazio não pode AFIRMAR um plástico que não tem")


# ---------------------------------------------------------------------------
# 2. O PACOTE — escreve o que leu, cala o que não leu
# ---------------------------------------------------------------------------
def test_o_pacote_veste_a_cor_lida_e_nao_inventa_a_que_faltou() -> None:
    """`plastico` sai do pacote com o `#hex` do controle, ou vazio.

    O ESPERADO É LIDO, e não digitado: `monta.cor_da_zona` é o dono da tradução
    colorway → cor, e ele lê o `<style>` que o `gerar_cores_do_dualsense.py`
    escreveu no SVG. Um hexadecimal escrito aqui seria a segunda lista de cores
    que o `docs/data/cores-do-dualsense.csv` existe para não ter.

    E O VAZIO É METADE DA RÉGUA: pelo rádio o mapa de canais responde
    `identidade.cor_do_aparelho = não`, e a regra dela é *campo sem informação
    não mostra nada*. Um pacote que caísse no colorway do mockup passaria na
    primeira metade desta função e falharia nesta.
    """
    mesa = _mesa(LIDO, SEM_LEITURA)
    ctx = Contexto(
        state={"controllers": []},
        mesa=mesa,
        conectados=[{"uniq": c["uniq"], "transport": c["transporte"]} for c in mesa],
        estados={},
    )
    colunas = a05_vibracao.pacote(ctx).get("colunas") or {}
    assert set(colunas) == {c["uniq"] for c in mesa}, (
        f"as colunas do pacote não são as da mesa: {sorted(colunas)}")

    lido, sem = mesa[0]["uniq"], mesa[1]["uniq"]
    assert colunas[lido].get("plastico") == monta.cor_da_zona(LIDO), (
        "a coluna do controle lido não recebeu a cor do plástico dele: "
        f"{colunas[lido].get('plastico')!r}")
    assert colunas[sem].get("plastico") == "", (
        "a coluna do controle sem cor legível recebeu uma cor — o pacote "
        f"inventou o que ninguém leu: {colunas[sem].get('plastico')!r}")


# ---------------------------------------------------------------------------
# 3. O CHIP DA FITA — tem dono, e cala a cor que não veio
# ---------------------------------------------------------------------------
def test_o_chip_da_fita_tem_dono_e_cala_a_cor_que_nao_veio() -> None:
    """`monta.fita` emite chips endereçados e não levanta sem colorway.

    DUAS COISAS NUMA SÓ FUNÇÃO porque são a mesma linha do gerador:

    * `data-campo` diz que ali não mora desenho — o produto troca a fita
      inteira a cada tique (`hefesto_vivo._fita`), e sem o endereço a régua da
      identidade contava os três valores de cada chip como congelados;
    * um controle SEM colorway não pode derrubar a fita. `cor_da_zona("")`
      levanta `SystemExit`, e era isso que fazia o piloto desistir da fita
      inteira e deixar os dois controles do MOCKUP na tela dela.

    A MORDIDA: tirar o `data-campo` do chip faz o
    `check_identidade_vem_de_cima --bancada --aba 05` voltar de 0 para 8.

    O RECORTE É O ENDEREÇO, E NÃO A CLASSE — 03/09/2026, e DUAS frentes da
    mesma leva chegaram a esta cura sem saber uma da outra, o que é a melhor
    confirmação que um conserto pode ter.

    Esta função escolhia os chips por `class="… plastico"`, e isso valia
    enquanto `monta.fita` a escrevia em TODO chip (o commit `80f8c859`, que
    trouxe esta régua). O `c6adb2d8` a tornou condicional, e com razão:
    `.chip.plastico` desenha a borda com `var(--plastico)`, e vesti-la num chip
    sem cor lida pintaria uma borda que ninguém leu — que é o defeito desta onda
    inteira, e é a regra dela: campo sem informação não mostra nada.

    Com o recorte velho a própria régua se contradizia: ela exigia dois chips
    **e** que o segundo não tivesse cor, e o segundo era justamente o que a
    classe deixava de fora. Duas coisas que não podem ser verdade juntas — e o
    merge do dia deixou esta função vermelha no `dev`.

    `data-campo="fita-chip"` é o endereço, está nos dois, e é o que estas linhas
    medem. A CLASSE PASSA A SER COBRADA em vez de recortar, o que faz esta régua
    medir uma coisa a mais do que antes de quebrar.
    """
    html = monta.fita(mesa=_mesa(LIDO, SEM_LEITURA))
    # TODOS os chips da fita, e não só os endereçados: é a diferença entre eles
    # que faz a mordida do `data-campo` reprovar em vez de sumir do recorte.
    na_fita = [a for t, a in _elementos_de(html)
               if "chip" in (a.get("class") or "").split()]
    chips = [a for a in na_fita if a.get("data-campo") == "fita-chip"]

    assert len(na_fita) == 3, (
        f"a fita não emitiu o 'Todos' mais os dois chips da mesa: {html}")
    assert len(chips) == 2, (
        f"há chip de fita sem endereço — o `data-campo` saiu de "
        f"{len(na_fita) - 1 - len(chips)} deles: {html}")
    assert monta.cor_da_zona(LIDO) in chips[0].get("style", ""), (
        "o chip do controle lido não veste a cor dele")
    assert "plastico" in (chips[0].get("class") or "").split(), (
        f"o chip do controle lido perdeu a classe que pinta a borda: {chips[0]}")
    assert "--plastico" not in chips[1].get("style", ""), (
        "o chip do controle sem cor legível veste uma cor que ninguém leu: "
        f"{chips[1].get('style')!r}")
    assert "plastico" not in (chips[1].get("class") or "").split(), (
        "o chip sem cor lida ficou com a classe da borda colorida, e a borda "
        f"cairia no tom da folha em vez de sumir: {chips[1]}")


def test_a_fita_viva_nao_desiste_quando_a_cor_nao_veio() -> None:
    """A guarda de `_fita` não pode voltar a exigir cor de TODO controle.

    ELA EXISTIU, e o efeito estava na tela: `if not mesa or any(not c.get("cor")
    for c in mesa): return ""` esperava por uma resposta que pelo RÁDIO nunca
    chega — `mesa_viva.LeitorDeCor` guarda `None` para aquele endereço de uma
    vez por todas. Com um controle no cabo e outro no rádio, que é a mesa dela,
    a fita ficava eternamente no desenho.

    ESTA FUNÇÃO LÊ O FONTE, e o diz: importar o piloto traria GTK e WebKit para
    dentro da suíte (é a razão escrita em
    `test_o_lugar_vazio_para_de_mostrar_o_desenho`). O que ela procura é a
    AUSÊNCIA de uma condição, dentro da função certa — achada pelo `ast`, não
    por um `grep` no arquivo inteiro.
    """
    arvore = ast.parse(PILOTO.read_text(encoding="utf-8"))
    corpo = [n for n in ast.walk(arvore)
             if isinstance(n, ast.FunctionDef) and n.name == "_fita"]
    assert corpo, "o `_fita` sumiu do piloto"
    fonte = ast.get_source_segment(PILOTO.read_text(encoding="utf-8"), corpo[0]) or ""
    # As linhas de comentário explicam a cicatriz e CITAM a guarda velha; a
    # régua olha o código, não a prosa.
    codigo = "\n".join(
        linha for linha in fonte.splitlines()
        if not linha.lstrip().startswith("#")
    )
    assert 'c.get("cor")' not in codigo, (
        "a guarda que desiste da fita quando falta uma cor voltou ao `_fita` — "
        "e com ela volta o mockup na tela dela")


# ---------------------------------------------------------------------------
# 4. O ELO — o alvo que a página pede é um que o pintor sabe escrever
# ---------------------------------------------------------------------------
def test_todo_alvo_que_a_pagina_pede_o_pintor_sabe_escrever() -> None:
    """Nenhum `data-hef-alvo` da 05 é desconhecido do `escrever()` do piloto.

    É O ELO QUE FAZ ESTE CONSERTO SER ENTREGA E NÃO MAQUIAGEM. Um endereço com
    um alvo que o pintor não implementa zera a régua da identidade e deixa a
    tela igualmente mentindo: o `escrever()` cai no ramo padrão e escreve o
    valor como TEXTO — aqui, o `#hex` da cor dentro da moldura, por cima do
    desenho do controle.

    OS DOIS LADOS SÃO LIDOS: os alvos pedidos saem do HTML gerado, e os alvos
    conhecidos saem dos ramos `alvo === '…'` do `BOOTSTRAP`, mais o `texto`, que
    é o padrão quando o atributo falta.
    """
    pedidos = {
        a["data-hef-alvo"] for _t, a in _elementos(BANCADA) if a.get("data-hef-alvo")
    }
    sabidos = set(re.findall(r"alvo === '([a-z]+)'", PILOTO.read_text(encoding="utf-8")))
    sabidos.add("texto")

    assert "plastico" in pedidos, (
        "a bancada da 05 deixou de pedir o alvo da cor do plástico")
    assert pedidos <= sabidos, (
        f"a página pede alvo que o pintor não escreve: {sorted(pedidos - sabidos)}")


def _elementos_de(html: str) -> list[tuple[str, dict[str, str]]]:
    leitor = _Elementos()
    leitor.feed(html)
    return leitor.achados
