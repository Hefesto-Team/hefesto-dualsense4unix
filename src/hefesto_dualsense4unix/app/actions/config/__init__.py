"""A aba Configurações — onde entra o que o Hefesto não tem como medir.

A décima primeira aba. As dez de hoje operam sobre o que o produto **mede**;
esta é o lugar do que ele **não consegue medir** e precisa que a pessoa
declare — onde o dongle está fisicamente, se há um hub no caminho, o que é
aquele rádio vizinho, qual a cor do plástico quando a leitura falha.

O teste de admissão de qualquer controle novo aqui é uma pergunta só: *o
Hefesto conseguiria descobrir isso sozinho?* Se sim, o lugar não é esta aba.

Como a aba Início, o Glade só reserva o container (`tab_config_box`): todo
widget é montado em código. É o padrão dos widgets dinâmicos desta casa, imune
ao bug de popup do cosmic-comp (cosmic-epoch#2497).

**O mapa deste pacote**, para quem chega:

    moldura.py       o molde visual de uma seção (Gtk.Frame + título + margens)
    secoes.py        a ORDEM das cinco
    mixin.py         o montador: cria as molduras e chama cada seção
    secao_exame.py       seção 0 — "Está tudo certo?"
    secao_controles.py   seção 1 — "Os controles"
    secao_mesa.py        seção 2 — "A mesa"
    secao_orcamento.py   seção 3 — "Orçamento"
    secao_janela.py      seção 4 — "A janela"
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.config.mixin import (
    ABA_CONFIG,
    ConfigActionsMixin,
)
from hefesto_dualsense4unix.app.actions.config.secoes import SECOES, SECOES_DA_ABA

__all__ = [
    "ABA_CONFIG",
    "SECOES",
    "SECOES_DA_ABA",
    "ConfigActionsMixin",
]
