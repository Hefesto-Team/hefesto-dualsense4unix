"""Seção 0 da aba Configurações — o exame da mesa, com resposta em uma linha.

O `scripts/doctor.sh` tem milhares de linhas de diagnóstico e é invisível para
quem não abre terminal, que é a maior parte de quem usa o produto. Esta seção
dá cara de gente ao que já existe: um selo com o veredito, o botão que refaz o
exame, os CARDS do que fazer, e as linhas do que foi conferido.

DUAS ZONAS, E O QUE MANDA VEM EM CIMA (25/08/2026)
----------------------------------------------------

Até esta data a seção publicava cinco palavras e mais nada: a cura de quatro
das cinco conferências existia, e chegava à tela SÓ dentro de um
`set_tooltip_text` (`_dica_do_item`, e não havia um segundo caminho). Quem não
passasse o mouse por cima da palavra certa nunca descobria o que fazer — a
`A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` na forma mais barata de consertar.

Agora há duas zonas: em cima os cards do que fazer, embaixo a tira do que foi
conferido. Um card de ORDEM (`integrations/ordens_da_mesa.Ordem`) traz o
imperativo e as TRÊS linhas de porquê, cada uma com o selo de procedência; um
card de CURA traz o que fazer e o que se mediu, sem selo, porque uma cura de
conferência não tem medição por trás dizendo de onde vem o conselho.

**A terceira linha é sempre visível**, inclusive quando confessa que o ganho não
foi medido. É ela que impede raciocínio de se vestir de medição: uma ordem que
manda mover sem dizer quanto se ganha é honesta; a mesma com o ganho escondido é
palpite com cara de laudo.

Fonte única: a seção NÃO reimplementa checagem nenhuma. Toda medição vem de
`integrations/exame_da_mesa.py`, e o SELO vem de `exame_da_mesa.veredito()` —
nunca de uma conta feita aqui. Isso é regra, não estilo: a casa pagou duas
vezes em agosto (`6c86e295`, `c3d3518f`) por uma tela que mostrava verde em
cima de vermelho, e a cicatriz está escrita em `scripts/doctor.sh:1647-1651`.
Um segundo lugar decidindo a cor do topo é como aquilo volta.

O QUE MORA AQUI E NÃO LÁ: a cor, o glifo, e o texto que a pessoa lê. O módulo
devolve chave, estado e um porquê; a tradução para tela é desta camada, e é
por isso que nenhuma mensagem do doctor chega à tela — as de lá carregam
`sudo` e carregam endereço de rádio, e esta tela é fotografada e versionada
(`interface/olhar.py --todas --publicado --doc`; era
`scripts/gui-captura/retratar_abas.py` até 06/09/2026, apagado com a janela
GTK — `D-0609-GTK-LEVA-INTEIRA`).

QUANDO O EXAME RODA: ao ENTRAR na aba e no botão. Nunca na montagem — era o
caminho por onde o retrato das abas passava, e um exame ali poria leitura viva
de `/sys` e do rádio dentro de um PNG que entra em `docs/usage/assets/` sem
revisão humana. **A regra sobrevive ao retratista que a motivou**: o de hoje
não monta esta seção (fotografa HTML já gravado), mas o produto monta a cada
entrada na aba, e é dele que a leitura viva tem de continuar fora.

O CARD RESPONDE (26/08/2026)
-----------------------------

O conselho dispensado nunca sumia. Cada card de ordem traz `[Ignorar]`: grava a
dispensa no rascunho da máquina, chaveada pelo ARRANJO (`D-ORDEM-IGNORADA-VOLTA`).
Ela mexeu nos cabos e a mesma regra disparou com arranjo novo? é fato novo, e a
ordem VOLTA. O `[Já movi — reexaminar]` saiu: ela decidiu em 31/08/2026 que não
faz sentido ter o examinar e o reexaminar.

O TOPO, E QUEM DECIDE A COR (26/08/2026)
------------------------------------------

O selo passa a dizer o texto de `ordens_da_mesa.cabecalho()` — os quatro
cabeçalhos da §8.3 da ORDEM-DE-SERVIÇO-01, que curam a queixa dela de que
*"o 'está tudo certo' não fala nada"*: o estado bom passa a contar QUANTA coisa
foi conferida, e o "não soube" deixa de se disfarçar dele.

**A cor continua sendo de `exame_da_mesa.veredito()`, e por uma razão medida:**
`cabecalho()` não vê `ESTADO_PROBLEMA` — a assinatura dele conhece ordens e duas
contagens, e nada mais. Um selo pintado só por ele mostraria "Nada a mudar" em
VERDE com a linha de pareamentos em VERMELHO logo abaixo, que é a cicatriz de
`6c86e295` voltando pela porta dos fundos. Por isso o topo é o estado MAIS
GRAVE entre os dois, e quem for mais grave também é quem dá a frase. Escalar
nunca inventa um verde; só o apaga.

TERRITÓRIO DE CONFIG-09. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    ESTADO_PROBLEMA,
    Item,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "Está tudo certo?"

ESCOPO = (
    "Este exame olha o que está ligado: portas, energia e rádio. O estado do "
    "Hefesto e do som fica na aba Sistema."
)

DICA: str | None = (
    "O mesmo exame que o Hefesto já sabe fazer pelo terminal, agora com "
    f"resposta em uma linha. Só lê — não muda nada na máquina. {ESCOPO}"
)


FRASE_DO_SELO = {
    ESTADO_CERTO: "Pronto para jogar",
    ESTADO_ATENCAO: "Dá para jogar, mas vale um ajuste",
    ESTADO_PROBLEMA: "Há algo atrapalhando o jogo",
    ESTADO_NAO_SEI: "Não deu para conferir tudo",
}


DICAS_DAS_LINHAS = {
    "energia_do_radio": (
        "O sistema está proibido de desligar os adaptadores para poupar "
        "energia. Se desligar, o controle cai sozinho no meio do jogo."
    ),
    "energia_das_portas": (
        "Nenhuma porta está entregando menos corrente do que o aparelho pede."
    ),
    "pareamentos": (
        "Todos os controles têm pareamento salvo e válido. Pareamento pela "
        "metade faz o controle cair logo depois de conectar."
    ),
    "suporte_ao_controle": "O módulo que fala com o DualSense está carregado.",
    "vizinhanca_das_portas": (
        "Há um Wi-Fi USB 3.0 na porta ao lado de um adaptador Bluetooth. Ele "
        "emite ruído bem em cima da faixa dos controles. Vale mudar de porta."
    ),
}

PREFIXO_DA_CURA = "O que fazer: "


ESCADA_DE_GRAVIDADE = (
    ESTADO_PROBLEMA,
    ESTADO_ATENCAO,
    ESTADO_NAO_SEI,
    ESTADO_CERTO,
)

COLUNAS = 2


def _escapar(texto: str) -> str:
    """Escapa o que o Pango leria como marcação."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def o_mais_grave(primeiro: str, segundo: str) -> str:
    """O pior dos dois estados — e, no empate, o segundo."""
    for estado in ESCADA_DE_GRAVIDADE:
        if segundo == estado:
            return segundo
        if primeiro == estado:
            return primeiro
    return segundo


