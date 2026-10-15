"""Presets de posição para modos MultiPositionFeedback e MultiPositionVibration.

Cada preset define um array de 10 intensidades (uma por posição do gatilho,
0-8) que popula os sliders da aba Gatilhos instantaneamente. O usuário ainda
pode ajustar fino depois de aplicar um preset.

Range canônico: 0-8 (alinhado com `trigger_effects.multi_position_feedback`
e `trigger_effects.multi_position_vibration` que validam `lo=0, hi=8`).

Uso tipico:
    from hefesto_dualsense4unix.profiles.trigger_presets import (
        FEEDBACK_POSITION_PRESETS,
        VIBRATION_POSITION_PRESETS,
        FEEDBACK_POSITION_LABELS,
        VIBRATION_POSITION_LABELS,
    )
    valores = FEEDBACK_POSITION_PRESETS["rampa_crescente"]  # [0, 1, 2, ...]
    label   = FEEDBACK_POSITION_LABELS["rampa_crescente"]   # "Endurece no fim"
"""
from __future__ import annotations

from typing import Literal, TypeVar

#: Os nomes de antes de 15/10/2026 → os de agora. A chave guardada no perfil, no
#: desenho ou numa conversa é lida pelos DOIS nomes (as tabelas abaixo respondem a
#: ambos), e só os novos aparecem ao listar.
NOMES_ANTIGOS_DOS_PRESETS_DE_POSICAO: dict[str, str] = {
    "stop_hard": "parede_no_fim",
    "stop_macio": "parede_macia",
    "machine_gun": "vibra_em_degraus",
    "galope": "duas_ondas_no_curso",
    "senoide": "sobe_e_desce",
    "vibracao_final": "vibra_no_fim",
}

_V = TypeVar("_V")


class _LidaPelosDoisNomes(dict[str, _V]):
    """Um `dict` que lista só os nomes de agora e responde também aos de antes."""

    def __getitem__(self, chave: str) -> _V:
        return super().__getitem__(NOMES_ANTIGOS_DOS_PRESETS_DE_POSICAO.get(chave, chave))

    def __contains__(self, chave: object) -> bool:
        return super().__contains__(
            NOMES_ANTIGOS_DOS_PRESETS_DE_POSICAO.get(str(chave), chave))

    def get(self, chave: str, padrao: _V | None = None) -> _V | None:  # type: ignore[override]
        return super().get(NOMES_ANTIGOS_DOS_PRESETS_DE_POSICAO.get(chave, chave), padrao)


def chave_de_agora(chave: str) -> str:
    """O nome de agora de um preset de posição, dado o de agora ou o de antes."""
    return NOMES_ANTIGOS_DOS_PRESETS_DE_POSICAO.get(chave, chave)


# Presets para Feedback por posicao (MultiPositionFeedback)

FEEDBACK_POSITION_PRESETS: dict[str, list[int]] = _LidaPelosDoisNomes({
    "rampa_crescente":   [0, 1, 2, 3, 4, 5, 6, 7, 8, 8],
    "rampa_decrescente": [8, 7, 6, 5, 4, 3, 2, 1, 0, 0],
    "plateau_central":   [0, 2, 4, 6, 8, 8, 6, 4, 2, 0],
    "parede_no_fim":     [0, 0, 0, 0, 0, 0, 8, 8, 8, 8],
    "parede_macia":      [0, 1, 2, 4, 6, 7, 8, 8, 8, 8],
    "linear_medio":      [4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
})


VIBRATION_POSITION_PRESETS: dict[str, list[int]] = _LidaPelosDoisNomes({
    "pulso_crescente": [0, 0, 1, 2, 4, 5, 6, 7, 8, 8],
    "vibra_em_degraus":    [0, 8, 0, 8, 0, 8, 0, 8, 0, 8],
    "duas_ondas_no_curso": [0, 6, 8, 4, 0, 0, 6, 8, 4, 0],
    "sobe_e_desce":        [0, 2, 5, 7, 8, 8, 7, 5, 2, 0],
    "vibra_no_fim":        [0, 0, 0, 0, 0, 0, 2, 5, 7, 8],
})


FEEDBACK_POSITION_LABELS: dict[str, str] = _LidaPelosDoisNomes({
    "rampa_crescente":   "Endurece no fim",
    "rampa_decrescente": "Solta no fim",
    "plateau_central":   "Pico no meio",
    "parede_no_fim":     "Parede no fim",
    "parede_macia":      "Parede macia",
    "linear_medio":      "Peso igual",
    "custom":            "Personalizar",
})

VIBRATION_POSITION_LABELS: dict[str, str] = _LidaPelosDoisNomes({
    "pulso_crescente":     "Pulso crescente",
    "vibra_em_degraus":    "Vibra em degraus",
    "duas_ondas_no_curso": "Duas ondas no curso",
    "sobe_e_desce":        "Sobe e desce",
    "vibra_no_fim":        "Vibra no fim",
    "custom":              "Personalizar",
})


FeedbackPositionPreset = Literal[
    "rampa_crescente",
    "rampa_decrescente",
    "plateau_central",
    "parede_no_fim",
    "parede_macia",
    "linear_medio",
]

VibrationPositionPreset = Literal[
    "pulso_crescente",
    "vibra_em_degraus",
    "duas_ondas_no_curso",
    "sobe_e_desce",
    "vibra_no_fim",
]


__all__ = [  # noqa: RUF022
    "FEEDBACK_POSITION_LABELS",
    "FEEDBACK_POSITION_PRESETS",
    "FeedbackPositionPreset",
    "VIBRATION_POSITION_LABELS",
    "NOMES_ANTIGOS_DOS_PRESETS_DE_POSICAO",
    "VIBRATION_POSITION_PRESETS",
    "VibrationPositionPreset",
    "chave_de_agora",
]
