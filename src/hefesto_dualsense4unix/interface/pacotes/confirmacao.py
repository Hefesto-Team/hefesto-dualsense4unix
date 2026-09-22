#!/usr/bin/env python3
"""A JANELA DO CONSENTIMENTO DE DOIS TEMPOS — quanto tempo um botão fica armado.

Um botão que fecha a Steam dela — ou que faz qualquer coisa cara e destrutiva —
não age no primeiro clique: ele **arma**, troca de rótulo e espera a
confirmação. Este módulo guarda a DURAÇÃO dessa espera, e só ela.

O MECANISMO SAIU DAQUI — 21/09/2026
-----------------------------------
Até esta data moravam aqui também o relógio (``_ARMADO``), o ``data-v`` do
botão armado (``confirmo``) e a conta que decidia o clique
(``este_clique_confirma``). Eles nasceram privados na aba 07 e subiram para cá
em 20/09 (STEAM-INPUT-01), quando o chip «Steam Input» da aba Jogar pareceu
precisar do mesmo mecanismo — e não precisou: um chip estático não tem rótulo
para trocar nem ``data-v`` para carregar, e quem completa o vdf naquela aba é
o ``hefesto-steam-input-guard.path``.

Em 21/09/2026 os botões da aba 07 que fechavam a Steam saíram, palavra dela:
*"a ideia é termos os mesmos botões pra todos os lançadores. sempre."* O
mecanismo ficou sem chamador, e o portão ``casa-sabe`` o acusou.

**A DÍVIDA DOS DOIS RELÓGIOS ACABOU JUNTO.** A aba 09 fecha a Steam com relógio
próprio (``a09_sistema._confirmado``, que tem ``antes_de_armar`` e não cabia na
conta daqui), e a conferência de 20/09 mediu que armar a 07 e a 09 deixava os
dois pendurados ao mesmo tempo. Sem a 07, há UM relógio sobre a Steam dela — e
``test_steam_input_01_o_chip_que_acende_por_jogo`` reprova a segunda aba que
fechar a Steam com relógio próprio.

**NÃO É UM PACOTE DE ABA**: ele não tem ``@registrar`` nem ``@gesto``. É um
ajudante compartilhado, como ``pacotes/perfil.py`` e ``pacotes/mapa.py``.
"""
from __future__ import annotations

#: Quanto tempo um gesto fica ARMADO depois do primeiro clique.
#:
#: O DONO É ESTE, e ele não é um número solto: é o consentimento que
#: ``steam_launch_options.with_steam_closed`` EXIGE de quem a chama, na forma
#: que uma página tem. ``a09_sistema.segundos_para_confirmar()`` o lê daqui, e
#: ``test_a_09_sistema_confirma_em_dois_cliques`` trava as duas pontas.
SEGUNDOS_PARA_CONFIRMAR = 20.0
