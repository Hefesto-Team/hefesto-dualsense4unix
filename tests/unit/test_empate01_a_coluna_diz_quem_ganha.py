"""EMPATE-01 (E2) — a coluna "Quando usar" nunca anuncia um vencedor que o gerente não elege."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("empate01: a coluna diz quem ganha")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    LABEL_SO_MANUAL,
    ProfilesActionsMixin,
    explicacao_da_disputa,
    rotulo_quando_usar,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
)


def _perfil(nome: str, prioridade: int, match: Any) -> Profile:
    return Profile(name=nome, priority=prioridade, match=match)


def _catch_all(nome: str, prioridade: int) -> Profile:
    return _perfil(nome, prioridade, MatchAny())


def _mesa_dela() -> list[Profile]:
    return [
        _catch_all("fallback", 0),
        _catch_all("meu_perfil", 1),
        _catch_all("Pragmata", 5),          # pragmata.json
        _perfil(                            # pragmata2.json — saiu da disputa
            "Pragmata2", 85, MatchCriteria(window_class=["steam_app_3357650"])
        ),
        _catch_all("vitoria", 0),
    ]


class TestOTextoDaColuna:
    def test_nenhum_sempre_anuncia_disputa(self) -> None:
        """Os quatro «Sempre» da mesa dela dizem só «Sempre»: ninguém vence sozinho."""
        perfis = _mesa_dela()
        for perfil in perfis:
            if perfil.match.type == "any":
                assert rotulo_quando_usar(perfil, perfis, "Pragmata2") == "Sempre"

    def test_um_catch_all_sozinho_continua_sempre(self) -> None:
        """Recém-instalado: só o `fallback` no disco. Nada a explicar."""
        perfis = [
            _catch_all("fallback", 0),
            _perfil("FPS", 60, MatchCriteria(process_name=["cs2"])),
        ]
        assert rotulo_quando_usar(perfis[0], perfis, None) == "Sempre"

    def test_as_outras_frases_da_coluna_nao_mudaram(self) -> None:
        """R-12/LEIGO-06 continuam valendo — esta entrega só toca o "Sempre"."""
        perfis = [
            *_mesa_dela(),
            _perfil("FPS", 60, MatchCriteria(process_name=["cs2"])),
            _perfil("vazio", 50, MatchCriteria()),
            _perfil("manual", 50, MatchManual()),
        ]
        por_nome = {p.name: p for p in perfis}
        assert rotulo_quando_usar(por_nome["FPS"], perfis, None) == "Só neste programa"
        assert rotulo_quando_usar(por_nome["vazio"], perfis, None) == LABEL_SO_MANUAL
        assert rotulo_quando_usar(por_nome["manual"], perfis, None) == LABEL_SO_MANUAL


class TestAColunaEspelhaOManager:
    """O ponto que impede a tela de mentir: o vencedor é o do `ProfileManager`."""

    @staticmethod
    def _quem_o_manager_escolhe(
        perfis: list[Profile], incumbente: str | None, monkeypatch: Any
    ) -> str | None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.profiles.manager.load_all_profiles",
            lambda: list(perfis),
        )

        class _Store:
            active_profile = incumbente

        gerente = ProfileManager(controller=None, store=_Store())
        escolhido, _motivo = gerente.select_for_window_ex(
            {"wm_class": "nautilus", "wm_name": "Pastas", "exe_basename": "nautilus"}
        )
        return None if escolhido is None else escolhido.name

    @pytest.mark.parametrize("incumbente", ["Pragmata2", "vitoria", None])
    def test_o_manager_nao_elege_sempre_e_a_coluna_nao_anuncia(
        self, monkeypatch: pytest.MonkeyPatch, incumbente: str | None
    ) -> None:
        """Janela de desktop sem regra: o gerente não elege ninguém, a coluna também."""
        perfis = _mesa_dela()
        real = self._quem_o_manager_escolhe(perfis, incumbente, monkeypatch)
        anunciado = [
            p.name for p in perfis
            if "vence" in rotulo_quando_usar(p, perfis, incumbente)
        ]
        assert real is None
        assert anunciado == []


class TestOTooltip:
    def test_o_sempre_nao_tem_mais_tooltip(self) -> None:
        """A frase «é o que entra quando nenhuma regra específica casa» saiu."""
        perfis = _mesa_dela()
        for perfil in perfis:
            assert explicacao_da_disputa(perfil, perfis, "Pragmata2") == ""

    def test_o_veto_do_jogo_realmente_acontece(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dentro de um jogo sem regra própria, nenhum «Sempre» entra."""
        perfis = _mesa_dela()
        monkeypatch.setattr(
            "hefesto_dualsense4unix.profiles.manager.load_all_profiles",
            lambda: list(perfis),
        )

        class _Store:
            active_profile = "vitoria"

        gerente = ProfileManager(controller=None, store=_Store())
        escolhido, motivo = gerente.select_for_window_ex(
            {"wm_class": "steam_app_9999999", "wm_name": "Jogo", "exe_basename": "j.exe"}
        )
        assert escolhido is None
        assert motivo == "jogo_sem_perfil_proprio"


class TestFiacaoDaColuna:
    """O ListStore carrega a frase e o tooltip — a metade que precisa de GTK."""

    @staticmethod
    def _stub() -> Any:
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

            def _get(self, nome: str) -> Any:
                return self._tree

        return _Stub()

    def test_o_store_recebe_a_frase_e_o_tooltip(self) -> None:
        stub = self._stub()
        perfis = _mesa_dela()
        stub._active_profile_hint = "Pragmata2"
        stub._populate_profiles_store(perfis, None)
        linhas = {linha[0]: (linha[2], linha[4]) for linha in stub._profiles_store}
        assert linhas["Pragmata"] == ("Sempre", "")
        assert linhas["vitoria"] == ("Sempre", "")
        assert linhas["Pragmata2"] == ("Só neste programa", "")

    def test_trocar_de_perfil_ativo_nao_inventa_vencedor(self) -> None:
        """Trocar o ativo não faz nenhum «Sempre» virar o vencedor da coluna."""
        stub = self._stub()
        perfis = [_catch_all("aaa", 7), _catch_all("zzz", 7)]
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "aaa"
        stub._populate_profiles_store(perfis, None)
        stub._mark_active_profile_row("zzz")
        depois = {linha[0]: linha[2] for linha in stub._profiles_store}
        assert depois == {"aaa": "Sempre", "zzz": "Sempre"}
