"""P10 — quatro caminhos desta aba não tinham UMA mordida."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("p10: os quatro caminhos da aba Perfis")

from typing import Any

import pytest

from hefesto_dualsense4unix.app import gui_dialogs
from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
)

SACKBOY = Profile(
    name="Sackboy",
    match=MatchCriteria(window_class=["steam_app_1599660"]),
    priority=80,
    leds=LedsConfig(lightbar=(0, 255, 0)),
)


class _Entry:
    def __init__(self, texto: str = "") -> None:
        self._t = texto

    def get_text(self) -> str:
        return self._t

    def set_text(self, texto: str) -> None:
        self._t = texto


class _Aba(pa.ProfilesActionsMixin):  # type: ignore[misc]
    """A aba, com o disco e os diálogos na mão do teste."""

    def __init__(self, selecionado: str | None = "Sackboy") -> None:
        self._profiles_cache: list[Profile] = [SACKBOY]
        self._selecionado = selecionado
        self._duplicate_source: Profile | None = None
        self._new_profile = False
        self._alvo_do_salvar: str | None = "Sackboy"
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _Entry("Sackboy"),
            "main_window": object(),
        }
        self.toasts: list[str] = []
        self.recarregou: list[Any] = []
        self.abas_refeitas = 0
        self.avisou_launch_env = 0

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _selected_profile_name(self, _selection: Any = None) -> str | None:
        return self._selecionado

    def _reload_profiles_store(self, **kw: Any) -> None:
        self.recarregou.append(kw)

    def _notify_launch_env_refresh(self) -> None:
        self.avisou_launch_env += 1

    def _recarregar_as_abas_do_perfil_ativo(self) -> None:
        self.abas_refeitas += 1

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


class TestRemover:
    def test_cancelar_nao_toca_o_disco(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MORDE a confirmação (BUG-DELETE-NO-CONFIRM-01)."""
        aba = _Aba()
        apagados: list[str] = []
        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name, aviso=None: False
        )
        monkeypatch.setattr(pa, "delete_profile", lambda n: apagados.append(n))

        aba.on_profile_remove(None)

        assert apagados == [], "cancelar apagou o arquivo dela"
        assert aba.toasts == ["Remoção cancelada."]

    def test_confirmar_apaga_e_avisa_o_daemon(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O `launch_env` do perfil apagado tem de sumir junto (DEDUP-04)."""
        aba = _Aba()
        apagados: list[str] = []
        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name, aviso=None: True
        )
        monkeypatch.setattr(pa, "delete_profile", lambda n: apagados.append(n))

        aba.on_profile_remove(None)

        assert apagados == ["Sackboy"]
        assert aba.toasts == ["Perfil removido: Sackboy"]
        assert aba.avisou_launch_env == 1

    def test_o_alvo_do_salvar_nao_e_zerado_e_isso_e_decisao_medida(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NUNCA-TROCA-O-ALVO-01: a decisão foi medida, e este teste a trava."""
        aba = _Aba()
        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name, aviso=None: True
        )
        monkeypatch.setattr(pa, "delete_profile", lambda _n: None)

        aba.on_profile_remove(None)

        assert aba._alvo_do_salvar == "Sackboy"

    def test_falha_de_disco_vira_frase_e_nao_excecao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nada aqui pode subir exceção pela thread do GTK."""
        aba = _Aba()

        def _explode(_n: str) -> None:
            raise OSError("permissão negada")

        monkeypatch.setattr(
            gui_dialogs, "confirm_delete_profile", lambda parent, name, aviso=None: True
        )
        monkeypatch.setattr(pa, "delete_profile", _explode)

        aba.on_profile_remove(None)

        assert aba.toasts[-1].startswith("Falha ao remover:")
        assert aba.recarregou == [], "a lista não recarrega depois de falhar"

    def test_sem_linha_selecionada_nao_apaga_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aba = _Aba(selecionado=None)
        monkeypatch.setattr(
            gui_dialogs,
            "confirm_delete_profile",
            lambda parent, name, aviso=None: pytest.fail("perguntou sem perfil selecionado"),
        )
        aba.on_profile_remove(None)
        assert aba.toasts == ["Selecione um perfil para remover"]


class TestDuplicar:
    def test_a_fonte_inteira_viaja_e_nao_so_o_nome(self) -> None:
        """MORDE o BUG-DUPLICATE-NO-CONFIG-COPY-01."""
        aba = _Aba()
        aba.on_profile_duplicate(None)

        assert aba._duplicate_source is SACKBOY, (
            "sem a fonte, `_build_profile_from_editor` não tem de onde copiar"
        )

    def test_duplicar_sai_do_estado_perfil_novo(self) -> None:
        """R-09: duplicar É partir de uma fonte. Arranque e a cópia nasce vazia."""
        aba = _Aba()
        aba._new_profile = True
        aba.on_profile_duplicate(None)
        assert aba._new_profile is False

    def test_o_salvar_deixa_de_mirar_a_fonte_no_mesmo_instante(self) -> None:
        """MORDE a linha mais perigosa das três (NUNCA-TROCA-O-ALVO-01)."""
        aba = _Aba()
        assert aba._alvo_do_salvar == "Sackboy"
        aba.on_profile_duplicate(None)
        assert aba._alvo_do_salvar is None

    def test_o_nome_ganha_o_sufixo_de_copia(self) -> None:
        aba = _Aba()
        aba.on_profile_duplicate(None)
        assert aba._get("profile_name_entry").get_text() == "Sackboy (cópia)"
        assert aba.toasts[-1].startswith("Editor preenchido com cópia completa")

    def test_sem_linha_selecionada_nao_duplica(self) -> None:
        aba = _Aba(selecionado=None)
        aba.on_profile_duplicate(None)
        assert aba._duplicate_source is None
        assert aba.toasts == ["Selecione um perfil para duplicar"]


class TestTirarDaLista:
    def test_passa_pelo_escritor_unico_e_nao_pelo_remove_direto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE o dono único da escrita."""
        aba = _Aba()
        gravados: list[tuple[str, bool]] = []
        monkeypatch.setattr(
            pa.ProfilesActionsMixin,
            "_gravar_marca_do_steam_input",
            lambda self, appid, marcar: gravados.append((appid, marcar)),
        )

        aba._ao_tirar_outro_marcado(None, "1599660")

        assert gravados == [("1599660", False)]

    def test_tirar_nao_pergunta_do_relancar_e_a_diferenca_e_medida(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pergunta do RELANCAR-01 é para o jogo DESTE editor, não para os outros."""
        aba = _Aba()
        monkeypatch.setattr(
            pa.ProfilesActionsMixin,
            "_perguntar_antes_de_relancar",
            lambda self, **kw: pytest.fail("o Tirar perguntou do relançamento"),
        )
        monkeypatch.setattr(
            pa.ProfilesActionsMixin,
            "_gravar_marca_do_steam_input",
            lambda self, appid, marcar: None,
        )

        aba._ao_tirar_outro_marcado(None, "1599660")


class _AbaComEdicao(_Aba):
    def __init__(self, pendente: bool) -> None:
        super().__init__()
        self._pendente = pendente
        self._active_profile_name = "vitoria"
        self.perguntou: list[tuple[str, str | None]] = []
        self.resposta = False

    def _tem_edicao_pendente(self) -> bool:
        return self._pendente


class TestRefazerAsAbasAposAtivar:
    def _armar(
        self, aba: _AbaComEdicao, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            gui_dialogs,
            "confirm_discard_pending_edits",
            lambda parent, ativado, editando=None: (
                aba.perguntou.append((ativado, editando)) or aba.resposta
            ),
        )

    def test_sem_edicao_pendente_refaz_as_abas_sem_perguntar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aba = _AbaComEdicao(pendente=False)
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.perguntou == [], "perguntou sem haver o que proteger"
        assert aba.abas_refeitas == 1

    def test_com_edicao_pendente_a_decisao_e_dela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE o portão da edição pendente."""
        aba = _AbaComEdicao(pendente=True)
        aba.resposta = False
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.perguntou == [("Sackboy", "vitoria")]
        assert aba.abas_refeitas == 0, (
            "a recusa dela tem de deixar as abas exatamente como estavam"
        )
        assert "não salvas" in aba.toasts[-1], (
            "e a tela tem de DIZER que as abas seguem mostrando o rascunho dela"
        )
        assert "vitoria" in aba.toasts[-1], "sem dizer QUAL, é meia informação"

    def test_ela_aceita_descartar_e_as_abas_passam_a_mostrar_o_ativado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        aba = _AbaComEdicao(pendente=True)
        aba.resposta = True
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.abas_refeitas == 1

    def test_a_guarda_que_estoura_nao_impede_a_pergunta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_tem_edicao_pendente` que levanta não pode virar "não há edição"."""
        aba = _AbaComEdicao(pendente=False)

        def _explode(self: Any) -> bool:
            raise RuntimeError("rascunho ilegível")

        monkeypatch.setattr(_AbaComEdicao, "_tem_edicao_pendente", _explode)
        self._armar(aba, monkeypatch)

        aba._refazer_as_abas_apos_ativar("Sackboy")

        assert aba.perguntou == []
        assert aba.abas_refeitas == 1
