"""STEAM-NO-FISICO-01 — o número do jogador e a barra que o diz são do Hefesto.

A PALAVRA DELA, 23/09/2026 (`D-2309-O-HEFESTO-MANDA-NO-NUMERO`):

    *"Hefesto manda e controla sempre, steam sequestrou hefesto corrigiu ao no
    segundo após e temos que fazer o jogo entender isso."*

A primeira das três obrigações: a réplica da camada do jogo deixa de trocar o
número do físico, **mesmo em co-op**. O diário dela mostrou a troca acontecendo
(21/09/2026): `game_output_replicado autoridade=game campos=['player_leds']
players=(False, True, False, True, False)` e, sob `unknown`, a cor da paleta
de jogador do SDL junto — `(64, 0, 0)` com o padrão do jogador 2.

A COR QUE É NÚMERO. O SDL só pinta a barra com a paleta dele quando o jogo NÃO
escolheu cor (`SDL_hidapi_ps5.c`, `ctx->color_set`). Uma cor da paleta é o
número escrito na barra; recusar só o `player_leds` deixaria o aparelho dizendo
«jogador 1» nas lâmpadas e «jogador 2» na barra — e o aparelho nunca se
contradiz (decisão dela de 20/09). A cor que o jogo ESCOLHE continua passando.

AS MORDIDAS, exercidas uma a uma e devolvidas: arrancar a peneira da ENTRADA
em `set_game_output_for` faz o nó receber o número do jogo; arrancar a do
MERGE em `_merged_desired_for_key` faz a camada escrita antes da regra voltar
pelo resolve.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import structlog
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec

MAC_1 = "AA:BB:CC:00:00:01"
UNIQ_1 = "aabbcc000001"
MAC_2 = "AA:BB:CC:00:00:02"
UNIQ_2 = "aabbcc000002"

#: O número que o Hefesto dá a cada peça (a camada automática, a cor do número).
NUMERO_1 = (False, False, True, False, False)
NUMERO_2 = (False, True, False, True, False)
COR_DO_NUMERO_1 = (0, 90, 255)
COR_DO_NUMERO_2 = (255, 40, 40)

#: O que o SDL escreve no vpad quando numera: o padrão e a cor da paleta dele.
NUMERO_DO_SDL_2 = (False, True, False, True, False)
NUMERO_DO_SDL_3 = (True, False, True, False, True)

#: Uma cor que o JOGO escolhe de propósito (gameplay) — esta passa.
COR_DE_GAMEPLAY = (200, 60, 0)

#: As quatro medidas no diário dela, e as três que só o fonte tem.
PALETA_MEDIDA = [(0, 0, 64), (64, 0, 0), (0, 64, 0), (32, 0, 32)]
PALETA_DO_FONTE = [(32, 16, 0), (0, 16, 16), (16, 16, 16)]


class _NoDeLed:
    """Nó sysfs falso — grava as chamadas, nunca toca o filesystem."""

    def __init__(self) -> None:
        self.rgb_calls: list[tuple[int, int, int]] = []
        self.player_calls: list[tuple[bool, ...]] = []

    def set_rgb(self, r: int, g: int, b: int) -> bool:
        self.rgb_calls.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.player_calls.append(tuple(bits))
        return True

    def invalidate_cache(self) -> None:
        return None


def _handle() -> SimpleNamespace:
    return SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
    )


def _numero_automatico(uniq: str) -> bp._DesiredOutput:
    if uniq == UNIQ_2:
        return bp._DesiredOutput(led=COR_DO_NUMERO_2, player_leds=NUMERO_2)
    return bp._DesiredOutput(led=COR_DO_NUMERO_1, player_leds=NUMERO_1)


def _mesa(
    autoridade: str | None = "game", *, dois: bool = False
) -> tuple[bp.PyDualSenseController, dict[str, _NoDeLed]]:
    """Mesa com o Hefesto numerando (camada automática) e o jogo aberto."""
    ctl = bp.PyDualSenseController()
    nos = {MAC_1: _NoDeLed()}
    ctl._handles = {MAC_1: _handle()}
    if dois:
        nos[MAC_2] = _NoDeLed()
        ctl._handles[MAC_2] = _handle()
    ctl._sysfs = dict(nos)
    ctl.set_auto_output_provider(_numero_automatico)
    if autoridade is not None:
        ctl.set_game_authority_provider(lambda: autoridade)
    return ctl, nos


def _eventos(registros: list[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [r for r in registros if r["event"] == nome]


class TestOPredicado:
    def test_player_leds_e_numero_sempre(self) -> None:
        assert bp.numeracao_do_jogo({"player_leds": NUMERO_DO_SDL_2}) == {"player_leds"}

    @pytest.mark.parametrize("cor", PALETA_MEDIDA + PALETA_DO_FONTE)
    def test_a_paleta_do_sdl_e_numero(self, cor: tuple[int, int, int]) -> None:
        assert bp.numeracao_do_jogo({"led": cor}) == {"led"}

    def test_a_cor_escolhida_pelo_jogo_nao_e_numero(self) -> None:
        assert bp.numeracao_do_jogo({"led": COR_DE_GAMEPLAY}) == frozenset()

    def test_valor_ausente_nao_e_numero(self) -> None:
        assert bp.numeracao_do_jogo({"led": None, "player_leds": None}) == frozenset()

    def test_a_paleta_tem_as_sete_do_fonte(self) -> None:
        """A tabela é a do `SetLedsForPlayerIndex` do SDL, inteira."""
        assert set(bp.PALETA_DE_JOGADOR_DO_SDL) == set(PALETA_MEDIDA + PALETA_DO_FONTE)


class TestONumeroDoJogoNaoChegaAoFisico:
    @pytest.mark.parametrize("autoridade", ["game", "unknown", "daemon", None])
    def test_nem_camada_nem_escrita_nem_retencao(self, autoridade: str | None) -> None:
        """A MORDIDA da peneira da ENTRADA: sem ela, sob `game`/`unknown`/sem
        provider o nó recebe o padrão do SDL, e sob `daemon` ele fica retido."""
        ctl, nos = _mesa(autoridade)

        assert ctl.set_game_output_for(MAC_1, player_leds=NUMERO_DO_SDL_2) is True

        assert NUMERO_DO_SDL_2 not in nos[MAC_1].player_calls
        assert UNIQ_1 not in ctl._game_output_by_uniq
        assert ctl._retained_game_outputs == {}
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).player_leds == NUMERO_1

    @pytest.mark.parametrize("cor", PALETA_MEDIDA)
    def test_a_barra_que_diz_o_numero_do_sdl_nao_chega(
        self, cor: tuple[int, int, int]
    ) -> None:
        ctl, nos = _mesa("unknown")

        ctl.set_game_output_for(MAC_1, led=cor, player_leds=NUMERO_DO_SDL_2)

        assert cor not in nos[MAC_1].rgb_calls
        with ctl._io_lock:
            resolvido = ctl._merged_desired_for_key(MAC_1)
        assert resolvido.led == COR_DO_NUMERO_1
        assert resolvido.player_leds == NUMERO_1

    def test_a_cor_de_gameplay_continua_passando(self) -> None:
        """REPLICA-03 intacta para o que não é número: a barra do jogo pinta."""
        ctl, nos = _mesa("game")

        ctl.set_game_output_for(
            MAC_1, led=COR_DE_GAMEPLAY, player_leds=NUMERO_DO_SDL_2
        )

        assert nos[MAC_1].rgb_calls == [COR_DE_GAMEPLAY]
        assert nos[MAC_1].player_calls == []
        with ctl._io_lock:
            resolvido = ctl._merged_desired_for_key(MAC_1)
        assert resolvido.led == COR_DE_GAMEPLAY
        assert resolvido.player_leds == NUMERO_1


class TestMesmoEmCoop:
    def test_o_jogo_numera_os_dois_e_os_dois_ficam_com_o_numero_da_mesa(self) -> None:
        """«Mesmo em co-op»: o SDL numera cada vpad (o P1 da mesa vira o 2 do
        jogo, o P2 vira o 3) e nenhum físico muda de número."""
        ctl, nos = _mesa("game", dois=True)

        ctl.set_game_output_for(MAC_1, led=(64, 0, 0), player_leds=NUMERO_DO_SDL_2)
        ctl.set_game_output_for(MAC_2, led=(0, 64, 0), player_leds=NUMERO_DO_SDL_3)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).player_leds == NUMERO_1
            assert ctl._merged_desired_for_key(MAC_2).player_leds == NUMERO_2
        for no in nos.values():
            assert no.player_calls == []
            assert no.rgb_calls == []

    def test_a_camada_de_coop_do_hefesto_continua_numerando(self) -> None:
        """O co-op que numera é o do HEFESTO (`set_coop_outputs`) — ele não é o
        jogo, e a regra não o toca."""
        ctl, nos = _mesa("game", dois=True)

        ctl.set_coop_outputs(
            {MAC_1: OutputSpec(player_leds=NUMERO_1), MAC_2: OutputSpec(player_leds=NUMERO_2)}
        )
        ctl.set_game_output_for(MAC_2, player_leds=NUMERO_DO_SDL_3)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_2).player_leds == NUMERO_2
        assert NUMERO_DO_SDL_3 not in nos[MAC_2].player_calls


class TestOPortaoDoMerge:
    def test_camada_escrita_antes_da_regra_nao_volta_pelo_resolve(self) -> None:
        """A MORDIDA da peneira do MERGE: a camada GAME já tem o número e a cor
        da paleta (escrita por uma versão sem a regra, ou por um caminho que
        ainda não passe pela entrada) — o resolve não pode devolvê-los, porque
        é dele que saem o reassert, o priming e o `0x31` do gatilho da cor."""
        ctl, _nos = _mesa("game")
        ctl._game_output_by_uniq[UNIQ_1] = bp._DesiredOutput(
            led=(0, 64, 0), player_leds=NUMERO_DO_SDL_3
        )

        with ctl._io_lock:
            resolvido = ctl._merged_desired_for_key(MAC_1)

        assert resolvido.player_leds == NUMERO_1
        assert resolvido.led == COR_DO_NUMERO_1

    def test_o_gatilho_da_cor_pelo_radio_leva_o_numero_da_mesa(self) -> None:
        """O que chega ao plástico pelo rádio sai do mesmo merge."""
        ctl, _nos = _mesa("game")
        escritos: list[list[int]] = []
        handle = ctl._handles[MAC_1]
        handle.writeReport = lambda r: escritos.append(r) or len(r)
        ctl._detect_transport = lambda _h: "bt"  # type: ignore[method-assign]
        ctl.set_game_output_for(MAC_1, led=(64, 0, 0), player_leds=NUMERO_DO_SDL_2)

        with structlog.testing.capture_logs() as registros:
            ctl.reescrever_lightbar_por_hidraw()

        escrita = _eventos(registros, "gatilho_da_cor_escrito")
        assert escrita[0]["players"] == NUMERO_1
        assert escrita[0]["cor"] == COR_DO_NUMERO_1


class TestOJournalDizARecusa:
    def test_uma_vez_por_campo_e_por_sessao(self) -> None:
        ctl, _nos = _mesa("game")

        with structlog.testing.capture_logs() as registros:
            for _ in range(10):
                ctl.set_game_output_for(
                    MAC_1, led=(64, 0, 0), player_leds=NUMERO_DO_SDL_2
                )

        ditos = _eventos(registros, "game_output_recusado_o_hefesto_numera")
        assert len(ditos) == 1
        assert ditos[0]["campos"] == ["led", "player_leds"]
        assert ditos[0]["cor"] == (64, 0, 0)
        assert ditos[0]["players"] == NUMERO_DO_SDL_2
        assert ditos[0]["autoridade"] == "game"
        assert not _eventos(registros, "game_output_replicado")

    def test_a_sessao_seguinte_volta_a_dizer(self) -> None:
        ctl, _nos = _mesa("game")
        ctl.set_game_output_for(MAC_1, player_leds=NUMERO_DO_SDL_2)
        ctl.end_game_session_for(MAC_1)

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(MAC_1, player_leds=NUMERO_DO_SDL_2)

        assert len(_eventos(registros, "game_output_recusado_o_hefesto_numera")) == 1
