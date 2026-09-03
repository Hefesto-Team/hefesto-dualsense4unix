#!/usr/bin/env python3
"""Onde mora cada página: a BANCADA e o PUBLICADO. Dono único das duas pastas.

DECISÃO DELA, 31/08/2026, e ela reorienta o trabalho inteiro:

    "primeiro **nunca terminamos o mockup**, por isso não era pra ser feito no
    layout final. **Vamos concluir lá e depois seguimos pra interface.**"

O fluxo, na direção que ela decidiu:

    src/hefesto_dualsense4unix/interface/abaNN.py   ← os geradores ficam AQUI
              │  python3 abaNN.py
    mockup/NN-*.html               ← a BANCADA. O desenho sendo concluído.
              │  só quando ela aprovar a aba inteira
    layout/NN-*.html               ← o PUBLICADO. É o que o produto renderiza.

POR QUE ESTE ARQUIVO EXISTE, e o preço estava medido antes de ele nascer: até
31/08 o gerador escrevia direto em `layout/`, e
`src/hefesto_dualsense4unix/interface/paginas/02-controles.html` é o
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

import os
import pathlib

#: A RAIZ DO REPOSITÓRIO. Este arquivo mora em
#: `src/hefesto_dualsense4unix/interface/`, logo são TRÊS níveis acima — era
#: dois quando ele vivia em `src/hefesto_dualsense4unix/interface/`, e a mudança é de 01/09/2026.
#:
#: POR QUE A INTERFACE MUDOU PARA DENTRO DO `src/`, e é a razão inteira: o wheel
#: empacota `packages = ["src/hefesto_dualsense4unix"]`, e nada fora dali entra.
#: Enquanto as páginas viviam em `layout/`, quem instalasse o Hefesto NÃO
#: RECEBIA A INTERFACE — ela só existia na árvore de quem a desenvolvia. Foi o
#: que a auditoria das dez ondas mediu, e o que ela mandou desfazer: *"preciso
#: do produto completo"*.
RAIZ = pathlib.Path(__file__).resolve().parents[3]

#: A PASTA DESTE MÓDULO — onde as páginas publicadas moram, DENTRO do pacote.
AQUI = pathlib.Path(__file__).resolve().parent

#: A bancada — o desenho sendo concluído. É onde os geradores escrevem e é o que
#: ela olha. Muda a cada `python3 abaNN.py`.
BANCADA = RAIZ / "mockup"

#: O publicado — o que o produto renderiza. Só muda pelo `--publicar`, depois do
#: OK dela na aba inteira.
#: O PUBLICADO agora mora no PACOTE, não numa pasta ao lado: é o que faz a
#: interface existir depois de um `pip install`. O caminho sai de `AQUI` e não
#: da `RAIZ` de propósito — instalado, não há repositório nenhum acima.
PUBLICADO = AQUI / "paginas"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)


#: O DESVIO DA ESCRITA, e ele existe para UMA coisa: deixar um portão rodar os
#: dez geradores sem tocar na bancada dela. Com `HEFESTO_BANCADA` apontando para
#: um diretório temporário, `pagina()` e `gravar()` passam a escrever lá  # (noqa-acento): função
#: — e o portão compara o que SAIU com o que está no disco.
#:
#: POR QUE ISSO PRECISOU EXISTIR, medido em 01/09/2026: `aba06.py` estava
#: marcada com os endereços da pintura e o `mockup/06-navegacao.html` NÃO — o
#: gerador fora editado e nunca rodado. O produto mostrava zero endereços numa
#: aba que o gerador dizia ter oito, e portão nenhum desta casa via a
#: diferença. É o mesmo buraco que deixou a `novo-layout/` divergir 25 KB calada.
#:
#: Ele NÃO tem efeito quando a variável não está posta, que é sempre — nenhum
#: fluxo dela passa por aqui, e um desvio que agisse sozinho seria pior que a
#: doença.
_DESVIO = "HEFESTO_BANCADA"


def saida() -> pathlib.Path:
    """Para onde os geradores escrevem AGORA: a bancada, ou o desvio do portão."""
    desviado = os.environ.get(_DESVIO)
    return pathlib.Path(desviado) if desviado else BANCADA


def pagina(nome: str, publicado: bool = False) -> pathlib.Path:
    """O caminho de uma página, na bancada (padrão) ou no publicado.

    `nome` é o arquivo com extensão — ``"02-controles.html"``. O padrão é a
    BANCADA de propósito: todo instrumento desta casa existe para medir o
    desenho de HOJE, e apontá-lo para o publicado o faria dar **verde sobre a
    página congelada** — que é a armadilha mais cara do
    `docs/process/COMO-OLHAR-A-TELA.md` (*"régua que pergunta no lugar errado
    produz não-achado convincente"*), e ela reincidiu quatro vezes só em 31/08.
    """
    return (PUBLICADO if publicado else saida()) / nome


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
