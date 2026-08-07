"""Testes unitários do FooterActionsMixin (UI-GLOBAL-FOOTER-ACTIONS-01).

Cobre:
  - on_apply_draft: chama ipc_bridge.call_async com método e draft_dict corretos.
  - on_save_profile: chama save_profile e recarrega lista de perfis.
  - on_import_profile: valida JSON, copia para profiles_dir.
  - _freeze_ui: seta sensitive nos widgets de FROZEN_WIDGET_IDS.

Não requer GTK instalado: usa mocks para todos os widgets e diálogos.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("footer actions")

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import FROZEN_WIDGET_IDS, FooterActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Executa ``ipc_bridge.run_in_thread`` de forma síncrona nos testes.

    PERF-FOOTER-ASYNC-IO-01 moveu o I/O de disco dos handlers do rodapé para um
    worker (``run_in_thread`` + ``GLib.idle_add``). Sem um loop GTK rodando nos
    testes unit, os callbacks nunca executariam — então rodamos o worker e o
    callback na mesma thread, preservando a semântica observável.
    """

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            result = fn()
        except Exception as exc:  # espelha o run_in_thread real
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(result)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


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

        def fake_save(profile: Profile, *, origem: str | None = None) -> Path:
            # `origem` espelha a assinatura real de `save_profile`.
            salvo.append(profile.name)
            return Path(f"/tmp/{profile.name}.json")

        mock_dialogs = MagicMock()
        mock_dialogs.prompt_profile_name.return_value = "novo_perfil"
        mock_dialogs.prompt_overwrite_existing.return_value = True

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch("hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles", return_value=[]),  # noqa: E501
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile", side_effect=fake_save),  # noqa: E501
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
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile") as mock_save,
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
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile") as mock_save,
        ):
            stub.on_save_profile()
            assert not mock_save.called

    def test_toast_confirmacao_exibido(self) -> None:
        stub = _make_stub()

        def fake_save(profile: Profile, *, origem: str | None = None) -> Path:
            return Path(f"/tmp/{profile.name}.json")

        mock_dialogs = MagicMock()
        mock_dialogs.prompt_profile_name.return_value = "meu_novo"
        mock_dialogs.prompt_overwrite_existing.return_value = True

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch("hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles", return_value=[]),  # noqa: E501
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile", side_effect=fake_save),  # noqa: E501
        ):
            stub.on_save_profile()

        assert any("meu_novo" in msg for msg in stub._toasted)


# ---------------------------------------------------------------------------
# JANELA-FIEL-01/E4 — o conflito de perfil é por SLUG, não por nome cru
# ---------------------------------------------------------------------------


class TestSaveProfileConflitoPorSlug:
    """R-10 (auditoria 23/07): a identidade de um perfil em disco é o SLUG.

    `save_profile` grava `<slugify(name)>.json`, e o `slugify` tira acento e
    baixa a caixa. O gate deste rodapé comparava STRING CRUA, então digitar
    "Navegacao" com a "Navegação" dela em disco (prioridade 50, com regra de
    janela e de processo) não casava: o diálogo de sobrescrita não aparecia e
    `navegacao.json` era regravado em silêncio — com `MatchAny()` e prioridade
    recalculada, virando um catch-all a mais, que é a doença da
    AUTOMATISMO-MORTO-01. Cinco dos quinze perfis dela colidem por acento ou
    por caixa.

    NOTA DATADA — 06/08/2026: o número caducou; a frase, não. São 13 arquivos
    hoje e nove nomes cujo slug difere. E "colidir" aqui nunca significou perfil
    contra perfil — significa que uma variante digitada cai em cima do arquivo
    que já existe. A conta está na JANELA-FIEL-01. O que este teste mede não
    mudou: o gate compara nome cru, e é isso que ele morde.

    MORDIDA: os testes de hoje só exercitavam nome IDÊNTICO ("existente" contra
    "existente"), que passa com a cura arrancada. Aqui o par é acentuado contra
    sem acento (e maiúscula contra minúscula): com `nome in existentes` de
    volta, o diálogo nunca é chamado e o `save_profile` é — reprova nas duas.
    """

    @staticmethod
    def _dialogos(resposta: bool) -> MagicMock:
        mock_dialogs = MagicMock()
        mock_dialogs.prompt_overwrite_existing.return_value = resposta
        return mock_dialogs

    @pytest.mark.parametrize(
        ("em_disco", "digitado"),
        [
            ("Navegação", "Navegacao"),
            ("Navegação", "navegação"),
            ("FPS", "fps"),
            ("Ação", "acao"),  # sem acento é o ponto do caso (noqa-acento)
            ("Meu Perfil", "meu-perfil"),
        ],
    )
    def test_pergunta_antes_de_sobrescrever_quem_disputa_o_arquivo(
        self, em_disco: str, digitado: str
    ) -> None:
        stub = _make_stub()
        mock_dialogs = self._dialogos(False)
        mock_dialogs.prompt_profile_name.return_value = digitado

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch(
                "hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles",
                return_value=[_make_profile(em_disco)],
            ),
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile") as mock_save,
        ):
            stub.on_save_profile()

        assert mock_dialogs.prompt_overwrite_existing.called, (
            "o arquivo dela seria regravado sem uma pergunta"
        )
        assert not mock_save.called, "recusar a sobrescrita não pode gravar nada"

    def test_o_dialogo_cita_o_perfil_do_disco_e_nao_o_digitado(self) -> None:
        """Quem some é a "Navegação" dela — o diálogo tem de dizer o nome dela."""
        stub = _make_stub()
        mock_dialogs = self._dialogos(False)
        mock_dialogs.prompt_profile_name.return_value = "Navegacao"

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch(
                "hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles",
                return_value=[_make_profile("Navegação")],
            ),
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile"),
        ):
            stub.on_save_profile()

        _, kwargs = mock_dialogs.prompt_overwrite_existing.call_args
        assert kwargs["name"] == "Navegação"

    def test_nome_que_nao_disputa_arquivo_nenhum_salva_direto(self) -> None:
        """Sem colisão de slug não há pergunta — o gate não pode virar pedágio."""
        stub = _make_stub()
        salvos: list[str] = []
        mock_dialogs = self._dialogos(True)
        mock_dialogs.prompt_profile_name.return_value = "Corrida"

        def fake_save(profile: Profile, *, origem: str | None = None) -> Path:
            salvos.append(profile.name)
            return Path(f"/tmp/{profile.name}.json")

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch(
                "hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles",
                return_value=[_make_profile("Navegação")],
            ),
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile", side_effect=fake_save),  # noqa: E501
        ):
            stub.on_save_profile()

        assert not mock_dialogs.prompt_overwrite_existing.called
        assert salvos == ["Corrida"]

    def test_confirmar_a_sobrescrita_grava(self) -> None:
        stub = _make_stub()
        salvos: list[str] = []
        mock_dialogs = self._dialogos(True)
        mock_dialogs.prompt_profile_name.return_value = "Navegacao"

        def fake_save(profile: Profile, *, origem: str | None = None) -> Path:
            salvos.append(profile.name)
            return Path(f"/tmp/{profile.name}.json")

        with (
            patch("hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", mock_dialogs),
            patch(
                "hefesto_dualsense4unix.app.actions.footer_actions.load_all_profiles",
                return_value=[_make_profile("Navegação")],
            ),
            patch("hefesto_dualsense4unix.app.actions.profile_writer.save_profile", side_effect=fake_save),  # noqa: E501
        ):
            stub.on_save_profile()

        assert salvos == ["Navegacao"]
