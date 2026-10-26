"""A-VIBRACAO-DO-CABO-ACORDA-O-MOTOR-E-DEVOLVE-A-HAPTICA-01.

Medido em 26/10/2026 (cabo e rádio, na mão de quem testou, estímulos alternados): o motor só
obedece ao report com o ``HAPTICS_SELECT``; esse bit cala o PCM da háptica e fica preso até um
report sem ``0x01``/``0x02``. Os dois não andam juntos pelo report. A cura: com a háptica por
áudio tocando, a vibração do jogo vira áudio no endpoint (o ``TocadorDoRumble``), e o report sai
SEM os dois bits; sem a háptica, o motor vai pelo report, como sempre; ao abrir o hidraw do
cabo, uma soltura desfaz o bit que outro processo deixou.

A BANCADA: o handle é o ``_PinnedPyDualSense`` real, sem device, e os reports saem do montador
real (cabo ``0x02``, rádio ``0x31``). O subsystem é o real, no mundo dublado do Xbox (quatro
controles, de P1 a P4, no cabo e no rádio). A MORDIDA de cada régua está no docstring dela.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from tests.unit import test_a_haptica_chega_a_quem_entra_depois as _da_mesa
from tests.unit import test_no_modo_xbox_a_haptica_fina as _do_mundo
from tests.unit.test_no_modo_xbox_a_haptica_fina import (
    _ABERTO,
    _MARCA,
    _QUATRO,
    _Mundo,
    _no_cabo_os_quatro,
    _no_radio_os_quatro,
    _Tocador,
)

# As duas fixtures do mundo dublado, reexportadas com o mesmo nome para o pytest as achar.
mesa = _da_mesa.mesa
mundo = _do_mundo.mundo

BIT0 = rep.VALID_FLAG0_COMPATIBLE_VIBRATION
BIT1 = rep.VALID_FLAG0_HAPTICS_SELECT
V2 = rep.VALID_FLAG2_COMPATIBLE_VIBRATION2


def _handle(
    *,
    v2: bool = True,
    haptica: bool = False,
    motores: tuple[int, int] = (255, 255),
    tipo: ConnectionType = ConnectionType.USB,
) -> Any:
    """O handle real sem device, só com o estado que o montador lê."""
    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor, h.rightMotor = motores
    h.conType = tipo
    h._rumble_active = bool(any(motores))
    h._rumble_stop_pending = False
    h._bt_seq = 0
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._mic_mute_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    h.set_vibracao_v2(v2)
    if haptica:
        h.set_haptica_de_audio(True)
    return h


def _bits(report: list[int] | bytes, *, radio: bool) -> tuple[int, int]:
    """``(flag0, flag2)`` como saem no fio: o common começa no byte 3 do rádio e no 1 do cabo."""
    base = 3 if radio else 1
    return int(report[base]), int(report[base + rep.COMMON_VALID_FLAG2])


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
@pytest.mark.parametrize("v2", [True, False], ids=["v2", "v1"])
def test_sem_haptica_o_motor_acorda_com_o_haptics_select(radio: bool, v2: bool) -> None:
    """Vibração e nenhuma háptica: o report leva o ``HAPTICS_SELECT`` (e o V2 no flag2 da v2).

    MORDIDA: arranque o ``HAPTICS_SELECT`` do ``_build_common`` e o motor chega mudo.
    """
    h = _handle(v2=v2, tipo=ConnectionType.BT if radio else ConnectionType.USB)
    flag0, flag2 = _bits(h.prepareReport(), radio=radio)

    assert flag0 & BIT1, "o motor sem o HAPTICS_SELECT não vibra (medido em 26/10)"
    assert bool(flag2 & V2) is v2
    assert bool(flag0 & BIT0) is (not v2)


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
@pytest.mark.parametrize("v2", [True, False], ids=["v2", "v1"])
def test_com_haptica_a_vibracao_vai_como_audio_e_o_report_fica_sem_os_bits(
    radio: bool, v2: bool
) -> None:
    """Háptica tocando e vibração pedida: nem ``0x01`` nem ``0x02`` nem o V2.

    MORDIDA: devolva o ``HAPTICS_SELECT`` ao caso ``_haptica_de_audio`` de ``_build_common``
    (a ``vibra_pelo_audio`` sempre falsa) e o report cala o PCM da háptica.
    """
    h = _handle(v2=v2, haptica=True, tipo=ConnectionType.BT if radio else ConnectionType.USB)
    flag0, flag2 = _bits(h.prepareReport(), radio=radio)

    assert not flag0 & (BIT0 | BIT1), f"o report levou o bit que cala o PCM: {flag0:#04x}"
    assert not flag2 & V2


@pytest.mark.parametrize("radio", [False, True], ids=["cabo", "radio"])
def test_a_soltura_do_motor_leva_os_bits_e_o_report_seguinte_devolve_a_haptica(
    radio: bool,
) -> None:
    """Motores a 0 com a háptica tocando: o report da soltura PARA o motor; o seguinte, não.

    O report que para o motor leva os bits (sem eles o motor seguiria vibrando); o seguinte, sem
    nenhum, solta o PCM. MORDIDA: faça ``vibra_pelo_audio`` ignorar os motores a 0 (basta
    ``self._haptica_de_audio``) e o motor nunca recebe a parada.
    """
    tipo = ConnectionType.BT if radio else ConnectionType.USB
    h = _handle(haptica=True, motores=(255, 0), tipo=tipo)
    h.leftMotor = 0
    h._rumble_active = False
    h._rumble_stop_pending = True

    parada, _ = _bits(h.prepareReport(), radio=radio)
    depois, _ = _bits(h.prepareReport(), radio=radio)

    assert parada & BIT1, "a parada do motor saiu sem os bits: o motor ficaria vibrando"
    assert not depois & (BIT0 | BIT1), "o report seguinte à parada manteve o bit que cala o PCM"


def test_a_haptica_que_para_devolve_o_haptics_select_ao_motor() -> None:
    """A háptica parou: a vibração seguinte volta a pedir o motor pelo report."""
    h = _handle(haptica=True)
    assert not _bits(h.prepareReport(), radio=False)[0] & BIT1
    h.set_haptica_de_audio(False)
    assert _bits(h.prepareReport(), radio=False)[0] & BIT1


def test_abrir_o_hidraw_do_cabo_escreve_a_soltura(monkeypatch: pytest.MonkeyPatch) -> None:
    """No cabo, a abertura escreve um ``0x02`` com todos os flags a 0: desfaz o bit preso.

    MORDIDA: tire a chamada de ``soltar_o_motor_preso`` de ``init`` (ou o corpo do método) e o
    controle que o kernel deixou com o ``HAPTICS_SELECT`` segue mudo para a háptica.
    """
    h = _handle(tipo=ConnectionType.USB)
    escritos: list[list[int]] = []
    monkeypatch.setattr(h, "writeReport", lambda r, *a, **k: escritos.append(list(r)) or len(r))

    h.soltar_o_motor_preso()

    assert len(escritos) == 1
    soltura = escritos[0]
    assert soltura[0] == rep.USB_REPORT_ID
    assert not any(soltura[1:1 + rep.COMMON_LEN]), "a soltura levou um flag válido"


def test_no_radio_a_abertura_nao_escreve_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """No rádio a ponte do ``0x36`` solta a cada quadro: a abertura não escreve."""
    h = _handle(tipo=ConnectionType.BT)
    escritos: list[Any] = []
    monkeypatch.setattr(h, "writeReport", lambda r, *a, **k: escritos.append(r))
    h.soltar_o_motor_preso()
    assert escritos == []


def test_a_soltura_nunca_levanta(monkeypatch: pytest.MonkeyPatch) -> None:
    """O hidraw que recusa a escrita não derruba a abertura."""
    h = _handle(tipo=ConnectionType.USB)

    def _recusa(*_a: Any, **_k: Any) -> None:
        raise OSError("hidraw recusou")

    monkeypatch.setattr(h, "writeReport", _recusa)
    h.soltar_o_motor_preso()


def test_o_init_solta_o_motor_antes_da_volta_de_report() -> None:
    """A soltura sai ANTES de o fio de report nascer: o primeiro report da volta já a segue."""
    import inspect

    fonte = inspect.getsource(_PinnedPyDualSense.init)
    assert "self.soltar_o_motor_preso()" in fonte
    assert fonte.index("self.soltar_o_motor_preso()") < fonte.index("self.ds_thread = True")


# --- o pad DualSense do jogo (uhid): a vibração soma na háptica dele ---------------------------


def _montar(mundo: _Mundo, transporte: str) -> list[Any]:
    return (_no_cabo_os_quatro if transporte == "cabo" else _no_radio_os_quatro)(mundo)


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
@pytest.mark.parametrize("uniq", _QUATRO, ids=["P1", "P2", "P3", "P4"])
def test_o_pad_uhid_com_a_haptica_do_jogo_tocando_vibra_como_audio(
    mundo: _Mundo, transporte: str, uniq: str
) -> None:
    """O jogo toca a háptica no endpoint do controle: o rumble do pad ``uhid`` soma nela.

    O motor do HID fica em zero (o bit do report calaria a háptica), e o tocador leva o par.
    MORDIDA: em ``_levar_a_haptica_fina`` volte ``converte = e_xbox`` e o rumble do pad
    ``uhid`` segue ao HID com a háptica do jogo tocando, calando-a.
    """
    controles = _montar(mundo, transporte)
    mundo.mesa.servidor.jogo_em.add(eh.nome_do_endpoint(uniq))
    mundo.mesa.volta(*controles)
    assert mundo.sub.o_jogo_toca_a_haptica_em(uniq), "a háptica do jogo não chegou ao controle"

    mundo.rumble(uniq, 100, 200, vpad=UhidDualSense(player=1))
    mundo.mesa.volta(*controles)

    assert mundo.tocador(uniq).nivel == (100, 200)
    assert mundo.backend.do(uniq)[-1] == (0, 0), "o HID levou o motor e calou a háptica"


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_o_pad_uhid_sem_a_haptica_do_jogo_segue_nos_motores_do_hid(
    mundo: _Mundo, transporte: str
) -> None:
    """Sem a háptica tocando, o pad ``uhid`` vibra pelos motores do HID, como sempre.

    MORDIDA: converta todo pad (``converte = True``) e o tocador sobe sem háptica a somar.
    """
    controles = _montar(mundo, transporte)
    mundo.mesa.volta(*controles)
    assert not mundo.sub.o_jogo_toca_a_haptica_em(_QUATRO[0])

    assert mundo.rumble(_QUATRO[0], 100, 200, vpad=UhidDualSense(player=1)) == (100, 200)
    assert _Tocador.criados == {}
    assert mundo.backend.do(_QUATRO[0])[-1] == (100, 200)


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_a_haptica_que_comeca_com_o_rumble_em_curso_passa_o_motor_ao_audio(
    mundo: _Mundo, transporte: str
) -> None:
    """O rumble começou nos motores do HID; o jogo começa a tocar a háptica: a volta o reaplica.

    O pad ``uhid`` foi anotado como «vivo» (o rumble em curso que ainda não converte), e a borda
    da háptica muda o retrato do caminho. MORDIDA: tire o ``vivo`` do ``_levar_a_haptica_fina``
    (ou o quarto elemento de ``_retrato_do_rumble``) e o motor do HID segue, calando a háptica.
    """
    uniq = _QUATRO[1]
    controles = _montar(mundo, transporte)
    mundo.mesa.volta(*controles)
    mundo.rumble(uniq, 100, 200, vpad=UhidDualSense(player=1))
    assert mundo.backend.do(uniq)[-1] == (100, 200)

    mundo.mesa.servidor.jogo_em.add(eh.nome_do_endpoint(uniq))
    mundo.mesa.volta(*controles)

    assert mundo.tocador(uniq).nivel == (100, 200), "a borda da háptica não reaplicou o rumble"
    assert mundo.backend.do(uniq)[-1] == (0, 0), "o motor do HID seguiu vibrando"


def test_o_xbox_com_o_jogo_tocando_soma_no_endpoint_e_abre_o_laco(mundo: _Mundo) -> None:
    """O pad Xbox converte sempre; com o jogo tocando, o rumble soma na háptica dele."""
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_QUATRO[0]))
    mundo.mesa.volta(*controles)
    mundo.rumble(_QUATRO[0], 100, 200)
    mundo.mesa.volta(*controles)
    assert mundo.tocador(_QUATRO[0]).nivel == (100, 200)
    assert mundo.backend.do(_QUATRO[0])[-1] == (0, 0)
    assert mundo.mesa.servidor.volumes[mundo.mesa.servidor.fluxo_do_laco(_QUATRO[0])] == _ABERTO


def test_o_marcador_do_tocador_separa_o_nosso_fluxo_do_do_jogo(mundo: _Mundo) -> None:
    """O fluxo do nosso tocador não conta como o jogo: a partida segue sem dono."""
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    mundo.rumble(_QUATRO[0], 100, 200)
    mundo.mesa.volta(*controles)
    assert mundo.fluxos.tocando == {_MARCA[_QUATRO[0]]: "61"}
    assert mundo.sub._donos_dos_fluxos() == frozenset()
