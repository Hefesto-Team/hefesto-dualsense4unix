"""MIC-DA-MESA-ELEICAO-01 — o LED do microfone, POR CONTROLE.

Decisão dela, 01/09/2026: *"As pessoas precisam ter um aviso visual que o mic tá
funcionando. (…) com 4 pessoas com controle na mão localmente isso é
necessário."* Nesta casa, **aceso = este microfone está VIVO** — a inversão da
convenção da Sony, e ela é do CHAMADOR: o byte `common[8]` não mudou de
contrato.

Quatro réguas, e as quatro medem o BYTE ou o ESTADO, nunca a chamada. Medir a
chamada é medir a palavra em vez do ato, que é a família das onze réguas falsas
desta casa.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    _PinnedPyDualSense,
    PyDualSenseController,
)

_A = "aabbcc000001"
_B = "aabbcc000002"
_C = "aabbcc000003"
_D = "aabbcc000004"


class _LockFalso:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


def _handle() -> Any:
    """Handle da pydualsense sem device — só o estado que o builder lê."""
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor = 0
    h.rightMotor = 0
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._preamp_audio = None
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    return h


@pytest.fixture()
def mesa_de_quatro() -> Any:
    """Backend com quatro handles endereçáveis e overrides por-uniq vivos."""
    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput

    ctrl = PyDualSenseController.__new__(PyDualSenseController)
    ctrl._handles = {mac: _handle() for mac in (_A, _B, _C, _D)}
    ctrl._io_lock = _LockFalso()
    ctrl._primary_key = _A
    ctrl._output_target_key = None
    ctrl._desired_default = _DesiredOutput()
    ctrl._desired_by_uniq = {mac: _DesiredOutput(mic_led=False) for mac in (_A, _B, _C, _D)}
    ctrl._desired_owner_by_uniq = {}
    return ctrl


# ---------------------------------------------------------------------------
# 3. O LED escreve SÓ em quem apertou
# ---------------------------------------------------------------------------


def test_o_led_com_uniq_escreve_so_no_handle_daquele_controle(mesa_de_quatro: Any) -> None:
    """`set_mic_led(True, uniq=B)`: o byte sai no B e em mais ninguém.

    CURA A ARRANCAR: tirar o `uniq` e deixar cair no `_for_each` sem alvo — os
    quatro acendem, e a régua reprova na primeira metade.
    """
    mesa_de_quatro.set_mic_led(True, uniq=_B)

    for mac, handle in mesa_de_quatro._handles.items():
        comum = handle._build_common(rumble_asserted=False)
        se_esperava = mac == _B
        assert bool(
            comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        ) is se_esperava, f"o controle {mac} não devia ter mudado"
        assert comum[8] == (1 if se_esperava else 0)


def test_o_led_com_uniq_nao_apaga_o_estado_dos_outros_tres(mesa_de_quatro: Any) -> None:
    """A segunda metade, e ela é a que mais dói.

    Com `target_key=None` o `_record_desired_locked` grava no `_desired_default`
    **e ZERA o campo `mic_led` de todos os overrides por-uniq**. Numa mesa de
    quatro, a borda do Jogador 2 apagaria o estado por-controle dos outros três
    — o pedido dela (*"cada uma vê no PRÓPRIO controle"*) morre aí.

    CURA A ARRANCAR: a mesma de cima. Com o `_for_each` sem alvo, os overrides
    de A, C e D voltam a `None` e esta régua reprova.
    """
    mesa_de_quatro.set_mic_led(True, uniq=_B)

    assert mesa_de_quatro._desired_by_uniq[_B].mic_led is True
    for mac in (_A, _C, _D):
        override = mesa_de_quatro._desired_by_uniq.get(mac)
        assert override is not None, f"o override de {mac} sumiu inteiro"
        assert (
            override.mic_led is False
        ), f"o override de {mac} foi zerado por uma escrita que não era dele"


def test_o_led_sem_uniq_continua_valendo_para_o_alvo(mesa_de_quatro: Any) -> None:
    """A metade que prova que a cura não é "parar de funcionar".

    Sem `uniq` o caminho antigo continua inteiro — é o do perfil e o do DSX.
    """
    mesa_de_quatro.set_mic_led(True)
    for handle in mesa_de_quatro._handles.values():
        comum = handle._build_common(rumble_asserted=False)
        assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        assert comum[8] == 1


# ---------------------------------------------------------------------------
# 4. A posse do PERFIL chega ao BYTE
# ---------------------------------------------------------------------------


def test_apply_output_defaults_com_mic_led_acende_o_byte(mesa_de_quatro: Any) -> None:
    """O LED do perfil em broadcast tem de acender `common[8]`, não só o espelho.

    O DEFEITO MEDIDO: `apply_output_defaults` chamava
    `h.audio.setMicrophoneLED(flag)` CRU, que só mexe no espelho da
    pydualsense. `_mic_led_desejado` continuava `None`, e com `None` o
    `_build_common` APAGA o bit `0x01` e deixa `common[8]` inerte — o LED do
    perfil não acendia um único byte, enquanto o MESMO campo pelo
    `apply_output_for` acendia. Dois caminhos do mesmo campo, um deles mudo.

    CURA A ARRANCAR: voltar ao `h.audio.setMicrophoneLED(flag)` — o bit sai
    apagado, o byte viaja inerte, e a régua reprova.
    """
    from hefesto_dualsense4unix.core.controller import OutputSpec

    mesa_de_quatro._reassert_task = None
    mesa_de_quatro.apply_output_defaults(OutputSpec(mic_led=True))

    for handle in mesa_de_quatro._handles.values():
        comum = handle._build_common(rumble_asserted=False)
        assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE, (
            "o bit de autorização tem de sair LIGADO"
        )
        assert comum[8] == 1, "e o byte tem de sair com o valor"


# ---------------------------------------------------------------------------
# 5. A devolução DEVOLVE
# ---------------------------------------------------------------------------


def test_devolver_a_posse_limpa_o_bit_e_o_byte(mesa_de_quatro: Any) -> None:
    """`set_microphone_led(None)` devolve `common[8]` ao kernel.

    Só o `0x01` do flag1 cai — nem lightbar nem player-LED são tocados, nos
    dois transportes. Isto NÃO é o `RELEASE_LEDS` (0x31), que só existe no
    rádio e apaga os player-LEDs sempre.

    CURA A ARRANCAR: fazer o caminho tratar `None` como `False` — o bit de
    autorização continua ligado e a régua reprova. Confundir `false` com `null`
    foi o defeito do `3d9bb7e`, no byte vizinho.
    """
    mesa_de_quatro.set_microphone_led(True, uniq=_A)
    comum = mesa_de_quatro._handles[_A]._build_common(rumble_asserted=False)
    assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE

    mesa_de_quatro.set_microphone_led(None, uniq=_A)
    comum = mesa_de_quatro._handles[_A]._build_common(rumble_asserted=False)
    assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0
    assert comum[8] == 0

    outras = mesa_de_quatro._handles[_A]._build_common(rumble_asserted=False)
    assert outras[1] & rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE, (
        "a lightbar continua nossa — a devolução é do byte do LED do mic, só"
    )


# ---------------------------------------------------------------------------
# 6. A inversão SOBREVIVE ao toque
# ---------------------------------------------------------------------------


def test_a_borda_muda_o_report_montado(mesa_de_quatro: Any) -> None:
    """Reafirmar o mesmo valor NÃO chega ao aparelho — o report tem de MUDAR.

    `sendReport` só escreve quando `out != self._last_out_report`, mais um
    keepalive limitado à janela de confirmação de 2,0 s (RUMBLE-SEM-DONO-01).
    O kernel, ao contrário, escreve `mute_button_led = ds->mic_muted` a CADA
    borda. Quem escreveu por último a cada toque, então, é o kernel — a não ser
    que o nosso valor desejado MUDE.

    Sem isso a inversão dura exatamente um toque e depois a luz volta à
    convenção da Sony, com a tela dizendo "no ar" e o plástico dizendo o
    contrário.

    CURA A ARRANCAR: reafirmar o mesmo valor em vez de mudá-lo — os dois
    reports ficam idênticos, nada é escrito, e esta régua reprova.
    """
    handle = mesa_de_quatro._handles[_A]

    mesa_de_quatro.set_mic_led(True, uniq=_A)
    primeiro = bytes(handle._build_common(rumble_asserted=False))

    # A borda seguinte: o controle passou a MUDO, logo o aviso de vida APAGA.
    mesa_de_quatro.set_mic_led(False, uniq=_A)
    segundo = bytes(handle._build_common(rumble_asserted=False))

    assert segundo != primeiro, (
        "report idêntico não é escrito — o LED ficaria com o que o kernel pôs"
    )
    assert primeiro[8] == 1
    assert segundo[8] == 0
