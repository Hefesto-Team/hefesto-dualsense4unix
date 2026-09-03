#!/usr/bin/env python3
"""check_identidade_vem_de_cima.py — a identidade do controle vem da FITA, nunca do mockup.

A LEI, e ela é dela (03/09/2026)
---------------------------------
    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado. Por isso temos o mapa pra servir como
    variável de identificação"

A fita do topo lê do aparelho. Toda aba abaixo dela tem de usar AQUELE controle.
Um nome de cor ou um `--plastico` escrito à mão dentro da página é o mockup
mandando na tela do produto — e o resultado é o que ela viu em 03/09: a fita
dizendo `P1 · White · USB` com o card logo abaixo dizendo `Cosmic Red`.

POR QUE ESTA RÉGUA EXISTE ALÉM DA QUE JÁ HAVIA
-----------------------------------------------
A `interface/regua_do_mockup.py` mede muito bem — mas ela só enumera elementos
que JÁ TÊM endereço: `ATRIBUTOS_DE_CAMPO = ("data-campo", "data-papel",
"data-hef")`. Um valor congelado sem endereço nenhum **não é um campo para
ela**, e por isso não aparece nem como `MOCKUP` nem como `INDECIDÍVEL` — ele
simplesmente não é contado.

Medido em 03/09/2026: a régua velha dizia `283 PRODUTO · 53 MOCKUP · 0
INDECIDÍVEL` enquanto havia **129 nomes de cor e 48 `--plastico` congelados**
fora do alcance dela. As duas réguas não se sobrepõem: uma mede o que tem
endereço, esta acha o que não tem.

É a regra desta casa, e ela já foi paga três vezes: **duas réguas independentes
é o que revela.** Uma régua que só olha onde já se olhou não descobre nada.

O QUE ELA REPROVA
-----------------
Numa página PUBLICADA (`interface/paginas/NN-*.html`), qualquer um destes:

1. `--plastico:#hex` escrito à mão num elemento sem endereço que permita ao
   produto reescrevê-lo;
2. um nome de colorway do `docs/data/cores-do-dualsense.csv` no texto que a
   TELA mostra, num elemento sem endereço.

Comentário não conta — `<!-- ... -->` e `/* ... */` são prosa, e contá-los
inflaria o número. Número inflado é a coisa que esta casa mais derruba.

O que ela NÃO reprova, de propósito: `P1`, `P2`, `P3`, `P4`. O número do
jogador é ESTRUTURA — é a posição na mesa, não a identidade do aparelho. Ela
disse com todas as letras: *"O p1 ou p2 reflete o player do jogador."*

AS ISENÇÕES
-----------
Um valor congelado legítimo (a legenda de uma ajuda, um exemplo dentro de um
texto explicativo) se declara em `ISENCOES`, com a razão. Isenção sem razão não
é isenção — é ponto cego com nome bonito.

    scripts/check_identidade_vem_de_cima.py            # reprova, listando
    scripts/check_identidade_vem_de_cima.py --censo    # só o retrato, rc=0
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys
from html.parser import HTMLParser

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
CORES_CSV = RAIZ / "docs/data/cores-do-dualsense.csv"

#: Os atributos que dão ao produto o direito de reescrever o elemento. São os
#: MESMOS da `regua_do_mockup` de propósito: duas réguas com vocabulários
#: diferentes seria uma terceira forma de mentir.
ENDERECOS = ("data-campo", "data-papel", "data-hef")

COMENTARIO = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)
PLASTICO = re.compile(r"--plastico\s*:\s*(#[0-9a-fA-F]{3,8}|var\([^)]*\))")

#: Isenções declaradas, com a razão. `(arquivo, agulha) -> por quê`.
#: Vazia hoje, e isso é uma afirmação: nenhum congelado desta árvore se
#: justificou ainda. Quem acrescentar uma linha aqui está dizendo "este valor
#: NÃO é identidade de aparelho", e tem de poder defender isso.
ISENCOES: dict[tuple[str, str], str] = {}


def nomes_de_colorway() -> list[str]:
    """Os nomes de cor, lidos do CSV que é dono deles.

    Digitá-los aqui criaria uma segunda lista que envelhece sozinha — o defeito
    que o `cores-do-dualsense.csv` existe para não ter.
    """
    linhas = [
        linha
        for linha in CORES_CSV.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    nomes = {
        (linha.get("nome") or "").strip()
        for linha in csv.DictReader(linhas)
    }
    # Os mais longos primeiro: senão "White" casa dentro de nada, mas um nome
    # composto que contenha outro daria dois achados no mesmo texto.
    return sorted((n for n in nomes if len(n) >= 4), key=len, reverse=True)


class _Varredor(HTMLParser):
    """Percorre a página guardando a PILHA de ancestrais de cada posição.

    POR QUE UMA PILHA, E NÃO A TAG MAIS PRÓXIMA À ESQUERDA: a primeira versão
    desta régua olhava o `<` anterior, e isso a fazia acusar texto que vem
    depois de um `</span>` mesmo com o endereço correto no elemento PAI. Num
    `<span data-campo="x">P1 <span class="pt">•</span> White</span>` o "White"
    tem à esquerda um `</span>` sem endereço — e a régua velha o acusava.

    Acusar quem já está curado é o pior defeito que uma régua pode ter: ela
    manda consertar o que está certo. Foi pego na mordida, antes de despachar
    ninguém para caçar o fantasma.
    """

    def __init__(self, nomes: list[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.nomes = nomes
        self.pilha: list[bool] = []          # cada nível: tem endereço?
        self.achados: list[tuple[int, str, str]] = []

    #: Tags que não fecham — sem elas a pilha desanda e tudo depois fica errado.
    VAZIAS = frozenset(
        ["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"]
    )

    def _coberto(self) -> bool:
        return any(self.pilha)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        dicio = {k: (v or "") for k, v in attrs}
        tem = any(a in dicio for a in ENDERECOS)
        linha = self.getpos()[0]

        # O `--plastico` mora no atributo `style` do PRÓPRIO elemento, então ele
        # é julgado pelo endereço DELE, não pelo dos ancestrais: um pai
        # endereçado não dá ao filho o direito de trazer cor congelada.
        estilo = dicio.get("style", "")
        if not tem:
            for m in PLASTICO.finditer(estilo):
                self._registrar(linha, "--plastico cravado", m.group(0))

        # O `title` é texto que a tela mostra (a dica), então conta.
        for atributo in ("title", "aria-label"):
            if atributo in dicio and not (tem or self._coberto()):
                self._nomes_em(linha, dicio[atributo], f"no {atributo}")

        if tag not in self.VAZIAS:
            self.pilha.append(tem)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VAZIAS and self.pilha:
            self.pilha.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.VAZIAS and self.pilha:
            self.pilha.pop()

    def handle_data(self, data: str) -> None:
        if self._coberto():
            return
        self._nomes_em(self.getpos()[0], data, "no texto")

    def _nomes_em(self, linha: int, texto: str, onde: str) -> None:
        for nome in self.nomes:
            if nome in texto:
                self._registrar(linha, f"nome de cor congelado {onde} ({nome})", nome)
                return          # o mais longo já casou; não conta duas vezes

    def _registrar(self, linha: int, o_que: str, trecho: str) -> None:
        self.achados.append((linha, o_que, " ".join(trecho.split())[:90]))


def congelados_de(caminho: pathlib.Path, nomes: list[str]) -> list[tuple[int, str, str]]:
    """Os valores de identidade congelados nesta página.

    Devolve `(linha, o quê, o trecho)`, sem repetição.
    """
    bruto = caminho.read_text(encoding="utf-8", errors="replace")
    # As quebras de linha sobrevivem ao apagador de prosa; sem isso um
    # comentário de vinte linhas vira uma só e todo número depois dele erra.
    limpo = COMENTARIO.sub(
        lambda m: "".join(c if c == "\n" else " " for c in m.group(0)), bruto
    )
    varredor = _Varredor(nomes)
    varredor.feed(limpo)
    achados = [
        (linha, o_que, trecho)
        for linha, o_que, trecho in varredor.achados
        if (caminho.name, trecho) not in ISENCOES
    ]
    return sorted(set(achados))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--censo", action="store_true",
                   help="só o retrato de hoje, sem reprovar")
    #: A BANCADA existe aqui por causa do fluxo que ELA decidiu: os geradores
    #: escrevem em `mockup/`, e PUBLICAR é ato dela. Sem esta opção, quem
    #: conserta uma aba não teria como provar o conserto — a página publicada só
    #: fica verde no minuto em que ela mandar publicar. Medir a bancada é medir o
    #: trabalho; medir o publicado é medir a tela dela. São coisas diferentes e
    #: as duas importam.
    p.add_argument("--bancada", action="store_true",
                   help="mede `mockup/` em vez das páginas publicadas")
    p.add_argument("--aba", default="", help="só esta aba (ex.: 04)")
    args = p.parse_args()

    alvo = (RAIZ / "mockup") if args.bancada else PAGINAS
    if not alvo.is_dir():
        print(f"não achei as páginas em {alvo}", file=sys.stderr)
        return 2

    nomes = nomes_de_colorway()
    total = 0
    print(f"{'bancada' if args.bancada else 'publicado':<26} {'congelados':>11}")
    print("-" * 40)
    detalhe: list[str] = []
    padrao = f"{args.aba}-*.html" if args.aba else "[0-9][0-9]-*.html"
    for caminho in sorted(alvo.glob(padrao)):
        achados = congelados_de(caminho, nomes)
        total += len(achados)
        if achados:
            print(f"{caminho.name:<26} {len(achados):>11}")
            for linha, o_que, trecho in achados[:6]:
                detalhe.append(f"  {caminho.name}:{linha}  {o_que}  ->  {trecho}")
            if len(achados) > 6:
                detalhe.append(f"  {caminho.name}: … e mais {len(achados) - 6}")
    print("-" * 40)
    print(f"{'TOTAL':<26} {total:>11}")

    if detalhe:
        print()
        print("\n".join(detalhe))

    if args.censo:
        return 0
    if total:
        print()
        print("A identidade do controle vem da FITA DO TOPO, que lê do aparelho —")
        print("nunca do mockup. Cada valor acima é o desenho mandando na tela do")
        print("produto: a fita diz `P1 · White · USB` e a aba abaixo diz outra coisa.")
        print()
        print("O conserto é dar ENDEREÇO ao elemento (`data-campo` + `data-hef-alvo`)")
        print("e o pacote da aba passar a escrevê-lo com o que leu do daemon.")
        print("Se o valor NÃO for identidade de aparelho, declare em `ISENCOES`")
        print("com a razão — isenção sem razão é ponto cego com nome bonito.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
