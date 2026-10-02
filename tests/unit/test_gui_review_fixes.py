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

from types import SimpleNamespace

import pytest

from tests.conftest import skip_sem_gi_real
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
        eff = build_from_name("MultiPositionVibration", [40, 1, 2, 3, 4, 5, 6, 7, 8, 0, 0])
        assert eff is not None

    def test_custom_flat(self) -> None:
        eff = build_from_name("Custom", [1, 2, 3, 4, 5, 6, 7, 8])
        assert eff.mode == 1

    def test_feedback_flat_invalido_levanta_erro_claro(self) -> None:
        with pytest.raises(ValueError, match="10 strengths"):
            build_from_name("MultiPositionFeedback", [1, 2, 3])

    def test_retrocompat_nested_e_dict(self) -> None:
        nested = build_from_name(
            "MultiPositionFeedback", [[1, 1, 1, 1, 1], [2, 2, 2, 2, 2]]
        )
        assert nested is not None
        dict_form = build_from_name("Custom", {"mode": 3, "forces": (0, 0, 0, 0, 0, 0, 0)})
        assert dict_form.mode == 3

    def test_preset_posicional_normal_intacto(self) -> None:
        from hefesto_dualsense4unix.core.trigger_effects import rigid

        eff = build_from_name("Rigid", [5, 200])
        assert eff.mode == rigid(5, 200).mode
        assert eff.forces == rigid(5, 200).forces


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
        flat = (1, 2, 3, 4, 5, 6, 7, 0)
        draft = DraftConfig.default().model_copy(
            update={
                "triggers": TriggersDraft(
                    right=TriggerDraft(mode="Custom", params=flat),
                )
            }
        )
        ipc = draft.to_ipc_dict()
        assert ipc["triggers"]["right"]["params"] == list(flat)
        eff = build_from_name("Custom", ipc["triggers"]["right"]["params"])
        assert eff.mode == 1


@skip_sem_gi_real
def test_gui_dialogs_confirm_delete_profile_exportado() -> None:
    from hefesto_dualsense4unix.app import gui_dialogs

    assert hasattr(gui_dialogs, "confirm_delete_profile")
    assert "confirm_delete_profile" in gui_dialogs.__all__


@skip_sem_gi_real
def test_restore_dialog_nao_cita_navegacao(monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-RESTORE-DIALOG-WRONG-PROFILE-01: o texto EXIBIDO não cita 'Navegação'."""
    from hefesto_dualsense4unix.app import gui_dialogs

    exibidos: list[str] = []

    class _DialogoFalso:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def format_secondary_text(self, texto: str) -> None:
            exibidos.append(texto)

        def add_button(self, *_args: object) -> None:
            pass

        def set_default_response(self, *_args: object) -> None:
            pass

        def run(self) -> object:
            return gui_dialogs.Gtk.ResponseType.CANCEL

        def destroy(self) -> None:
            pass

    gtk_falso = SimpleNamespace(
        MessageDialog=_DialogoFalso,
        MessageType=gui_dialogs.Gtk.MessageType,
        ButtonsType=gui_dialogs.Gtk.ButtonsType,
        ResponseType=gui_dialogs.Gtk.ResponseType,
    )
    monkeypatch.setattr(gui_dialogs, "Gtk", gtk_falso)

    assert gui_dialogs.confirm_restore_default(None) is False

    (secundario,) = exibidos
    assert "Navegação" not in secundario
    from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO

    assert f"'{NOME_DO_PADRAO}'" in secundario
    assert "Personalizado" not in secundario
    assert "meu_perfil" not in secundario
    assert "aplica-se a todos os apps" in secundario
