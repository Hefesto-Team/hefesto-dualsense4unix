"""tests/unit/test_color_contrast.py — a razão de contraste e o formato hex."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.utils.color_contrast import (
    luminancia_relativa,
    razao_contraste,
    rgb_para_hex,
)


def test_extremos_da_luminancia() -> None:
    assert luminancia_relativa((0, 0, 0)) == 0.0
    assert luminancia_relativa((255, 255, 255)) == pytest.approx(1.0)


def test_razao_de_preto_contra_branco_e_21() -> None:
    assert razao_contraste((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert razao_contraste((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0)


def test_razao_contraste_bate_com_o_valor_provado() -> None:
    """(16,32,72) contra #282a36 = 1.12:1 (recalculado por dois revisores)."""
    assert 1.10 <= razao_contraste((16, 32, 72), (0x28, 0x2A, 0x36)) <= 1.13


def test_aceita_lista_do_ipc_e_faz_clamp() -> None:
    assert razao_contraste([16, 32, 72], [0, 0, 0]) == razao_contraste((16, 32, 72), (0, 0, 0))
    assert rgb_para_hex((300, -5, 128)) == rgb_para_hex((255, 0, 128))


def test_entrada_invalida_levanta_value_error() -> None:
    with pytest.raises(ValueError):
        luminancia_relativa((1, 2))


def test_rgb_para_hex() -> None:
    assert rgb_para_hex((16, 32, 72)) == "#102048"
    assert rgb_para_hex((0, 0, 0)) == "#000000"
    assert rgb_para_hex((255, 255, 255)) == "#ffffff"
