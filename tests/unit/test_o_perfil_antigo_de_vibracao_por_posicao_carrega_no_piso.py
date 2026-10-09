"""O perfil antigo de vibração por posição carrega no piso.

O-PERFIL-ANTIGO-DE-VIBRACAO-POR-POSICAO-CARREGA-NO-PISO-01 (09/10/2026). Desde a gatilho-1-13,
``multi_position_vibration`` recusa frequência 0 com alguma amplitude (o controle lê o bloco
como desligado). Um perfil gravado antes disso passava na validação e só explodia no
``build_from_name`` do ``apply()``, e o perfil inteiro deixava de aplicar por causa de um
gatilho. A cura mora no ``TriggerConfig`` (onde o perfil nasce): a frequência 0 com amplitude vira
40, sem aviso. O construtor continua recusando.

TUDO É DE MENTIRA: só objetos em memória; nada chega a daemon nem ao aparelho.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.trigger_effects import (
    FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO,
    build_from_name,
    multi_position_vibration,
)
from hefesto_dualsense4unix.profiles.manager import _controllers_to_specs
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

AMPLITUDES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 8]
MODO = "MultiPositionVibration"


def _velho() -> list[int]:
    return [0, *AMPLITUDES]


def test_a_frequencia_zero_com_amplitude_carrega_com_quarenta() -> None:
    tc = TriggerConfig(mode=MODO, params=_velho())
    assert tc.params == [FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO, *AMPLITUDES]
    assert FREQUENCIA_PADRAO_DA_VIBRACAO_POR_POSICAO == 40
    build_from_name(tc.mode, tc.params)


def test_o_gatilho_global_do_perfil_aplica() -> None:
    perfil = Profile(
        name="antigo",
        match={"type": "any"},
        triggers=TriggersConfig(left=TriggerConfig(mode=MODO, params=_velho()),
                                right=TriggerConfig(mode="Off", params=[])),
    )
    efeito = build_from_name(perfil.triggers.left.mode, perfil.triggers.left.params)
    assert efeito == multi_position_vibration(40, AMPLITUDES)


def test_o_gatilho_de_cada_controle_aplica() -> None:
    sobre = ControllerOverrides(triggers=TriggersConfig(
        left=TriggerConfig(mode=MODO, params=_velho()),
        right=TriggerConfig(mode=MODO, params=_velho())))
    specs = _controllers_to_specs({"aa:bb:cc:00:00:01": sobre})
    spec = specs["aa:bb:cc:00:00:01"]
    assert spec.trigger_left == multi_position_vibration(40, AMPLITUDES)
    assert spec.trigger_right == multi_position_vibration(40, AMPLITUDES)


def test_o_perfil_lido_do_json_antigo_carrega_no_piso() -> None:
    """O caminho do disco: o JSON gravado antes passa pela mesma validação."""
    tc = TriggerConfig.model_validate_json(
        '{"mode": "MultiPositionVibration", "params": [0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0]}')
    assert tc.params[0] == 40 and tc.params[1:] == [0, 0, 5, 0, 0, 0, 0, 0, 0, 0]


def test_frequencia_zero_com_todas_as_amplitudes_zero_fica_como_esta() -> None:
    tc = TriggerConfig(mode=MODO, params=[0, *([0] * 10)])
    assert tc.params == [0, *([0] * 10)]
    build_from_name(tc.mode, tc.params)


@pytest.mark.parametrize("frequencia", [1, 40, 120, 255])
def test_frequencia_nao_zero_fica_como_esta(frequencia: int) -> None:
    tc = TriggerConfig(mode=MODO, params=[frequencia, *AMPLITUDES])
    assert tc.params == [frequencia, *AMPLITUDES]


def test_o_formato_aninhado_nao_muda_e_ja_sai_com_quarenta() -> None:
    aninhado = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
    tc = TriggerConfig(mode=MODO, params=aninhado)
    assert tc.params == aninhado
    assert build_from_name(tc.mode, tc.params) == multi_position_vibration(40, AMPLITUDES)


def test_outro_modo_com_zero_na_primeira_casa_nao_e_tocado() -> None:
    tc = TriggerConfig(mode="MultiPositionFeedback", params=[*AMPLITUDES])
    assert tc.params == AMPLITUDES
    tc2 = TriggerConfig(mode="Rigid", params=[0, 200])
    assert tc2.params == [0, 200]


def test_o_construtor_continua_recusando_quem_o_chama_direto() -> None:
    with pytest.raises(ValueError, match="frequency 0"):
        multi_position_vibration(0, AMPLITUDES)
