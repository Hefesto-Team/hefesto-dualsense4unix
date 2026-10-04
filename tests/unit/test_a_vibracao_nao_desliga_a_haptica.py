"""A-VIBRACAO-NAO-DESLIGA-A-HAPTICA-01, o passo 1: o bit do rumble.

Medido com ela em 03/10 (quatro controles num adaptador, e de novo dois por
adaptador, com `cedidos=0`): a vibração pelo nó do jogo e a háptica de teste ao
mesmo tempo ALTERNAVAM no mesmo controle. O report do rumble saía com
`HAPTICS_SELECT` (`flag0` bit 1), que no `hid-playstation`, no SDL e no
pydualsense troca os atuadores para a vibração emulada e cala a háptica por
áudio até o bit cair.

A cura do passo 1: com a háptica por áudio tocando no controle, o rumble vai
com `COMPATIBLE_VIBRATION` (bit 0) e sem `HAPTICS_SELECT`; sem háptica, como
sempre. Quem diz que a háptica toca é o dono das pontes, o
`AltoFalanteSubsystem`, pelo `set_haptica_de_audio_for` do controlador.

A BANCADA: o handle é o `_PinnedPyDualSense` real, sem device (o mesmo molde
das réguas da AUDIO-OWNER-01), e o report de rádio sai do montador real
(`build_bt_report`). O controlador é o real, com quatro handles nas chaves de
MAC da faixa forjada. O subsystem é o real, com o servidor de som dublado na
borda (`sinks_que_tocam`). A MORDIDA de cada régua está no docstring dela.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _PinnedPyDualSense,
)
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt

BIT0 = rep.VALID_FLAG0_COMPATIBLE_VIBRATION
BIT1 = rep.VALID_FLAG0_HAPTICS_SELECT
CHAVES = tuple(f"AA:BB:CC:00:00:0{n}" for n in range(1, 5))
UNIQS = tuple(c.replace(":", "").lower() for c in CHAVES)


def _handle(*, haptica: bool = False, motores: tuple[int, int] = (0, 0)) -> Any:
    """O handle real sem device, só com o estado que o montador lê."""
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor, h.rightMotor = motores
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._mic_mute_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    if haptica:
        h.set_haptica_de_audio(True)
    return h


def _flag0_no_radio(h: Any, *, rumble: bool) -> int:
    """O `flag0` como ele sai no `0x31` do rádio (o common começa no byte 3)."""
    report = rep.build_bt_report(h._build_common(rumble_asserted=rumble), seq=0)
    assert report[0] == rep.BT_REPORT_ID and report[2] == rep.BT_TAG
    return int(report[3])


def test_com_a_haptica_tocando_o_rumble_vai_sem_haptics_select() -> None:
    """Régua 1: háptica ativa e rumble pedido → bit 0 ligado, bit 1 desligado.

    No `0x31` do rádio e no `0x02` do cabo, que leva o mesmo `common`.

    MORDIDA: tire o ramo `elif self._haptica_de_audio` de `_build_common` e o
    `flag0` leva o bit 1, que cala a háptica.
    """
    h = _handle(haptica=True, motores=(255, 255))

    flag0 = _flag0_no_radio(h, rumble=True)
    assert flag0 & BIT0, "o rumble perdeu o COMPATIBLE_VIBRATION: os motores não tocariam"
    assert not flag0 & BIT1, "o rumble com a háptica tocando levou o HAPTICS_SELECT"
    usb = rep.build_usb_report(h._build_common(rumble_asserted=True))
    assert usb[0] == rep.USB_REPORT_ID
    assert usb[1] & BIT0 and not usb[1] & BIT1
    common = h._build_common(rumble_asserted=True)
    assert common[1] & rep.VALID_FLAG1_MOTOR_POWER, "a potência do motor caiu junto"
    assert (common[2], common[3]) == (255, 255)


def test_sem_haptica_o_rumble_segue_como_hoje() -> None:
    """Régua 2: sem háptica, o rumble leva os bits 0 e 1, como o jogo só de motor espera.

    E sem rumble, nenhum dos dois, com ou sem háptica (o keepalive neutro).

    MORDIDA: tirar o bit 1 sempre (sem olhar a háptica) muda o jogo que só usa
    motor, e esta régua reprova.
    """
    sem = _handle(motores=(200, 100))
    flag0 = _flag0_no_radio(sem, rumble=True)
    assert flag0 & BIT0 and flag0 & BIT1, f"o rumble sem háptica mudou: flag0={flag0:#04x}"
    for h in (_handle(), _handle(haptica=True)):
        neutro = _flag0_no_radio(h, rumble=False)
        assert not neutro & (BIT0 | BIT1), f"o keepalive pediu vibração: {neutro:#04x}"


def test_a_haptica_que_para_devolve_o_bit() -> None:
    """A háptica parou: o rumble seguinte volta a levar o bit 1."""
    h = _handle(haptica=True, motores=(255, 0))
    assert not _flag0_no_radio(h, rumble=True) & BIT1
    h.set_haptica_de_audio(False)
    assert _flag0_no_radio(h, rumble=True) & BIT1


def _null_evdev() -> EvdevReader:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


def _controlador_com_quatro() -> tuple[PyDualSenseController, list[Any]]:
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    handles = [_handle(motores=(255, 255)) for _ in CHAVES]
    inst._handles = dict(zip(CHAVES, handles, strict=True))
    inst._primary_key = CHAVES[0]
    return inst, handles


@pytest.mark.parametrize("jogador", range(4), ids=["P1", "P2", "P3", "P4"])
def test_o_controlador_mira_o_handle_do_controle(jogador: int) -> None:
    """De P1 a P4: só o handle do controle com a háptica perde o bit 1.

    MORDIDA: o roteador que não acha o handle (devolver False antes de
    definir) deixa o bit 1 no controle que toca a háptica.
    """
    inst, handles = _controlador_com_quatro()

    assert inst.set_haptica_de_audio_for(UNIQS[jogador], True) is True

    for i, h in enumerate(handles):
        com_bit1 = bool(_flag0_no_radio(h, rumble=True) & BIT1)
        assert com_bit1 is (i != jogador), (
            f"P{i + 1}: bit 1 {'presente' if com_bit1 else 'ausente'} "
            f"com a háptica no P{jogador + 1}")
    assert inst.set_haptica_de_audio_for("aabbcc0000ff", True) is False


class _Controlador:
    """O controlador de mentira: anota o que o subsystem disse a quem."""

    def __init__(self) -> None:
        self.ditos: list[tuple[str, bool]] = []

    def set_haptica_de_audio_for(self, uniq: str, ativa: bool) -> bool:
        self.ditos.append((uniq, ativa))
        return True


class _Ponte:
    def __init__(self) -> None:
        self.de_pe = True

    def esta_de_pe(self) -> bool:
        return self.de_pe


def _subsystem(monkeypatch: pytest.MonkeyPatch, tocando: set[str]) -> Any:
    monkeypatch.setattr(alto_falante_bt, "sinks_que_tocam", lambda nomes, *a, **k: set(tocando))
    sub = mod.AltoFalanteSubsystem(gerenciador=None, fonte_de_controles=list)
    sub._backend = _Controlador()
    sub._aparelho_de = {u: f"aparelho-{i}" for i, u in enumerate(UNIQS)}
    sub._endpoints = {
        f"aparelho-{i}": SimpleNamespace(nome=f"hefesto_haptica_{i}") for i in range(4)
    }
    return sub


def _no_radio(sub: Any, uniq: str, modo: str = "haptica") -> _Ponte:
    i = UNIQS.index(uniq)
    ponte = _Ponte()
    sub._pontes[uniq] = ponte
    sub._modo_da_ponte[uniq] = modo
    sub._endpoint_da_ponte = {**sub._endpoint_da_ponte, uniq: f"hefesto_haptica_{i}"}
    return ponte


def test_o_subsystem_diz_a_borda_da_haptica_ao_controlador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ponte `0x32` de pé com o endpoint tocando: o controlador ouve True, uma vez.

    A ponte desce: ouve False. O controle com a ponte do SOM (`0x35`) e o
    endpoint sem fluxo não contam.

    MORDIDA: o subsystem que nunca chama `set_haptica_de_audio_for` deixa o
    controlador sem saber, e o rumble segue calando a háptica.
    """
    sub = _subsystem(monkeypatch, {"hefesto_haptica_0", "hefesto_haptica_1"})
    controles = [SimpleNamespace(uniq=u) for u in UNIQS]
    ponte = _no_radio(sub, UNIQS[0])
    _no_radio(sub, UNIQS[1], modo="som")
    _no_radio(sub, UNIQS[2])

    sub._dizer_a_haptica_aos_controles(controles)
    sub._dizer_a_haptica_aos_controles(controles)

    assert sub._backend.ditos == [(UNIQS[0], True)], sub._backend.ditos
    ponte.de_pe = False
    sub._dizer_a_haptica_aos_controles(controles)
    assert sub._backend.ditos[-1] == (UNIQS[0], False)


