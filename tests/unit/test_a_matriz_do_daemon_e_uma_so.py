"""Os estados em que o Hefesto está DE PÉ têm um dono só, e a tela nova o lê.

Medido em 05/09/2026: `gui/aba_sistema.DE_PE` era digitado como
``("online_systemd", "online_avulso")`` e o comentário AFIRMAVA ser "a mesma
matriz de ``daemon_actions._ESTADOS_COM_DAEMON_DE_PE``". Faltava ``iniciando``,
e o dono guarda a razão de ele estar lá:

    "a unidade já está `active` e um 'Ligar' ali é o clique que não faz nada"

O que a falta produzia na tela, com a unit subindo — três frases falsas sobre o
mesmo instante:

* a linha dizia **"Ligando…"**;
* o botão trocava para **"Ativar o serviço"**;
* a dica do Reiniciar dizia *"O serviço está desligado — não há o que
  reiniciar"*;
* e o clique levantava *"o systemd nem chegou a ser chamado"*, com
  `_is_service_active()` respondendo `active`.

Esta régua não digita a lista: compara as duas pontas.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin
from hefesto_dualsense4unix.gui import aba_sistema


def test_a_tela_nova_le_a_matriz_do_dono():
    assert set(aba_sistema.DE_PE) == set(DaemonActionsMixin._ESTADOS_COM_DAEMON_DE_PE), (
        "a tela nova voltou a digitar os estados em vez de ler o dono. Um "
        "estado a menos aqui faz a tela oferecer 'Ativar' sobre um serviço que "
        "já está de pé, e o clique devolve um erro falso."
    )


def test_iniciando_conta_como_de_pe():
    """O estado que faltava, nomeado — para a lápide não perder o objeto."""
    assert "iniciando" in aba_sistema.DE_PE, (
        "`iniciando` saiu da matriz: a unit `active` com o processo ainda "
        "subindo volta a ser lida como serviço desligado"
    )


def test_a_lista_nao_e_literal_no_fonte():
    """A MORDIDA estrutural: redigitar a lista tem de ser visível."""
    import inspect

    fonte = inspect.getsource(aba_sistema)
    assert "DE_PE = _de_pe_do_dono()" in fonte, (
        "`DE_PE` deixou de ser derivado do dono. Se voltou a ser um literal, "
        "as duas listas passam a envelhecer separadas — que é exatamente o "
        "defeito que esta régua enterrou."
    )
