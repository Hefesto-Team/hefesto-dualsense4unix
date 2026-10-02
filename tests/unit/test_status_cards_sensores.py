"""Os três módulos de sensor DENTRO do card da aba Status (S2), com GTK real.

O contrato que estes testes travam é sempre o mesmo, em três lugares
diferentes: **ausência de sensor não vira zero na tela**. Três barras de
giroscópio paradas no centro, um medidor de mic vazio ou um touchpad sem
ponto diriam "o controle está em repouso" — quando a verdade é "não tenho
esse sensor". Cada módulo some inteiro em vez disso.

Também travam a coexistência com a linha `texto_motion`, que já existia: ela
diz se o giroscópio FLUI PARA O JOGO; as barras novas mostram o VALOR. São
duas perguntas diferentes e as duas continuam respondidas.

A última seção é de STATUS-SIMETRIA-01 e mede o LAYOUT MONTADO numa
`Gtk.OffscreenWindow` — alinhamento dos analógicos, ordem horizontal da faixa e
crescimento do glifo com a escala de fonte. Ela existe porque o precedente do
rumble (teste que passou com a cura arrancada, porque chamava a peça e não a
fiação) não pode se repetir: os três asserts caem quando a cura é removida.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status cards sensores")

from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")


from hefesto_dualsense4unix.interface import cartao_do_controle as cc_mod
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    gyro_do_inputs,
    speaker_do_entry,
    touchpad_do_inputs,
)
from hefesto_dualsense4unix.interface.sensores import (
    posicao_normalizada,
    texto_eixo,
    texto_toques,
    texto_volume,
)


def _inputs(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
        "l2_raw": 0,
        "r2_raw": 0,
        "buttons": [],
    }
    base.update(extra)
    return base


def _entry(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "index": 0,
        "connected": True,
        "transport": "usb",
        "is_primary": True,
        "uniq": "aa:bb:cc:00:00:01",
        "battery_pct": 80,
        "player": None,
        "player_slot": 1,
        "lightbar_rgb": [255, 121, 198],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "inputs": _inputs(),
        "vpad_backend": "uhid",
        "vpad_motivo": None,
    }
    base.update(kw)
    return base


_ESTADO: dict[str, Any] = {"native_mode": False}

_GYRO = {"x": 143.2, "y": -412.0, "z": 22.8}
_TOUCH = {"touching": True, "x": 1440, "y": 270, "width": 1920, "height": 1080}


def test_gyro_do_inputs_le_os_tres_eixos() -> None:
    assert gyro_do_inputs(_inputs(gyro=_GYRO)) == (143.2, -412.0, 22.8)


@pytest.mark.parametrize(
    "inputs",
    [None, {}, _inputs(), _inputs(gyro={"x": 1.0}), _inputs(gyro="lixo")],
)
def test_gyro_ausente_ou_malformado_vira_none(inputs: Any) -> None:
    """None é o que faz o módulo SUMIR; (0,0,0) fingiria repouso."""
    assert gyro_do_inputs(inputs) is None


def test_touchpad_do_inputs_normaliza_pelos_limites_do_payload() -> None:
    lido = touchpad_do_inputs(_inputs(touchpad=_TOUCH))

    assert lido is not None
    tocando, fx, fy = lido
    assert tocando is True
    assert fx == pytest.approx(0.75)
    assert fy == pytest.approx(0.25)


def test_touchpad_com_limites_proprios_nao_usa_1920x1080() -> None:
    """Quem declara os limites é o kernel, no próprio payload."""
    bloco = {"touching": True, "x": 500, "y": 250, "width": 1000, "height": 500}

    lido = touchpad_do_inputs(_inputs(touchpad=bloco))

    assert lido is not None
    _tocando, fx, fy = lido
    assert (fx, fy) == pytest.approx((0.5, 0.5))


@pytest.mark.parametrize("inputs", [None, _inputs(), _inputs(touchpad={"x": 1})])
def test_touchpad_ausente_ou_malformado_vira_none(inputs: Any) -> None:
    assert touchpad_do_inputs(inputs) is None


def test_texto_do_eixo_tem_largura_fixa() -> None:
    """Campo fixo: a 10 Hz, texto que muda de largura faz o painel respirar"""
    larguras = {len(texto_eixo(v)) for v in (0.0, -9.9, 143.2, -412.0, 1999.9)}

    assert larguras == {7}


def test_posicao_normalizada_grampeia_fora_de_faixa() -> None:
    assert posicao_normalizada(9999, -50, 1920, 1080) == (1.0, 0.0)
    assert posicao_normalizada(10, 10, 0, 0) == (0.0, 0.0)


@pytest.mark.parametrize(
    ("n", "esperado"), [(0, "Sem toque"), (1, "1 toque"), (2, "2 toques")]
)
def test_texto_toques(n: int, esperado: str) -> None:
    assert texto_toques(n) == esperado


def test_nenhum_caminho_esconde_o_bloco_do_microfone() -> None:
    """MIC-PRESENTE-01/E3, segunda metade: nenhum `hide()` no bloco do mic."""
    fonte = Path(cc_mod.__file__).read_text(encoding="utf-8")

    assert "_mic_box.hide()" not in fonte
    assert "_esconder_modulo(mic)" not in fonte


@pytest.mark.parametrize(
    "entrada",
    [
        {"speaker": {"volume": 180, "muted": False}},
        {"inputs": _inputs(speaker={"volume": 180, "muted": False})},
    ],
)
def test_speaker_lido_do_entry_ou_do_inputs(entrada: dict[str, Any]) -> None:
    """Quem publica é o daemon; o widget não pode quebrar por causa de ONDE"""
    assert speaker_do_entry(entrada) == (180, False)


@pytest.mark.parametrize(
    "entrada",
    [
        None,
        {},
        {"speaker": "lixo"},
        {"speaker": {}},
        {"speaker": {"volume": "alto"}},
        {"speaker": {"volume": True}},
    ],
)
def test_speaker_ausente_ou_malformado_vira_none(entrada: Any) -> None:
    assert speaker_do_entry(entrada) is None


def test_speaker_sem_mute_no_payload_nao_chuta() -> None:
    assert speaker_do_entry({"speaker": {"volume": 255}}) == (255, None)


def test_texto_volume_sem_mute_lido_mostra_so_a_porcentagem() -> None:
    assert texto_volume(255, None) == "100 %"
    assert texto_volume(0, None) == "0 %"


_LARGURA_DO_CARD = 620

_janelas_vivas: list[Any] = []


_LARGURA_DO_GRID_COM_GLIFO_CRU = 4 * 20 + 3 * 2


