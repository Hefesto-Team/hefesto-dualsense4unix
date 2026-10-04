"""O jogo manda; na ausência dele, o perfil ganha — a decisão dela de 03/10/2026.

*«o certo seria os controles obedecerem quando o jogo manda e na ausencia disso
o perfil ganha.»* (ela, 03/10/2026 ~18h15, na bancada do Forja; revoga a
PERFIL-MANDA-01 de 16/09, «meu perfil manda»). <!-- noqa-acento: citação literal dela -->

A causa, medida no `807c8a6d7` (`agentes/mic-15/medida-o-jogo-manda.txt`): com a
cor e o gatilho no perfil do controle, o jogo pintou e a lightbar que valia era a
do perfil, `(255, 255, 0)`, e o bloco cru do gatilho do jogo nunca chegou ao
handle. A regra era o `_campos_do_perfil_locked` (`core/backend_pydualsense.py`),
consultado no merge, no `set_game_output_for` e no `set_game_trigger_for`, e o
carimbo do perfil que soltava o gatilho do jogo.

O número do jogador segue do Hefesto, e o gesto dela na interface (a ordem mais
nova) vale até o jogo pintar de novo. Vale para os quatro controles, os modos
DualSense e Xbox, cabo e rádio: a regra é do backend, por `uniq`, antes do
transporte.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import structlog
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp

MAC_1 = "AA:BB:CC:00:00:01"
UNIQ_1 = "aabbcc000001"

COR_DELA = (255, 255, 0)
PADRAO_DELA = (True, False, False, False, False)

COR_DO_JOGO = (200, 60, 0)
PADRAO_DO_JOGO = (True, False, True, False, True)

BLOCO_DO_JOGO = bytes([0x26, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


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


def _controle(
    *,
    campos_dela: dict[str, Any] | None = None,
    autoridade: str = "game",
) -> tuple[bp.PyDualSenseController, _NoDeLed, SimpleNamespace]:
    """Controle com o jogo no comando e os campos DELA já carimbados."""
    ctl = bp.PyDualSenseController()
    handle = _handle()
    no = _NoDeLed()
    ctl._handles = {MAC_1: handle}
    ctl._sysfs = {MAC_1: no}
    ctl.set_game_authority_provider(lambda: autoridade)
    if campos_dela:
        ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(**campos_dela)
        ctl._desired_owner_by_uniq[UNIQ_1] = dict.fromkeys(
            campos_dela, bp._LAYER_PROFILE
        )
    return ctl, no, handle


def _eventos(registros: list[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [r for r in registros if r["event"] == nome]


class TestOJogoManda:
    def test_a_cor_do_jogo_vence_a_do_perfil(self) -> None:
        """MORDIDA: devolver a peneira do perfil no merge e a cor do perfil volta."""
        ctl, no, _ = _controle(campos_dela={"led": COR_DELA})

        assert ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO) is True

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DO_JOGO
        assert no.rgb_calls[-1] == COR_DO_JOGO
        assert ctl._game_output_by_uniq[UNIQ_1].led == COR_DO_JOGO

    def test_o_gatilho_do_jogo_vence_o_do_perfil(self) -> None:
        """MORDIDA: devolver a recusa do `set_game_trigger_for` e o bloco não chega."""
        efeito = bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))
        ctl, _no, handle = _controle(campos_dela={"trigger_right": efeito})

        assert ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO) is True

        assert handle._raw_trigger_right == BLOCO_DO_JOGO
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": BLOCO_DO_JOGO}

    def test_o_perfil_aplicado_depois_nao_solta_o_gatilho_do_jogo(self) -> None:
        """A troca de janela reaplica o perfil: o carimbo dele não tira o que o jogo pintou."""
        ctl, _no, handle = _controle()
        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(
                trigger_right=bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))
            )
            ctl._stamp_owner_locked(UNIQ_1, ("trigger_right",), bp._LAYER_PROFILE)

        assert handle._raw_trigger_right == BLOCO_DO_JOGO

    def test_o_numero_do_jogador_segue_do_hefesto(self) -> None:
        ctl, no, _ = _controle(campos_dela={"player_leds": PADRAO_DELA})

        ctl.set_game_output_for(MAC_1, player_leds=PADRAO_DO_JOGO)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).player_leds == PADRAO_DELA
        assert PADRAO_DO_JOGO not in no.player_calls

    def test_ninguem_recusa_mais_pelo_perfil(self) -> None:
        efeito = bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA, "trigger_left": efeito})

        with structlog.testing.capture_logs() as registros:
            ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
            ctl.set_game_trigger_for(MAC_1, "left", BLOCO_DO_JOGO)

        nomes = {r["event"] for r in registros}
        assert "game_output_recusado_o_perfil_manda" not in nomes
        assert "game_trigger_recusado_o_perfil_manda" not in nomes
        assert not hasattr(ctl, "_campos_do_perfil_locked")


class TestNaAusenciaOPerfilGanha:
    def test_sem_o_jogo_pintar_vale_o_perfil(self) -> None:
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DELA

    def test_o_jogo_que_sai_devolve_a_cor_do_perfil(self) -> None:
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        ctl.end_game_session_for(MAC_1)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DELA

    def test_sem_autoridade_do_jogo_o_pedido_fica_retido(self) -> None:
        """Com o daemon no comando (sem jogo), o perfil vale e o pedido espera."""
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA}, autoridade="daemon")

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DELA
        assert ctl._retained_game_outputs[UNIQ_1]["led"] == COR_DO_JOGO


class TestOQueNaoTemDonoContinuaSendoDoJogo:
    def test_sem_dono_o_jogo_continua_vencendo(self) -> None:
        """REPLICA-03 intacta: quem não configurou nada não perde a luz."""
        ctl, no, _ = _controle()
        ctl._desired_default.led = (9, 9, 9)

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DO_JOGO
        assert no.rgb_calls == [COR_DO_JOGO]


class TestOGestoDelaNoMeioDoJogo:
    """O gesto dela na interface é a ordem mais nova: vale até o jogo pintar de novo."""

    def test_a_cor_que_ela_escolhe_agora_vence_e_o_jogo_que_repinta_volta(self) -> None:
        """MORDIDA: o gesto sem soltar a camada do jogo e a cor dela não aparece."""
        ctl, _no, _ = _controle()
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(led=COR_DELA)
            ctl._stamp_owner_locked(UNIQ_1, ("led",), bp._LAYER_USER)
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DELA

        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DO_JOGO

    def test_o_gatilho_dela_solta_o_bloco_cru_do_jogo_e_so_aquele_lado(self) -> None:
        ctl, _no, handle = _controle()
        ctl.set_game_trigger_for(MAC_1, "left", BLOCO_DO_JOGO)
        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(
                trigger_left=bp.TriggerEffect(mode=1, forces=(6, 0, 0, 0, 0, 0, 0))
            )
            ctl._stamp_owner_locked(UNIQ_1, ("trigger_left",), bp._LAYER_USER)

        assert handle._raw_trigger_left is None
        assert handle._raw_trigger_right == BLOCO_DO_JOGO
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": BLOCO_DO_JOGO}
        ctl.set_game_trigger_for(MAC_1, "left", BLOCO_DO_JOGO)
        assert handle._raw_trigger_left == BLOCO_DO_JOGO, "o jogo que repinta não voltou"


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_cada_um_dos_quatro_obedece_ao_jogo(n: int) -> None:
    """P1 a P4: a regra é por `uniq`, e o jogo pinta cada um com o seu perfil de pé."""
    mac = f"AA:BB:CC:00:00:0{n}"
    uniq = f"aabbcc00000{n}"
    ctl = bp.PyDualSenseController()
    ctl._handles = {mac: _handle()}
    ctl._sysfs = {mac: _NoDeLed()}
    ctl.set_game_authority_provider(lambda: "game")
    ctl._desired_by_uniq[uniq] = bp._DesiredOutput(led=COR_DELA)
    ctl._desired_owner_by_uniq[uniq] = {"led": bp._LAYER_PROFILE}

    ctl.set_game_output_for(mac, led=COR_DO_JOGO)

    with ctl._io_lock:
        assert ctl._merged_desired_for_key(mac).led == COR_DO_JOGO
