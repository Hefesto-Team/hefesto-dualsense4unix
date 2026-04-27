"""Testes unitários do FooterActionsMixin (UI-GLOBAL-FOOTER-ACTIONS-01).

Cobre:
  - on_apply_draft: chama ipc_bridge.call_async com método e draft_dict corretos.
  - on_save_profile: chama save_profile e recarrega lista de perfis.
  - on_import_profile: valida JSON, copia para profiles_dir.
  - _freeze_ui: seta sensitive nos widgets de FROZEN_WIDGET_IDS.

Não requer GTK instalado: usa mocks para todos os widgets e diálogos.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from hefesto_dualsense4unix.app.actions.footer_actions import FROZEN_WIDGET_IDS, FooterActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub() -> FooterActionsMixin:
    """Constrói instância stub de FooterActionsMixin com builder mock."""

    class _Stub(FooterActionsMixin):
        def __init__(self) -> None:
            self.draft = DraftConfig.default()
            self._reloaded: list[str | None] = []
            self._toasted: list[str] = []

        def _reload_profiles_store(self, select_name: str | None = None) -> None:
            self._reloaded.append(select_name)

        def _footer_toast(self, msg: str, context: str = "footer") -> None:
            self._toasted.append(msg)

    stub = _Stub()
    widget_mock = MagicMock()
    builder = MagicMock()
    builder.get_object.return_value = widget_mock
    stub.builder = builder
    return stub


def _make_profile(name: str = "teste") -> Profile:
    return Profile(name=name, version=1, match=MatchAny(), priority=0)


# ---------------------------------------------------------------------------
# _freeze_ui
# ---------------------------------------------------------------------------


class TestFreezeUi:
    def test_freeze_true_chama_set_sensitive_false(self) -> None:
        stub = _make_stub()
        widget_mock = MagicMock()
        stub.builder.get_object.return_value = widget_mock

        stub._freeze_ui(True)

        assert widget_mock.set_sensitive.call_count == len(FROZEN_WIDGET_IDS)
        for c in widget_mock.set_sensitive.call_args_list:
            assert c == call(False)

    def test_freeze_false_chama_set_sensitive_true(self) -> None:
        stub = _make_stub()
        widget_mock = MagicMock()
        stub.builder.get_object.return_value = widget_mock

        stub._freeze_ui(False)

        for c in widget_mock.set_sensitive.call_args_list:
            assert c == call(True)

    def test_widget_ausente_ignorado_sem_excecao(self) -> None:
        stub = _make_stub()
        stub.builder.get_object.return_value = None
        # Não deve lançar exceção
        stub._freeze_ui(True)


# ---------------------------------------------------------------------------
# on_apply_draft
# ---------------------------------------------------------------------------


class TestOnApplyDraft:
    def test_chama_call_async_com_metodo_correto(self) -> None:
        stub = _make_stub()
        capturado: dict[str, Any] = {}

        def fake_call_async(method, params, on_success, on_failure=None, timeout_s=1.5):
            capturado["method"] = method
            capturado["params"] = params
            on_success(True)

        with patch(
            "hefesto_dualsense4unix.app.actions.footer_actions.ipc_bridge"
        ) as mock_ipc:
            mock_ipc.call_async.side_effect = fake_call_async
            stub.on_apply_draft()

        assert capturado.get("method") == "profile.apply_draft"
        assert "triggers" in capturado.get("params", {})
        assert "leds" in capturado.get("params", {})

    def test_congela_e_descongela_apos_sucesso(self) -> None:
        stub = _make_stub()
        sensitive_calls: list[bool] = []
        widget_mock = MagicMock()
        widget_mock.set_sensitive.side_effect = lambda v: sensitive_calls.append(v)
        stub.builder.get_object.return_value = widget_mock

        def fake_call_async(method, params, on_success, on_failure=None, timeout_s=1.5):
            on_success({"status": "ok"})

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.ipc_bridge") as mock_ipc:
            mock_ipc.call_async.side_effect = fake_call_async
            stub.on_apply_draft()

        assert False in sensitive_calls   # congelou
        assert True in sensitive_calls    # descongelou

    def test_descongela_apos_erro(self) -> None:
        stub = _make_stub()
        sensitive_calls: list[bool] = []
        widget_mock = MagicMock()
        widget_mock.set_sensitive.side_effect = lambda v: sensitive_calls.append(v)
        stub.builder.get_object.return_value = widget_mock

        def fake_call_async(method, params, on_success, on_failure=None, timeout_s=1.5):
            if on_failure is not None:
                on_failure(ConnectionError("daemon offline"))

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.ipc_bridge") as mock_ipc:
            mock_ipc.call_async.side_effect = fake_call_async
            stub.on_apply_draft()

        assert True in sensitive_calls


# ---------------------------------------------------------------------------
# on_save_profile
# ---------------------------------------------------------------------------


class TestOnSaveProfile:
    def test_salva_e_recarrega_lista(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub = _make_stub()
        salvo: list[str] = []

        def fake_save(profile: Profile) -> Path:
            salvo.append(profile.name)
            return Path(f"/tmp/{profile.name}.json")

        mock_dialogs = MagicMock()
        mock_dialogs.prompt_profile_name.return_value = "novo_perfil"
        mock_dialogs.prompt_overwrite_existing.return_value = True

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch("hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles", return_value=[]),  # noqa: E501
            patch("hefesto_dualsense4unix.app.actions.footer_actions.save_profile", side_effect=fake_save),  # noqa: E501
        ):
            stub.on_save_profile()

        assert "novo_perfil" in salvo
        assert "novo_perfil" in stub._reloaded

    def test_cancela_se_usuario_nao_digitar_nome(self) -> None:
        stub = _make_stub()

        mock_dialogs = MagicMock()
        mock_dialogs.prompt_profile_name.return_value = None

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch("hefesto_dualsense4unix.app.actions.footer_actions.save_profile") as mock_save,
        ):
            stub.on_save_profile()
            assert not mock_save.called

    def test_nao_salva_se_usuario_recusa_sobrescrita(self) -> None:
        stub = _make_stub()
        perfil_existente = _make_profile("existente")

        mock_dialogs = MagicMock()
        mock_dialogs.prompt_profile_name.return_value = "existente"
        mock_dialogs.prompt_overwrite_existing.return_value = False

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch(
                "hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles",
                return_value=[perfil_existente],
            ),
            patch("hefesto_dualsense4unix.app.actions.footer_actions.save_profile") as mock_save,
        ):
            stub.on_save_profile()
            assert not mock_save.called

    def test_toast_confirmacao_exibido(self) -> None:
        stub = _make_stub()

        def fake_save(profile: Profile) -> Path:
            return Path(f"/tmp/{profile.name}.json")

        mock_dialogs = MagicMock()
        mock_dialogs.prompt_profile_name.return_value = "meu_novo"
        mock_dialogs.prompt_overwrite_existing.return_value = True

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch("hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles", return_value=[]),  # noqa: E501
            patch("hefesto_dualsense4unix.app.actions.footer_actions.save_profile", side_effect=fake_save),  # noqa: E501
        ):
            stub.on_save_profile()

        assert any("meu_novo" in msg for msg in stub._toasted)
