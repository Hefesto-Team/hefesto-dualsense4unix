#!/usr/bin/env python3
"""NADA-MOCKADO-01 — o portão que responde à pergunta dela, e não envelhece.

**A PERGUNTA DELA, 08/09/2026:**

    "acelerômetro, giroscópio, máscara nintendo e modo (tanto o switch ps + R3)
     quanto o funcionamento mútuo delas estão funcionando? e serão reconhecidos
     in game? Tipo todas as features aqui. não tem nada rodando em sandbox ou
     mockada, certo?"
    (noqa-acento: citação literal dela, palavra por palavra)

**Esta pergunta não se responde com uma resposta — ela se responde com um
PORTÃO**, senão a resposta envelhece no dia seguinte. É a mesma forma do
`casa-sabe`, que responde *"o produto FAZ o que a casa diz?"*.

## Por que esta casa não pode responder de cabeça

Está escrito, e é a cicatriz de 03/09: **quatro instrumentos davam verde sobre
nada**. E a de 04/09: *"a máscara que NUNCA gravou um byte — o dicionário ia
como `timeout` posicional, e o dublê do teste era mais frouxo que a ponte
real"*. A máscara Nintendo é uma das linhas dessa lista.

## O que este portão mede

Uma linha do mapa que diz **`aciona = sim`** está afirmando que o aparelho FAZ
aquilo. Três coisas podem sustentar a afirmação:

1. **`provado_por`** preenchido — alguém provou, e a coluna diz como
   (`aparelho`, `fonte-do-driver`, `olho-dela`, `descritor`);
2. uma **ressalva declarada** naquele transporte (`cabo_ressalva` /
   `radio_ressalva`) — a afirmação vem com o que a limita, escrito;
3. nada — e aí é **desenho fingindo ser produto**.

**MEDIDO EM 09/09/2026, nas 311 linhas do mapa:**

    afirmações fortes (aciona = sim)             208
    sem `provado_por`                            104
    dessas, COM ressalva declarada                68
    dessas, sem prova E sem ressalva              36   <- a dívida

Das 104 sem prova, **81 dizem `de_onde_sei = inferido-do-codigo`**: o mapa
afirma que o aparelho aciona porque alguém LEU o código, não porque tocou o
aparelho. *Ler o código e tocar o aparelho são coisas diferentes, e esta casa
tem quatro cicatrizes provando isso.*

## O TETO, e por que ele não é frouxidão

Exigir prova de aparelho nas 104 hoje pararia a casa — e a sprint diz o
contrário: *"comece por ali, não do zero"*. O que este portão faz é **travar a
dívida onde ela está**: uma linha NOVA que afirme forte tem de trazer prova ou
ressalva, e o número só desce.

É o mesmo desenho de `_CITACOES_PENDENTES` e das listas de isenção declarada
que os outros portões desta casa usam.
"""
from __future__ import annotations

import csv
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs/data/mapa-controles.csv"

#: A DÍVIDA DE 09/09/2026, e ela **só desce**. Quem baixar o número troca esta
#: constante no mesmo commit — é a prova de que a linha ganhou prova ou
#: ressalva, e não de que a régua afrouxou.
#:
#: **SE VOCÊ PRECISA SUBIR ESTE NÚMERO, a linha nova está errada**: ela afirma
#: que o aparelho aciona sem ninguém ter provado e sem dizer o que limita a
#: afirmação. Ponha `provado_por` (como provou) ou a ressalva do transporte.
TETO_SEM_PROVA_NEM_RESSALVA = 36

#: O MESMO PARA O CONJUNTO MAIOR — as fortes sem `provado_por`, com ou sem
#: ressalva. Ele desce mais devagar (cada uma pede aparelho na mesa dela), e
#: está aqui para que a conta não se perca entre uma leva e outra.
TETO_SEM_PROVA = 104

_SIM = {"sim", "1", "true"}


