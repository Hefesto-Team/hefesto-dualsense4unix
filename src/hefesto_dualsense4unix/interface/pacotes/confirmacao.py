#!/usr/bin/env python3
"""O CONSENTIMENTO DE DOIS TEMPOS, com UM dono para as abas que o pedem.

Um botão que fecha a Steam dela — ou que faz qualquer coisa cara e destrutiva —
não age no primeiro clique: ele **arma**, troca de rótulo e espera a
confirmação. O mecanismo é o mesmo em toda aba; o que muda é a frase. **E ele
só serve a quem tem onde MOSTRAR a pergunta** — ver o bloco do chamador único,
abaixo.

POR QUE ELE SAIU DA ABA 07 — STEAM-INPUT-01, 20/09/2026
--------------------------------------------------------
Ele nasceu privado em ``a07_lancadores`` (``_este_clique_confirma``,
``_ARMADO``, ``_confirmo``), e isso bastava enquanto UMA aba fechava a Steam.
O chip «Steam Input» da aba **Jogar** nasceu precisando do mesmo mecanismo:
construir a ponte reescreve o ``localconfig.vdf`` dela, e para isso a Steam tem
de estar fechada (``integrations/steam_input_ponte.garantir_ponte``).

As duas saídas erradas estavam nomeadas na sprint, e são as de sempre nesta
casa:

* **importar o símbolo privado da outra aba** — os pacotes são território
  exclusivo por desenho, e um ``from .a07_lancadores import
  _este_clique_confirma`` amarra a aba 01 ao arquivo de outra frente;
* **reescrever a conta na 01** — é como se fabrica a divergência. A terceira
  cópia é sempre a mais frouxa, e o comentário de ``este_clique_confirma`` já
  dizia isso quando ele era da 07: *"Três cópias do consentimento que fecha a
  Steam dela é exatamente onde uma delas ficaria mais frouxa que as outras."*

Então o par virou público aqui e a ``a07`` passou a importar daqui — zero
mudança de comportamento: são as MESMAS funções, com o MESMO ``_ARMADO``.

**HOJE ELE TEM UM CHAMADOR SÓ, e a razão está medida.** A aba 01 acabou NÃO
pedindo consentimento: o botão da 07 é redesenhado a cada tique
(``_botao_armavel``) e TROCA de rótulo para «Fechar e continuar»; o chip da 01 é
um ``<span>`` estático da fileira, sem rótulo para trocar e sem ``data-v`` para
carregar — e o segundo guarda de :func:`este_clique_confirma` exige justamente
esse ``data-v``, que *só existe no cartão já armado*. Um consentimento que ela
não LÊ não é consentimento, e o que completa o vdf naquela aba é o
``hefesto-steam-input-guard.path``, que acorda quando a Steam sai.

A extração fica de pé assim mesmo, e não por zelo: o mecanismo passou a ter
**um dono público**, e `test_steam_input_01_o_chip_que_acende_por_jogo` varre
todos os ``pacotes/a*.py`` e reprova qualquer um que defina o seu. A aba que
precisar dele amanhã tem porta; a cópia que tentar nascer tem régua.

O QUE ESTE MÓDULO **NÃO** FAZ
-----------------------------
Ele não tem opinião sobre o que é caro. Quem decide se um ato pede
consentimento é a aba, e a razão está escrita na 07, palavra por palavra:
*"pedir consentimento para um ato reversível ensina que todo botão pede
consentimento, e aí o consentimento que importa deixa de ser lido."*

Ele também não pinta nada. O botão armado é desenhado pela aba (a 07 tem o
``_botao_armavel``); o que sai daqui é só o ``data-v`` que aquele botão tem de
carregar (:func:`confirmo`) e a conta que o decide (:func:`este_clique_confirma`).

**NÃO É UM PACOTE DE ABA**: ele não tem ``@registrar`` nem ``@gesto``. É um
ajudante compartilhado, como ``pacotes/perfil.py`` e ``pacotes/mapa.py``.
"""
from __future__ import annotations

import time
from typing import Any

#: Quanto tempo um gesto fica ARMADO depois do primeiro clique.
#:
#: O DONO É ESTE, e ele não é um número solto: é o consentimento que
#: ``steam_launch_options.with_steam_closed`` EXIGE de quem a chama, na forma
#: que uma página tem. ``a09_sistema.segundos_para_confirmar()`` o lê daqui
#: (pela reexportação em ``a07_lancadores``), e
#: ``test_a_09_sistema_confirma_em_dois_cliques`` trava as duas pontas.
SEGUNDOS_PARA_CONFIRMAR = 20.0

