"""P7 — Remover apagava o perfil ATIVO sem uma palavra."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("p7: o Remover diz o que apaga")

import types
from typing import Any

import pytest

from hefesto_dualsense4unix.app import gui_dialogs
from hefesto_dualsense4unix.app.actions import profiles_actions as pa


def _valendo(nome: str | None, fonte: str) -> pa.PerfilQueVale:
    return pa.PerfilQueVale(nome, fonte)


class TestAFraseSoFalaDoPerfilQueVale:
    def test_remover_o_ativo_diz_o_que_nao_se_desfaz(self) -> None:
        """MORDE o leitor: sem ele o diálogo é o mesmo de qualquer remoção."""
        frase = pa.frase_da_remocao_do_perfil_ativo(
            "Sackboy", _valendo("Sackboy", "disco")
        )
        assert frase is not None
        assert "está valendo agora" in frase
        assert "não desfaz" in frase, "o controle continua com as seções dele"
        assert "marcador" in frase, "o marcador em disco fica órfão"
        assert "ative outro perfil" in frase, "toda frase daqui diz o que fazer"

    def test_o_ativo_reportado_pelo_daemon_tambem_conta(self) -> None:
        frase = pa.frase_da_remocao_do_perfil_ativo(
            "Sackboy", _valendo("Sackboy", "daemon")
        )
        assert frase is not None

    def test_o_slug_e_o_nome_sao_o_mesmo_perfil(self) -> None:
        """O marcador guarda `Sackboy`; a lista pode trazer `sackboy`."""
        for como_esta_na_lista in ("sackboy", "SACKBOY", "Sackboy"):
            assert (
                pa.frase_da_remocao_do_perfil_ativo(
                    como_esta_na_lista, _valendo("Sackboy", "disco")
                )
                is not None
            )


class TestOSilencioContinuaSendoARegra:
    def test_remover_outro_perfil_nao_ganha_texto_novo(self) -> None:
        """MORDE o silêncio: aviso em toda remoção vira linha que se pula."""
        assert (
            pa.frase_da_remocao_do_perfil_ativo(
                "Pragmata", _valendo("Sackboy", "disco")
            )
            is None
        )

    def test_quando_ninguem_sabe_quem_vale_a_tela_cala(self) -> None:
        """`nao_sei` não é `é este` — a disciplina do §P1, aqui também."""
        assert (
            pa.frase_da_remocao_do_perfil_ativo("Sackboy", _valendo(None, "nao_sei"))
            is None
        )

    def test_sem_perfil_ativo_nenhum_nao_ha_o_que_avisar(self) -> None:
        assert (
            pa.frase_da_remocao_do_perfil_ativo("Sackboy", _valendo(None, "nenhum"))
            is None
        )

    def test_nome_vazio_cala(self) -> None:
        assert (
            pa.frase_da_remocao_do_perfil_ativo("", _valendo("Sackboy", "disco"))
            is None
        )


class _Aba(pa.ProfilesActionsMixin):  # type: ignore[misc]
    def __init__(self, selecionado: str = "Sackboy") -> None:
        self._selecionado = selecionado
        self._widgets: dict[str, Any] = {"main_window": object()}
        self.toasts: list[str] = []
        self.avisou_launch_env = 0

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _selected_profile_name(self, _selection: Any = None) -> str | None:
        return self._selecionado

    def _reload_profiles_store(self, **_kw: Any) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        self.avisou_launch_env += 1

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


def _espiar_o_dialogo(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    """Troca o diálogo por um espião e devolve a lista de `aviso` recebidos."""
    vistos: list[str | None] = []

    def _falso(parent: Any, name: str, aviso: str | None = None) -> bool:
        vistos.append(aviso)
        return False

    monkeypatch.setattr(gui_dialogs, "confirm_delete_profile", _falso)
    return vistos


class TestOBotaoCalculaAFrase:
    def test_remover_o_ativo_manda_o_aviso_ao_dialogo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE a costura: a frase certa e o diálogo mudo não curam nada."""
        monkeypatch.setattr(pa, "perfil_que_ela_ativou", lambda: "Sackboy")
        vistos = _espiar_o_dialogo(monkeypatch)

        _Aba("Sackboy").on_profile_remove(None)

        assert len(vistos) == 1
        assert vistos[0] is not None
        assert "está valendo agora" in vistos[0]

    def test_remover_outro_manda_none_e_o_dialogo_fica_como_ontem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pa, "perfil_que_ela_ativou", lambda: "Sackboy")
        vistos = _espiar_o_dialogo(monkeypatch)

        _Aba("Pragmata").on_profile_remove(None)

        assert vistos == [None]

    def test_o_disco_mudo_nao_derruba_a_thread_do_gtk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ler o marcador é I/O, e I/O falha. Falhar aqui custaria a janela."""

        def _explode() -> str:
            raise OSError("disco fora")

        monkeypatch.setattr(pa, "perfil_que_ela_ativou", _explode)
        vistos = _espiar_o_dialogo(monkeypatch)

        _Aba("Sackboy").on_profile_remove(None)

        assert vistos == [None]


class TestADialogoCarregaAFrase:
    """O `gui_dialogs` só ENCAIXA a frase — quem sabe o fato é quem a escreve."""

    @staticmethod
    def _gtk_de_mentira() -> tuple[Any, dict[str, Any]]:
        registro: dict[str, Any] = {}

        class _Dialogo:
            def __init__(self, **kw: Any) -> None:
                registro["titulo"] = kw.get("text")

            def format_secondary_text(self, texto: str) -> None:
                registro["secundário"] = texto

            def add_button(self, *_a: Any) -> None:
                return None

            def set_default_response(self, *_a: Any) -> None:
                return None

            def destroy(self) -> None:
                return None

        resposta = types.SimpleNamespace(CANCEL="cancel", OK="ok")
        falso = types.SimpleNamespace(
            MessageDialog=_Dialogo,
            MessageType=types.SimpleNamespace(WARNING="warn"),
            ButtonsType=types.SimpleNamespace(NONE="none"),
            ResponseType=resposta,
            Window=object,
        )
        return falso, registro

    def test_o_aviso_vem_antes_do_permanente(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A linha que ela já leu mil vezes não pode ficar na frente da nova."""
        falso, registro = self._gtk_de_mentira()
        monkeypatch.setattr(gui_dialogs, "Gtk", falso)
        monkeypatch.setattr(gui_dialogs, "_apply_app_theme", lambda _d: None)
        monkeypatch.setattr(
            gui_dialogs, "executar_dialogo", lambda _d, nome="": "cancel"
        )

        gui_dialogs.confirm_delete_profile(
            parent=None, name="Sackboy", aviso="ESTE É O AVISO"
        )

        texto = registro["secundário"]
        assert "ESTE É O AVISO" in texto, "o diálogo jogou o aviso fora"
        assert "permanente" in texto, "a linha de sempre não pode sumir"
        assert texto.index("ESTE É O AVISO") < texto.index("permanente")

    def test_sem_aviso_o_dialogo_e_byte_a_byte_o_de_ontem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        falso, registro = self._gtk_de_mentira()
        monkeypatch.setattr(gui_dialogs, "Gtk", falso)
        monkeypatch.setattr(gui_dialogs, "_apply_app_theme", lambda _d: None)
        monkeypatch.setattr(
            gui_dialogs, "executar_dialogo", lambda _d, nome="": "cancel"
        )

        gui_dialogs.confirm_delete_profile(parent=None, name="Sackboy")

        assert registro["secundário"] == (
            "Esta ação é permanente e não pode ser desfeita."
        )
