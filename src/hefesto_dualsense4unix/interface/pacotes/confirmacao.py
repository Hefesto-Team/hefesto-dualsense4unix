#!/usr/bin/env python3
"""O CONSENTIMENTO DE DOIS TEMPOS — o relógio único sobre a Steam dela.

Um botão que fecha a Steam dela — ou que faz qualquer coisa cara e destrutiva —
não age no primeiro clique: ele **arma**, troca de rótulo e espera a
confirmação. Este módulo guarda a DURAÇÃO dessa espera e o RELÓGIO: o que está
armado agora, e até quando.

O RELÓGIO VOLTOU PARA CÁ — 24/09/2026, STEAM-INPUT-01
-----------------------------------------------------
Ele morou aqui de 20/09 a 21/09, saiu quando os botões da aba 07 que fechavam a
Steam saíram (*"a ideia é termos os mesmos botões pra todos os lançadores.
sempre."*), e ficou só a duração. Voltou porque o chip «Steam Input» da aba
Jogar passou a fechar a Steam, e a decisão é dela
(`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`): *"o primeiro clique avisa, o segundo
fecha"*.

**UM RELÓGIO SÓ, e é a razão de ele morar aqui.** A conferência de 20/09 mediu
que duas abas com relógio próprio deixavam dois consentimentos pendurados sobre
a MESMA Steam. A aba 09 (`a09_sistema._ARMADO`) é este mesmo dicionário, e a
aba 01 arma por :func:`armar`: armar uma desarma a outra.
``test_steam_input_01_o_chip_que_acende_por_jogo`` reprova a aba que fechar a
Steam com relógio próprio.

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
#: que uma página tem. ``a09_sistema.segundos_para_confirmar()`` o lê daqui, e
#: ``test_a_09_sistema_confirma_em_dois_cliques`` trava as duas pontas.
SEGUNDOS_PARA_CONFIRMAR = 20.0

#: O QUE ESTÁ ARMADO AGORA: ``{"gesto": <chave>, "ate": <time.monotonic>}``.
#: Vazio = nada armado. Uma coisa só de cada vez, em TODA a interface — armar a
#: segunda desarma a primeira, e o tique de cada aba repõe o rótulo dela.
#:
#: A chave é a de quem armou: a aba 09 escreve o nome do gesto, e a aba 01 o
#: gesto COM o jogo (:func:`chave`), porque o consentimento dela vale para o
#: jogo da pergunta e para nenhum outro.
ARMADO: dict[str, Any] = {}


def chave(*partes: object) -> str:
    """A chave do que se arma: as partes juntas, e a página na frente.

    Uma chave com a página não casa com o nome solto de um gesto da aba 09 —
    as duas abas partilham o relógio sem partilhar o que ele guarda.
    """
    return ":".join(str(p) for p in partes)


def armado_agora() -> str:
    """A chave armada NESTE instante, ou ``""`` — e ela desarma sozinha no tempo.

    O relógio é lido aqui, e não guardado num ``bool``: um ``bool`` armado por um
    clique que ninguém confirmou continuaria armado depois de a janela passar, e
    o segundo clique de dez minutos depois valeria como consentimento.
    """
    if ARMADO and time.monotonic() >= float(ARMADO.get("ate") or 0.0):
        ARMADO.clear()
    return str(ARMADO.get("gesto") or "")


def armar(chave_: str) -> None:
    """Arma ``chave_`` por :data:`SEGUNDOS_PARA_CONFIRMAR`, desarmando o resto."""
    ARMADO.clear()
    ARMADO.update(gesto=chave_, ate=time.monotonic() + SEGUNDOS_PARA_CONFIRMAR)


def desarmar() -> None:
    """Nada fica armado. É o que o clique de confirmação faz ANTES de agir."""
    ARMADO.clear()
