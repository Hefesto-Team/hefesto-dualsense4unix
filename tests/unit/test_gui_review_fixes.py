"""Regressões do review de GUI (bugs/consistência).

Cobre os fixes pure-Python (sem GTK) de maior valor encontrados no review
multi-dimensional da interface:

- BUG-TRIGGER-FLAT-MULTIPOS-01: build_from_name aceita lista posicional PLANA
  para MultiPositionFeedback/Vibration/Custom (antes só nested/dict), e o draft
  faz round-trip por to_profile/from_profile sem perder os params.
- BUG-DELETE-NO-CONFIRM-01 / BUG-RESTORE-DIALOG-WRONG-PROFILE-01: gui_dialogs
  exporta confirm_delete_profile e o texto do restore não cita 'Navegação'.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.draft_config import (
    DraftConfig,
    TriggerDraft,
    TriggersDraft,
)
from hefesto_dualsense4unix.core.trigger_effects import build_from_name


class TestBuildFromNameFlatMultiPos:
    """build_from_name deve aceitar lista posicional plana nos 3 modos especiais."""

    def test_multi_position_feedback_flat(self) -> None:
        eff = build_from_name("MultiPositionFeedback", [0, 1, 2, 3, 4, 5, 6, 7, 8, 0])
        assert eff is not None

    def test_multi_position_vibration_flat(self) -> None:
        # [frequency, s0..s9]
        eff = build_from_name("MultiPositionVibration", [40, 1, 2, 3, 4, 5, 6, 7, 8, 0, 0])
        assert eff is not None

    def test_custom_flat(self) -> None:
        # [mode, f0..f6]
        eff = build_from_name("Custom", [1, 2, 3, 4, 5, 6, 7, 8])
        assert eff.mode == 1

    def test_feedback_flat_invalido_levanta_erro_claro(self) -> None:
        # menos de 10 strengths -> a factory valida e levanta ValueError claro,
        # não um TypeError de factory(*params).
        with pytest.raises(ValueError, match="10 strengths"):
            build_from_name("MultiPositionFeedback", [1, 2, 3])

    def test_retrocompat_nested_e_dict(self) -> None:
        # Os formatos antigos seguem funcionando (sem regressão).
        nested = build_from_name(
            "MultiPositionFeedback", [[1, 1, 1, 1, 1], [2, 2, 2, 2, 2]]
        )
        assert nested is not None
        dict_form = build_from_name("Custom", {"mode": 3, "forces": (0, 0, 0, 0, 0, 0, 0)})
        assert dict_form.mode == 3

    def test_preset_posicional_normal_intacto(self) -> None:
        # Presets de assinatura posicional comum não são afetados.
        eff = build_from_name("Rigid", [5, 200])
        assert eff.mode == 5


class TestDraftMultiPosRoundTrip:
    """Salvar (to_profile) e recarregar (from_profile) preserva os params."""

    def test_multi_position_feedback_roundtrip(self) -> None:
        flat = (0, 1, 2, 3, 4, 5, 6, 7, 8, 0)
        draft = DraftConfig.default().model_copy(
            update={
                "triggers": TriggersDraft(
                    left=TriggerDraft(mode="MultiPositionFeedback", params=flat),
                )
            }
        )
        profile = draft.to_profile("teste_multipos")
        assert tuple(profile.triggers.left.params) == flat

        recovered = DraftConfig.from_profile(profile)
        assert recovered.triggers.left.mode == "MultiPositionFeedback"
        assert recovered.triggers.left.params == flat

    def test_to_ipc_dict_preserva_params_planos(self) -> None:
        flat = (1, 2, 3, 4, 5, 6, 7, 0)  # Custom: [mode, f0..f6]
        draft = DraftConfig.default().model_copy(
            update={
                "triggers": TriggersDraft(
                    right=TriggerDraft(mode="Custom", params=flat),
                )
            }
        )
        ipc = draft.to_ipc_dict()
        assert ipc["triggers"]["right"]["params"] == list(flat)
        # E o daemon consegue construir o efeito a partir desse dict plano.
        eff = build_from_name("Custom", ipc["triggers"]["right"]["params"])
        assert eff.mode == 1


def test_gui_dialogs_confirm_delete_profile_exportado() -> None:
    from hefesto_dualsense4unix.app import gui_dialogs

    assert hasattr(gui_dialogs, "confirm_delete_profile")
    assert "confirm_delete_profile" in gui_dialogs.__all__


def test_restore_dialog_nao_cita_navegacao() -> None:
    # BUG-RESTORE-DIALOG-WRONG-PROFILE-01: o texto EXIBIDO não deve citar o asset
    # errado ('Navegação'). Checa a string passada a format_secondary_text.
    import inspect

    from hefesto_dualsense4unix.app import gui_dialogs

    src = inspect.getsource(gui_dialogs.confirm_restore_default)
    # A frase enganosa antiga sumiu e a correta está presente.
    assert "cópia original (Navegação)" not in src
    assert "aplica-se a todos os apps" in src
