"""STEAM-NO-FISICO-01 — o número do jogador e a barra que o diz: a camada de baixo é do Hefesto.

Nota de 03/11/2026: a D-2309-O-HEFESTO-MANDA-NO-NUMERO caducou pela
D-0211-A-LUZ-DE-JOGADOR-E-DO-JOGO (A-LUZ-QUE-O-JOGO-PINTA-CHEGA-A-TODO-CONTROLE-01). Com a
autoridade no jogo, o número e a cor de índice do SDL que o jogo escreve chegam ao físico; fora
da autoridade (o cliente da Steam fora de jogo), ficam retidos, e o número do Hefesto volta no fim
da sessão.
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

NUMERO_1 = (False, False, True, False, False)
NUMERO_2 = (False, True, False, True, False)
COR_DO_NUMERO_1 = (0, 90, 255)
COR_DO_NUMERO_2 = (255, 40, 40)

NUMERO_DO_SDL_2 = (False, True, False, True, False)
NUMERO_DO_SDL_3 = (True, False, True, False, True)

COR_DE_GAMEPLAY = (200, 60, 0)

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


class TestNaoHaMaisVeto:
    def test_o_veto_do_numero_saiu_do_backend(self) -> None:
        veto = ("numeracao_do_jogo", "PALETA_DE_JOGADOR_DO_SDL", "_CAMPOS_QUE_O_HEFESTO_NUMERA")
        for nome in veto:
            assert not hasattr(bp, nome), nome


class TestComOJogoNaAutoridade:
    @pytest.mark.parametrize("autoridade", ["game", "unknown", None])
    def test_o_numero_do_jogo_chega(self, autoridade: str | None) -> None:
        ctl, nos = _mesa(autoridade)

        assert ctl.set_game_output_for(MAC_1, player_leds=NUMERO_DO_SDL_2) is True

        assert NUMERO_DO_SDL_2 in nos[MAC_1].player_calls
        assert ctl._retained_game_outputs == {}
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).player_leds == NUMERO_DO_SDL_2

    @pytest.mark.parametrize("cor", PALETA_MEDIDA + PALETA_DO_FONTE)
    def test_a_barra_da_paleta_do_sdl_chega(self, cor: tuple[int, int, int]) -> None:
        ctl, nos = _mesa("game")

        ctl.set_game_output_for(MAC_1, led=cor, player_leds=NUMERO_DO_SDL_2)

        assert cor in nos[MAC_1].rgb_calls
        with ctl._io_lock:
            resolvido = ctl._merged_desired_for_key(MAC_1)
        assert resolvido.led == cor
        assert resolvido.player_leds == NUMERO_DO_SDL_2

    def test_a_cor_de_gameplay_continua_passando(self) -> None:
        ctl, nos = _mesa("game")

        ctl.set_game_output_for(MAC_1, led=COR_DE_GAMEPLAY)

        assert nos[MAC_1].rgb_calls == [COR_DE_GAMEPLAY]
        with ctl._io_lock:
            resolvido = ctl._merged_desired_for_key(MAC_1)
        assert resolvido.led == COR_DE_GAMEPLAY
        assert resolvido.player_leds == NUMERO_1


class TestOClienteDaSteamForaDeJogo:
    @pytest.mark.parametrize("cor", PALETA_MEDIDA)
    def test_a_pintura_dele_fica_retida(self, cor: tuple[int, int, int]) -> None:
        ctl, nos = _mesa("daemon")

        ctl.set_game_output_for(MAC_1, led=cor, player_leds=NUMERO_DO_SDL_2)

        assert cor not in nos[MAC_1].rgb_calls
        assert NUMERO_DO_SDL_2 not in nos[MAC_1].player_calls
        assert UNIQ_1 not in ctl._game_output_by_uniq
        assert ctl._retained_game_outputs[UNIQ_1]["player_leds"] == NUMERO_DO_SDL_2
        with ctl._io_lock:
            resolvido = ctl._merged_desired_for_key(MAC_1)
        assert resolvido.led == COR_DO_NUMERO_1
        assert resolvido.player_leds == NUMERO_1


class TestEmCoop:
    def test_o_jogo_numera_os_dois(self) -> None:
        ctl, nos = _mesa("game", dois=True)

        ctl.set_game_output_for(MAC_1, led=(64, 0, 0), player_leds=NUMERO_DO_SDL_2)
        ctl.set_game_output_for(MAC_2, led=(0, 64, 0), player_leds=NUMERO_DO_SDL_3)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).player_leds == NUMERO_DO_SDL_2
            assert ctl._merged_desired_for_key(MAC_2).player_leds == NUMERO_DO_SDL_3
        assert nos[MAC_1].player_calls == [NUMERO_DO_SDL_2]
        assert nos[MAC_2].player_calls == [NUMERO_DO_SDL_3]

    def test_a_camada_de_coop_do_hefesto_fica_por_baixo(self) -> None:
        ctl, _nos = _mesa("game", dois=True)
        ctl.set_coop_outputs(
            {MAC_1: OutputSpec(player_leds=NUMERO_1), MAC_2: OutputSpec(player_leds=NUMERO_2)}
        )

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_2).player_leds == NUMERO_2
        ctl.set_game_output_for(MAC_2, player_leds=NUMERO_DO_SDL_3)
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_2).player_leds == NUMERO_DO_SDL_3
        ctl.end_game_session_for(MAC_2)
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_2).player_leds == NUMERO_2


class TestOFimDaSessaoDevolveOHefesto:
    def test_pelo_merge_e_pelo_radio(self) -> None:
        ctl, _nos = _mesa("game")
        escritos: list[list[int]] = []
        handle = ctl._handles[MAC_1]
        handle.writeReport = lambda r: escritos.append(r) or len(r)
        ctl._detect_transport = lambda _h: "bt"  # type: ignore[method-assign]
        ctl.set_game_output_for(MAC_1, led=(64, 0, 0), player_leds=NUMERO_DO_SDL_2)

        with structlog.testing.capture_logs() as registros:
            ctl.reescrever_lightbar_por_hidraw()
        escrita = _eventos(registros, "gatilho_da_cor_escrito")
        assert escrita[0]["players"] == NUMERO_DO_SDL_2
        assert escrita[0]["cor"] == (64, 0, 0)

        ctl.end_game_session_for(MAC_1)
        with structlog.testing.capture_logs() as registros:
            ctl.reescrever_lightbar_por_hidraw()
        escrita = _eventos(registros, "gatilho_da_cor_escrito")
        assert escrita[0]["players"] == NUMERO_1
        assert escrita[0]["cor"] == COR_DO_NUMERO_1


class TestOJournalDizAReplica:
    def test_uma_vez_por_campo_e_por_sessao(self) -> None:
        ctl, _nos = _mesa("game")

        with structlog.testing.capture_logs() as registros:
            for _ in range(10):
                ctl.set_game_output_for(MAC_1, led=(64, 0, 0), player_leds=NUMERO_DO_SDL_2)

        ditos = _eventos(registros, "game_output_replicado")
        assert len(ditos) == 1
        assert ditos[0]["campos"] == ["led", "player_leds"]
        assert ditos[0]["players"] == NUMERO_DO_SDL_2
        assert ditos[0]["autoridade"] == "game"
        assert not _eventos(registros, "game_output_recusado_o_hefesto_numera")
