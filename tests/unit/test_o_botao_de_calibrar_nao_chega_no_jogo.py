"""O gesto de calibrar não vira ação dentro do jogo aberto atrás da janela."""
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
    """A posse é de MÓDULO, então ela tem de morrer com o teste."""
    POSSE.soltar()
    yield
    POSSE.soltar()


def test_com_a_janela_em_foco_o_despacho_para() -> None:
    """Com a posse declarada, zero eventos do vocabulário chegam ao vpad."""
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
    """A posse é do vocabulário DELA, não do controle inteiro."""
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
    """A posse acompanha o FOCO, não a vida da janela."""
    POSSE.tomar()
    POSSE.soltar()
    assert POSSE.dono == ""
    assert botoes_para_o_jogo({"cross"}) == frozenset({"cross"})


def test_o_vocabulario_e_o_minimo_que_a_cerimonia_precisa() -> None:
    """Quatro botões: confirmar, voltar e andar na lista."""
    assert set(VOCABULARIO_DA_CALIBRACAO) == {
        "cross",
        "circle",
        "dpad_up",
        "dpad_down",
    }
