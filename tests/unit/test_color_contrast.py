"""tests/unit/test_color_contrast.py — fundação de contraste do STATUS-03."""
from __future__ import annotations

import colorsys

import pytest

from hefesto_dualsense4unix.utils.color_contrast import (
    ACCENT_NEUTRO,
    FUNDO_STICK_PREVIEW,
    FUNDO_TEMA_GTK_ESCURO,
    PIOR_FUNDO,
    RATIO_MINIMO,
    ensure_min_contrast,
    luminancia_relativa,
    razao_contraste,
    rgb_para_hex,
    tintar_progressbar,
)

RGB = tuple[int, int, int]


def _lum(rgb: RGB) -> float:
    def lin(canal: int) -> float:
        c = canal / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contraste(a: RGB, b: RGB) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _matiz_graus(rgb: RGB) -> float:
    h, _l, _s = colorsys.rgb_to_hls(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    return h * 360.0


def _dif_angular(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _chroma(rgb: RGB) -> int:
    return max(rgb) - min(rgb)


_CHROMA_MINIMO_CROMATICA = 24


CORES: list[RGB] = [
    (16, 32, 72),
    (0, 0, 0),
    (255, 255, 255),
    (189, 147, 249),
    (98, 114, 164),
    (80, 250, 123),
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (0, 0, 128),
    (128, 0, 128),
    (0, 128, 128),
    (139, 0, 0),
    (25, 25, 112),
    (0, 100, 0),
    (72, 61, 139),
    (47, 79, 79),
    (34, 139, 34),
    (75, 0, 130),
    (128, 128, 0),
    (255, 215, 0),
    (255, 105, 180),
    (105, 105, 105),
    (10, 10, 10),
    (1, 2, 3),
    (40, 42, 54),
    (53, 53, 53),
]

CORES_CROMATICAS: list[RGB] = [
    c for c in CORES if _chroma(c) >= _CHROMA_MINIMO_CROMATICA
]
CORES_JA_LEGIVEIS: list[RGB] = [
    c for c in CORES if _contraste(c, PIOR_FUNDO) >= RATIO_MINIMO
]


def test_amostra_de_cores_cobre_o_criterio() -> None:
    """Meta-teste: >= 20 cores, com as obrigatórias e subconjuntos não-vazios."""
    assert len(CORES) >= 20
    assert (16, 32, 72) in CORES
    assert (0, 0, 0) in CORES
    assert len(CORES_CROMATICAS) >= 10
    assert len(CORES_JA_LEGIVEIS) >= 5


@pytest.mark.parametrize("cor", CORES, ids=[rgb_para_hex(c) for c in CORES])
def test_contraste_minimo_contra_pior_fundo(cor: RGB) -> None:
    """A saída atinge >= 3.0:1 contra o pior fundo (oráculo independente)."""
    saida = ensure_min_contrast(cor)
    assert _contraste(saida, PIOR_FUNDO) >= RATIO_MINIMO, (
        f"{cor} -> {saida}: contraste {_contraste(saida, PIOR_FUNDO):.3f} < 3.0"
    )


@pytest.mark.parametrize(
    "cor", CORES_CROMATICAS, ids=[rgb_para_hex(c) for c in CORES_CROMATICAS]
)
def test_matiz_preservado_para_cromaticas(cor: RGB) -> None:
    """Δmatiz <= 4° quando a cor de entrada é cromática."""
    saida = ensure_min_contrast(cor)
    delta = _dif_angular(_matiz_graus(cor), _matiz_graus(saida))
    assert delta <= 4.0, f"{cor} -> {saida}: Δmatiz {delta:.2f}° > 4°"


@pytest.mark.parametrize("cor", CORES, ids=[rgb_para_hex(c) for c in CORES])
def test_idempotencia_geral(cor: RGB) -> None:
    """f(f(x)) == f(x) para toda cor."""
    uma_vez = ensure_min_contrast(cor)
    assert ensure_min_contrast(uma_vez) == uma_vez


@pytest.mark.parametrize(
    "cor", CORES_JA_LEGIVEIS, ids=[rgb_para_hex(c) for c in CORES_JA_LEGIVEIS]
)
def test_cores_ja_legiveis_passam_intactas(cor: RGB) -> None:
    """Cor com contraste cru >= 3.0 contra o pior fundo NÃO é alterada."""
    assert ensure_min_contrast(cor) == cor


def test_cor_real_da_maquina_clareia_preservando_matiz_azul() -> None:
    """(16,32,72) — ilegível crua (1.12:1) — sobe SÓ a luminosidade."""
    saida = ensure_min_contrast((16, 32, 72))
    assert saida != (16, 32, 72)
    assert _lum(saida) > _lum((16, 32, 72))
    assert _contraste(saida, PIOR_FUNDO) >= 3.0
    assert _dif_angular(_matiz_graus(saida), 222.86) <= 4.0


def test_preto_vira_cinza_neutro_legivel() -> None:
    """(0,0,0) clareia para um NEUTRO (r==g==b) legível — sem matiz inventado."""
    saida = ensure_min_contrast((0, 0, 0))
    r, g, b = saida
    assert r == g == b, f"preto devia virar cinza neutro, veio {saida}"
    assert _contraste(saida, PIOR_FUNDO) >= 3.0


def test_claridade_minima_nao_estoura_para_branco() -> None:
    """O ajuste para no MÍNIMO legível — não pula para branco."""
    saida = ensure_min_contrast((16, 32, 72))
    assert saida != (255, 255, 255)
    mais_escura = (
        int(saida[0] * 0.96),
        int(saida[1] * 0.96),
        int(saida[2] * 0.96),
    )
    assert _contraste(mais_escura, PIOR_FUNDO) < 3.0


def test_ratio_customizado() -> None:
    """ratio=4.5 (régua de texto) também é honrado."""
    saida = ensure_min_contrast((16, 32, 72), 4.5)
    assert _contraste(saida, PIOR_FUNDO) >= 4.5


def test_fundo_customizado_muda_a_referencia() -> None:
    """fundo= troca a referência: contra preto, clareia bem menos."""
    preto = (0, 0, 0)
    saida_preto = ensure_min_contrast((16, 32, 72), fundo=preto)
    assert _contraste(saida_preto, preto) >= 3.0
    saida_default = ensure_min_contrast((16, 32, 72))
    assert _lum(saida_preto) < _lum(saida_default)


def test_aceita_lista_do_ipc() -> None:
    """O IPC entrega [r, g, b] — lista é aceita e a saída é tuple."""
    assert ensure_min_contrast([16, 32, 72]) == ensure_min_contrast((16, 32, 72))
    assert isinstance(ensure_min_contrast([16, 32, 72]), tuple)


def test_clamp_de_entrada_fora_da_faixa() -> None:
    """Canais fora de 0-255 sofrem clamp em vez de explodir."""
    assert ensure_min_contrast((300, -5, 128)) == ensure_min_contrast((255, 0, 128))


def test_entrada_invalida_levanta_value_error() -> None:
    with pytest.raises(ValueError):
        ensure_min_contrast((1, 2))


def test_accent_neutro_e_o_6272a4_do_sprint() -> None:
    """#6272a4 — accent dos rótulos "apagada"/"desconhecida" (contrato do card)."""
    assert ACCENT_NEUTRO == (0x62, 0x72, 0xA4)
    assert rgb_para_hex(ACCENT_NEUTRO) == "#6272a4"


def test_pior_fundo_e_o_mais_desfavoravel_dos_fundos_reais() -> None:
    """PIOR_FUNDO domina em luminância o fundo do StickPreview e o envelope."""
    assert luminancia_relativa(PIOR_FUNDO) >= luminancia_relativa(FUNDO_STICK_PREVIEW)
    assert luminancia_relativa(PIOR_FUNDO) >= luminancia_relativa(FUNDO_TEMA_GTK_ESCURO)
    saida = ensure_min_contrast((16, 32, 72))
    assert _contraste(saida, FUNDO_STICK_PREVIEW) >= 3.0


def test_razao_contraste_bate_com_o_valor_provado_do_sprint() -> None:
    """(16,32,72) vs #282a36 = 1.12:1 (recalculado por 2 revisores no doc)."""
    valor = razao_contraste((16, 32, 72), FUNDO_STICK_PREVIEW)
    assert 1.10 <= valor <= 1.13


def test_rgb_para_hex() -> None:
    assert rgb_para_hex((16, 32, 72)) == "#102048"
    assert rgb_para_hex((0, 0, 0)) == "#000000"
    assert rgb_para_hex((255, 255, 255)) == "#ffffff"


def test_tintar_progressbar_e_importavel_sem_gtk() -> None:
    """O helper existe no módulo puro (o import do GTK é tardio, na chamada)."""
    assert callable(tintar_progressbar)