def contagens_do_cabecalho(itens: Sequence[Item]) -> tuple[int, int]:
    """Quantas checagens responderam, e quantas rodaram sem saber."""
    conferencias = [item for item in itens if item.ordem is None]
    sem_resposta = sum(
        1 for item in conferencias if item.estado == ESTADO_NAO_SEI
    )
    return len(conferencias) - sem_resposta, sem_resposta


def leitura_das_ordens(maquina: Any) -> Any:
    """O que o catálogo de ordens lê — o barramento MAIS o desenho dela."""
    from hefesto_dualsense4unix.integrations import (
        censo_do_barramento,
        entrada_a_entrada,
        entradas_do_gabinete,
        mapa_das_portas,
        ordens_da_mesa,
    )
    from hefesto_dualsense4unix.utils.maquina import entradas_do_mapa

    censo = censo_do_barramento.ler_o_barramento()
    mapa = maquina.mapa
    radios = maquina.mesa.radios
    return ordens_da_mesa.Leitura(
        censo=censo,
        entradas=entradas_do_gabinete.listar_entradas(),
        vizinhas=mapa_das_portas.vizinhas_de_verdade(mapa, censo),
        ocupante_da_entrada={
            numero: mapa_das_portas.ocupante_de(mapa, numero, censo)
            for numero in mapa.portas
        },
        entradas_livres_declaradas=mapa_das_portas.portas_livres(mapa, censo),
        nomes_declarados={
            chave: radio.apelido
            for chave, radio in radios.items()
            if radio.apelido
        },
        tipos_declarados={
            chave: radio.tipo for chave, radio in radios.items() if radio.tipo
        },
        nomes_das_entradas={
            numero: nome
            for numero in entradas_do_mapa(mapa)
            if (nome := entrada_a_entrada.nome_da_entrada(numero, maquina=maquina))
        },
    )


