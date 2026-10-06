#!/usr/bin/env python3
"""RECADO-VPAD-01 — o recado da Vibração não manda ligar o que já está ligado.

O DEFEITO, visto por ela em 17/09/2026: o rodapé da aba Vibração mandava
*"Ponha o Status em «Ligado» na aba Jogar"* com o Status **já aceso**. A causa
era a de sempre nesta casa, **duas leituras paralelas da mesma pergunta**: o
recado perguntava por ``native_mode`` + ``rumble_ff.vpads`` e o interruptor por
``mode_of_state`` → ``MODOS_LIGADOS``. Esta régua compara contra o dono, nunca
contra um texto digitado aqui.

O QUE MUDOU EM 03/10/2026 (``D-2909-A-NAVEGACAO-NAO-E-AVISO-NA-VIBRACAO``): o
ramo da Navegação saiu do recado. Ali nenhum jogo recebe gamepad por decisão
de produto (``D-1409``) e a intensidade fica guardada, então a faixa cala. O aviso só
existe para a emulação ligada sem gamepad virtual, e nesse estado o interruptor
da aba Jogar diz «Ligado» em 100% das vezes. O que continua valendo aqui é só
isto: **o recado nunca manda ligar o que já está ligado**, e a pergunta tem um
dono só.

AS MORDIDAS
-----------
* ponha a instrução velha («Ponha o Status em “Ligado”») no recado do vpad que
  não subiu → ``test_o_recado_nao_manda_ligar_o_que_o_painel_diz_ligado``
  reprova;
* troque a leitura de ``rumble_actions`` por uma cópia própria de
  ``MODOS_LIGADOS`` (ou reescreva ``mode_of_state`` ali) →
  ``test_a_pergunta_tem_um_dono_so`` reprova.
"""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.rumble_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import rumble_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
)

VPAD_NAO_SUBIU: dict[str, Any] = {
    "native_mode": False,
    "gamepad_emulation": {"enabled": True},
    "rumble_ff": {"vpads": 0},
}


def test_o_recado_nao_manda_ligar_o_que_o_painel_diz_ligado() -> None:
    """No único estado em que o aviso sai, o interruptor já diz Ligado."""
    texto = rumble_actions.texto_do_alcance_da_intensidade(VPAD_NAO_SUBIU)
    assert texto is not None
    assert painel.hefesto_ligado(VPAD_NAO_SUBIU) is True
    for imperativo in ("Ponha", "Ligue", "Troque"):
        assert imperativo not in texto, (
            f"o recado manda agir ({imperativo!r}) com o painel já em Ligado: "
            f"{texto!r}"
        )
    assert texto.startswith(rumble_actions._ALCANCE_O_QUE_ACONTECE)
    assert texto.endswith(rumble_actions._ALCANCE_O_QUE_SOBRA)


def test_a_pergunta_tem_um_dono_so() -> None:
    """O recado não reconstrói a regra do interruptor por conta própria."""
    fonte = vars(rumble_actions)
    assert "MODOS_LIGADOS" not in fonte, (
        "o recado ganhou a sua própria cópia de MODOS_LIGADOS — a pergunta "
        "voltou a ter dois donos"
    )
    assert "mode_of_state" not in fonte
    assert {MODE_GAMEPAD, MODE_DESKTOP} == set(painel.MODOS_LIGADOS), (
        "MODOS_LIGADOS mudou de conteúdo e o recado não foi junto: "
        f"{painel.MODOS_LIGADOS!r}"
    )
