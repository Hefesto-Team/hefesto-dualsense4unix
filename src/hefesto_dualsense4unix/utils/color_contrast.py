"""utils/color_contrast.py — razão de contraste WCAG e formato de cor 8-bit."""
from __future__ import annotations

from collections.abc import Sequence

RGB = tuple[int, int, int]


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


def rgb_para_hex(rgb: Sequence[int]) -> str:
    """Formata uma cor 8-bit como ``#rrggbb`` (minúsculo)."""
    r, g, b = _valida_rgb(rgb)
    return f"#{r:02x}{g:02x}{b:02x}"
