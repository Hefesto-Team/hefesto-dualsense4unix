#!/usr/bin/env python3
"""A ABA 05 VESTE A COR DO CONTROLE LIDO — a identidade vem da fita, não do desenho."""
from __future__ import annotations

import ast
import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao

import monta

BANCADA = RAIZ / "mockup/05-vibracao.html"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: `""` NÃO é descuido: é o que `mesa_viva.mesa_do_estado` põe quando o mapa de
LIDO = "white"
SEM_LEITURA = ""

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
    quatro DualSense do usuário na mesa: o daemon publicava os quatro, o pacote
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


def test_o_pacote_veste_a_cor_lida_e_nao_inventa_a_que_faltou() -> None:
    """`plastico` sai do pacote com o `#hex` do controle, ou vazio."""
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


def test_o_chip_da_fita_tem_dono_e_cala_a_cor_que_nao_veio() -> None:
    """`monta.fita` emite chips endereçados e não levanta sem colorway.

    DUAS COISAS NUMA SÓ FUNÇÃO porque são a mesma linha do gerador:

    * `data-campo` diz que ali não mora desenho — o produto troca a fita
      inteira a cada tique (`hefesto_vivo._fita`), e sem o endereço a régua da
      identidade contava os três valores de cada chip como congelados;
    * um controle SEM colorway não pode derrubar a fita. `cor_da_zona("")`
      levanta `SystemExit`, e era isso que fazia o piloto desistir da fita
      inteira e deixar os dois controles do MOCKUP na tela do usuário.

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
    inteira, e é a regra de produto: campo sem informação não mostra nada.

    Com o recorte velho a própria régua se contradizia: ela exigia dois chips
    **e** que o segundo não tivesse cor, e o segundo era justamente o que a
    classe deixava de fora. Duas coisas que não podem ser verdade juntas — e o
    merge do dia deixou esta função vermelha no `dev`.

    `data-campo="fita-chip"` é o endereço, está nos dois, e é o que estas linhas
    medem. A CLASSE PASSA A SER COBRADA em vez de recortar, o que faz esta régua
    medir uma coisa a mais do que antes de quebrar.
    """
    html = monta.fita(mesa=_mesa(LIDO, SEM_LEITURA))
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
    """A guarda de `_fita` não pode voltar a exigir cor de TODO controle."""
    arvore = ast.parse(PILOTO.read_text(encoding="utf-8"))
    corpo = [n for n in ast.walk(arvore)
             if isinstance(n, ast.FunctionDef) and n.name == "_fita"]
    assert corpo, "o `_fita` sumiu do piloto"
    fonte = ast.get_source_segment(PILOTO.read_text(encoding="utf-8"), corpo[0]) or ""
    codigo = "\n".join(
        linha for linha in fonte.splitlines()
        if not linha.lstrip().startswith("#")
    )
    assert 'c.get("cor")' not in codigo, (
        "a guarda que desiste da fita quando falta uma cor voltou ao `_fita` — "
        "e com ela volta o mockup na tela dela")


def test_todo_alvo_que_a_pagina_pede_o_pintor_sabe_escrever() -> None:
    """Nenhum `data-hef-alvo` da 05 é desconhecido do `escrever()` do piloto."""
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
