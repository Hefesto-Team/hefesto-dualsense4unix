"""Aba "No jogo": o que está atravessando para o jogo, recurso por recurso.

O PEDIDO DELA (09/08/2026), literal, quando perguntou como validar giroscópio
e touchpad:

    *"eu sei que a aba status é uma coisa, mas isso converter em input seja
    via xbox ou dualsense ou nativo é outra"*

Ela está certa, e o produto não sabia responder. A aba Status mostra o controle
**FÍSICO** — os sticks tremem, o giroscópio pinta barras, o touchpad acende um
ponto. Nada disso diz o que o JOGO recebe: entre o controle e o jogo há um
gamepad virtual (nas duas máscaras) ou não há nada (na Conexão Nativa, em que o
jogo abre o controle físico direto). Para saber, ela tinha de abrir o testador
da Steam.

Esta aba é a resposta, e o trabalho aqui é quase todo de TELA: os números já
subiam no ``daemon.state_full`` (``rumble_ff.per_vpad``) e a REGRA que os lê já
existia — ela mora em :func:`controller_card.estado_do_recurso`, entregue pela
PAINEL-DA-VERDADE-01 e ampliada pela ORFAOS-QUE-VOLTAM-01 e pela
MOTOR-QUE-NAO-SE-VE-01. Este módulo **chama** aquela função; não reimplementa
nem uma linha dela.

POR QUE NÃO É UMA CÓPIA DA LINHA DO CARD
----------------------------------------

O card já mostra ``resumo_do_que_chega_ao_jogo`` — uma frase corrida, ótima
para o relance ("está tudo bem?") e ruim para o gesto que ela descreveu: trocar
a máscara na aba Início, aplicar, e conferir se **movimento** e **toque**
continuam atravessando. Numa frase corrida os recursos mudam de posição
conforme mudam de situação, e comparar antes/depois vira leitura de texto.

Aqui cada recurso tem LINHA FIXA, na mesma ordem, sempre — o que muda é só a
coluna da direita. Trocar a máscara e olhar duas vezes para o mesmo lugar é o
que fecha a pergunta dela em três minutos, sem terminal e sem a Steam.

A HONESTIDADE QUE ESTE MÓDULO TEM DE MANTER
-------------------------------------------

É a mesma da PAINEL-DA-VERDADE-01, e está herdada por construção, porque as
frases nascem da função de lá: nenhuma linha afirma que o JOGO consumiu o dado
— isso depende de qual biblioteca o jogo carregou (medido em 01/08: a
``libSDL2`` do Ubuntu não enumerava o gamepad virtual; a SDL3 que a Steam
distribui enumerava). O que se afirma é o que o daemon PODE saber: o dado saiu
daqui, e alguém escreveu de volta.

E onde não há dado, a tela **cala** em vez de escrever zero. Campo ausente
vira ``None`` lá dentro e some daqui.
"""
from __future__ import annotations


def _detalhe(frase: str, nome: str) -> str:
    """O que sobra da frase da função-dona depois do nome do recurso."""
    if frase == nome:
        return ""
    if frase.startswith(nome):
        return frase[len(nome) :].strip()
    return frase


