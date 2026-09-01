#!/usr/bin/env python3
"""Onde mora cada página: a BANCADA e o PUBLICADO. Dono único das duas pastas.

DECISÃO DELA, 31/08/2026, e ela reorienta o trabalho inteiro:

    "primeiro **nunca terminamos o mockup**, por isso não era pra ser feito no
    layout final. **Vamos concluir lá e depois seguimos pra interface.**"

O fluxo, na direção que ela decidiu:

    layout/_ferramentas/abaNN.py   ← os geradores ficam AQUI
              │  python3 abaNN.py
    mockup/NN-*.html               ← a BANCADA. O desenho sendo concluído.
              │  só quando ela aprovar a aba inteira
    layout/NN-*.html               ← o PUBLICADO. É o que o produto renderiza.

POR QUE ESTE ARQUIVO EXISTE, e o preço estava medido antes de ele nascer: até
31/08 o gerador escrevia direto em `layout/`, e `layout/02-controles.html` é o
que o piloto `controles_vivos.py` abre no `WebKit2.WebView`. Logo, rodar
`python3 aba02.py` **já trocava o produto**, sem passar pelo olho dela. Era o
mesmo colapso que ela diagnosticou na pasta anterior, com estas palavras:

    "o problema original foi não ter separado a pasta do mockup e ter feito a
    interface usando o HTML do mockup. **Se alteramos no layout final a
    referência do mockup se perde.**"

QUANDO O PUBLICADO RECEBE, e é escolha dela em 31/08: **a cada aba fechada** —
quando todos os pontos daquela aba do `mockup/TODO-DELA.md` tiverem o OK dela.
Nem a cada ponto (o produto mudaria sete vezes), nem só no fim (o produto
ficaria a lista inteira parado). O comando é
`scripts/check_o_desenho_aprovado.py --publicar NN`.

DOIS NOMES, UM LUGAR CADA. Este módulo é o único que escreve os dois caminhos.
Quem precisar de uma página importa daqui — nunca monta `RAIZ / "layout"` à mão.
A regra é a mesma da logo, da fita e das cores do plástico: **o que tem dono não
se digita.** Já custou caro nesta casa quando cada arquivo carregava a própria
cópia do caminho.

A RAIZ SAI DE `__file__`, NUNCA CRAVADA. Medido em 28/08/2026: oito arquivos
desta casa cravavam o caminho absoluto da árvore DELA, e por isso rodar uma
CÓPIA do gerador REESCREVIA o mockup dela.
"""
from __future__ import annotations

import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[2]

#: A bancada — o desenho sendo concluído. É onde os geradores escrevem e é o que
#: ela olha. Muda a cada `python3 abaNN.py`.
BANCADA = RAIZ / "mockup"

#: O publicado — o que o produto renderiza. Só muda pelo `--publicar`, depois do
#: OK dela na aba inteira.
PUBLICADO = RAIZ / "layout"


def pagina(nome: str, publicado: bool = False) -> pathlib.Path:
    """O caminho de uma página, na bancada (padrão) ou no publicado.

    `nome` é o arquivo com extensão — ``"02-controles.html"``. O padrão é a
    BANCADA de propósito: todo instrumento desta casa existe para medir o
    desenho de HOJE, e apontá-lo para o publicado o faria dar **verde sobre a
    página congelada** — que é a armadilha mais cara do
    `docs/process/COMO-OLHAR-A-TELA.md` (*"régua que pergunta no lugar errado
    produz não-achado convincente"*), e ela reincidiu quatro vezes só em 31/08.
    """
    return (PUBLICADO if publicado else BANCADA) / nome


def paginas(publicado: bool = False) -> list[pathlib.Path]:
    """As páginas da pasta, em ordem. Só `.html`, sem os `.dc.html` do Design."""
    pasta = PUBLICADO if publicado else BANCADA
    return sorted(
        p
        for p in pasta.glob("*.html")
        if not p.name.startswith(".") and not p.name.endswith(".dc.html")
    )


def gravar(nome: str, doc: str) -> pathlib.Path:
    """Grava uma página na bancada, SEM espaço sobrando no fim das linhas.

    DONO ÚNICO DA ESCRITA. As três escritas desta casa passam por aqui —
    `monta()` e o pós-processamento da `aba06` e da `aba08`, que injetam as telas
    de pop-up depois que o esqueleto já saiu.

    O `rstrip` não é asseio: é o que deixa o `git diff` de uma aba legível. O
    `ds_limpo.svg` traz linhas com indentação e nada mais, e elas atravessavam
    para as dez páginas. Medido em 31/08/2026, no dia em que o fluxo inverteu:
    uma regeração **sem mudança nenhuma de conteúdo** produzia 263 linhas de
    diff em nove abas, todas de espaço. Num trabalho que é diff de HTML gerado
    do começo ao fim, esse ruído esconde a mudança real.

    A PROVA de que ele não muda o desenho: com esta normalização, a regeração
    das dez sai byte a byte IGUAL ao que ela aprovou. O alvo não é uma convenção
    de estilo — é o arquivo dela.
    """
    destino = pagina(nome)
    destino.write_text("\n".join(linha.rstrip() for linha in doc.split("\n")))
    return destino
