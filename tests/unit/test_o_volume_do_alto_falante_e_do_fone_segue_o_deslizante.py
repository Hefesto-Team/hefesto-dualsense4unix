"""A interface é a lei: o deslizante do alto-falante e do fone vale no FIRMWARE, por controle.

A cura `d61af1907` pôs a placa do cabo em 100 % (`alto_falante_bt.garantir_a_placa_cheia`), e ela
escalava o alto-falante e o fone: com os 40 % do WirePlumber (fator 0,064, -23,9 dB) fora do
caminho, a mesma posição do deslizante soava ~24 dB mais alta. E no Modo Nativo o laço não escreve
(FEAT-NATIVE-OUTPUT-MUTE-01), então o deslizante só valia na memória.

A régua: para os controles 1 a 4, no cabo e no rádio, com o Nativo ligado e desligado, o byte que
sai em `common[4]` (fone) e `common[5]` (alto-falante) é o do deslizante pela conta única
(`speaker_scale.registrador_no_firmware`), só no controle escolhido, e a placa não é o destino.

MORDIDAS: trocar `placa_cheia=cabo` por `placa_cheia=False` em `_escrever_volume_no_handle` reprova
o cabo; arrancar o bloco do Modo Nativo dele reprova o Nativo; mandar o deslizante ao `pactl`
reprova `test_a_placa_nunca_e_o_destino_do_deslizante`.
"""

from __future__ import annotations

