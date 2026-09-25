"""A tela renomeia junto com mover — APARELHO-NAO-SE-CONTRADIZ-01, PARTE 2.

DECISÃO DELA, 20/09/2026: **«Curar — renomear junto com mover»**. A razão é de
acessibilidade: 1,6 s é tempo de sobra para o olho pegar, e num produto de
acessibilidade um número errado é caro.

## O que foi medido

Lido pela ponte JS no WebKit vivo, a 400 ms, com o daemon e quatro controles::

                          23:56:17.998                  23:56:19.604
    cartão `p3`           «Player 4» Galactic Purple    «Player 3» …
    chip da fita          «P4 • Galactic Purple»        «P3 • …»

Duas vezes na mesma noite, com o mesmo vão: 1,60 s e 1,61 s. **O endereço do
cartão e o texto dentro dele se contradiziam** — e o vão era interno à tela: a
MESMA leitura do daemon dava as duas respostas, porque a posição compacta na
hora e o ``player_slot`` leva um batimento.

## Onde esta régua morde

A cura é a POSIÇÃO ceder, nunca o número: quem manda no número é o daemon
(``actions/base.numero_do_controle``, fonte única desde a COR-01), e deixar a
tela compactá-lo por conta própria seria duas verdades sobre qual é o Player 3.

:class:`TestAMordida` exerce o caminho PRÉ-CURA — o ``pref`` pela posição na
lista — e exige que ele reproduza a contradição medida. Se os dois caminhos
responderem igual, a régua está medindo a si mesma.

Nenhum endereço real: faixa forjada ``aa:bb:cc:…`` com os octetos 4 e 5
zerados.
"""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.mesa_viva`, que carrega o GTK")

from hefesto_dualsense4unix.interface import mesa_viva

#: Os quatro da mesa dela, na ordem em que ela os liga.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"


def _estado(*pares: tuple[str, int | None]) -> dict[str, Any]:
    """O `state_full` com os controles que importam, e só o que a mesa lê."""
    return {
        "controllers": [
            {"uniq": uniq, "connected": True, "transport": "bt",
             "player_slot": slot, "index": i}
            for i, (uniq, slot) in enumerate(pares)
        ]
    }


def _cartoes(*pares: tuple[str, int | None]) -> dict[str, tuple[str, int]]:
    """`{uniq: (pref, jogador)}` — o endereço do cartão e o texto dentro dele."""
    return {
        str(c["uniq"]): (str(c["pref"]), int(c["jogador"]))
        for c in mesa_viva.mesa_do_estado(_estado(*pares), {})
    }


class TestOCartaoNaoSeContradiz:
    """O endereço do cartão e o número dentro dele dizem a mesma coisa."""

    def test_o_instante_medido_de_20_09(self) -> None:
        """O P3 saiu e o daemon ainda não renomeou o roxo.

        É a leitura de ``23:56:17.998``: três na mesa, e o roxo ainda é o
        jogador 4. O cartão dele fica no LUGAR 4 — que é o que ele diz ser.
        """
        cartoes = _cartoes((P1, 1), (P2, 2), (P4, 4))
        assert cartoes[P4] == ("p4", 4), (
            "o cartão do roxo mudou de lugar antes de mudar de nome — é a "
            "contradição de 1,6 s que esta sprint veio fechar")
        assert cartoes[P1] == ("p1", 1)
        assert cartoes[P2] == ("p2", 2)

    def test_o_instante_seguinte_move_e_renomeia_junto(self) -> None:
        """``23:56:19.604``: o daemon renomeou, e o cartão vai junto."""
        cartoes = _cartoes((P1, 1), (P2, 2), (P4, 3))
        assert cartoes[P4] == ("p3", 3)

    def test_nenhuma_leitura_tem_texto_de_um_jogador_em_lugar_de_outro(self) -> None:
        """A régua da sprint, dita como ela pede: em NENHUMA leitura.

        Varre as duas leituras do vão medido e mais a mesa cheia. É a forma
        forte porque o defeito era intermitente por desenho — ele só existia
        entre dois batimentos.
        """
        for mesa in (
            ((P1, 1), (P2, 2), (P3, 3), (P4, 4)),
            ((P1, 1), (P2, 2), (P4, 4)),
            ((P1, 1), (P2, 2), (P4, 3)),
            ((P2, 2), (P4, 4)),
        ):
            for uniq, (pref, jogador) in _cartoes(*mesa).items():
                assert pref == f"p{jogador}", (
                    f"{uniq}: o cartão {pref} diz «Player {jogador}» — "
                    f"endereço e texto se contradizem na mesa {mesa}")


class TestOsDoisCasosQueVoltamAContarPorPosicao:
    """A cura cede onde o número não é um lugar — e volta ao de antes."""

    def test_numero_acima_do_ultimo_cartao(self) -> None:
        """Um externo na mesa empurra os DualSense para cima do teto.

        O desenho tem quatro cartões; um jogador 5 não tem onde pousar. A mesa
        inteira volta a contar 1..N, que é o comportamento anterior.
        """
        cartoes = _cartoes((P1, 2), (P2, 5))
        assert [p for p, _ in cartoes.values()] == ["p1", "p2"]

    def test_numero_repetido_nao_empilha_dois_no_mesmo_lugar(self) -> None:
        """Daemon velho sem `player_slot`: `numero_do_controle` cai na posição.

        Dois cartões no mesmo endereço seria pior que o defeito curado — um
        deles simplesmente não existiria na tela.
        """
        cartoes = _cartoes((P1, None), (P2, None))
        prefs = [p for p, _ in cartoes.values()]
        assert len(set(prefs)) == len(prefs), f"dois cartões no mesmo lugar: {prefs}"


class TestOQuePedeOProduto:
    """A hipótese tem de explicar o que já funcionava."""

    def test_o_numero_continua_vindo_do_daemon(self) -> None:
        """`jogador` é a fonte única, e nada aqui a substitui (COR-01/D6)."""
        from hefesto_dualsense4unix.app.actions.base import numero_do_controle

        entrada = {"uniq": P4, "connected": True, "player_slot": 4, "index": 0}
        (cartao,) = mesa_viva.mesa_do_estado({"controllers": [entrada]}, {})
        assert cartao["jogador"] == numero_do_controle(entrada) == 4

    def test_o_teto_e_perguntado_ao_dono_dos_lugares(self) -> None:
        """`pacotes.TODOS_OS_LUGARES` manda — o número não se digita aqui."""
        from hefesto_dualsense4unix.interface.pacotes import TODOS_OS_LUGARES

        assert mesa_viva._quantos_lugares() == len(TODOS_OS_LUGARES)


class TestAMordida:
    """Arranque a cura e veja a contradição voltar."""

    def test_o_caminho_pre_cura_poe_o_player_4_no_cartao_tres(self) -> None:
        """A cura arrancada = `pref` pela posição na lista.

        É EXATAMENTE o código anterior a esta sprint, e com ele o cartão `p3`
        diz «Player 4» — a leitura de ``23:56:17.998``.
        """
        mesa = ((P1, 1), (P2, 2), (P4, 4))
        cartoes = _cartoes(*mesa)
        assert cartoes[P4][0] == "p4"  # com a cura

        por_posicao = [f"p{i}" for i in range(1, len(mesa) + 1)]
        assert por_posicao[-1] == "p3" and cartoes[P4][1] == 4, (
            "a mordida não reproduziu o mundo pré-cura: se a contagem por "
            "posição desse o mesmo endereço, esta régua não mediria nada")
