"""O gesto de calibrar não vira ação dentro do jogo aberto atrás da janela.

``CALIBRAR-AS-ENTRADAS-01``, tarefa ``CAL-5``, o furo **F-3** (26/08/2026).

O FURO, MEDIDO NO FONTE
------------------------

O despacho para o gamepad virtual é gateado **só** pelos 0,3 s de grace, e
sobrevive de propósito ao ``daemon.pause`` **e** ao modo jogo. O bloco está em
``daemon/lifecycle.py``, no ``_dispatch_gamepad_emulation``, e o comentário dele
diz por quê: *"o gamepad é despachado AQUI, gateado SÓ pelo grace-period
(anti-ghost-input), com os botões CRUS"*.

Consequência: usar direcional e X para navegar esta janela **vaza para o jogo**.
Confirmar uma entrada com o cabo na mão, atrás do gabinete, dispararia um pulo,
um tiro ou um menu no jogo que está rodando na TV.

O QUE ESTA FRENTE ENTREGA, E O QUE ELA NÃO PODE ENTREGAR
----------------------------------------------------------

A janela **declara a posse** do vocabulário que usa enquanto tem foco, e
``botoes_para_o_jogo`` é a peneira que essa posse arma. **Quem tem de
perguntar é o daemon**, e ``daemon/lifecycle.py`` não é posse desta frente
(regra R-A da leva: precisou de arquivo alheio, relata e para).

Então esta régua monta o despacho de mentira — um vpad que recebe o que passar
pela peneira — e mede a peneira. O que ela NÃO prova é que o daemon já pergunta:
isso está declarado na entrega e na lápide do módulo, e é a ``A-CASA-SABE-E-O-
PRODUTO-NÃO-FAZ`` sendo escrita em vez de escondida.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.widgets.calibrar_entradas import (
    POSSE,
    VOCABULARIO_DA_CALIBRACAO,
    botoes_para_o_jogo,
)


class JogoSimulado:
    """O gamepad virtual com um jogo atrás. Guarda tudo o que chegou nele."""

    def __init__(self) -> None:
        self.recebidos: list[str] = []

    def despachar(self, botoes: frozenset[str] | set[str]) -> None:
        """O que o ``_dispatch_gamepad_emulation`` faria com os botões crus."""
        self.recebidos.extend(sorted(botoes_para_o_jogo(botoes)))


@pytest.fixture(autouse=True)
def _sem_posse_pendurada():
    """A posse é de MÓDULO, então ela tem de morrer com o teste.

    Sem isto, um teste que toma a posse e falha no meio deixa o vocabulário
    preso para o resto do processo — e o arquivo seguinte mediria uma janela
    que ninguém abriu.
    """
    POSSE.soltar()
    yield
    POSSE.soltar()


# ---------------------------------------------------------------------------
# A mordida
# ---------------------------------------------------------------------------


def test_com_a_janela_em_foco_o_despacho_para() -> None:
    """Com a posse declarada, zero eventos do vocabulário chegam ao vpad.

    MORDIDA: arrancar a subtração de ``botoes_para_o_jogo`` (devolver
    ``frozenset(botoes)`` sempre), que é a versão sem posse nenhuma. O evento
    aparece no vpad e o teste reprova **dizendo qual botão vazou** — porque
    "vazou alguma coisa" não conserta nada, e "vazou o `cross`" conserta.
    """
    jogo = JogoSimulado()
    POSSE.tomar()
    assert POSSE.dono

    jogo.despachar({"cross", "r1"})

    vazados = sorted(set(jogo.recebidos) & set(VOCABULARIO_DA_CALIBRACAO))
    assert not vazados, (
        f"o gesto de calibrar chegou ao jogo: {', '.join(vazados)}. Confirmar "
        "uma entrada com o cabo na mão dispararia essa ação dentro do jogo "
        "que está aberto atrás da janela"
    )


def test_o_que_nao_e_da_janela_continua_indo_para_o_jogo() -> None:
    """A posse é do vocabulário DELA, não do controle inteiro.

    Um dublê que só sabe recusar não é régua: tomar o controle todo deixaria o
    jogo mudo, que é um estrago maior que o vazamento.
    """
    jogo = JogoSimulado()
    POSSE.tomar()
    jogo.despachar({"cross", "r1", "square"})

    assert "r1" in jogo.recebidos and "square" in jogo.recebidos, (
        "a janela tomou botão que não é dela e deixou o jogo mudo"
    )


def test_sem_a_janela_em_foco_nada_muda() -> None:
    """Fechada a janela, o despacho é a identidade — e é 99,9% do tempo."""
    jogo = JogoSimulado()
    POSSE.soltar()
    jogo.despachar({"cross", "dpad_up"})

    assert sorted(jogo.recebidos) == ["cross", "dpad_up"]


def test_perder_o_foco_devolve_o_vocabulario() -> None:
    """A posse acompanha o FOCO, não a vida da janela.

    Com a janela aberta e o foco no jogo, o controle é do jogo. Uma posse
    presa à janela deixaria o jogo sem X enquanto a calibração estivesse
    aberta em segundo plano.
    """
    POSSE.tomar()
    POSSE.soltar()
    assert POSSE.dono == ""
    assert botoes_para_o_jogo({"cross"}) == frozenset({"cross"})


def test_o_vocabulario_e_o_minimo_que_a_cerimonia_precisa() -> None:
    """Quatro botões: confirmar, voltar e andar na lista.

    O tamanho é o contrato. Cada botão a mais é um botão que o jogo perde
    enquanto a janela tem foco, e a cerimônia inteira cabe em quatro.
    """
    assert set(VOCABULARIO_DA_CALIBRACAO) == {
        "cross",
        "circle",
        "dpad_up",
        "dpad_down",
    }
