"""Testes de restore_default do FooterActionsMixin (UI-GLOBAL-FOOTER-ACTIONS-01).

Cenários:
  - tmp_path como profiles_dir substituto.
  - meu_perfil.json modificado em profiles_dir.
  - on_restore_default com asset presente e confirmação simulada restaura
    o conteúdo ao estado do asset.
  - self.draft é recarregado após restaurar.
  - Confirmação cancelada não altera o perfil.
  - Asset ausente exibe toast de erro sem lançar exceção.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hefesto.app.actions.footer_actions import _MEU_PERFIL_ASSET, FooterActionsMixin
from hefesto.app.draft_config import DraftConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def asset_content() -> dict:  # type: ignore[type-arg]
    """Conteúdo canônico do asset meu_perfil.json."""
    return json.loads(_MEU_PERFIL_ASSET.read_text(encoding="utf-8"))


@pytest.fixture
def profiles_dir_isolado(tmp_path: Path) -> Path:
    d = tmp_path / "profiles"
    d.mkdir()
    return d


@pytest.fixture
def stub_mixin(profiles_dir_isolado: Path) -> FooterActionsMixin:
    """Stub de FooterActionsMixin com builder mock e _footer_toast capturado."""

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
    builder = MagicMock()
    builder.get_object.return_value = MagicMock()
    stub.builder = builder
    return stub


def _perfil_modificado() -> dict:  # type: ignore[type-arg]
    """Retorna um dict de perfil com priority diferente do asset (99)."""
    return {
        "name": "meu_perfil",
        "version": 1,
        "match": {"type": "any"},
        "priority": 99,
        "triggers": {
            "left": {"mode": "Rigid", "params": [5, 5]},
            "right": {"mode": "Rigid", "params": [5, 5]},
        },
        "leds": {
            "lightbar": [255, 0, 0],
            "player_leds": [True, True, True, True, True],
            "lightbar_brightness": 0.5,
        },
        "rumble": {"passthrough": False},
    }


# ---------------------------------------------------------------------------
# Fluxo feliz
# ---------------------------------------------------------------------------


class TestRestoreDefault:
    def test_restaura_conteudo_do_asset(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        asset_content: dict,  # type: ignore[type-arg]
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Conteúdo de meu_perfil.json em profiles_dir deve voltar ao asset."""
        destino = profiles_dir_isolado / "meu_perfil.json"
        destino.write_text(json.dumps(_perfil_modificado()), encoding="utf-8")

        import hefesto.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = True

        with patch("hefesto.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        resultado = json.loads(destino.read_text(encoding="utf-8"))
        assert resultado["priority"] == asset_content["priority"]
        assert resultado["leds"]["lightbar"] == asset_content["leds"]["lightbar"]

    def test_draft_recarregado_apos_restore(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """self.draft deve ser substituído pelo perfil restaurado."""
        import hefesto.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        draft_antes = stub_mixin.draft

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = True

        with patch("hefesto.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        assert stub_mixin.draft is not draft_antes

    def test_toast_exibido_apos_restaurar(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Statusbar deve receber mensagem mencionando meu_perfil."""
        import hefesto.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = True

        with patch("hefesto.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        assert any("meu_perfil" in msg for msg in stub_mixin._toasted)


# ---------------------------------------------------------------------------
# Casos de borda
# ---------------------------------------------------------------------------


class TestRestoreDefaultCasosDeBorda:
    def test_cancela_se_usuario_recusa(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Perfil não deve ser alterado se usuário cancelar o diálogo."""
        import hefesto.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        destino = profiles_dir_isolado / "meu_perfil.json"
        destino.write_text(json.dumps(_perfil_modificado()), encoding="utf-8")

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = False

        with patch("hefesto.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        resultado = json.loads(destino.read_text(encoding="utf-8"))
        assert resultado["priority"] == 99  # não foi alterado

    def test_asset_ausente_exibe_toast_sem_crash(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Quando asset não existe, exibe toast e não lança exceção."""
        import hefesto.app.actions.footer_actions as footer_mod

        monkeypatch.setattr(
            footer_mod,
            "_MEU_PERFIL_ASSET",
            profiles_dir_isolado / "nao_existe.json",
        )

        stub_mixin.on_restore_default()

        assert any(
            "indisponível" in msg or "ausente" in msg or "não encontrado" in msg
            for msg in stub_mixin._toasted
        )

    def test_toast_cancelamento(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Deve exibir toast de cancelamento quando usuário recusa."""
        import hefesto.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = False

        with patch("hefesto.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        assert any("cancelad" in msg.lower() for msg in stub_mixin._toasted)
