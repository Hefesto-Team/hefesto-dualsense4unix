"""«Tudo na TV e Nada no Controle» — e o «tudo» inclui o som DO controle.

**A ORDEM É DELA, 21/09/2026**, olhando os três botões da fileira do som:

    "os 3 botões do som não tão tendo os outputs diferenciados digo sobre o som
     da tv ser A, o som do controle ser B, aí o som do controle faz só A,
     controle e tv no controle faz AB, e controle e tv na tv faz ab na tv.
     isso não rola ainda."

Os três estados que ela descreve, com A = o som que já sai na TV e B = o que o
jogo endereça ao controle:

===========================  ===========  ==================================
botão                        a TV toca    o alto-falante do controle toca
===========================  ===========  ==================================
Sons do jogo                 A            B
No controle e na TV          A            A + B
Tudo na TV e Nada no Controle  **A + B**  nada
===========================  ===========  ==================================

**A TERCEIRA LINHA ERA A QUE FALTAVA.** Antes desta sprint o terceiro botão
calava o alto-falante (rota 0, estéreo no fone) e punha a `fonte` em `sfx` — e
o B ficava no nó, sem ninguém para escutá-lo. Ela ouvia o silêncio e leu isso
como *"o botão não faz nada de diferente"*, que é exatamente o que acontecia do
ponto de vista dela: dois botões diferentes, o mesmo resultado audível.

O MECANISMO
===========

Um `pw-loopback` do **monitor** do nó do controle (``hefesto_som_<hex6>``) para
a saída padrão. O que o jogo escreve naquele sink passa a sair pela TV, sem
copiar amostra por cano de shell e sem tocar no servidor de som dela — um
loopback é ADITIVO, cria um nó novo e não muda nada do que já estava de pé.

**O DONO DO `pw-loopback` É UM SÓ** (`integrations/laco_de_audio.py`), e este
arquivo é a fachada dele para este eixo — o mesmo arranjo do 🎙 da coluna do
microfone.

O QUE ELE NÃO É
===============

**Não é o `♪`.** O mudo do alto-falante é um byte de FIRMWARE e cala o plástico.
Este laço diz para onde vai o que o jogo endereçou ao nó — camadas diferentes,
donos diferentes.

**Não é a `fonte` `mix`.** O `mix` liga o monitor da saída PADRÃO ao nó do
controle: é o PC indo para o controle, o sentido oposto deste. Os dois podem
existir ao mesmo tempo sem se cancelar, e é por isso que o terceiro botão
desliga o `mix` antes: com os dois de pé o som daria a volta e voltaria.
"""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink
from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos

__all__ = ["desligar", "desligar_todos", "esta_ligado", "ligados", "ligar"]

#: A família deste eixo, e o nome que aparece no `qpwgraph`.
_LACOS = Lacos("som-do-controle-na-tv")


def esta_ligado(uniq: str) -> bool:
    """O som deste controle está saindo na TV AGORA?"""
    return _LACOS.esta_ligado(uniq)


def ligados() -> tuple[str, ...]:
    """Os `uniq` cujo som está indo para a TV, em ordem estável."""
    return _LACOS.ligados()


def ligar(uniq: str, *, destino: str = "") -> bool:
    """Manda o som deste controle para a TV. `True` = de pé.

    :param destino: o sink de saída; vazio manda à saída padrão, que é a TV
        dela — e é a resposta certa a *"tudo na TV"*.

    **ESTÉREO, e o mapa vai escrito**: o que o jogo endereça ao controle é
    estéreo, e deixar o PipeWire adivinhar produziria um laço mono com metade
    do campo perdida. O irmão do microfone é MONO pela razão simétrica.

    **A CAPTURA É O `.monitor`**, nunca o sink cru: um sink não se «lê», lê-se
    o monitor dele. Pedir o nome sem sufixo faz o `pw-loopback` subir mudo e
    sem erro — a classe de defeito em que o produto responde «aplicado» sobre
    nada.
    """
    sink = nome_do_sink(uniq)
    if not sink:
        return False
    return _LACOS.ligar(
        uniq, captura=f"{sink}.monitor", destino=destino,
        canais=2, mapa="[ FL FR ]")


def desligar(uniq: str) -> bool:
    """Para de mandar o som deste controle para a TV."""
    return _LACOS.desligar(uniq)


def desligar_todos() -> int:
    """Fecha todos os laços deste eixo e devolve quantos eram."""
    return _LACOS.desligar_todos()
