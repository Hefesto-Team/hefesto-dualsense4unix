"""utils/color_contrast.py — fundação de contraste mínimo para tinting (STATUS-03)."""
from __future__ import annotations

import colorsys
from collections.abc import Sequence
from typing import Any, Final

RGB = tuple[int, int, int]

RATIO_MINIMO: Final[float] = 3.0

FUNDO_STICK_PREVIEW: Final[RGB] = (0x28, 0x2A, 0x36)

FUNDO_TEMA_GTK_ESCURO: Final[RGB] = (0x35, 0x35, 0x35)

ACCENT_NEUTRO: Final[RGB] = (0x62, 0x72, 0xA4)

TROUGH_HEX: Final[str] = "#21222c"


def _valida_rgb(rgb: Sequence[int]) -> RGB:
    """Normaliza uma cor 8-bit (aceita tuple/list do IPC), com clamp 0-255."""
    if len(rgb) != 3:
        raise ValueError(f"cor RGB precisa de 3 canais, veio {len(rgb)}: {rgb!r}")
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return (r, g, b)


def _linearizar(canal: float) -> float:
    """Lineariza um canal sRGB em [0,1] (fórmula WCAG 2.x)."""
    if canal <= 0.03928:
        return canal / 12.92
    return float(((canal + 0.055) / 1.055) ** 2.4)


def luminancia_relativa(rgb: Sequence[int]) -> float:
    """Luminância relativa WCAG de uma cor 8-bit (0.0 = preto, 1.0 = branco)."""
    r, g, b = _valida_rgb(rgb)
    return (
        0.2126 * _linearizar(r / 255)
        + 0.7152 * _linearizar(g / 255)
        + 0.0722 * _linearizar(b / 255)
    )


def razao_contraste(cor_a: Sequence[int], cor_b: Sequence[int]) -> float:
    """Razão de contraste WCAG entre duas cores 8-bit (1.0 a 21.0)."""
    la = luminancia_relativa(cor_a)
    lb = luminancia_relativa(cor_b)
    claro, escuro = (la, lb) if la >= lb else (lb, la)
    return (claro + 0.05) / (escuro + 0.05)


PIOR_FUNDO: Final[RGB] = max(
    (FUNDO_STICK_PREVIEW, FUNDO_TEMA_GTK_ESCURO),
    key=luminancia_relativa,
)


def _hls_para_rgb8(h: float, luz: float, s: float) -> RGB:
    """Converte HLS (frações 0-1) para RGB 8-bit arredondado."""
    r, g, b = colorsys.hls_to_rgb(h, luz, s)
    return (round(r * 255), round(g * 255), round(b * 255))


def ensure_min_contrast(
    rgb: Sequence[int],
    ratio: float = RATIO_MINIMO,
    *,
    fundo: Sequence[int] | None = None,
) -> RGB:
    """Clareia ``rgb`` até o contraste WCAG contra o pior fundo ser >= ``ratio``."""
    alvo: RGB = PIOR_FUNDO if fundo is None else _valida_rgb(fundo)
    cor = _valida_rgb(rgb)
    if razao_contraste(cor, alvo) >= ratio:
        return cor

    h, luz, s = colorsys.rgb_to_hls(cor[0] / 255, cor[1] / 255, cor[2] / 255)
    lo, hi = luz, 1.0
    for _ in range(32):
        meio = (lo + hi) / 2
        if razao_contraste(_hls_para_rgb8(h, meio, s), alvo) >= ratio:
            hi = meio
        else:
            lo = meio
    candidata = _hls_para_rgb8(h, hi, s)
    while razao_contraste(candidata, alvo) < ratio and hi < 1.0:
        hi = min(1.0, hi + 1 / 255)
        candidata = _hls_para_rgb8(h, hi, s)
    return candidata


def rgb_para_hex(rgb: Sequence[int]) -> str:
    """Formata uma cor 8-bit como ``#rrggbb`` (minúsculo)."""
    r, g, b = _valida_rgb(rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def tintar_progressbar(
    barra: Any,
    rgb: Sequence[int],
    ratio: float = RATIO_MINIMO,
) -> str:
    """Tinta o preenchimento de uma ``Gtk.ProgressBar`` com a cor ajustada."""
    hex_cor = rgb_para_hex(ensure_min_contrast(rgb, ratio))
    if getattr(barra, "_hefesto_tint_hex", None) == hex_cor:
        return hex_cor

    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    css = (
        f"progressbar trough {{ background-color: {TROUGH_HEX};"
        f" background-image: none; }}\n"
        f"progressbar trough progress {{ background-color: {hex_cor};"
        f" background-image: none; }}\n"
    )
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))
    contexto = barra.get_style_context()
    anterior = getattr(barra, "_hefesto_tint_provider", None)
    if anterior is not None:
        contexto.remove_provider(anterior)
    contexto.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    barra._hefesto_tint_provider = provider
    barra._hefesto_tint_hex = hex_cor
    return hex_cor
