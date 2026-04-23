"""Testes unitarios para hefesto.profiles.trigger_presets.

Valida:
- Todos os presets resolvíveis têm exatamente 10 posicoes.
- Todos os valores estão no range 0-8 (limite do firmware DualSense).
- "custom" não está nos dicts de preset resolvível (só nos labels).
- Funções de resolucao retornam None para "custom" e lista para chaves validas.
"""
from __future__ import annotations

import pytest

from hefesto.profiles.trigger_presets import (
    FEEDBACK_POSITION_LABELS,
    FEEDBACK_POSITION_PRESETS,
    VIBRATION_POSITION_LABELS,
    VIBRATION_POSITION_PRESETS,
    resolve_feedback_preset,
    resolve_vibration_preset,
)

# ---------------------------------------------------------------------------
# Constantes de referência
# ---------------------------------------------------------------------------

_RANGE_MIN = 0
_RANGE_MAX = 8
_N_POSICOES = 10


# ---------------------------------------------------------------------------
# Testes — Feedback por posicao
# ---------------------------------------------------------------------------


class TestFeedbackPositionPresets:
    def test_todos_presets_tem_10_posicoes(self) -> None:
        for nome, valores in FEEDBACK_POSITION_PRESETS.items():
            assert len(valores) == _N_POSICOES, (
                f"Preset feedback '{nome}' tem {len(valores)} posicoes, esperado {_N_POSICOES}"
            )

    def test_todos_valores_dentro_do_range(self) -> None:
        for nome, valores in FEEDBACK_POSITION_PRESETS.items():
            for idx, v in enumerate(valores):
                assert _RANGE_MIN <= v <= _RANGE_MAX, (
                    f"Preset feedback '{nome}' posicao {idx} = {v} fora do range "
                    f"{_RANGE_MIN}-{_RANGE_MAX}"
                )

    def test_custom_nao_esta_nos_presets_resolviveis(self) -> None:
        assert "custom" not in FEEDBACK_POSITION_PRESETS

    def test_custom_esta_nos_labels(self) -> None:
        assert "custom" in FEEDBACK_POSITION_LABELS

    def test_todos_presets_possuem_label(self) -> None:
        for chave in FEEDBACK_POSITION_PRESETS:
            assert chave in FEEDBACK_POSITION_LABELS, (
                f"Preset feedback '{chave}' não tem label correspondente"
            )

    @pytest.mark.parametrize("chave", list(FEEDBACK_POSITION_PRESETS.keys()))
    def test_resolve_retorna_lista(self, chave: str) -> None:
        resultado = resolve_feedback_preset(chave)
        assert resultado is not None
        assert len(resultado) == _N_POSICOES

    def test_resolve_custom_retorna_none(self) -> None:
        assert resolve_feedback_preset("custom") is None

    def test_resolve_chave_inexistente_retorna_none(self) -> None:
        assert resolve_feedback_preset("nao_existe") is None

    def test_rampa_crescente_valores_corretos(self) -> None:
        valores = FEEDBACK_POSITION_PRESETS["rampa_crescente"]
        assert valores[0] == 0, "rampa_crescente deve comecar em 0"
        assert valores[-1] == 8, "rampa_crescente deve terminar em 8"
        # Deve ser não-decrescente
        for i in range(len(valores) - 1):
            assert valores[i] <= valores[i + 1], (
                f"rampa_crescente não é monotonica na posicao {i}"
            )

    def test_rampa_decrescente_valores_corretos(self) -> None:
        valores = FEEDBACK_POSITION_PRESETS["rampa_decrescente"]
        assert valores[0] == 8, "rampa_decrescente deve comecar em 8"
        assert valores[-1] == 0, "rampa_decrescente deve terminar em 0"
        # Deve ser não-crescente
        for i in range(len(valores) - 1):
            assert valores[i] >= valores[i + 1], (
                f"rampa_decrescente não é monotonica na posicao {i}"
            )


# ---------------------------------------------------------------------------
# Testes — Vibracao por posicao
# ---------------------------------------------------------------------------


class TestVibrationPositionPresets:
    def test_todos_presets_tem_10_posicoes(self) -> None:
        for nome, valores in VIBRATION_POSITION_PRESETS.items():
            assert len(valores) == _N_POSICOES, (
                f"Preset vibracao '{nome}' tem {len(valores)} posicoes, esperado {_N_POSICOES}"
            )

    def test_todos_valores_dentro_do_range(self) -> None:
        for nome, valores in VIBRATION_POSITION_PRESETS.items():
            for idx, v in enumerate(valores):
                assert _RANGE_MIN <= v <= _RANGE_MAX, (
                    f"Preset vibracao '{nome}' posicao {idx} = {v} fora do range "
                    f"{_RANGE_MIN}-{_RANGE_MAX}"
                )

    def test_custom_nao_esta_nos_presets_resolviveis(self) -> None:
        assert "custom" not in VIBRATION_POSITION_PRESETS

    def test_custom_esta_nos_labels(self) -> None:
        assert "custom" in VIBRATION_POSITION_LABELS

    def test_todos_presets_possuem_label(self) -> None:
        for chave in VIBRATION_POSITION_PRESETS:
            assert chave in VIBRATION_POSITION_LABELS, (
                f"Preset vibracao '{chave}' não tem label correspondente"
            )

    @pytest.mark.parametrize("chave", list(VIBRATION_POSITION_PRESETS.keys()))
    def test_resolve_retorna_lista(self, chave: str) -> None:
        resultado = resolve_vibration_preset(chave)
        assert resultado is not None
        assert len(resultado) == _N_POSICOES

    def test_resolve_custom_retorna_none(self) -> None:
        assert resolve_vibration_preset("custom") is None

    def test_resolve_chave_inexistente_retorna_none(self) -> None:
        assert resolve_vibration_preset("nao_existe") is None

    def test_machine_gun_alterna(self) -> None:
        """machine_gun deve ter padrão alternado de alta/baixa amplitude."""
        valores = VIBRATION_POSITION_PRESETS["machine_gun"]
        # Posicoes impares (1, 3, 5, 7, 9) devem ser maiores que as pares vizinhas
        for i in range(1, len(valores), 2):
            assert valores[i] >= valores[i - 1], (
                f"machine_gun: posicao {i} ({valores[i]}) deveria ser >= posicao "
                f"{i-1} ({valores[i-1]})"
            )


# ---------------------------------------------------------------------------
# Testes de integridade das constantes exportadas
# ---------------------------------------------------------------------------


class TestIntegridadeExportacoes:
    def test_feedback_presets_nao_vazio(self) -> None:
        assert len(FEEDBACK_POSITION_PRESETS) >= 6

    def test_vibration_presets_nao_vazio(self) -> None:
        assert len(VIBRATION_POSITION_PRESETS) >= 5

    def test_labels_feedback_incluem_custom_e_presets(self) -> None:
        chaves_esperadas = set(FEEDBACK_POSITION_PRESETS.keys()) | {"custom"}
        assert chaves_esperadas.issubset(set(FEEDBACK_POSITION_LABELS.keys()))

    def test_labels_vibration_incluem_custom_e_presets(self) -> None:
        chaves_esperadas = set(VIBRATION_POSITION_PRESETS.keys()) | {"custom"}
        assert chaves_esperadas.issubset(set(VIBRATION_POSITION_LABELS.keys()))