def test_no_cabo_o_laco_aberto_com_o_endpoint_tocando_conta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No cabo, o laço do aparelho com o portão aberto e fluxo no endpoint."""
    sub = _subsystem(monkeypatch, {"hefesto_haptica_3"})
    rota = SimpleNamespace(dono=UNIQS[3])
    portoes = {"aparelho-3": True}
    sub._cabo = SimpleNamespace(
        aparelhos=lambda: {"aparelho-3": rota}, portao=lambda marca: portoes.get(marca)
    )
    controles = [SimpleNamespace(uniq=UNIQS[3])]

    sub._dizer_a_haptica_aos_controles(controles)
    assert sub._backend.ditos == [(UNIQS[3], True)]
    portoes["aparelho-3"] = False
    sub._dizer_a_haptica_aos_controles(controles)
    assert sub._backend.ditos[-1] == (UNIQS[3], False)


def test_o_servidor_de_som_mudo_nao_muda_o_que_foi_dito(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`sinks_que_tocam` sem resposta: nada vai ao controlador, nos dois sentidos."""
    sub = _subsystem(monkeypatch, {"hefesto_haptica_0"})
    _no_radio(sub, UNIQS[0])
    controles = [SimpleNamespace(uniq=UNIQS[0])]
    sub._dizer_a_haptica_aos_controles(controles)
    monkeypatch.setattr(alto_falante_bt, "sinks_que_tocam", lambda nomes, *a, **k: None)
    sub._dizer_a_haptica_aos_controles(controles)
    assert sub._backend.ditos == [(UNIQS[0], True)]


def test_a_reconciliacao_das_pontes_diz_a_haptica() -> None:
    """A volta que casa as pontes termina dizendo a háptica ao controlador.

    MORDIDA: tire a chamada de `_dizer_a_haptica_aos_controles` do fim de
    `_casar_as_pontes` e nada no produto avisa o controlador.
    """
    fonte = inspect.getsource(mod.AltoFalanteSubsystem._casar_as_pontes)
    assert "self._dizer_a_haptica_aos_controles(controles)" in fonte
