"""O canal de captura de UM controle, com o nome DELE — não o do transporte.

ONDA5-MIC-VIRTUAL-01, e a decisão é dela, 05/09/2026:

    *"Criamos mecanismos pra usarmos todas as feature. Exemplo controle do Xbox
    não tem microfone mas se o Mic do dualsense passa a ser lido a parte via Mic
    virtual. Usaríamos essa feature do controle mesmo no Xbox. Mesmo problema
    BT. Hj já funciona assim, sem a parte do Mic virtual."*
    <!-- as duas metades, e as duas são engenharia -->

O princípio que manda este módulo existir está em
`docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md`,
e a regra que ele deixa é uma linha: **o Hefesto não explica a própria falha —
ele a conserta.**

O DEFEITO MEDIDO, e ele é de NOME
----------------------------------

Hoje o microfone do mesmo controle se chama de dois jeitos:

===========  ==============================================  ================
transporte   como o microfone daquele controle se chama      tem identidade?
===========  ==============================================  ================
rádio        ``hefesto_dualsense_bt_<hex6>`` — os três        **sim**
             últimos octetos do MAC
cabo         um nó ALSA cujo ``-00``/``-00.2`` é desempate    **não**
             posicional do PipeWire
===========  ==============================================  ================

**Troque o transporte e o microfone daquele controle muda de nome.** Um app que
fixou o device perde o microfone: o nome que ele guardou deixou de existir.

O custo disso já está pago e dá para medi-lo — responder *"qual nó é o microfone
DESTE controle"* custa hoje `fontes_de_captura.escolher_fonte`, quatro regras
mais um censo do dispositivo USB pai, com quatro chamadores independentes. E a
regra do USB pai **não existe no rádio**, porque a placa de som segue o
transporte: para o controle no rádio a resposta certa daquela função é ``None``,
e a docstring dela o diz.

O QUE ESTE MÓDULO É, E O QUE ELE **NÃO** É
-------------------------------------------

Ele é o **dono único do NOME e do CICLO DE VIDA** do canal por controle. Ele não
é um mecanismo novo: o mecanismo — ``module-pipe-source``, um módulo, um fifo,
zero processo intermediário — já existe e está medido em
:class:`~hefesto_dualsense4unix.integrations.dualsense_bt_audio.SourceVirtualPipeWire`,
publicado pela ponte de rádio desde 25/07/2026. **Ele é reusado daqui, não
reescrito** — que é exatamente a ordem dela: *"ao invés de aproveitar o do gtk e
adaptar ele pra funcionar no html. estamos recriando um produto que estava
praticamente pronto"*.

Pela mesma razão a PRIORIDADE não é um literal novo:
``PRIORIDADE_SESSAO_DA_PONTE`` é lida do dono, com a medição de 03/09 na máquina
dela por trás. Um número inventado aqui repetiria o defeito que aquele
comentário registra — um literal catorze dias atrás da doutrina que ele
espelhava.

O QUE ESTA SPRINT **NÃO** FAZ, e o corte é por REVERSIBILIDADE
---------------------------------------------------------------

Ela constrói o nó com nome. **Ela não converte o rádio**, e a razão não é
tamanho:

* **no CABO existe rede embaixo** — o nó ALSA continua publicado enquanto o nó
  novo sobe ao lado. Se o novo não servir, ninguém fica sem microfone;
* **no RÁDIO não existe** — ``hefesto_dualsense_bt_<hex6>`` é o ÚNICO canal que
  o rádio tem hoje. Mexer nele antes de o novo estar provado tira dela o
  microfone por Bluetooth inteiro.

A ONDA5-MIC-VIRTUAL-02 faz o rádio alimentar este nó e converte os quatro
chamadores de ``escolher_fonte``. Ela só começa com este nó de pé e medido com
dois controles na bancada.

**E NADA AQUI CARREGA MÓDULO SOZINHO.** :func:`abrir` é chamada, não agendada; o
ponto de entrada dela é o ``pedir_canal`` da eleição
(`integrations/eleicao_de_microfone.py`), que já é o gesto DELA desde 01/09 — o
botão do microfone, que quer dizer *"eu falo por este controle"*.

A ARMADILHA QUE ESTE MÓDULO HERDA, e ela já tem nome na árvore
---------------------------------------------------------------

``quem_ouve_o_microfone.e_stream_do_hefesto`` existe porque *"o medidor do
próprio Hefesto não pode contar como ouvinte. Se contar, a luz acende sozinha e
a peça inteira mente"*. **O que alimentar este nó cai na MESMA armadilha, com o
mesmo sintoma:** a luz vermelha do microfone dela acesa para sempre.

E o mesmo módulo já ensinou como NÃO combinar isso: *"a junta com a peça B não é
um nome combinado — é um espaço de nome"*. Então aqui também não se combina
nome: as propriedades do nó nascem no espaço ``hefesto.``
(:data:`~hefesto_dualsense4unix.integrations.quem_ouve_o_microfone.PREFIXO_PROPRIEDADE_HEFESTO`),
lido do dono, e quem reconhece continua sendo aquela peça.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    PRIORIDADE_SESSAO_DA_PONTE,
    SourceVirtualPipeWire,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    MIN_HEX_SUFIXO_BT,
    so_hex,
)
from hefesto_dualsense4unix.integrations.quem_ouve_o_microfone import (
    PREFIXO_PROPRIEDADE_HEFESTO,
)

logger = logging.getLogger(__name__)

#: O PREFIXO DO NOME, e ele é DESTE módulo — não do transporte.
#:
#: ``hefesto_mic_<hex6>``. O sufixo é o MESMO de identidade que a ponte de rádio
#: já publica (os três últimos octetos do MAC), e é ele que faz o nome
#: sobreviver à troca de transporte: o controle é o mesmo controle no cabo e no
#: rádio, então o microfone dele tem de se chamar igual nos dois.
#:
#: **Por que um prefixo NOVO e não o da ponte.** ``hefesto_dualsense_bt_`` diz o
#: transporte no próprio nome — é o defeito que este módulo existe para curar, e
#: reusá-lo apenas mudaria de lugar. E `sufixo_da_ponte_bt` continua tendo de
#: reconhecer o nome VELHO enquanto o rádio o publicar: dois prefixos vivos é o
#: preço declarado da transição, e a MIC-VIRTUAL-02 é quem o paga.
PREFIXO_CANAL = "hefesto_mic_"


#: Quantos dígitos hex um endereço de aparelho tem, sem os separadores. Doze —
#: seis octetos. É o que separa um MAC de uma string qualquer.
_HEX_DE_UM_ENDERECO = 12

#: O que se tira de um `uniq` antes de perguntar se o resto é hex. Só
#: separadores de endereço; nada de letras.
_SEPARADORES = (":", "-", ".", " ")


def sufixo_do_controle(uniq: str) -> str:
    """Os seis últimos dígitos hex do `uniq` — "" se ele não for um endereço.

    É a MESMA regra de `NoDualSenseBT.nome_curto`, e a diferença é o que
    acontece quando não dá: aquela propriedade cai no nome do nó, o que só faz
    sentido para quem está lendo o sysfs do Bluetooth. Aqui a resposta certa é
    `""` — **sem identidade não se batiza um canal**, e um nome inventado
    colidiria com o do vizinho na mesa de quatro, que é pior que não ter nome.

    E ELE EXIGE UM ENDEREÇO INTEIRO, não "seis dígitos hex em algum lugar" —
    medido ao escrever este módulo, em 05/09/2026: ``so_hex`` sobre
    ``"sem-identidade"`` devolve ``"emdedade"``, porque **e**, **d** e **a** são
    dígitos hex, e o canal nasceria batizado ``hefesto_mic_dedade``. É a mesma
    armadilha de casamento por acaso que `fontes_de_captura.sufixo_da_ponte_bt`
    já paga com o ``so_hex(resto) != resto``, aqui na entrada em vez da saída.
    """
    limpo = uniq.lower()
    for separador in _SEPARADORES:
        limpo = limpo.replace(separador, "")
    if len(limpo) < _HEX_DE_UM_ENDERECO or so_hex(limpo) != limpo:
        return ""
    return limpo[-MIN_HEX_SUFIXO_BT:]


def nome_do_canal(uniq: str) -> str:
    """`hefesto_mic_<hex6>` para este controle — "" se ele não tem identidade."""
    sufixo = sufixo_do_controle(uniq)
    return f"{PREFIXO_CANAL}{sufixo}" if sufixo else ""


def sufixo_do_canal(nome: str) -> str:
    """O caminho de volta: de que controle é este nó — "" se não for um nosso.

    Recorta o prefixo ANTES de filtrar hex, e a ordem não é detalhe: o prefixo
    ``hefesto_mic_`` tem letras hex dentro (``e``, ``f``, ``c``), e passar o nome
    inteiro por :func:`so_hex` produziria um "MAC" com lixo grudado na frente —
    casamento por acaso. É a mesma armadilha, e a mesma cura, de
    `fontes_de_captura.sufixo_da_ponte_bt`.
    """
    baixa = nome.lower()
    if not baixa.startswith(PREFIXO_CANAL):
        return ""
    resto = baixa[len(PREFIXO_CANAL) :]
    if len(resto) < MIN_HEX_SUFIXO_BT or so_hex(resto) != resto:
        return ""
    return resto


def propriedades_do_canal(uniq: str) -> dict[str, str]:
    """As propriedades que o nó carrega — no ESPAÇO DE NOME, nunca combinadas.

    ``hefesto.papel`` e ``hefesto.uniq`` caem sob
    :data:`quem_ouve_o_microfone.PREFIXO_PROPRIEDADE_HEFESTO`, que é lido do
    dono. Quem reconhece o que é do Hefesto continua sendo aquela peça, e ela o
    faz pelo PREFIXO — nenhuma chave combinada entre os dois arquivos.
    """
    return {
        f"{PREFIXO_PROPRIEDADE_HEFESTO}papel": "canal-do-microfone",
        f"{PREFIXO_PROPRIEDADE_HEFESTO}uniq": uniq,
    }


#: Os canais de pé, por `uniq`. O módulo é o dono do ciclo de vida, e o dono
#: precisa saber o que já subiu: pedir duas vezes o mesmo canal é o caminho
#: normal (duas abas, dois cliques), e carregar dois `module-pipe-source` com o
#: mesmo `source_name` publicaria dois nós disputando um nome só.
_DE_PE: dict[str, SourceVirtualPipeWire] = {}
_TRANCA = threading.Lock()


def abrir(uniq: str, descricao: str, *, fabrica: Any = None) -> SourceVirtualPipeWire | None:
    """Sobe o canal deste controle, ou devolve o que já estava de pé.

    `None` = não deu, e **nada ficou pela metade** — o contrato é o do
    `SourceVirtualPipeWire.iniciar`, que desfaz o que subiu antes de devolver
    `False`. Nunca levanta: o caminho até aqui é o toque dela no botão do
    microfone, e um traceback no laço do daemon é pior que uma recusa.

    `fabrica` existe para a régua: ela troca o mecanismo por um dublê sem tocar
    no PipeWire da máquina. Em produção é `None` e o dono do mecanismo é o da
    ponte de rádio.
    """
    nome = nome_do_canal(uniq)
    if not nome:
        logger.debug("canal_do_mic_sem_identidade", extra={"uniq": uniq})
        return None
    with _TRANCA:
        ja = _DE_PE.get(uniq)
        if ja is not None:
            return ja
        construir = fabrica or SourceVirtualPipeWire
        try:
            source = construir(nome=nome, descricao=descricao)
            if not source.iniciar():
                return None
        except Exception:  # o gesto dela não vira traceback
            logger.warning("canal_do_mic_nao_subiu", exc_info=True)
            return None
        _DE_PE[uniq] = source
        return source


def fechar(uniq: str) -> bool:
    """Derruba o canal deste controle. False = não havia nada de pé.

    O canal MORRE COM O ÚLTIMO PEDIDO, e não com a desconexão: um controle que
    pisca no cabo (o caso do hub sobrecarregado, medido nesta casa) derrubaria e
    subiria o nó a cada piscada, e todo app que estivesse gravando perderia a
    fonte no meio da frase.
    """
    with _TRANCA:
        source = _DE_PE.pop(uniq, None)
    if source is None:
        return False
    try:
        source.parar()
    except Exception:
        logger.warning("canal_do_mic_nao_parou", exc_info=True)
    return True


def de_pe() -> dict[str, str]:
    """`{uniq: nome do nó}` do que está publicado agora. Cópia, não a tabela."""
    with _TRANCA:
        return {uniq: source.nome for uniq, source in _DE_PE.items()}


def prioridade() -> int:
    """A `priority.session` do canal — a MESMA faixa do cabo, lida do dono.

    Não é um número deste arquivo. `PRIORIDADE_SESSAO_DA_PONTE` carrega a
    medição de 03/09/2026 na máquina dela e o invariante que ela materializa:
    *um microfone de verdade nunca pode perder para um monitor*. Um literal aqui
    repetiria, na íntegra, o defeito que aquele comentário registra.
    """
    return PRIORIDADE_SESSAO_DA_PONTE
