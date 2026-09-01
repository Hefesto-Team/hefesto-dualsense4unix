#!/usr/bin/env python3
"""A BANCADA DE BT — o degrau 0.9.5, medido por leitura de arquivo.

ELE NASCEU EM 01/09/2026, e a escada de releases o previa pelo nome:
`docs/process/2026-08-24-A-ESCADA-DE-RELEASES.md`, seção *0.9.5 — o rádio para
de mentir*, declarava *"arquivo a nascer: `scripts/check_bancada_de_bt.py`"*.
Sem ele, o degrau dela não tinha como ser conferido por ninguém — só descrito.

O DEGRAU É DELA, na palavra dela: *"quando terminarmos a bancada do specs em
bt"*. E o que ele exige NÃO é construir canal nenhum. A escada é explícita:

    "Este degrau não manda construir canal nenhum — manda PARAR DE AFIRMAR o que
     não se mediu. Preencher `radio_por_que_nao_aciona` com `decisao-tomada`
     fecha a R1 e é verdade. Rebaixar um `sim` não medido para `parcial` fecha a
     R2 e é verdade."

Por isso este script lê **só dois CSV** — `docs/data/mapa-controles.csv` e
`docs/data/ensaios.csv`. Nada de hardware, nada de daemon: ele roda no CI.

AS QUATRO RÉGUAS, e cada uma sai da tabela da escada:

    R1  célula de rádio que admite NÃO acionar e não nomeia a culpa
    R2  célula de rádio que afirma acionar e não foi medida
    R3  das SETE perguntas de rádio dela, quantas seguem sem medição
    R4  ensaio de rádio no caderno sem o `degrau` preenchido

A QUINTA É DE BANCADA E NÃO ENTRA AQUI: `ls /sys/class/bluetooth/` devolvendo
três adaptadores, e um ensaio com quatro DualSense simultâneos no rádio
observado por ela. Nenhum arquivo responde isso, e fingir que responde seria a
doença que este degrau existe para curar.

O CORTE É `controle == dualsense`, pela decisão **D-J**: cobertura de aparelho
que ela não tem na mesa é assunto da 1.0. `--todos` tira o corte, para o dia em
que ela decidir o contrário.
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
MAPA = RAIZ / "docs/data/mapa-controles.csv"
CADERNO = RAIZ / "docs/data/ensaios.csv"

#: O que conta como "sim" nas colunas de acionamento.
SIM = {"sim", "true", "1"}

#: AS SETE PERGUNTAS DE RÁDIO DELA, do `SPRINT_ORDER.md` §2.1 — e a família do
#: mapa que cada uma destrava. A tabela de lá está na ordem das ABAS, não do
#: protocolo, *"assim cada medição destrava uma tela, e não só uma linha"*.
#:
#: A oitava (o preço em bateria) entra DEPOIS das sete, por pedido dela em
#: 24/08, e por isso não conta aqui.
PERGUNTAS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("vibracao-por-radio",
     "a vibração do jogo chega ao motor por rádio?", ("vibracao",)),
    ("quantos-por-radio",
     "quantos DualSense por rádio o produto sustenta, e com quantos adaptadores?",
     ("plataforma", "identidade")),
    ("alto-falante-por-radio",
     "o alto-falante emite por rádio?", ("audio",)),
    ("barra-de-luz-por-radio",
     "a barra de luz obedece por rádio, e sob qual regime?", ("luz",)),
    ("gatilho-fora-do-rigid",
     "o gatilho adaptativo funciona por rádio fora do `Rigid`?", ("gatilho",)),
    ("cursor-por-radio",
     "gatilho e analógico movem o cursor por rádio?", ("entrada", "combinacao")),
    ("microfone-por-radio",
     "existe fonte de captura de microfone por rádio?", ("audio",)),
)


def _linhas(caminho: pathlib.Path) -> list[dict[str, str]]:
    if not caminho.exists():
        raise SystemExit(
            f"ERRO: não achei {caminho.relative_to(RAIZ)}. Ele é a fonte deste "
            f"portão — sem ele, toda régua daria zero, e zero por ausência de "
            f"dado se lê como aprovação.")
    with caminho.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sim(valor: str | None) -> bool:
    return (valor or "").strip().lower() in SIM


def r1(pecas: list[dict]) -> list[str]:
    """Célula de rádio que admite não acionar e NÃO nomeia a culpa.

    Uma célula assim é a pior forma de vazio: ela diz "não funciona" e não diz
    por quê, então quem lê não sabe se é limitação do aparelho, decisão da casa
    ou trabalho por fazer. A escada é clara — preencher com `decisao-tomada`
    fecha esta régua e é verdade.
    """
    return [f"{peca['chave']}  ({peca['rotulo'][:48]})"
            for peca in pecas
            if not _sim(peca.get("radio_aciona"))
            and not (peca.get("radio_por_que_nao_aciona") or "").strip()]


def r2(pecas: list[dict]) -> list[str]:
    """Célula que AFIRMA acionar por rádio e não foi medida.

    É a afirmação forte sem lastro — a casa dizendo que funciona porque leu o
    código, ou porque supôs do cabo. Rebaixar para `parcial` fecha e é verdade.
    """
    return [f"{peca['chave']}  (de_onde_sei={peca.get('radio_de_onde_sei') or '—'})"
            for peca in pecas
            if _sim(peca.get("radio_aciona"))
            and (peca.get("radio_de_onde_sei") or "").strip() != "medido"]


def r3(pecas: list[dict]) -> list[str]:
    """Das sete perguntas dela, quantas seguem sem UMA medição de rádio.

    A PERGUNTA DELA É SOBRE A TELA, e uma tela não se sustenta numa linha: ela
    só fecha quando TODA a família que destrava estiver medida.

    O critério frouxo — "basta uma peça medida" — foi tentado primeiro e dava
    ZERO, enquanto a escada de 24/08 contava 6 de 7. Régua que devolve zero onde
    o documento conta seis está medindo outra coisa, e zero por critério frouxo
    se lê como aprovação.
    """
    fora = []
    for chave, texto, familias in PERGUNTAS:
        da_familia = [peca for peca in pecas if peca.get("familia") in familias]
        sem_medida = [peca for peca in da_familia
                      if (peca.get("radio_de_onde_sei") or "").strip() != "medido"]
        if sem_medida:
            fora.append(f"{chave}: {texto} "
                        f"({len(sem_medida)} de {len(da_familia)} sem medição)")
    return fora


def r4(ensaios: list[dict]) -> list[str]:
    """Ensaio de rádio no caderno sem o `degrau` preenchido.

    O degrau é a escada de conexão em que o ensaio correu, e sem ele a medição
    não se compara com outra: dois ensaios do mesmo assunto em degraus
    diferentes medem coisas diferentes.
    """
    return [f"{e.get('id') or '?'}  ({(e.get('linha_id') or '')[:40]})"
            for e in ensaios
            if (e.get("transporte") or "").strip().lower() == "radio"
            and not (e.get("degrau") or "").strip()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--todos", action="store_true",
                   help="tira o corte `dualsense` — inclui Pro e 8BitDo, que a "
                        "decisão D-J deixou para a 1.0")
    p.add_argument("--lista", action="store_true",
                   help="mostra cada item de cada régua, não só a contagem")
    args = p.parse_args()

    pecas = _linhas(MAPA)
    if not args.todos:
        pecas = [peca for peca in pecas if peca.get("controle") == "dualsense"]
    ensaios = _linhas(CADERNO)

    reguas = (
        ("R1", "admite não acionar por rádio e não nomeia a culpa", r1(pecas)),
        ("R2", "afirma acionar por rádio e não foi medido", r2(pecas)),
        ("R3", "pergunta de rádio dela com peça da família por medir", r3(pecas)),
        ("R4", "ensaio de rádio sem o degrau preenchido", r4(ensaios)),
    )

    alvo = "todos os controles" if args.todos else "DualSense (corte da D-J)"
    print(f"bancada de BT — {len(pecas)} peças de {alvo}, {len(ensaios)} ensaios\n")
    total = 0
    for nome, texto, itens in reguas:
        total += len(itens)
        marca = "ok " if not itens else "FALTA"
        print(f"  {marca} {nome}  {len(itens):3d}  {texto}")
        if args.lista and itens:
            for i in itens[:40]:
                print(f"           · {i}")
            if len(itens) > 40:
                print(f"           … e mais {len(itens) - 40}")

    print()
    if total:
        print(f"O DEGRAU 0.9.5 NÃO ESTÁ FECHADO: {total} pendência(s) nas quatro réguas.")
        print("Elas fecham por HONESTIDADE, não por construção — a escada de")
        print("releases diz com todas as letras que este degrau *'não manda")
        print("construir canal nenhum, manda parar de afirmar o que não se mediu'*.")
        print()
        print("E A QUINTA RÉGUA NÃO ESTÁ AQUI: três adaptadores em")
        print("`/sys/class/bluetooth/` e um ensaio com quatro DualSense no rádio,")
        print("observado por ela. Nenhum arquivo responde isso.")
        return 1
    print("As quatro réguas de arquivo estão zeradas.")
    print("Falta a R5, que é de bancada e não se lê em arquivo: três adaptadores")
    print("e um ensaio de quatro DualSense no rádio, com o olho dela.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
