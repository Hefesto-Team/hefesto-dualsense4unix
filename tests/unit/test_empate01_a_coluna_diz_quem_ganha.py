"""EMPATE-01 (E2) — a coluna "Quando usar" diz que HÁ disputa e quem ganha.

Medido no disco dela em 31/07/2026: QUATRO perfis dizem "Sempre" ao mesmo
tempo (`fallback` prio 0, `vitoria` prio 0, `meu_perfil` prio 1 e `Pragmata`
prio 5). A coluna escrevia a MESMA palavra nas quatro linhas, um deles vencia
e nada na tela dizia qual, nem por quê. É o mecanismo direto da queixa mais
antiga da casa, *"a config que eu deixo nunca é respeitada"*.

Este arquivo trava as duas metades:

- que a frase da coluna NÃO INVENTE critério — o vencedor anunciado tem de ser
  o mesmo que o `ProfileManager` de verdade elege, e há um teste que confronta
  os dois lado a lado, com os perfis montados aqui;
- que ela não passe a mentir no caso simples: com um catch-all só (o usuário
  recém-instalado, com o `fallback` sozinho) a palavra continua sendo "Sempre",
  sem disputa nenhuma pendurada.

Sem GTK de propósito: `rotulo_quando_usar`, `perfis_em_disputa` e
`vencedor_da_disputa` são funções puras justamente para o contrato de texto
ficar testável no CI headless. A fiação do ListStore (a 5ª coluna do tooltip)
é o único ponto que exige widget, e vive em `TestFiacaoDaColuna`, atrás do
`exigir_gi_real` do módulo — que roda no topo, antes de qualquer import de
`gi`, pela regra GUARDA-GI-REAL-01.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("empate01: a coluna diz quem ganha")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    LABEL_SO_MANUAL,
    ProfilesActionsMixin,
    explicacao_da_disputa,
    perfis_em_disputa,
    rotulo_quando_usar,
    vencedor_da_disputa,
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


#: A mesa dela, reduzida ao que importa para a disputa. A ORDEM é a do loader
#: (`sorted(glob("*.json"))`, loader.py:568) porque ela É o terceiro termo do
#: desempate — trocar a ordem aqui trocaria o vencedor esperado.
def _mesa_dela() -> list[Profile]:
    return [
        _catch_all("fallback", 0),          # fallback.json
        _catch_all("meu_perfil", 1),        # meu_perfil.json
        _catch_all("Pragmata", 5),          # pragmata.json
        _perfil(                            # pragmata2.json — saiu da disputa
            "Pragmata2", 85, MatchCriteria(window_class=["steam_app_3357650"])
        ),
        _catch_all("vitoria", 0),           # vitoria.json
    ]


class TestQuemDisputa:
    def test_so_o_sempre_entra_na_disputa(self) -> None:
        """`MatchCriteria` vazio é catch-all para o manager e NÃO disputa.

        `MatchCriteria.matches` devolve False sem condição alguma — o perfil
        nunca vira candidato. Contá-lo inflaria o número anunciado com quem não
        disputa nada, e a coluna já o chama de `LABEL_SO_MANUAL`.
        """
        perfis = [
            _catch_all("fallback", 0),
            _perfil("vazio", 50, MatchCriteria()),
            _perfil("manual", 50, MatchManual()),
            _catch_all("vitoria", 0),
        ]
        assert [p.name for p in perfis_em_disputa(perfis)] == ["fallback", "vitoria"]

    def test_o_pragmata2_saiu_da_disputa_nesta_madrugada(self) -> None:
        """Regra de jogo não disputa com catch-all — a medição de hoje."""
        nomes = [p.name for p in perfis_em_disputa(_mesa_dela())]
        assert nomes == ["fallback", "meu_perfil", "Pragmata", "vitoria"]
        assert "Pragmata2" not in nomes


class TestOTextoDaColuna:
    def test_quatro_disputam_e_a_coluna_diz_quem_ganha(self) -> None:
        perfis = _mesa_dela()
        rotulos = {p.name: rotulo_quando_usar(p, perfis, "Pragmata2") for p in perfis}
        assert rotulos["Pragmata"] == "Sempre — 4 disputam, este vence"
        for perdedor in ("fallback", "meu_perfil", "vitoria"):
            assert rotulos[perdedor] == "Sempre — 4 disputam, vence Pragmata"

    def test_a_coluna_nao_para_mais_em_sempre(self) -> None:
        """A mordida direta: nenhum dos quatro pode dizer só "Sempre"."""
        perfis = _mesa_dela()
        for perfil in perfis_em_disputa(perfis):
            assert rotulo_quando_usar(perfil, perfis, None) != "Sempre"

    def test_um_catch_all_sozinho_nao_inventa_disputa(self) -> None:
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


class TestODesempateEspelhaOManager:
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
        # Janela de DESKTOP: nenhuma regra específica casa, então só os
        # catch-all viram candidatos — é exatamente a situação que a coluna
        # descreve.
        escolhido, _motivo = gerente.select_for_window_ex(
            {"wm_class": "nautilus", "wm_name": "Pastas", "exe_basename": "nautilus"}
        )
        return None if escolhido is None else escolhido.name

    def test_maior_prioridade_vence_e_a_coluna_concorda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        perfis = _mesa_dela()
        real = self._quem_o_manager_escolhe(perfis, "Pragmata2", monkeypatch)
        anunciado = [
            p.name
            for p in perfis_em_disputa(perfis)
            if "este vence" in rotulo_quando_usar(p, perfis, "Pragmata2")
        ]
        assert real == "Pragmata"
        assert anunciado == [real]

    def test_no_empate_quem_ja_esta_ativo_continua_e_a_coluna_concorda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Terceiro termo do desempate: o INCUMBENTE (manager.py:688-695)."""
        perfis = [_catch_all("aaa", 7), _catch_all("zzz", 7)]
        real = self._quem_o_manager_escolhe(perfis, "zzz", monkeypatch)
        assert real == "zzz"
        assert vencedor_da_disputa(perfis, "zzz").name == "zzz"
        assert rotulo_quando_usar(perfis[1], perfis, "zzz") == (
            "Sempre — 2 disputam, este vence"
        )
        assert rotulo_quando_usar(perfis[0], perfis, "zzz") == (
            "Sempre — 2 disputam, vence zzz"
        )

    def test_sem_incumbente_o_empate_cai_na_ordem_do_arquivo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem incumbente entre os empatados, vence o primeiro da ordem de carga.

        Não é critério de ninguém — é o `sorted(glob)` do loader —, e por isso
        mesmo a tela tem de anunciar o MESMO acidente que o daemon comete.
        """
        perfis = [_catch_all("aaa", 7), _catch_all("zzz", 7)]
        real = self._quem_o_manager_escolhe(perfis, "Pragmata2", monkeypatch)
        assert real == "aaa"
        assert vencedor_da_disputa(perfis, "Pragmata2").name == "aaa"

    def test_o_incumbente_e_comparado_por_slug_como_no_manager(self) -> None:
        """`_refers_same_profile` compara slugs — "Navegacao" é "Navegação"."""
        perfis = [_catch_all("aaa", 7), _catch_all("Navegação", 7)]
        assert vencedor_da_disputa(perfis, "Navegacao").name == "Navegação"


class TestOTooltipDizOPrecoInteiro:
    def test_lista_os_disputantes_o_vencedor_e_a_ordem_do_desempate(self) -> None:
        perfis = _mesa_dela()
        texto = explicacao_da_disputa(perfis[0], perfis, "Pragmata2")
        assert "4 perfis" in texto
        for nome in ("fallback", "meu_perfil", "Pragmata", "vitoria"):
            assert nome in texto
        assert "prioridade 5" in texto
        # As três regras do desempate, em palavras.
        assert "regra própria" in texto
        assert "maior prioridade" in texto
        assert "já estava ativo" in texto

    def test_diz_que_dentro_do_jogo_nenhum_deles_entra(self) -> None:
        """Verdade dos DOIS ramos do manager, e a tela não pode omiti-la.

        Em janela de jogo: ou todos os candidatos são catch-all e o veto R-21
        recusa trocar (`manager.py:620-630`), ou existe um perfil com regra
        própria — e aí ele ganha de qualquer "Sempre" pelo PRIMEIRO termo da
        chave (`not e_catch_all`, `manager.py:640`).
        """
        perfis = _mesa_dela()
        texto = explicacao_da_disputa(perfis[0], perfis, "Pragmata2")
        assert "jogo" in texto

    def test_o_veto_do_jogo_realmente_acontece(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A frase acima é medida, não retórica."""
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

    def test_quem_nao_e_sempre_nao_tem_tooltip(self) -> None:
        perfis = _mesa_dela()
        regra = next(p for p in perfis if p.name == "Pragmata2")
        assert explicacao_da_disputa(regra, perfis, None) == ""


