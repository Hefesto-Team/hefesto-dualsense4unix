"""Nenhuma linha do mapa afirma sem dizer DE ONDE SABE — e o ponteiro se segue.

O DEFEITO, E ELE É DELA
------------------------
Palavra dela, 26/08/2026, sobre as features do DualSense pelo cabo:

    "já validamos via testes individuais mas nunca marcamos num canto e
     integramos ao projeto lá, usamos a tentativa e erro pra eliminação e
     equiparar as features do cabo com os canais do bt."

O conhecimento existe. Está em teste, em sprint, em commit e na cabeça dela. O
que faltava era **o ponteiro de cada linha para a prova dela** — e o mapa não
tinha régua nenhuma cobrando isso.

O ESTADO MEDIDO, E ELE MUDOU DUAS VEZES
----------------------------------------
Em 26/08/2026 a sprint contou **62 afirmações sem procedência** (`cabo_aceita =
sim` com `ponte_de_onde_sei` vazio). Em 06/09/2026, com o mapa em 308 linhas e
616 células, o número que sobrava era outro e menor: **30 células diziam de onde
sabem e não diziam ONDE isso está escrito**.

Dessas 30, **SETE eram piores que vazias**: o `radio_codigo_ref` delas dizia
`idem`. `idem` ocupa a coluna do ponteiro sem apontar — é legível por gente e
ilegível por régua, o `validar-citacoes-de-linha.py` não o confere, e o
`specs.html` publica a palavra no lugar do endereço. Quem abre só a metade do
rádio não tem para onde ir.

**As 30 fecharam em 06/09/2026, e o piso agora é ZERO.** As sete `idem` ganharam
o endereço que a palavra escondia; as outras 23 ganharam o `grep` ou o
`arquivo:linha` que as sustenta, cada um conferido rodando o comando.

O QUE ESTA RÉGUA COBRA — quatro regras, todas DURAS
----------------------------------------------------
1. `test_a_celula_que_afirma_diz_de_onde_sabe` — célula que AFIRMA
   (`aciona`/`aceita` em `sim`/`parcial`) com `*_de_onde_sei` VAZIO.
2. `test_a_celula_medida_aponta_a_prova` — `*_de_onde_sei = medido` sem UM
   ponteiro sequer. É a regra mais dura das quatro de propósito: `medido` é a
   palavra mais forte do vocabulário deste mapa, e dizer "eu medi" sem dizer
   onde está a medição é a forma exata do instrumento que dá verde sobre nada.
3. `test_o_ponteiro_da_procedencia_se_pode_seguir` — `*_codigo_ref` com uma
   palavra da família `idem` no lugar do endereço.
4. `test_toda_procedencia_declarada_aponta_a_prova` — o piso ZERO das 30.

E A QUINTA GUARDA UM DEFEITO DE FORMA, não de dado
---------------------------------------------------
`test_a_mesa_e_a_procedencia_leem_as_mesmas_colunas` amarra esta régua à
`scripts/mesa_de_medicao.py`. A mesa monta o **COMO** de cada célula
(`_como_da_celula`: canal, report, offset, comando, código, mordida) e esta
régua cobra o **DE ONDE SEI** — duas perguntas irmãs sobre as MESMAS colunas,
com duas leituras independentes. No dia em que uma coluna mudar de nome, uma das
duas passa a responder outra coisa CALADA, e é a régua que mente, não o produto.
É o defeito que esta casa já pagou em 05/09/2026, quando *a régua da palavra
vigiava UMA palavra na tela nova e o portão vigiava ONZE*.

A cura é a regra da casa: **pergunta com dono se PERGUNTA ao dono.** O dono é
`check_paridade_transporte.procedencia_da_celula()`, e este arquivo o importa em
vez de reimplementar. O que a quinta guarda mede é a metade que a mesa NÃO pode
importar hoje sem ser editada — os dois campos que as duas leituras partilham
(`código` e `mordida`) têm de sair idênticos, célula por célula.

O QUE ELA NÃO PROVA, dito na cara
----------------------------------
Nada aqui põe o dedo no aparelho, e nada aqui confere se o ponteiro diz a
VERDADE. Ela cobra que o ponteiro EXISTA e que se possa segui-lo. Que o byte
seja 11 e não 47 continua sendo bancada — é o limite honesto que a docstring do
`check_paridade_transporte.py` já declara para a regra 19, e esta régua fica do
mesmo lado dele.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
MESA = RAIZ / "scripts" / "mesa_de_medicao.py"

sys.path.insert(0, str(RAIZ / "scripts"))
# O DONO DA PERGUNTA, e a razão de importar em vez de copiar está na docstring
# acima: duas leituras das mesmas colunas divergem CALADAS no dia em que o mapa
# muda de forma.
from check_paridade_transporte import (
    LADOS,
    PONTEIRO_QUE_NAO_SE_SEGUE,
    caderno_de_ensaios,
    procedencia_da_celula,
)

#: O que conta como AFIRMAÇÃO. `desconhecido` fica de fora de propósito: ele é
#: uma resposta honesta ("olhamos e não sabemos"), não uma afirmação — e
#: castigá-lo seria cobrar procedência de quem está justamente confessando que
#: não tem.
AFIRMA = frozenset({"sim", "parcial"})

#: A palavra mais forte do vocabulário do mapa.
MEDIDO = "medido"

#: O PISO, e ele é ZERO desde 06/09/2026. Este número existe para o dia em que
#: alguém acrescentar uma linha nova ao mapa sem o ponteiro: a régua nomeia a
#: célula, e não deixa o mapa voltar a crescer em afirmação sem prova.
#:
#: Ele NÃO é um teto móvel para conveniência. Se uma leva precisar subi-lo, a
#: subida é uma decisão escrita — e o commit que a fizer tem de dizer qual
#: célula ficou sem prova e por quê.
CELULAS_SEM_PONTEIRO_HOJE = 0


def _linhas() -> list[dict[str, str]]:
    with MAPA.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def linhas() -> list[dict[str, str]]:
    return _linhas()


@pytest.fixture(scope="module")
def ensaios() -> dict[tuple[str, str], list[dict]] | None:
    indice, _motivo = caderno_de_ensaios(RAIZ)
    return indice


def _celulas(linhas: list[dict[str, str]]):
    for linha in linhas:
        for lado in LADOS:
            yield linha, lado


def test_a_celula_que_afirma_diz_de_onde_sabe(linhas: list[dict[str, str]]) -> None:
    """Afirmar sem dizer de onde se sabe é o defeito que esta sprint nomeou.

    A regra 19 do `check_paridade_transporte.py` já cobra o caso em que há
    CONTEÚDO escrito naquele lado. Esta cobre o outro: a célula que responde
    `aceita`/`aciona` e não escreve mais nada — o `sim` pelado, que passava.
    """
    mudas = [
        f"{linha['id']} [{lado}]: aceita={linha[f'{lado}_aceita']!r} "
        f"aciona={linha[f'{lado}_aciona']!r} e `{lado}_de_onde_sei` vazia"
        for linha, lado in _celulas(linhas)
        if (
            (linha[f"{lado}_aciona"] or "").strip() in AFIRMA
            or (linha[f"{lado}_aceita"] or "").strip() in AFIRMA
        )
        and not (linha[f"{lado}_de_onde_sei"] or "").strip()
    ]
    assert not mudas, (
        "célula que AFIRMA sobre um transporte sem dizer de onde sabe — o mapa "
        "publica a afirmação no `specs.html` e ninguém consegue segui-la:\n  "
        + "\n  ".join(mudas)
    )


def test_a_celula_medida_aponta_a_prova(
    linhas: list[dict[str, str]],
    ensaios: dict[tuple[str, str], list[dict]] | None,
) -> None:
    """`medido` sem ponteiro nenhum é o instrumento que dá verde sobre nada."""
    sem_prova = [
        f"{linha['id']} [{lado}]"
        for linha, lado in _celulas(linhas)
        if (proc := procedencia_da_celula(linha, lado, ensaios)).de_onde_sei == MEDIDO
        and not proc.tem_ponteiro
    ]
    assert not sem_prova, (
        f"célula com `cabo_de_onde_sei`/`radio_de_onde_sei` = {MEDIDO} e NENHUM ponteiro para a "
        "prova (nem carimbo `provado_em`+`provado_por`, nem `teste_que_morde`, "
        "nem `*_codigo_ref`, nem `fonte_externa`, nem evidência com endereço, "
        "nem ensaio no caderno). Dizer que mediu sem dizer onde está a medição é "
        "afirmação sem rede:\n  " + "\n  ".join(sem_prova)
    )


def test_o_ponteiro_da_procedencia_se_pode_seguir(
    linhas: list[dict[str, str]],
) -> None:
    """`idem` na coluna do ponteiro ocupa o lugar do endereço sem apontar.

    Medido em 06/09/2026: SETE células de `radio_codigo_ref` diziam `idem`, e as
    sete eram justamente as que ninguém conseguiria seguir abrindo só o lado do
    rádio. `—` e `não-localizado` NÃO caem aqui de propósito — as duas dizem
    *"não há endereço"*, que é resposta; `idem` diz *"o endereço está noutro
    lugar"* sem dizer onde.
    """
    escondidos = [
        f"{linha['id']} [{lado}]: `{lado}_codigo_ref` = "
        f"{(linha[f'{lado}_codigo_ref'] or '').strip()!r}"
        for linha, lado in _celulas(linhas)
        if (linha[f"{lado}_codigo_ref"] or "").strip().lower()
        in PONTEIRO_QUE_NAO_SE_SEGUE
    ]
    assert not escondidos, (
        "ponteiro que não se segue na coluna do endereço. Escreva o endereço, "
        "mesmo que ele seja o mesmo do outro lado — quem abre a metade do rádio "
        "não vê a do cabo, e nenhuma régua desta casa confere uma palavra:\n  "
        + "\n  ".join(escondidos)
    )


def test_toda_procedencia_declarada_aponta_a_prova(
    linhas: list[dict[str, str]],
    ensaios: dict[tuple[str, str], list[dict]] | None,
) -> None:
    """O piso ZERO: quem diz de onde sabe diz ONDE isso está escrito."""
    sem_ponteiro = [
        f"{proc.id} [{proc.lado}]: de_onde_sei={proc.de_onde_sei}"
        for linha, lado in _celulas(linhas)
        if (proc := procedencia_da_celula(linha, lado, ensaios)).de_onde_sei
        and not proc.tem_ponteiro
    ]
    assert len(sem_ponteiro) <= CELULAS_SEM_PONTEIRO_HOJE, (
        f"{len(sem_ponteiro)} célula(s) declaram de onde sabem e não apontam "
        f"para prova nenhuma; o piso desta casa é {CELULAS_SEM_PONTEIRO_HOJE}. "
        "Aponte o `arquivo:linha`, o `grep` que você rodou, o ensaio do caderno "
        "ou o teste que morde:\n  " + "\n  ".join(sem_ponteiro)
    )


def test_a_mesa_e_a_procedencia_leem_as_mesmas_colunas(
    linhas: list[dict[str, str]],
    ensaios: dict[tuple[str, str], list[dict]] | None,
) -> None:
    """A mesa de medição e o dono da procedência não podem divergir.

    A `scripts/mesa_de_medicao.py` responde *como se exercita esta célula* e
    esta régua responde *de onde se sabe esta célula*. As duas leem as MESMAS
    colunas para dois dos campos — o endereço no código e o teste que morde —, e
    a mesa hoje as lê por conta própria (`_como_da_celula`).

    Esta guarda existe para o dia em que uma delas mudar: se a mesa passar a ler
    outra coluna, ou se o dono passar a ler outra, o desacordo aparece AQUI, com
    nome de célula, em vez de aparecer numa página que ela abre na bancada
    dizendo a coisa errada. **O melhor desfecho é a mesa importar o dono** — o
    endereço está na entrega desta sprint; enquanto isso não acontece, esta
    régua é a rede.
    """
    if not MESA.is_file():  # pragma: no cover - a mesa é de 06/09/2026
        pytest.skip("scripts/mesa_de_medicao.py não existe nesta árvore")

    import mesa_de_medicao

    divergem: list[str] = []
    for linha, lado in _celulas(linhas):
        como = dict(mesa_de_medicao._como_da_celula(linha, lado))
        proc = procedencia_da_celula(linha, lado, ensaios)
        ponteiros = dict(proc.ponteiros)
        for rotulo_da_mesa, rotulo_do_dono in (
            ("código", "código"),
            ("teste que morde", "mordida"),
        ):
            da_mesa = como.get(rotulo_da_mesa, "")
            do_dono = ponteiros.get(rotulo_do_dono, "")
            # O dono RECUSA `idem` (é o que a terceira regra cobra) e a mesa não
            # sabe recusar nada — então uma diferença só é divergência quando o
            # valor da mesa não é um ponteiro que o dono descartou de propósito.
            if da_mesa.lower() in PONTEIRO_QUE_NAO_SE_SEGUE:
                continue
            if da_mesa != do_dono:
                divergem.append(
                    f"{linha['id']} [{lado}] · {rotulo_da_mesa}: a mesa lê "
                    f"{da_mesa!r} e o dono lê {do_dono!r}"
                )

    assert not divergem, (
        "a `mesa_de_medicao._como_da_celula` e a "
        "`check_paridade_transporte.procedencia_da_celula` respondem coisas "
        "diferentes sobre as mesmas colunas. Uma das duas vai mentir no dia em "
        "que o mapa mudar — a cura é a mesa PERGUNTAR ao dono, não as duas "
        "lerem o CSV por conta própria:\n  " + "\n  ".join(divergem[:20])
    )
