"""O jogo manda; na ausência dele, o perfil ganha — a decisão dela de 03/10/2026.

*«o certo seria os controles obedecerem quando o jogo manda e na
ausencia disso o perfil ganha.»* <!-- noqa-acento: citação literal dela -->
(ela, 03/10/2026 ~18h15, na bancada do Forja; revoga a PERFIL-MANDA-01 de
16/09, «meu perfil manda»).

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


SEM_EFEITO = bytes(11)
SEM_EFEITO_OFICIAL = bytes([0x05] + [0] * 10)
EFEITO_DO_PERFIL = bp.TriggerEffect(mode=1, forces=(5, 200, 0, 0, 0, 0, 0))


class TestPerfilAteOJogoProvar:
    """Decisão dela de 04/10/2026 ~00h55: o «sem efeito» é ausência até o jogo provar."""

    @pytest.mark.parametrize("sem_efeito", [SEM_EFEITO, SEM_EFEITO_OFICIAL])
    def test_um_jogo_que_so_escreve_sem_efeito_deixa_o_perfil_valendo(
        self, sem_efeito: bytes
    ) -> None:
        """MORDIDA: tratar todo bloco como ordem e o Rígido do perfil some."""
        ctl, _no, handle = _controle(campos_dela={"trigger_right": EFEITO_DO_PERFIL})

        ctl.set_game_trigger_for(MAC_1, "right", sem_efeito)
        ctl.set_game_trigger_for(MAC_1, "left", sem_efeito)

        assert handle._raw_trigger_right is None
        assert handle._raw_trigger_left is None
        assert UNIQ_1 not in ctl._game_triggers_by_uniq
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).trigger_right == EFEITO_DO_PERFIL

    def test_o_primeiro_efeito_real_passa_a_mandar(self) -> None:
        """MORDIDA: não marcar o «já provou» e o «sem efeito» seguinte é descartado."""
        ctl, _no, handle = _controle(campos_dela={"trigger_right": EFEITO_DO_PERFIL})
        ctl.set_game_trigger_for(MAC_1, "right", SEM_EFEITO)

        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        assert handle._raw_trigger_right == BLOCO_DO_JOGO

    def test_o_sem_efeito_depois_de_provar_vale(self) -> None:
        """O menu do jogo que desliga o gatilho depois de ter mandado um efeito."""
        ctl, _no, handle = _controle(campos_dela={"trigger_right": EFEITO_DO_PERFIL})
        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        ctl.set_game_trigger_for(MAC_1, "right", SEM_EFEITO)

        assert handle._raw_trigger_right == SEM_EFEITO
        assert ctl._game_triggers_by_uniq[UNIQ_1] == {"right": SEM_EFEITO}

    def test_o_que_o_jogo_provou_vale_nos_dois_lados_do_mesmo_controle(self) -> None:
        ctl, _no, handle = _controle()
        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        ctl.set_game_trigger_for(MAC_1, "left", SEM_EFEITO)

        assert handle._raw_trigger_left == SEM_EFEITO

    def test_a_saida_do_jogo_devolve_o_perfil_e_zera_o_ja_provou(self) -> None:
        """MORDIDA: a saída sem zerar e o «sem efeito» da partida seguinte vira ordem."""
        ctl, _no, handle = _controle(campos_dela={"trigger_right": EFEITO_DO_PERFIL})
        ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)

        ctl.end_game_session_for(MAC_1)
        assert handle._raw_trigger_right is None
        assert UNIQ_1 not in ctl._jogo_provou_o_gatilho

        ctl.set_game_trigger_for(MAC_1, "right", SEM_EFEITO)
        assert handle._raw_trigger_right is None
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).trigger_right == EFEITO_DO_PERFIL

    def test_o_preto_de_quem_nunca_pintou_e_ausencia(self) -> None:
        """MORDIDA: o preto tratado como ordem e a cor do perfil apaga."""
        ctl, no, _ = _controle(campos_dela={"led": COR_DELA})

        ctl.set_game_output_for(MAC_1, led=(0, 0, 0))

        assert (0, 0, 0) not in no.rgb_calls
        assert UNIQ_1 not in ctl._game_output_by_uniq
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DELA

    def test_o_preto_depois_de_pintar_vale(self) -> None:
        ctl, no, _ = _controle(campos_dela={"led": COR_DELA})
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)

        ctl.set_game_output_for(MAC_1, led=(0, 0, 0))

        assert no.rgb_calls[-1] == (0, 0, 0)
        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == (0, 0, 0)

    def test_a_saida_do_jogo_zera_o_ja_pintou(self) -> None:
        ctl, _no, _ = _controle(campos_dela={"led": COR_DELA})
        ctl.set_game_output_for(MAC_1, led=COR_DO_JOGO)
        ctl.end_game_session_for(MAC_1)

        ctl.set_game_output_for(MAC_1, led=(0, 0, 0))

        with ctl._io_lock:
            assert ctl._merged_desired_for_key(MAC_1).led == COR_DELA

    def test_o_preto_junto_do_numero_nao_perde_o_numero_recusado(self) -> None:
        """O número do jogador segue do Hefesto, e o preto sozinho não pinta."""
        ctl, no, _ = _controle(campos_dela={"led": COR_DELA})

        ctl.set_game_output_for(MAC_1, led=(0, 0, 0), player_leds=PADRAO_DO_JOGO)

        assert not no.rgb_calls
        assert PADRAO_DO_JOGO not in no.player_calls

    @pytest.mark.parametrize("n", [1, 2, 3, 4])
    def test_cada_controle_prova_por_conta_propria(self, n: int) -> None:
        """P1 a P4: o que o jogo provou no P1 não vale no P2, nem a luz nem o gatilho."""
        macs = {i: f"AA:BB:CC:00:00:0{i}" for i in (1, 2, 3, 4)}
        ctl = bp.PyDualSenseController()
        handles = {mac: _handle() for mac in macs.values()}
        ctl._handles = dict(handles)
        ctl._sysfs = {mac: _NoDeLed() for mac in macs.values()}
        ctl.set_game_authority_provider(lambda: "game")
        provado = macs[n]
        ctl.set_game_trigger_for(provado, "right", BLOCO_DO_JOGO)
        ctl.set_game_output_for(provado, led=COR_DO_JOGO)

        for i, mac in macs.items():
            ctl.set_game_trigger_for(mac, "right", SEM_EFEITO)
            ctl.set_game_output_for(mac, led=(0, 0, 0))
            if i == n:
                assert handles[mac]._raw_trigger_right == SEM_EFEITO
                assert ctl._game_output_by_uniq[mac.replace(":", "").lower()].led == (0, 0, 0)
            else:
                assert handles[mac]._raw_trigger_right is None
                assert mac.replace(":", "").lower() not in ctl._game_output_by_uniq

    def test_o_gesto_dela_solta_e_o_jogo_provado_segue_provado(self) -> None:
        """O gesto tira o bloco do jogo, e o «sem efeito» que vem depois ainda é do jogo."""
        ctl, _no, handle = _controle()
        ctl.set_game_trigger_for(MAC_1, "left", BLOCO_DO_JOGO)
        with ctl._io_lock:
            ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(trigger_left=EFEITO_DO_PERFIL)
            ctl._stamp_owner_locked(UNIQ_1, ("trigger_left",), bp._LAYER_USER)
        assert handle._raw_trigger_left is None

        ctl.set_game_trigger_for(MAC_1, "left", SEM_EFEITO)

        assert handle._raw_trigger_left == SEM_EFEITO


def _handle_que_monta_o_report(transporte: str) -> Any:
    """Um handle de verdade (`_PinnedPyDualSense`), sem hidraw, que monta o report do fio."""
    from pydualsense.enums import ConnectionType

    handle = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    handle.conType = ConnectionType.BT if transporte == "radio" else ConnectionType.USB
    handle.leftMotor = 0
    handle.rightMotor = 0
    handle._rumble_active = False
    handle._rumble_stop_pending = False
    handle._suppress_leds = False
    handle._volumes_audio = None
    handle._mic_mute_desejado = None
    handle._preamp_audio = None
    handle._raw_trigger_right = None
    handle._raw_trigger_left = None
    handle.light = DSLight()
    handle.audio = DSAudio()
    handle.triggerR = DSTrigger()
    handle.triggerL = DSTrigger()
    return handle


def _gatilho_direito_no_fio(handle: Any, transporte: str) -> bytes:
    """Os 11 bytes do gatilho direito no report que vai ao controle (0x02 ou 0x31)."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    report = handle.prepareReport()
    common = handle._build_common(rumble_asserted=False)
    if transporte == "radio":
        assert report == list(rep.build_bt_report(common, seq=0)), "caiu no upstream"
        inicio = 3
    else:
        assert report == list(rep.build_usb_report(common)), "caiu no upstream"
        inicio = 1
    return bytes(report[inicio + 10 : inicio + 10 + bp.GAME_TRIGGER_BLOCK_LEN])


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_no_fio_o_perfil_vale_ate_o_jogo_provar(transporte: str) -> None:
    """Cabo e rádio: o report que sai leva o Rígido do perfil até o jogo provar.

    MORDIDA: tratar o «sem efeito» como ordem e o report sai com o gatilho zerado
    nos dois transportes, com o perfil de pé.
    """
    handle = _handle_que_monta_o_report(transporte)
    ctl = bp.PyDualSenseController()
    ctl._handles = {MAC_1: handle}
    ctl._sysfs = {MAC_1: _NoDeLed()}
    ctl.set_game_authority_provider(lambda: "game")
    ctl._desired_by_uniq[UNIQ_1] = bp._DesiredOutput(trigger_right=EFEITO_DO_PERFIL)
    ctl._desired_owner_by_uniq[UNIQ_1] = {"trigger_right": bp._LAYER_PROFILE}
    bp.PyDualSenseController._apply_trigger(handle, "right", EFEITO_DO_PERFIL)
    do_perfil = _gatilho_direito_no_fio(handle, transporte)
    assert do_perfil[:3] == bytes([0x01, 5, 200]), do_perfil

    ctl.set_game_trigger_for(MAC_1, "right", SEM_EFEITO)
    assert _gatilho_direito_no_fio(handle, transporte) == do_perfil

    ctl.set_game_trigger_for(MAC_1, "right", BLOCO_DO_JOGO)
    assert _gatilho_direito_no_fio(handle, transporte) == BLOCO_DO_JOGO

    ctl.set_game_trigger_for(MAC_1, "right", SEM_EFEITO)
    assert _gatilho_direito_no_fio(handle, transporte) == SEM_EFEITO

    ctl.end_game_session_for(MAC_1)
    assert _gatilho_direito_no_fio(handle, transporte) == do_perfil


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