class TestFiacaoDaColuna:
    """O ListStore carrega a frase e o tooltip — a metade que precisa de GTK."""

    @staticmethod
    def _stub() -> Any:
        from gi.repository import GObject, Gtk

        class _Stub(ProfilesActionsMixin):
            def __init__(self) -> None:
                self._profiles_store = Gtk.ListStore(
                    GObject.TYPE_STRING,
                    GObject.TYPE_INT,
                    GObject.TYPE_STRING,
                    GObject.TYPE_INT,
                    GObject.TYPE_STRING,
                )
                self._profiles_cache: list[Profile] = []
                self._active_profile_hint: str | None = None
                self._tree = Gtk.TreeView()

            def _get(self, nome: str) -> Any:
                return self._tree

        return _Stub()

    def test_o_store_recebe_a_disputa_e_o_tooltip(self) -> None:
        stub = self._stub()
        perfis = _mesa_dela()
        stub._active_profile_hint = "Pragmata2"
        stub._populate_profiles_store(perfis, None)
        linhas = {linha[0]: (linha[2], linha[4]) for linha in stub._profiles_store}
        assert linhas["Pragmata"][0] == "Sempre — 4 disputam, este vence"
        assert linhas["vitoria"][0] == "Sempre — 4 disputam, vence Pragmata"
        assert "prioridade 5" in linhas["vitoria"][1]
        # Quem não é "Sempre" não ganha tooltip nenhum.
        assert linhas["Pragmata2"] == ("Só neste programa", "")

    def test_trocar_de_perfil_ativo_recalcula_a_disputa_in_place(self) -> None:
        """O ativo É o incumbente: mudar de perfil pode mudar o vencedor.

        Sem este recálculo o negrito andaria e a frase ficaria congelada na
        disputa do perfil anterior — a tela diria dois donos ao mesmo tempo.
        """
        stub = self._stub()
        perfis = [_catch_all("aaa", 7), _catch_all("zzz", 7)]
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "aaa"
        stub._populate_profiles_store(perfis, None)
        antes = {linha[0]: linha[2] for linha in stub._profiles_store}
        assert antes["aaa"] == "Sempre — 2 disputam, este vence"

        stub._mark_active_profile_row("zzz")
        depois = {linha[0]: linha[2] for linha in stub._profiles_store}
        assert depois["zzz"] == "Sempre — 2 disputam, este vence"
        assert depois["aaa"] == "Sempre — 2 disputam, vence zzz"
