"""Testes do schema `TriggerConfig.params` aceitando formato aninhado.

Cobre SCHEMA-MULTI-POSITION-PARAMS-01:
  - aceita `list[int]` (backcompat)
  - aceita `list[list[int]]` (novo, para MultiPositionFeedback/Vibration)
  - rejeita misturas (`[[1, 2], 3]`)
  - `is_nested` reflete o formato
  - roundtrip JSON preserva aninhado
  - `build_from_name` com aninhado retorna factory correta
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core.trigger_effects import (
    TriggerMode,
    _flatten_multi_position,
    build_from_name,
)
from hefesto_dualsense4unix.profiles.schema import TriggerConfig


class TestValidatorParams:
    def test_aceita_simples(self) -> None:
        tc = TriggerConfig(mode="Rigid", params=[5, 200])
        assert tc.params == [5, 200]
        assert tc.is_nested is False

    def test_aceita_aninhado_10(self) -> None:
        nested = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
        tc = TriggerConfig(mode="MultiPositionFeedback", params=nested)
        assert tc.params == nested
        assert tc.is_nested is True

    def test_aceita_aninhado_5(self) -> None:
        nested = [[0, 1], [2, 3], [4, 5], [6, 7], [8, 8]]
        tc = TriggerConfig(mode="MultiPositionFeedback", params=nested)
        assert tc.is_nested is True

    def test_aceita_aninhado_2(self) -> None:
        nested = [[0, 1, 2, 3, 4], [5, 6, 7, 8, 8]]
        tc = TriggerConfig(mode="MultiPositionFeedback", params=nested)
        assert tc.is_nested is True

    def test_aceita_vazio(self) -> None:
        tc = TriggerConfig(mode="Off", params=[])
        assert tc.params == []
        assert tc.is_nested is False

    def test_rejeita_misto_simples_com_lista(self) -> None:
        with pytest.raises(ValidationError) as exc:
            TriggerConfig(mode="MultiPositionFeedback", params=[[1, 2], 3])
        msg = str(exc.value)
        assert "aninhado" in msg or "list[int]" in msg

    def test_rejeita_misto_lista_com_simples(self) -> None:
        with pytest.raises(ValidationError):
            TriggerConfig(mode="Rigid", params=[5, [1, 2]])

    def test_is_nested_false_para_simples(self) -> None:
        tc = TriggerConfig(mode="Rigid", params=[5, 200])
        assert tc.is_nested is False


class TestRoundtripJSON:
    def test_simples_roundtrip(self) -> None:
        tc = TriggerConfig(mode="Galloping", params=[0, 9, 7, 7, 10])
        raw = json.dumps(tc.model_dump())
        restored = TriggerConfig.model_validate(json.loads(raw))
        assert restored.params == tc.params
        assert restored.is_nested is False

    def test_aninhado_roundtrip_10(self) -> None:
        nested = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
        tc = TriggerConfig(mode="MultiPositionFeedback", params=nested)
        raw = json.dumps(tc.model_dump())
        restored = TriggerConfig.model_validate(json.loads(raw))
        assert restored.params == nested
        assert restored.is_nested is True


class TestFlattenMultiPosition:
    def test_flatten_10_sublistas(self) -> None:
        nested = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
        flat = _flatten_multi_position(nested)
        assert flat == [0, 1, 2, 3, 4, 5, 6, 7, 8, 8]

    def test_flatten_5_sublistas_pares(self) -> None:
        nested = [[0, 1], [2, 3], [4, 5], [6, 7], [8, 8]]
        flat = _flatten_multi_position(nested)
        assert flat == [0, 1, 2, 3, 4, 5, 6, 7, 8, 8]

    def test_flatten_2_sublistas_quintas(self) -> None:
        nested = [[0, 1, 2, 3, 4], [5, 6, 7, 8, 8]]
        flat = _flatten_multi_position(nested)
        assert flat == [0, 1, 2, 3, 4, 5, 6, 7, 8, 8]

    def test_flatten_rejeita_3_sublistas(self) -> None:
        with pytest.raises(ValueError, match="dimensão 3"):
            _flatten_multi_position([[0], [1], [2]])

    def test_flatten_rejeita_7_sublistas(self) -> None:
        with pytest.raises(ValueError, match="dimensão 7"):
            _flatten_multi_position([[0]] * 7)

    def test_flatten_rejeita_11_sublistas(self) -> None:
        with pytest.raises(ValueError, match="dimensão 11"):
            _flatten_multi_position([[0]] * 11)

    def test_flatten_5_valida_tamanho_sublista(self) -> None:
        with pytest.raises(ValueError, match="precisa exatamente 2"):
            _flatten_multi_position([[0], [1, 2], [3, 4], [5, 6], [7, 8]])

    def test_flatten_2_valida_tamanho_sublista(self) -> None:
        with pytest.raises(ValueError, match="precisa exatamente 5"):
            _flatten_multi_position([[0, 1, 2], [3, 4, 5, 6, 7]])

    def test_flatten_10_rejeita_sublista_vazia(self) -> None:
        with pytest.raises(ValueError, match="vazia"):
            _flatten_multi_position([[0], [], [2], [3], [4], [5], [6], [7], [8], [8]])


class TestBuildFromNameAninhado:
    def test_multi_position_feedback_10(self) -> None:
        nested = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
        effect = build_from_name("MultiPositionFeedback", nested)
        # RIGID_AB = 0x01 | 0x20 | 0x04 = 0x25 = 37
        # TRIGGER-CANON-01 (01/08/2026): o modo mudou porque o antigo NÃO
        # FUNCIONAVA — medido pelo tato dela. Ver `test_trigger_canon_01.py`.
        assert effect.mode == TriggerMode.FEEDBACK
        # 7 forces (packed bits)
        assert len(effect.forces) == 7

    def test_multi_position_feedback_5(self) -> None:
        nested = [[0, 1], [2, 3], [4, 5], [6, 7], [8, 8]]
        effect = build_from_name("MultiPositionFeedback", nested)
        # TRIGGER-CANON-01 (01/08/2026): o modo mudou porque o antigo NÃO
        # FUNCIONAVA — medido pelo tato dela. Ver `test_trigger_canon_01.py`.
        assert effect.mode == TriggerMode.FEEDBACK

    def test_multi_position_vibration_10(self) -> None:
        nested = [[0], [0], [5], [5], [5], [8], [8], [8], [8], [8]]
        effect = build_from_name("MultiPositionVibration", nested)
        # PULSE_A = 0x02 | 0x20 = 0x22 = 34
        # TRIGGER-CANON-01 (01/08/2026): o modo mudou porque o antigo NÃO
        # FUNCIONAVA — medido pelo tato dela. Ver `test_trigger_canon_01.py`.
        assert effect.mode == TriggerMode.VIBRATION
        # TRIGGER-CANON-01: a frequência mora no byte 9 do bloco, que é
        # `forces[6]` — antes ela era escrita em `forces[0]`, que no modo
        # oficial é a metade baixa do BITMASK DE ZONAS. Ou seja: a frequência
        # pedida virava zonas ativas, e as zonas pedidas não chegavam.
        assert effect.forces[6] == 0, "frequency default = 0 no formato aninhado"

    def test_simples_ainda_funciona(self) -> None:
        """Backcompat: list[int] no formato antigo continua válido."""
        effect = build_from_name("Galloping", [0, 9, 7, 7, 10])
        assert effect.forces == (0, 9, 7, 7, 10, 0, 0)

    def test_aninhado_rejeita_em_modo_nao_multi(self) -> None:
        with pytest.raises(ValueError, match="aninhado só é aceito"):
            build_from_name("Rigid", [[5], [200]])

    def test_dict_ainda_funciona(self) -> None:
        """Backcompat: dict nomeado continua válido.

        O que este teste trava é o CAMINHO (dict é aceito), não os bytes —
        estes mudaram na TRIGGER-CANON-01, porque os antigos mandavam `0x05`,
        que é o OFF do bloco de gatilho. A igualdade é contra a factory, e não
        contra literais: quem trava os bytes do `Rigid` é o
        `test_trigger_effects.py`, num lugar só.
        """
        from hefesto_dualsense4unix.core.trigger_effects import rigid

        effect = build_from_name("Rigid", {"position": 5, "force": 200})
        assert effect.forces == rigid(5, 200).forces
        assert effect.mode == TriggerMode.FEEDBACK