def _linhas() -> list[dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fortes_sem_prova() -> list[tuple[str, str, str]]:
    """`(chave, transporte, de_onde_sei)` de toda afirmação forte sem prova."""
    fora = []
    for linha in _linhas():
        for lado in ("cabo", "radio"):
            if linha.get(f"{lado}_aciona", "").strip().lower() not in _SIM:
                continue
            if linha.get("provado_por", "").strip():
                continue
            fora.append((linha.get("chave", ""), lado,
                         linha.get(f"{lado}_de_onde_sei", "").strip()))
    return fora


def _sem_prova_nem_ressalva() -> list[tuple[str, str, str]]:
    fora = []
    for linha in _linhas():
        for lado in ("cabo", "radio"):
            if linha.get(f"{lado}_aciona", "").strip().lower() not in _SIM:
                continue
            if linha.get("provado_por", "").strip():
                continue
            if linha.get(f"{lado}_ressalva", "").strip():
                continue
            fora.append((linha.get("chave", ""), lado,
                         linha.get(f"{lado}_de_onde_sei", "").strip()))
    return fora


def test_a_divida_das_afirmacoes_sem_prova_nem_ressalva_nao_cresce() -> None:
    """O piso da pergunta dela: nada de novo é afirmado sem sustentação.

    **A MORDIDA:** ponha uma linha nova no mapa com `cabo_aciona=sim`, sem
    `provado_por` e sem `cabo_ressalva`, e esta linha reprova nomeando a
    chave.
    """
    achados = _sem_prova_nem_ressalva()

    assert len(achados) <= TETO_SEM_PROVA_NEM_RESSALVA, (
        f"{len(achados)} linhas do mapa dizem que o aparelho ACIONA sem "
        f"`provado_por` e sem ressalva declarada — o teto é "
        f"{TETO_SEM_PROVA_NEM_RESSALVA}. As novas:\n  " +
        "\n  ".join(f"{c} [{lado}] de_onde_sei={fonte or '(vazio)'}"
                    for c, lado, fonte in achados[TETO_SEM_PROVA_NEM_RESSALVA:]))


def test_o_teto_acompanha_a_realidade_e_nunca_sobra() -> None:
    """Um teto folgado é um portão desligado — e é a cicatriz de 03/09.

    Se a dívida caiu e ninguém baixou a constante, o portão passa a aceitar
    afirmações novas sem sustentação, em silêncio. *Régua com folga acumulada
    dá verde sobre o defeito seguinte.*

    **A MORDIDA:** suba `TETO_SEM_PROVA_NEM_RESSALVA` para 50 e esta linha
    reprova dizendo quanto sobrou.
    """
    achados = len(_sem_prova_nem_ressalva())

    assert achados == TETO_SEM_PROVA_NEM_RESSALVA, (
        f"a dívida é {achados} e o teto diz {TETO_SEM_PROVA_NEM_RESSALVA} — "
        + ("baixe a constante no mesmo commit que baixou a dívida"
           if achados < TETO_SEM_PROVA_NEM_RESSALVA
           else "alguém afirmou sem sustentar"))


def test_a_divida_maior_das_afirmacoes_sem_prova_nao_cresce() -> None:
    """As 104 que afirmam forte e ninguém provou — com ou sem ressalva.

    **81 delas dizem `inferido-do-codigo`**, que é ler o código e não tocar o
    aparelho. Elas descem uma a uma, na bancada dela.

    **A MORDIDA:** a mesma da primeira; sem `cabo_ressalva` a linha cai nas
    duas contas, com ela cai só nesta.
    """
    achados = _fortes_sem_prova()

    assert len(achados) == TETO_SEM_PROVA, (
        f"as afirmações fortes sem `provado_por` são {len(achados)} e o teto "
        f"diz {TETO_SEM_PROVA}")


def test_medido_e_provado_nao_podem_discordar() -> None:
    """`de_onde_sei = medido` sem `provado_por` é o mapa discordando de si.

    **ACHADO AO ESCREVER ESTE PORTÃO, 09/09/2026: vinte linhas** dizem que a
    coisa foi MEDIDA e deixam em branco COMO se provou. As duas colunas
    respondem perguntas diferentes — *"de onde eu sei?"* e *"quem provou?"* —,
    mas `medido` só pode vir de um dos quatro jeitos que `provado_por` lista.

    O teto é o de hoje, e é um número pequeno de propósito: ele desce quando
    alguém escrever COMO mediu.

    **A MORDIDA:** ponha `de_onde_sei=medido` numa linha sem `provado_por` e o
    número sobe.
    """
    #: **MEDIDO EM 09/09/2026: são VINTE**, e o número saiu errado na primeira
    #: volta desta régua — eu contei seis, que é o subconjunto SEM ressalva.
    #: As outras catorze têm ressalva declarada e continuam sem dizer quem
    #: provou: as duas perguntas são independentes, e uma ressalva não
    #: responde *"quem mediu?"*.
    #:
    #: *Contar o subconjunto e chamá-lo do conjunto é a mesma família do
    #: número que envelhece calado.*
    teto = 20
    mudas = [(c, lado) for c, lado, fonte in _fortes_sem_prova()
             if fonte == "medido"]

    assert len(mudas) <= teto, (
        f"{len(mudas)} linhas dizem `de_onde_sei=medido` e não dizem quem "
        f"provou — o teto é {teto}:\n  " +
        "\n  ".join(f"{c} [{lado}]" for c, lado in mudas[teto:]))
