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

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("footer restore default")

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import (
    FooterActionsMixin,
    _meu_perfil_asset,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Executa ``ipc_bridge.run_in_thread`` de forma síncrona nos testes.

    PERF-FOOTER-ASYNC-IO-01 moveu o I/O de disco do ``on_restore_default`` para um
    worker; sem loop GTK nos testes, rodamos worker + callback na mesma thread.
    """
    from typing import Any

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            result = fn()
        except Exception as exc:  # espelha o run_in_thread real
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(result)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


@pytest.fixture
def asset_content() -> dict:  # type: ignore[type-arg]
    """Conteúdo canônico do asset meu_perfil.json.

    CI-SMOKE-SEM-ASSETS-01: o caminho é resolvido a partir do `__file__` do
    PACOTE, então no smoke multi-distro — onde o hefesto vem de um wheel
    instalado em `/usr/local/lib/...` e os `assets/` não são empacotados — o
    arquivo não existe e o teste morria com `FileNotFoundError` em vez de
    pular. Sem o asset do repositório não há contrato a verificar aqui: o que
    este teste trava é que o restore devolve EXATAMENTE o conteúdo do asset.

    JANELA-FIEL-01/E3: quem resolve o caminho passou a ser `_meu_perfil_asset()`
    (a cascata do loader), então o skip pergunta a ELA — e não a uma constante
    de módulo que só valia em instalação editável.
    """
    asset = _meu_perfil_asset()
    if asset is None:
        pytest.skip("preset meu_perfil.json ausente em todos os candidatos")
    return json.loads(asset.read_text(encoding="utf-8"))


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

        import hefesto_dualsense4unix.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = True

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs):
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
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        draft_antes = stub_mixin.draft

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = True

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        assert stub_mixin.draft is not draft_antes

    def test_toast_exibido_apos_restaurar(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Statusbar deve receber mensagem mencionando meu_perfil."""
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = True

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs):
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
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        destino = profiles_dir_isolado / "meu_perfil.json"
        destino.write_text(json.dumps(_perfil_modificado()), encoding="utf-8")

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = False

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        resultado = json.loads(destino.read_text(encoding="utf-8"))
        assert resultado["priority"] == 99  # não foi alterado

    def test_asset_ausente_exibe_toast_sem_crash(
        self,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Quando o preset não existe em candidato NENHUM, toast — sem exceção.

        JANELA-FIEL-01/E3: a injeção é a cascata do loader, não mais uma
        constante de módulo. Um diretório vazio como único candidato é
        exatamente "não há preset em lugar nenhum".
        """
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod,
            "_DEFAULT_SEED_SOURCE_DIRS",
            (profiles_dir_isolado / "sem_assets",),
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
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = False

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        assert any("cancelad" in msg.lower() for msg in stub_mixin._toasted)


# ---------------------------------------------------------------------------
# JANELA-FIEL-01/E3 — o botão fora da máquina de quem programou
# ---------------------------------------------------------------------------


class TestRestoreDefaultEmInstalacaoEmpacotada:
    """O preset não mora só no repositório — e o botão tem de achá-lo lá.

    `_MEU_PERFIL_ASSET` era `ROOT_DIR / "assets" / ...`, e `ROOT_DIR` é
    `parents[3]` do módulo: a raiz do repositório SÓ em instalação editável
    (`install.sh` instala com `-e`). Num `.deb` o pacote vive num venv em
    `/opt/...`, o módulo em `.../site-packages/hefesto_dualsense4unix/app/`, e
    `parents[3]` vira `.../venv/lib/python3.X` — um diretório onde `assets/`
    nunca existiu. O botão desistia com o toast de indisponível numa máquina
    onde o preset ESTÁ instalado: os três pacotes o embalam (`.deb` em
    `/usr/share/...`, AppImage e Flatpak em `sys.prefix/share/...`).

    MORDIDA: os testes abaixo põem o preset SÓ no segundo e no terceiro
    candidato da cascata — nunca no primeiro, que é o do repositório. Com o
    resolvedor de antes (um candidato só, o `ROOT_DIR`), os dois reprovam com o
    toast de "não encontrado" e sem gravar nada.
    """

    @staticmethod
    def _cascata_empacotada(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, com_preset: int
    ) -> Path:
        """Planta o preset no candidato `com_preset` (1=prefixo, 2=/usr/share).

        O candidato 0 (repositório) NÃO existe — é a instalação empacotada.
        """
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        candidatos = [
            tmp_path / "venv" / "lib" / "python3" / "assets" / "profiles_default",
            tmp_path / "prefixo" / "share" / "hefesto" / "profiles_default",
            tmp_path / "usr" / "share" / "hefesto" / "profiles_default",
        ]
        destino = candidatos[com_preset]
        destino.mkdir(parents=True)
        conteudo = _perfil_modificado()
        conteudo["priority"] = 42
        (destino / "meu_perfil.json").write_text(
            json.dumps(conteudo), encoding="utf-8"
        )
        monkeypatch.setattr(
            loader_mod, "_DEFAULT_SEED_SOURCE_DIRS", tuple(candidatos)
        )
        return destino

    @pytest.mark.parametrize("candidato", [1, 2])
    def test_restaura_com_o_preset_fora_do_repositorio(
        self,
        candidato: int,
        stub_mixin: FooterActionsMixin,
        profiles_dir_isolado: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        self._cascata_empacotada(monkeypatch, tmp_path, candidato)
        monkeypatch.setattr(
            loader_mod, "profiles_dir", lambda ensure=False: profiles_dir_isolado
        )

        mock_dialogs = MagicMock()
        mock_dialogs.confirm_restore_default.return_value = True

        with patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs):
            stub_mixin.on_restore_default()

        destino = profiles_dir_isolado / "meu_perfil.json"
        assert destino.is_file(), "o botão morre em instalação não-editável"
        assert json.loads(destino.read_text(encoding="utf-8"))["priority"] == 42
        assert not any("não encontrado" in msg for msg in stub_mixin._toasted)
