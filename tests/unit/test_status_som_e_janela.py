"""SOM-01 — os três pedidos que ela fez olhando a v2, medidos na geometria."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status som e janela")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets.controller_card import (

    GLYPH_ESPACO_COMPACTO,
    GLYPH_ESPACO_UNICO,
    LARGURA_CARD_ELASTICA,
    LARGURA_CARD_UNICO,
    ControllerCard,
    glyph_size,
    glyph_size_unico,
)

LARGURA_DA_TELA_DELA = 1870

_INPUTS: dict[str, Any] = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {
        "touching": True,
        "x": 1440,
        "y": 270,
        "width": 1920,
        "height": 1080,
    },
}
_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 80,
    "player": None,
    "player_slot": 1,
    "lightbar_rgb": [97, 53, 131],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
    "speaker": {"volume": 180, "muted": False},
}
_ESTADO: dict[str, Any] = {"native_mode": False}

_janelas_vivas: list[Any] = []


def _card(
    *, compact: bool = False, largura: int = LARGURA_DA_TELA_DELA
) -> Any:
    """Card montado e alocado numa janela da largura pedida."""
    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(largura, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_ENTRY, _ESTADO, LeituraMic(nivel=0.6, muted=False))
    janela.resize(largura, 900)
    while Gtk.events_pending():
        Gtk.main_iteration()
    return card


@pytest.mark.parametrize("compact", [False, True])
def test_o_alto_falante_fica_logo_abaixo_do_microfone(compact: bool) -> None:
    """O pedido ao pé da letra: ABAIXO, e na MESMA coluna."""
    card = _card(compact=compact)

    mic = card._mic_box.get_allocation()
    alto = card._speaker_box.get_allocation()

    assert alto.x == mic.x, (
        f"o alto-falante começa em x={alto.x} e o microfone em x={mic.x}: "
        "eles não estão na mesma coluna"
    )
    assert alto.width == mic.width, (
        f"o alto-falante mede {alto.width}px e o microfone {mic.width}px: a "
        "coluna do som ficou desalinhada"
    )
    assert alto.y >= mic.y + mic.height, (
        f"o alto-falante começa em y={alto.y} e o microfone só termina em "
        f"y={mic.y + mic.height}: ele não está ABAIXO do microfone"
    )
    assert card._speaker_box.get_parent() is card._coluna_audio
    assert card._mic_box.get_parent() is card._coluna_audio


def test_a_coluna_da_esquerda_nao_fica_orfa_de_altura() -> None:
    """O alto-falante saiu da coluna da esquerda — ela não pode ter afundado."""
    card = _card()

    touch = card._touch_box.get_allocation()
    mic = card._mic_box.get_allocation()
    sticks = card._stick_left.get_allocation()

    assert touch.y == mic.y, (
        f"o touchpad começa em y={touch.y} e o microfone em y={mic.y}: a "
        "coluna da esquerda saiu do topo da faixa"
    )
    assert touch.y <= sticks.y, "os sensores abrem a faixa, no alto"
    assert card._lightbar_box.get_allocation().y > touch.y
    assert card._speaker_box.get_parent() is not card._coluna_sensores


def test_o_glifo_do_card_de_um_controle_e_maior_que_o_do_compacto() -> None:
    """*"aumentar (...) os botões tipo x quadrado bola e triângulo"*."""
    unico = _card()
    compacto = _card(compact=True, largura=600)

    glifo_unico = unico._glyphs["triangle"].get_allocated_width()
    glifo_compacto = compacto._glyphs["triangle"].get_allocated_width()

    assert glifo_unico > glifo_compacto, (
        f"o glifo do card de um controle mede {glifo_unico}px e o do compacto "
        f"{glifo_compacto}px: ele parou de crescer onde havia largura"
    )
    assert glifo_unico == glyph_size_unico()
    assert glifo_compacto == glyph_size()
    assert unico._glyph_grid.get_allocated_width() > (
        compacto._glyph_grid.get_allocated_width()
    )


def test_os_glifos_do_card_de_um_controle_tem_respiro_entre_eles() -> None:
    """*"e espaçar mais"* — a segunda metade do pedido."""
    card = _card()

    cruz = card._glyphs["cross"].get_allocation()
    circulo = card._glyphs["circle"].get_allocation()
    cima = card._glyphs["dpad_up"].get_allocation()

    horizontal = circulo.x - (cruz.x + cruz.width)
    vertical = cima.y - (cruz.y + cruz.height)

    assert horizontal >= GLYPH_ESPACO_UNICO, (
        f"a cruz e a bola estão a {horizontal}px uma da outra (esperado ao "
        f"menos {GLYPH_ESPACO_UNICO}px): os botões voltaram a ficar colados"
    )
    assert vertical >= GLYPH_ESPACO_UNICO, (
        f"as duas fileiras estão a {vertical}px uma da outra (esperado ao "
        f"menos {GLYPH_ESPACO_UNICO}px)"
    )
    assert GLYPH_ESPACO_UNICO > GLYPH_ESPACO_COMPACTO


def test_o_card_compacto_mantem_o_glifo_de_hoje() -> None:
    """A contrapartida MEDIDA da decisão: no compacto o glifo não cresce."""
    compacto = _card(compact=True, largura=600)

    assert compacto._glyph_size == glyph_size()
    assert compacto._glyph_grid.get_row_spacing() == GLYPH_ESPACO_COMPACTO
    assert compacto._glyph_grid.get_column_spacing() == GLYPH_ESPACO_COMPACTO


def test_o_glifo_maior_continua_derivando_da_escala_de_fonte() -> None:
    """O tamanho novo não pode ser px cru: ele tem de crescer com a fonte dela."""
    assert glyph_size_unico(0) < glyph_size_unico(3)
    assert glyph_size_unico(0) > glyph_size(0)


@pytest.mark.parametrize(
    ("largura_da_janela", "esperado"),
    [
        (1180, 1180),
        (1400, 1400),
        (LARGURA_DA_TELA_DELA, LARGURA_CARD_ELASTICA),
    ],
)
def test_o_card_acompanha_a_janela_ate_o_teto_elastico(
    largura_da_janela: int, esperado: int
) -> None:
    """A curva inteira do teto elástico, e não só as pontas."""
    card = _card(largura=largura_da_janela)

    assert card.get_allocated_width() == esperado


def test_o_piso_do_card_e_o_que_o_conteudo_pede() -> None:
    """O piso não pode ser decorativo."""
    card = ControllerCard(compact=False)
    card.show_all()

    minimo, _natural = card.get_preferred_width()

    assert minimo <= LARGURA_CARD_UNICO, (
        f"o conteúdo do card pede {minimo}px e o piso compartilhado com o "
        f"frame Estado é de {LARGURA_CARD_UNICO}px: o piso virou enfeite"
    )
    assert LARGURA_CARD_UNICO < LARGURA_CARD_ELASTICA


def test_o_card_compacto_tambem_ganha_teto_elastico() -> None:
    """O corte passou a valer para os DOIS modos — EMPILHA-01, 02/08/2026."""
    card = _card(compact=True, largura=LARGURA_DA_TELA_DELA)

    assert LARGURA_DA_TELA_DELA > LARGURA_CARD_ELASTICA, (
        "a bancada precisa de uma tela MAIOR que o teto para medir o corte"
    )
    assert card.get_allocated_width() == LARGURA_CARD_ELASTICA
