"""P7 — Remover apagava o perfil ATIVO sem uma palavra."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("p7: o Remover diz o que apaga")

from typing import Any


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


