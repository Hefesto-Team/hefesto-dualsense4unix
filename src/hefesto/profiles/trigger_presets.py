"""Presets de posição para modos MultiPositionFeedback e MultiPositionVibration.

Cada preset define um array de 10 intensidades (uma por posição do gatilho,
0-8) que popula os sliders da aba Gatilhos instantaneamente. O usuario ainda
pode ajustar fino depois de aplicar um preset.

Range canônico: 0-8 (alinhado com `trigger_effects.multi_position_feedback`
e `trigger_effects.multi_position_vibration` que validam `lo=0, hi=8`).

Uso tipico:
    from hefesto.profiles.trigger_presets import (
        FEEDBACK_POSITION_PRESETS,
        VIBRATION_POSITION_PRESETS,
        FEEDBACK_POSITION_LABELS,
        VIBRATION_POSITION_LABELS,
    )
    valores = FEEDBACK_POSITION_PRESETS["rampa_crescente"]  # [0, 1, 2, ...]
    label   = FEEDBACK_POSITION_LABELS["rampa_crescente"]   # "Rampa crescente"
"""
from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Presets para Feedback por posicao (MultiPositionFeedback)
# Range 0-8 por posicao, 10 posicoes (Pos 0 a Pos 9).
# ---------------------------------------------------------------------------

FEEDBACK_POSITION_PRESETS: dict[str, list[int]] = {
    "rampa_crescente":   [0, 1, 2, 3, 4, 5, 6, 7, 8, 8],
    "rampa_decrescente": [8, 7, 6, 5, 4, 3, 2, 1, 0, 0],
    "plateau_central":   [0, 2, 4, 6, 8, 8, 6, 4, 2, 0],
    "stop_hard":         [0, 0, 0, 0, 0, 0, 8, 8, 8, 8],
    "stop_macio":        [0, 1, 2, 4, 6, 7, 8, 8, 8, 8],
    "linear_medio":      [4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
}

# ---------------------------------------------------------------------------
# Presets para Vibracao por posicao (MultiPositionVibration)
# Mesmo shape: 10 posicoes, range 0-8.
# ---------------------------------------------------------------------------

VIBRATION_POSITION_PRESETS: dict[str, list[int]] = {
    "pulso_crescente": [0, 0, 1, 2, 4, 5, 6, 7, 8, 8],
    "machine_gun":     [0, 8, 0, 8, 0, 8, 0, 8, 0, 8],
    "galope":          [0, 6, 8, 4, 0, 0, 6, 8, 4, 0],
    "senoide":         [0, 2, 5, 7, 8, 8, 7, 5, 2, 0],
    "vibracao_final":  [0, 0, 0, 0, 0, 0, 2, 5, 7, 8],
}

# ---------------------------------------------------------------------------
# Labels PT-BR para os dropdowns (inclui "custom" que não esta nos dicts acima)
# ---------------------------------------------------------------------------

FEEDBACK_POSITION_LABELS: dict[str, str] = {
    "rampa_crescente":   "Rampa crescente",
    "rampa_decrescente": "Rampa decrescente",
    "plateau_central":   "Plateau central",
    "stop_hard":         "Stop hard",
    "stop_macio":        "Stop macio",
    "linear_medio":      "Linear medio",
    "custom":            "Personalizar",
}

VIBRATION_POSITION_LABELS: dict[str, str] = {
    "pulso_crescente": "Pulso crescente",
    "machine_gun":     "Machine gun",
    "galope":          "Galope",
    "senoide":         "Senoide",
    "vibracao_final":  "Vibracao final",
    "custom":          "Personalizar",
}

# ---------------------------------------------------------------------------
# Tipos Literal para type-checkers (exclui "custom" — não e resolvivel)
# ---------------------------------------------------------------------------

FeedbackPositionPreset = Literal[
    "rampa_crescente",
    "rampa_decrescente",
    "plateau_central",
    "stop_hard",
    "stop_macio",
    "linear_medio",
]

VibrationPositionPreset = Literal[
    "pulso_crescente",
    "machine_gun",
    "galope",
    "senoide",
    "vibracao_final",
]

# ---------------------------------------------------------------------------
# Função utilitaria: resolve preset por nome
# ---------------------------------------------------------------------------


def resolve_feedback_preset(key: str) -> list[int] | None:
    """Retorna lista de 10 intensidades para o preset de feedback.

    Retorna None quando key == 'custom' (não altera sliders).
    """
    return FEEDBACK_POSITION_PRESETS.get(key)


def resolve_vibration_preset(key: str) -> list[int] | None:
    """Retorna lista de 10 intensidades para o preset de vibracao.

    Retorna None quando key == 'custom' (não altera sliders).
    """
    return VIBRATION_POSITION_PRESETS.get(key)


__all__ = [  # noqa: RUF022
    "FEEDBACK_POSITION_LABELS",
    "FEEDBACK_POSITION_PRESETS",
    "FeedbackPositionPreset",
    "VIBRATION_POSITION_LABELS",
    "VIBRATION_POSITION_PRESETS",
    "VibrationPositionPreset",
    "resolve_feedback_preset",
    "resolve_vibration_preset",
]
