"""PERFIL-ATUAL-01 — o perfil que ELA ativou tem cor e é o primeiro da lista."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("PERFIL-ATUAL-01 (a linha dela tem cor e o primeiro lugar)")

from pathlib import Path
from typing import Any


from hefesto_dualsense4unix.app.actions.profiles_actions import (
    ProfilesActionsMixin,
    ordem_de_exibicao,
    perfil_que_ela_ativou,
)
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile
from hefesto_dualsense4unix.utils.xdg_paths import config_dir

VERDE_DA_CASA = "#50fa7b"

PROFILES_PY = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "app"
    / "actions"
    / "profiles_actions.py"
)


def _catch_all(nome: str, prioridade: int) -> Profile:
    return Profile(name=nome, priority=prioridade, match=MatchAny())


def _do_jogo(nome: str, prioridade: int) -> Profile:
    return Profile(
        name=nome,
        priority=prioridade,
        match=MatchCriteria(window_class=[f"steam_app_{prioridade}"]),
    )


def _mesa_dela() -> list[Profile]:
    """A ordem de CARGA do loader é alfabética pelo ARQUIVO — imitada aqui."""
    return [
        _catch_all("Ação", 5),
        _do_jogo("Pragmata", 85),
        _catch_all("vitoria", 5),
    ]


def _stub() -> Any:
    """A aba Perfis com GTK de verdade e nada de janela."""
    from gi.repository import GObject, Gtk, Pango

    class _Stub(ProfilesActionsMixin):
        def __init__(self) -> None:
            self._profiles_store = Gtk.ListStore(
                GObject.TYPE_STRING,
                GObject.TYPE_INT,
                GObject.TYPE_STRING,
                GObject.TYPE_INT,
                GObject.TYPE_STRING,
                Pango.AttrList,
            )
            self._profiles_cache: list[Profile] = []
            self._active_profile_hint: str | None = None
            self._tree = Gtk.TreeView()
            self._tree.set_model(self._profiles_store)

        def _get(self, nome: str) -> Any:
            return self._tree

    return _Stub()


class TestOFatoDoGestoDela:
    """Ativar deixa RASTRO EM DISCO — e é dele que a aba parte."""

    def test_sem_gesto_nenhum_nao_ha_perfil_atual(self) -> None:
        assert perfil_que_ela_ativou() is None

    def test_o_ativar_de_ontem_ainda_responde_hoje(self) -> None:
        """`session.json` é o que o `profile.switch` grava — manual-only.

        Desde 01/10/2026 a resposta é a do dono (`a_escolha_dela`), que só diz
        um nome que CARREGA: o perfil está no disco.
        """
        from hefesto_dualsense4unix.profiles.loader import save_profile

        save_profile(Profile(name="Pragmata", match=MatchAny()), origem="regua")
        (config_dir(ensure=True) / "session.json").write_text(
            '{"last_profile": "Pragmata"}', encoding="utf-8"
        )
        assert perfil_que_ela_ativou() == "Pragmata"

    def test_o_marcador_e_espelho_e_nao_vence_o_session_json(self) -> None:
        """O `active_profile.txt` não decide nada: vale o `session.json`."""
        from hefesto_dualsense4unix.profiles.loader import save_profile

        for nome in ("Navegação", "vitoria"):
            save_profile(Profile(name=nome, match=MatchAny()), origem="regua")
        cfg = config_dir(ensure=True)
        (cfg / "session.json").write_text(
            '{"last_profile": "Navegação"}', encoding="utf-8"
        )
        (cfg / "active_profile.txt").write_text("vitoria\n", encoding="utf-8")
        assert perfil_que_ela_ativou() == "Navegação"

    def test_disco_ilegivel_nao_derruba_a_aba(self, monkeypatch) -> None:
        """Best-effort: sem nome não há destaque — nunca uma exceção na GTK."""
        import hefesto_dualsense4unix.utils.session as session

        def _explode() -> str | None:
            raise OSError("disco de mentira")

        monkeypatch.setattr(session, "resolve_boot_profile", _explode)
        assert perfil_que_ela_ativou() is None


class TestALinhaDeCor:


    def test_as_tres_colunas_visiveis_puxam_a_cor_da_mesma_coluna(self) -> None:
        """Ela pediu a LINHA colorida: o realce vale nas três."""
        for chamada in self._colunas_montadas():
            palavras = {kw.arg for kw in chamada.keywords}
            assert "attributes" in palavras, (
                "coluna da lista sem `attributes=` — a linha do perfil dela sai "
                "colorida pela metade (PERFIL-ATUAL-01)"
            )

    def test_a_cor_nao_volta_a_ser_um_foreground_de_celula(self) -> None:
        """A regressão MEDIDA, e a razão de o realce ser `AttrList`."""
        for chamada in self._colunas_montadas():
            palavras = {kw.arg for kw in chamada.keywords}
            assert "foreground" not in palavras, (
                "a cor da linha voltou a ser `foreground=` — ela some quando a "
                "linha está selecionada, que é o caso do perfil ativo "
                "(PERFIL-ATUAL-01)"
            )


class TestOrdemDeExibicao:
    """A função PURA — o ativo primeiro, o resto NA ORDEM DE CARGA."""

    def test_o_ativo_vai_para_a_frente(self) -> None:
        perfis = _mesa_dela()
        nomes = [p.name for p in ordem_de_exibicao(perfis, "vitoria")]
        assert nomes == ["vitoria", "Ação", "Pragmata"]

    def test_o_resto_nao_e_reembaralhado(self) -> None:
        perfis = _mesa_dela()
        nomes = [p.name for p in ordem_de_exibicao(perfis, "Ação")]
        assert nomes == ["Ação", "Pragmata", "vitoria"]

    def test_sem_ativo_a_ordem_de_carga_fica_intacta(self) -> None:
        perfis = _mesa_dela()
        assert [p.name for p in ordem_de_exibicao(perfis, None)] == [
            "Ação",
            "Pragmata",
            "vitoria",
        ]

    def test_nome_que_nao_existe_na_lista_nao_muda_nada(self) -> None:
        """Marker de versão antiga, perfil renomeado: degrada em silêncio."""
        perfis = _mesa_dela()
        assert [p.name for p in ordem_de_exibicao(perfis, "apagado")] == [
            "Ação",
            "Pragmata",
            "vitoria",
        ]

    def test_nao_devolve_a_lista_de_entrada(self) -> None:
        """Quem chama continua com a ordem de CARGA na mão — ver EMPATE-01/E2."""
        perfis = _mesa_dela()
        saida = ordem_de_exibicao(perfis, "vitoria")
        assert saida is not perfis
        assert [p.name for p in perfis] == ["Ação", "Pragmata", "vitoria"]