#: A frase de quem clicou tarde demais. Ela LEVANTA em vez de rearmar calado —
#: ver :func:`este_clique_confirma`.
#:
#: O NÚMERO DE SEGUNDOS NÃO ENTRA NELA — A2-056, 11/09/2026. A frase tinha 96
#: caracteres e ficou com 63: saber que eram vinte segundos não muda o que ela
#: faz a seguir, e o que ela faz a seguir é clicar de novo.
FORA_DO_PRAZO = "Passou do tempo e não fechei nada. Clique de novo para começar."

#: QUAL GESTO ESTÁ ARMADO E ATÉ QUANDO (``time.monotonic``). Vazio = nenhum.
#:
#: ERA UM FLOAT SÓ na aba 07, e virou dicionário em 06/09/2026: passaram a
#: existir TRÊS botões que fecham a Steam naquela aba, e um relógio único faria
#: o consentimento de um valer para o outro — clicar em "Posso fechar a Steam?"
#: e confirmar em "Deixar tudo pronto" rodaria o segundo com o sim dado ao
#: primeiro. **O consentimento é do ATO, nunca da aba.**
#:
#: E ELE PASSOU A SER O ÚNICO DA CASA — 20/09. Um dicionário POR ABA seria um
#: relógio por aba sobre a MESMA Steam, e dois consentimentos pendurados ao
#: mesmo tempo: a segunda confirmação não teria como dizer a qual responde.
#: Aqui, armar um desarma o outro, venha de onde vier.
_ARMADO: dict[str, float] = {}


def armado_agora() -> str:
    """O gesto armado NESTE instante, ou ``""`` — e ele desarma sozinho no tempo.

    O relógio é LIDO aqui, e não guardado num ``bool``: um ``bool`` armado por
    um clique que ninguém confirmou continuaria armado depois de a janela
    passar, e o segundo clique de dez minutos depois valeria como consentimento.
    """
    for nome, ate in list(_ARMADO.items()):
        if time.monotonic() >= ate:
            del _ARMADO[nome]
    return next(iter(_ARMADO), "")


def armar(nome: str) -> None:
    """Arma UM gesto e desarma o que estivesse — ver :data:`_ARMADO`."""
    _ARMADO.clear()
    _ARMADO[nome] = time.monotonic() + SEGUNDOS_PARA_CONFIRMAR


def desarmar(nome: str = "") -> None:
    """Desarma um gesto (ou todos, sem nome)."""
    if nome:
        _ARMADO.pop(nome, None)
    else:
        _ARMADO.clear()


def confirmo(nome: str) -> str:
    """O ``data-v`` que **só existe no botão já armado** daquele gesto.

    ELE É POR GESTO, e é o primeiro dos dois guardas: um ``"steam:confirmo"``
    único faria o botão armado de um ato confirmar o outro, que é justamente o
    que :data:`_ARMADO` deixou de permitir do lado do relógio.
    """
    return f"{nome}:confirmo"


def este_clique_confirma(nome: str, o: dict[str, Any]) -> bool:
    """Este clique é a CONFIRMAÇÃO? Quando não é, ARMA o botão e devolve ``False``.

    OS DOIS GUARDAS SÃO INDEPENDENTES DE PROPÓSITO:

    1. o clique tem de trazer :func:`confirmo` no ``data-v`` — um valor que
       **só existe no cartão já armado**, escrito por quem desenha o botão;
    2. e tem de chegar dentro de :data:`SEGUNDOS_PARA_CONFIRMAR`.

    O PRIMEIRO É O QUE SEGURA A RÉGUA AUTOMÁTICA: a ``--prova-gesto`` clica o
    que o DOM tinha, e o DOM tinha a pergunta. Um guarda só bastaria hoje; dois
    é o que sobrevive a uma régua que releia o DOM entre cliques.

    FORA DO PRAZO ELE LEVANTA, em vez de agir ou de rearmar calado: a frase vai
    para a tela pelo caminho do ``RuntimeError``, e o tique seguinte repõe a
    pergunta. Rearmar calado deixaria a tela dizendo "Fechar e continuar" sobre
    um consentimento que já tinha vencido.
    """
    if str(o.get("v") or "").strip() != confirmo(nome):
        armar(nome)
        return False
    estava = armado_agora() == nome
    desarmar(nome)
    if not estava:
        raise RuntimeError(FORA_DO_PRAZO)
    return True