import math
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _PinnedPyDualSense,
)
from hefesto_dualsense4unix.core.speaker_scale import (
    FATOR_DA_PLACA_DE_ANTES,
    _db_do_registrador,
    registrador_no_firmware,
    volume_do_percentual,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt

CHAVES = [f"AA:BB:CC:00:00:0{n}" for n in range(1, 5)]
UNIQS = [f"aabbcc00000{n}" for n in range(1, 5)]


class _Fio:
    """O hidraw de mentira: guarda cada quadro escrito."""

    def __init__(self) -> None:
        self.quadros: list[bytes] = []

    def write(self, quadro: bytes) -> int:
        self.quadros.append(bytes(quadro))
        return len(quadro)


def _handle(transporte: str) -> Any:
    """`_PinnedPyDualSense` sem aparelho, com o `writeReport` real sobre um fio de mentira."""
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
    h._speaker_volume_pref = None
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    h._output_muted = False
    h.connected = True
    h.conType = SimpleNamespace(name="USB" if transporte == "cabo" else "BT")
    h._write_lock = threading.Lock()
    h._entrega = threading.Lock()
    h._fechando = False
    h._fechado = False
    h._entregue = False
    h._dentro_do_c = 0
    h._bt_seq = 0
    h.device = _Fio()
    return h


def _mesa(transporte: str, *, nativo: bool) -> tuple[PyDualSenseController, list[Any]]:
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    inst = PyDualSenseController(evdev_reader=reader)
    handles = [_handle(transporte) for _ in CHAVES]
    inst._handles = dict(zip(CHAVES, handles, strict=True))  # type: ignore[arg-type]
    inst._primary_key = CHAVES[0]
    if nativo:
        inst._output_mute = True
        for h in handles:
            h._output_muted = True
    return inst, handles


def _common_do_quadro(quadro: bytes, transporte: str) -> bytes:
    if transporte == "cabo":
        assert quadro[0] == 0x02 and len(quadro) == rep.USB_REPORT_LEN
        return quadro[1 : 1 + rep.COMMON_LEN]
    assert quadro[0] == 0x31 and len(quadro) == rep.BT_REPORT_LEN
    return quadro[3 : 3 + rep.COMMON_LEN]


@pytest.mark.parametrize("nativo", [False, True], ids=["dualsense", "nativo"])
@pytest.mark.parametrize("transporte", ["cabo", "radio"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
@pytest.mark.parametrize("percentual", [10, 60, 100])
def test_o_byte_do_firmware_e_o_do_deslizante(
    percentual: int, jogador: int, transporte: str, nativo: bool
) -> None:
    inst, handles = _mesa(transporte, nativo=nativo)
    deslizante = volume_do_percentual(percentual)
    esperado = registrador_no_firmware(deslizante, placa_cheia=transporte == "cabo")

    assert inst.set_speaker_volume(deslizante, uniq=UNIQS[jogador - 1]) is True

    alvo = handles[jogador - 1]
    if nativo:
        assert len(alvo.device.quadros) == 1, "no Nativo o som sai sozinho, num quadro"
        common = _common_do_quadro(alvo.device.quadros[0], transporte)
        assert common[0] & ~rep.VALID_FLAG0_AUDIO_PATH == (
            rep.VALID_FLAG0_HEADPHONE_VOLUME | rep.VALID_FLAG0_SPEAKER_VOLUME
        ), "só os bytes do som ganham autorização: vibração e gatilho são do jogo"
        assert common[1] == rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
        assert common[2] == common[3] == 0
    else:
        assert alvo.device.quadros == [], "fora do Nativo quem escreve é o laço"
        common = alvo._build_common(rumble_asserted=False)
    assert common[rep.COMMON_HEADPHONE_VOLUME] == esperado, "o fone"
    assert common[rep.COMMON_SPEAKER_VOLUME] == esperado, "o alto-falante"
    assert alvo._speaker_volume_pref == deslizante, "a tela guarda o deslizante, não o byte"
    for outro in handles:
        if outro is not alvo:
            assert outro._volumes_audio == [None, None, None, None]
            assert outro.device.quadros == []


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_o_mudo_no_nativo_sai_como_zero(transporte: str) -> None:
    inst, handles = _mesa(transporte, nativo=True)
    inst.set_speaker_volume(volume_do_percentual(80), uniq=UNIQS[1])
    assert inst.set_speaker_volume(muted=True, uniq=UNIQS[1]) is True
    common = _common_do_quadro(handles[1].device.quadros[-1], transporte)
    assert common[rep.COMMON_SPEAKER_VOLUME] == common[rep.COMMON_HEADPHONE_VOLUME] == 0


@pytest.mark.parametrize("percentual", range(1, 101))
def test_a_mesma_posicao_soa_como_soava_com_a_placa_nos_40(percentual: int) -> None:
    """No papel, pela curva de 01/08: até 1 dB do nível de antes (A CONFIRMAR NO APARELHO)."""
    deslizante = volume_do_percentual(percentual)
    antes = _db_do_registrador(deslizante) + 20 * math.log10(FATOR_DA_PLACA_DE_ANTES)
    agora = _db_do_registrador(registrador_no_firmware(deslizante, placa_cheia=True))
    if registrador_no_firmware(deslizante, placa_cheia=True) > 1:
        assert abs(agora - antes) <= 1.0, (percentual, deslizante)


def test_a_conta_e_monotona_e_zero_e_mudo() -> None:
    bytes_do_cabo = [
        registrador_no_firmware(volume_do_percentual(p), placa_cheia=True) for p in range(101)
    ]
    assert bytes_do_cabo[0] == 0
    assert all(b >= 1 for b in bytes_do_cabo[1:]), "acima de zero nunca é mudo"
    assert bytes_do_cabo == sorted(bytes_do_cabo)
    for p in range(101):
        v = volume_do_percentual(p)
        assert registrador_no_firmware(v, placa_cheia=False) == v, "o rádio nunca passou pela placa"


def test_a_placa_nunca_e_o_destino_do_deslizante(monkeypatch: pytest.MonkeyPatch) -> None:
    """O deslizante vai ao firmware; o `pactl` não é chamado por ele, em modo nenhum."""
    chamadas: list[tuple[Any, ...]] = []

    def _anota(*args: Any, **kwargs: Any) -> Any:
        chamadas.append(args)
        raise AssertionError(f"o deslizante foi à placa: {args}")

    monkeypatch.setattr(alto_falante_bt, "rodar_pactl", _anota)
    monkeypatch.setattr(alto_falante_bt, "_rodar", _anota)
    monkeypatch.setattr(alto_falante_bt.subprocess, "run", _anota)
    for transporte in ("cabo", "radio"):
        for nativo in (False, True):
            inst, _handles = _mesa(transporte, nativo=nativo)
            for uniq in UNIQS:
                assert inst.set_speaker_volume(volume_do_percentual(45), uniq=uniq) is True
    assert chamadas == []

