#!/usr/bin/env python3
"""check_a_cor_vem_do_aparelho.py — a cor do plástico vem do APARELHO, não do desenho.

A LEI, e ela é dela (03/09/2026)
---------------------------------
    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
    entende? nada hardcoded. trazer tudo que eu já mapeei. eu quero que cada  # noqa-acento: citação literal dela
    user ao usar seu controle se toque disso que o app se adaptou ao controle
    dele"

    "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
    players com cada controle — tudo isso muda de acordo com o controle
    identificado no canto superior. é white no p1, mas a borda de tudo é cosmic  # noqa-acento: citação literal dela
    red e os svgs não são os que o meu mapa cataloga. isso tá errado"

Ela mapeou **28 modelos e 10 zonas** em ``docs/data/cores-do-dualsense.csv``. O
produto usa QUATRO — os do desenho, cravados. Quem tiver um Nova Pink vê um
Cosmic Red.

AS TRÊS FAMÍLIAS, e elas são três porque o desenho crava a cor de três jeitos
--------------------------------------------------------------------------------
``plastico``
    Um ``--plastico:#hex`` escrito na página. É a variável que pinta a borda do
    card, os chips da fita e os glifos (``.gb.plast{color:var(--plastico)}``).

``colorway``
    Um ``data-colorway="cosmic-red"`` numa tag. É o seletor com que o SVG
    escolhe o modelo.

``zona``
    Os ``--z-casca:#hex`` da folha embutida em cada SVG. **Aqui mora a
    armadilha**, e ela é o oposto do que parece.

O QUE **NÃO** É DÍVIDA, e confundir isto mandaria apagar o trabalho DELA
------------------------------------------------------------------------
Um CSS que declara os 28 modelos e escolhe por seletor **é a tabela dela,
publicada** — é o mecanismo certo, e é o que o ``mapa-do-controle.html`` já faz.
O que é dívida é o produto **escolher UM modelo** em vez de seguir o aparelho.

Por isso a família ``zona`` só conta os hexes de uma folha **incompleta**: uma
folha com os 28 é a tabela; uma folha com um é uma escolha cravada. Hoje o
``monta._so_o_colorway`` poda cada folha para o modelo pedido (3.082 bytes dos
45.452 dos 28), e é isso que este portão cobra.

As outras duas famílias saem da conta quando o PRODUTO pode reescrevê-las:

* ``--plastico`` com endereço e ``data-hef-alvo="plastico"`` (o alvo existe
  desde 03/09/2026; a ``05-vibracao`` já o usa na moldura dos quatro cards);
* ``data-colorway`` com endereço, ``data-hef-alvo="atributo"`` e
  ``data-hef-atributo="data-colorway"`` (o alvo de atributo, do mesmo dia);
* qualquer elemento com endereço e ``data-hef-alvo="html"``, que o produto
  troca por dentro — é como um ``<style>`` de página pode ser vivo.

E O BLOCO QUE O PILOTO TROCA INTEIRO: a ``.fita`` do topo. Ela não tem endereço
porque não se pinta campo a campo — ``hefesto_vivo.pintar`` substitui o
``outerHTML`` de ``document.querySelector('.fita')`` a cada tique, com o que
``monta.fita(mesa=…)`` monta da mesa VIVA. Contar os chips dela seria acusar
exatamente a única parte da tela que já obedece à lei.

O NÚMERO DE HOJE, e o portão NASCE VERMELHO
--------------------------------------------
Medido em 03/09/2026 sobre as dez páginas publicadas, com estas regras:

    plastico   18      colorway   18      zona  324      TOTAL  360

Sete das dez abas têm dívida; ``07-lancadores``, ``09-sistema`` e ``10-perfis``
nascem limpas — as duas cores que elas mostram estão na ``.fita``, que o produto
já troca inteira. A pior é a ``04-iluminacao``, com 88.

Isso é correto e é o ponto: ele mede a dívida **enquanto as dez abas a fecham**.
A próxima pessoa sabe de onde se partiu.

**ELE NÃO É O CENSO DE 503, e a diferença não é discordância** — é a definição.
O censo de 03/09 contou por expressão regular tudo o que se PARECE com cor
cravada: 34 ``--plastico``, 181 ``data-colorway`` (contando as ~10 linhas de
seletor CSS de cada SVG) e 288 hexes de zona. Este portão conta o que a lei
proíbe: 16 dos 34 ``--plastico`` estão na ``.fita`` ou já têm o alvo
``plastico`` (a ``05-vibracao`` curou os quatro dela), e o ``data-colorway`` de
uma REGRA CSS não é escolha cravada — é a tabela. Os dois números medem coisas
diferentes e os dois estão certos sobre o que medem.

**A PROVA DE QUE ELE DISTINGUE A TABELA DA ESCOLHA** está no disco, e é o
arquivo que ela usa para ver as 28 cores clicando: ``mapa-do-controle.html``
publica a folha inteira e sai deste portão com **zero** achados de ``zona``,
enquanto cada folha podada das abas rende 18. Uma régua que não distinguisse os
dois mandaria apagar o trabalho dela, que é o oposto da lei.

O QUE FAZER COM UM ACHADO
--------------------------
1. dê ENDEREÇO ao elemento e o alvo que o alcança (``plastico`` ou
   ``atributo``), e faça o pacote da aba escrevê-lo com o que leu do daemon;
2. para a família ``zona``: publique a folha inteira — os 28 — em vez da podada.
   Sem isso o alvo de atributo escreve um colorway que nenhuma regra casa, e o
   desenho cai nos ``fill`` crus (medido: ``rgb(58, 63, 75)``);
3. se o valor NÃO for identidade de aparelho, declare em :data:`ISENCOES` com a
   razão. Isenção sem razão é ponto cego com nome bonito.

    scripts/check_a_cor_vem_do_aparelho.py            # reprova, listando
    scripts/check_a_cor_vem_do_aparelho.py --censo    # só o retrato, rc=0
    scripts/check_a_cor_vem_do_aparelho.py --bancada  # mede `mockup/`

A RÉGUA IRMÃ é ``scripts/check_identidade_vem_de_cima.py``, e elas não se
sobrepõem: aquela acha NOME de cor e ``--plastico`` em elemento **sem endereço
nenhum**; esta acha cor cravada mesmo onde o endereço existe — porque um
endereço com o alvo errado não alcança a cor. Duas réguas independentes é o que
revela; é regra desta casa.
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

#: Os atributos que dão endereço a um elemento. São os MESMOS da
#: ``regua_do_mockup`` e da régua irmã de propósito: uma terceira lista seria
#: uma terceira forma de divergir em silêncio.
ENDERECOS = ("data-campo", "data-papel", "data-hef")

#: Comentário é prosa, e contá-lo inflaria o número — que é a coisa que esta
#: casa mais derruba. As quebras de linha sobrevivem: sem isso um comentário de
#: vinte linhas vira uma só e toda linha depois dele erra.
COMENTARIO = re.compile(r"<!--.*?-->|/\*.*?\*/", re.S)

#: Só o HEXADECIMAL conta. Um ``--plastico:var(--border-forte)`` é o tom NEUTRO
#: da folha de estilo — o que a página mostra quando não há cor lida —, e é
#: exatamente o que a regra dela pede: campo sem informação não mostra nada.
PLASTICO = re.compile(r"--plastico\s*:\s*(#[0-9a-fA-F]{3,8})")

#: Uma declaração de zona dentro da folha do SVG.
ZONA = re.compile(r"--z-[a-z0-9_-]+\s*:\s*#[0-9a-fA-F]{3,8}")

#: O seletor com que a folha escolhe o modelo.
REGRA_DE_COLORWAY = re.compile(r'svg\[data-colorway="([^"]+)"\]')

#: O BLOCO QUE O PILOTO TROCA INTEIRO, por CLASSE e não por endereço.
#:
#: ``hefesto_vivo.pintar`` faz ``document.querySelector('.fita').outerHTML =``
#: a cada tique, com o HTML que ``monta.fita(mesa=…)`` monta da mesa VIVA — e
#: depois carimba o selo da visita em cada ``[data-campo]`` de dentro. Um chip
#: com ``--plastico:#ae335a`` ali é o que o PRODUTO acabou de escrever, não o
#: que o desenho cravou.
#:
#: Não dá para inferir isto do HTML: a troca é por SELETOR, e o seletor mora no
#: JavaScript. Por isso é uma lista, curta, com a razão escrita — e o
#: ``test_a_fita_e_a_unica_isenta_por_bloco`` cobra que ela continue sendo uma.
TROCADOS_INTEIROS = ("fita",)

#: Os alvos que ALCANÇAM cada família. Um endereço com o alvo errado não é
#: cura: o ``escrever()`` cai no ramo padrão e escreve a cor como TEXTO.
ALVO_DA_FAMILIA = {
    "plastico": ("plastico", "html"),
    "colorway": ("atributo", "html"),
}

#: Isenções declaradas, com a razão. ``(arquivo, família, trecho) -> por quê``.
#: Vazia hoje, e isso é uma afirmação: nenhum congelado desta árvore se
#: justificou ainda fora da ``.fita``.
ISENCOES: dict[tuple[str, str, str], str] = {}


def colorways_do_mapa() -> set[str]:
    """Os 28 modelos, lidos do CSV que é dono deles.

    Digitá-los aqui criaria uma segunda lista que envelhece sozinha — o defeito
    que o ``cores-do-dualsense.csv`` existe para não ter.

    A coluna é ``id`` (``white``, ``cosmic-red``…), e não ``nome`` (``White``,
    ``Cosmic Red``): é o ``id`` que o ``gerar_cores_do_dualsense.py`` põe no
    ``svg[data-colorway="…"]``. A régua irmã lê a coluna ``nome`` pela razão
    oposta — ela procura o que a TELA mostra.
    """
    linhas = [
        linha
        for linha in CORES_CSV.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    return {
        (linha.get("id") or "").strip()
        for linha in csv.DictReader(linhas)
        if (linha.get("id") or "").strip()
    }


class _Varredor(HTMLParser):
    """Percorre a página guardando a PILHA de ancestrais.

    A pilha é o que responde as duas perguntas que decidem um achado: *este
    elemento está dentro de um bloco que o produto troca inteiro?* e *ele — ou
    um ancestral — tem endereço com o alvo que alcança esta cor?*

    POR QUE UMA PILHA, E NÃO A TAG MAIS PRÓXIMA À ESQUERDA: é a mesma lição que
    a régua irmã pagou. Um chip dentro da ``.fita`` tem, à esquerda, um
    ``</span>`` sem classe nenhuma — e uma régua que olhasse só isso acusaria
    quem já está curado, que é o pior defeito que uma régua pode ter.
    """

    #: Tags que não fecham — sem elas a pilha desanda e tudo depois fica errado.
    VAZIAS = frozenset([
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    ])

    def __init__(self, colorways: set[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.colorways = colorways
        #: cada nível: ``(trocado_inteiro, alvo_vivo)``
        self.pilha: list[tuple[bool, str]] = []
        self.achados: list[tuple[int, str, str, str]] = []
        self._folha: list[str] | None = None
        self._folha_linha = 0
        self._folha_viva = False

    # -- as duas perguntas da pilha ---------------------------------------
    def _trocado(self) -> bool:
        return any(t for t, _ in self.pilha)

    def _alvo_vivo(self) -> str:
        for _, alvo in reversed(self.pilha):
            if alvo:
                return alvo
        return ""

    @staticmethod
    def _alvo_deste(d: dict[str, str]) -> str:
        """O alvo com que o produto reescreve ESTE elemento, ou ``""``.

        Endereço sem alvo não conta, e alvo sem endereço também não: são as duas
        metades da mesma fechadura. ``achar()`` acha pelo endereço; o
        ``data-hef-alvo`` diz o que ele escreve quando chega lá.
        """
        if not any(a in d for a in ENDERECOS):
            return ""
        return (d.get("data-hef-alvo") or "texto").strip().lower()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        alvo = self._alvo_deste(d)
        trocado = any(c in (d.get("class") or "").split() for c in TROCADOS_INTEIROS)
        linha = self.getpos()[0]
        herdado = self._alvo_vivo()
        coberto = self._trocado() or trocado

        # O `--plastico` mora no `style` do PRÓPRIO elemento, e é ele quem tem
        # de ter o alvo: um pai endereçado não dá ao filho o direito de trazer
        # cor congelada — o `escrever()` escreve no elemento que ACHOU.
        if not coberto and alvo not in ALVO_DA_FAMILIA["plastico"]:
            for m in PLASTICO.finditer(d.get("style", "")):
                self._registrar(linha, "plastico", m.group(0),
                                self._porque(alvo, "plastico"))

        # O `data-colorway`, idem — e aqui o alvo tem de nomear O ATRIBUTO, não
        # só ser `atributo`: um `data-hef-atributo="data-modelo"` escreve outra
        # coisa e deixa o colorway cravado.
        if "data-colorway" in d and not coberto:
            nomeia = (d.get("data-hef-atributo") or "").strip().lower() == "data-colorway"
            if not (alvo == "atributo" and nomeia) and alvo != "html":
                self._registrar(linha, "colorway", f'data-colorway="{d["data-colorway"]}"',
                                self._porque(alvo, "colorway"))

        if tag == "style":
            self._folha = []
            self._folha_linha = linha
            # Uma folha VIVA é a que o produto troca por dentro (alvo `html`) ou
            # que mora num bloco trocado inteiro.
            self._folha_viva = coberto or alvo == "html" or herdado == "html"

        if tag not in self.VAZIAS:
            self.pilha.append((trocado, alvo))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VAZIAS and self.pilha:
            self.pilha.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self._folha is not None:
            self._fechar_folha("".join(self._folha))
            self._folha = None
        if tag not in self.VAZIAS and self.pilha:
            self.pilha.pop()

    def handle_data(self, data: str) -> None:
        if self._folha is not None:
            self._folha.append(data)

    # -- a folha das zonas -------------------------------------------------
    def _fechar_folha(self, css: str) -> None:
        """Julga uma folha de cores: tabela publicada, ou escolha cravada?

        A folha que traz os 28 modelos do mapa É a tabela dela — o produto
        escolhe por seletor, que é o mecanismo certo. A folha podada é uma
        escolha: o SVG não tem como virar outro modelo, e é isso que se conta.
        """
        declarados = set(REGRA_DE_COLORWAY.findall(css))
        if not declarados:
            # Um `--plastico` de REGRA CSS (`.ctl[data-controle="p1"]{…}`) não
            # tem elemento a que pertencer, e por isso não tem como ter alvo:
            # ele é a página decidindo qual controle é de que cor.
            if not self._folha_viva:
                for m in PLASTICO.finditer(css):
                    self._registrar(self._folha_linha, "plastico", m.group(0),
                                    "regra de CSS: nenhum elemento a endereçar")
            return
        faltam = self.colorways - declarados
        if not faltam or self._folha_viva:
            return
        n = len(ZONA.findall(css))
        if n:
            self._registrar(
                self._folha_linha, "zona",
                f"folha com {len(declarados)} de {len(self.colorways)} modelos "
                f"({n} hexes de zona)",
                f"faltam {len(faltam)} modelos do mapa dela", n)

    # -- o registro --------------------------------------------------------
    @staticmethod
    def _porque(alvo: str, familia: str) -> str:
        if not alvo:
            return "sem endereço: o produto não tem por onde reescrever"
        return (f"endereço com alvo `{alvo}`, que não alcança a família "
                f"`{familia}` (precisa de {' ou '.join(ALVO_DA_FAMILIA[familia])})")

    def _registrar(self, linha: int, familia: str, trecho: str, porque: str,
                   peso: int = 1) -> None:
        """Guarda um achado. O ``peso`` é QUANTAS cores cravadas ele vale.

        Um ``--plastico`` é uma cor; uma folha podada são as 18 declarações de
        zona daquele modelo. Contar a folha como UM esconderia o tamanho da
        dívida, e contá-la em 18 linhas de relato afogaria quem lê — o peso
        separa o que se CONTA do que se MOSTRA.
        """
        self.achados.append(
            (linha, familia, " ".join(trecho.split())[:90], porque, peso))


def cravados_no_texto(bruto: str, colorways: set[str],
                      nome: str = "") -> list[tuple[int, str, str, str, int]]:
    """As cores de aparelho cravadas neste HTML.

    Devolve ``(linha, família, trecho, razão, peso)`` — e quem conta soma os
    PESOS, não as linhas.

    Recebe TEXTO, e não caminho, porque é assim que a régua se morde: o teste
    arranca a cura de uma página real em memória e exige ver a acusação voltar.
    """
    limpo = COMENTARIO.sub(
        lambda m: "".join(c if c == "\n" else " " for c in m.group(0)), bruto)
    varredor = _Varredor(colorways)
    varredor.feed(limpo)
    return [
        achado for achado in varredor.achados
        if (nome, achado[1], achado[2]) not in ISENCOES
    ]


def cravados_de(caminho: pathlib.Path,
                colorways: set[str]) -> list[tuple[int, str, str, str, int]]:
    """O mesmo, para uma página do disco."""
    return cravados_no_texto(
        caminho.read_text(encoding="utf-8", errors="replace"),
        colorways, caminho.name)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--censo", action="store_true",
                   help="só o retrato de hoje, sem reprovar")
    #: A BANCADA existe aqui pela mesma razão da régua irmã: os geradores
    #: escrevem em `mockup/` e PUBLICAR é ato dela. Quem conserta uma aba precisa
    #: poder provar o conserto antes de ela mandar publicar.
    p.add_argument("--bancada", action="store_true",
                   help="mede `mockup/` em vez das páginas publicadas")
    p.add_argument("--aba", default="", help="só esta aba (ex.: 04)")
    args = p.parse_args()

    alvo = (RAIZ / "mockup") if args.bancada else PAGINAS
    if not alvo.is_dir():
        print(f"não achei as páginas em {alvo}", file=sys.stderr)
        return 2

    colorways = colorways_do_mapa()
    familias = ("plastico", "colorway", "zona")
    total = dict.fromkeys(familias, 0)
    print(f"{'bancada' if args.bancada else 'publicado':<22}"
          + "".join(f"{f:>10}" for f in familias) + f"{'total':>8}")
    print("-" * 62)
    detalhe: list[str] = []
    padrao = f"{args.aba}-*.html" if args.aba else "[0-9][0-9]-*.html"
    for caminho in sorted(alvo.glob(padrao)):
        achados = cravados_de(caminho, colorways)
        por_familia = {f: sum(a[4] for a in achados if a[1] == f) for f in familias}
        for f in familias:
            total[f] += por_familia[f]
        if achados:
            print(f"{caminho.name:<22}"
                  + "".join(f"{por_familia[f]:>10}" for f in familias)
                  + f"{sum(por_familia.values()):>8}")
            for linha, familia, trecho, porque, _peso in sorted(set(achados)):
                detalhe.append(
                    f"  {caminho.name}:{linha}  [{familia}]  {trecho}\n"
                    f"      {porque}")
    print("-" * 62)
    print(f"{'TOTAL':<22}" + "".join(f"{total[f]:>10}" for f in familias)
          + f"{sum(total.values()):>8}")

    if detalhe:
        print()
        print("\n".join(detalhe))

    if args.censo:
        return 0
    if sum(total.values()):
        print()
        print("A cor do plástico vem do APARELHO. Ela mapeou 28 modelos e 10")
        print("zonas; cada linha acima é o produto escolhendo UM em vez de")
        print("seguir o controle que a fita do topo identificou.")
        print()
        print("O conserto: endereço + o alvo que alcança (`plastico` para a")
        print("variável, `atributo` com `data-hef-atributo=\"data-colorway\"`")
        print("para o SVG), e a folha das zonas publicada com os 28 — uma folha")
        print("podada não tem como virar outro modelo.")
        print("Se o valor NÃO for identidade de aparelho, declare em `ISENCOES`")
        print("com a razão — isenção sem razão é ponto cego com nome bonito.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
