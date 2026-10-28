#!/usr/bin/env python3
"""O que a Jogar diz sem resposta do daemon, e de onde se lê o número de lugares.

NOTA DATADA, 28/10/2026: a frase por cima dos lugares apagados e o `+N` do quinto controle
saíram com o cartão (A-JOGAR-SE-PUBLICA-COM-OS-CONTROLES-E-A-02-SAI-01); a seção Controles
tem os quatro assentos e o Status em Desligado é o único sinal do serviço parado.
"""
from __future__ import annotations

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from pacotes import Contexto
from pacotes import a01_jogar as aba

def test_sem_daemon_a_aba_nao_afirma_que_a_mesa_esta_vazia() -> None:
    """`conectados` vazio pode ser "não há" ou "ninguém respondeu".

    É a mesma guarda do `_estado_da_tela`, e ela é a armadilha desta aba:
    escrever "nenhum controle na mesa" sobre um tique sem resposta é a tela
    afirmando o que não leu. Com o serviço parado a mesa também não escreve que ele parou
    (20/10/2026): o Status em Desligado é o único sinal.

    A MORDIDA: faça a posição do pacote sem `state` virar Ligado e a régua reprova.
    """
    vazio = Contexto(state={}, mesa=[], conectados=[], estados={})
    fora = aba.pacote(vazio)
    assert "mesa-frase" not in fora
    assert fora["hef-posicao"] == aba.POSICAO_COM_O_SERVICO_PARADO


def test_o_numero_de_lugares_se_le_do_desenho() -> None:
    """Cravar `4` poria nesta frase o mesmo defeito que ela denuncia."""
    assert aba.lugares_da_mesa() == len(monta.MESA)
