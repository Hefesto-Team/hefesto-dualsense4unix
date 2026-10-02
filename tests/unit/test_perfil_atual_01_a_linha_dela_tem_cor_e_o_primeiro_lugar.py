"""PERFIL-ATUAL-01 — o perfil que ELA ativou tem cor e é o primeiro da lista."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("PERFIL-ATUAL-01 (a linha dela tem cor e o primeiro lugar)")

import ast
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    COR_DO_PERFIL_ATIVO,
    ProfilesActionsMixin,
    ordem_de_exibicao,
    perfil_que_ela_ativou,
    realce_do_perfil_ativo,
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


VERDE_SERIALIZADO = "foreground #" + "".join(
    COR_DO_PERFIL_ATIVO[i : i + 2] * 2 for i in (1, 3, 5)
)


def _cor(valor: Any) -> str | None:
    """A cor de uma linha, legível: `None`, o verde da casa, ou o que veio."""
    if valor is None:
        return None
    texto = valor.to_string()
    return VERDE_DA_CASA if VERDE_SERIALIZADO in texto else texto


def _linhas(stub: Any) -> list[tuple[str, str | None]]:
    """(nome, cor) na ordem em que a lista desenha."""
    return [(linha[0], _cor(linha[5])) for linha in stub._profiles_store]


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

    def test_a_aba_semeia_o_destaque_do_disco_ao_abrir(self) -> None:
        """A FIAÇÃO: sem esta chamada o destaque nasce invisível na máquina dela."""
        arvore = ast.parse(PROFILES_PY.read_text(encoding="utf-8"))
        funcao = next(
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.FunctionDef) and no.name == "install_profiles_tab"
        )
        chamados = {
            no.func.id
            for no in ast.walk(funcao)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
        }
        assert "perfil_que_ela_ativou" in chamados, (
            "install_profiles_tab não semeia `_active_profile_hint` do disco — "
            "com o daemon respondendo null (o caso dela) a linha verde nunca "
            "aparece (PERFIL-ATUAL-01)"
        )


class TestONullDoDaemonNaoApagaOQueElaDecidiu:
    """Decisão dela: o perfil atual é o que ela ATIVOU, não o do daemon."""

    def test_status_sem_perfil_deixa_a_marca_dela_de_pe(self) -> None:
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "Pragmata"
        stub._populate_profiles_store(perfis, None)

        stub._on_daemon_status_for_sync({"active_profile": None})

        assert stub._active_profile_hint == "Pragmata"
        assert _linhas(stub)[0] == ("Pragmata", VERDE_DA_CASA)

    def test_o_daemon_com_nome_continua_mandando(self) -> None:
        """O autoswitch elegeu alguém e o daemon diz — a lista acompanha."""
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "Pragmata"
        stub._populate_profiles_store(perfis, None)

        stub._on_daemon_status_for_sync({"active_profile": "vitoria"})

        assert _linhas(stub)[0] == ("vitoria", VERDE_DA_CASA)


class TestALinhaDeCor:
    def test_so_o_perfil_dela_recebe_o_verde(self) -> None:
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "vitoria"
        stub._populate_profiles_store(perfis, None)

        cores = dict(_linhas(stub))
        assert cores["vitoria"] == VERDE_DA_CASA
        assert cores["Ação"] is None and cores["Pragmata"] is None

    def test_a_constante_do_produto_e_o_verde_do_tema(self) -> None:
        assert COR_DO_PERFIL_ATIVO == VERDE_DA_CASA

    def test_sem_perfil_ativo_ninguem_fica_verde(self) -> None:
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._populate_profiles_store(perfis, None)
        assert [cor for _nome, cor in _linhas(stub)] == [None, None, None]

    @staticmethod
    def _colunas_montadas() -> list[ast.Call]:
        arvore = ast.parse(PROFILES_PY.read_text(encoding="utf-8"))
        funcao = next(
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.FunctionDef) and no.name == "install_profiles_tab"
        )
        colunas = [
            no
            for no in ast.walk(funcao)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "TreeViewColumn"
        ]
        assert colunas, "install_profiles_tab não monta coluna nenhuma"
        return colunas

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

    def test_o_realce_carrega_o_verde_da_casa(self) -> None:
        assert VERDE_SERIALIZADO in realce_do_perfil_ativo().to_string()

    def test_o_realce_e_uma_instancia_so(self) -> None:
        """O modelo guarda a referência — montar um por linha seria desperdício."""
        assert realce_do_perfil_ativo() is realce_do_perfil_ativo()

    def test_a_cor_sai_da_linha_quando_o_perfil_deixa_de_ser_o_ativo(self) -> None:
        """Sem atributo nenhum, quem decide a cor volta a ser o tema."""
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "vitoria"
        stub._populate_profiles_store(perfis, None)

        stub._mark_active_profile_row("Ação")

        cores = dict(_linhas(stub))
        assert cores["Ação"] == VERDE_DA_CASA
        assert cores["vitoria"] is None


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


class TestAListaAbreNoPerfilDela:
    def test_a_primeira_linha_e_a_dela(self) -> None:
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "vitoria"
        stub._populate_profiles_store(perfis, None)
        assert [nome for nome, _cor in _linhas(stub)] == [
            "vitoria",
            "Ação",
            "Pragmata",
        ]

    def test_ativar_outro_perfil_move_a_linha_sem_reler_o_disco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O gesto de Ativar chega em `_mark_active_profile_row` e mais nada."""
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "vitoria"
        stub._populate_profiles_store(perfis, None)

        def _nao_pode(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("mover a linha não pode reler o disco")

        monkeypatch.setattr(
            "hefesto_dualsense4unix.app.actions.profiles_actions.load_all_profiles",
            _nao_pode,
        )
        stub._mark_active_profile_row("Pragmata")

        assert _linhas(stub) == [
            ("Pragmata", VERDE_DA_CASA),
            ("Ação", None),
            ("vitoria", None),
        ]

    def test_trocar_tres_vezes_nao_empilha_as_escolhas_velhas_no_topo(self) -> None:
        """A promessa é *o ativo primeiro, o resto na ordem de carga* — sempre."""
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "Ação"
        stub._populate_profiles_store(perfis, None)

        stub._mark_active_profile_row("vitoria")
        stub._mark_active_profile_row("Pragmata")

        assert [nome for nome, _cor in _linhas(stub)] == [
            "Pragmata",
            "Ação",
            "vitoria",
        ]

    def test_sem_cache_a_lista_nao_e_embaralhada(self) -> None:
        """Recarga em voo: a cor e o negrito valem sozinhos, a ordem espera."""
        stub = _stub()
        perfis = _mesa_dela()
        stub._populate_profiles_store(perfis, None)
        stub._mark_active_profile_row("vitoria")
        assert [nome for nome, _cor in _linhas(stub)] == [
            "Ação",
            "Pragmata",
            "vitoria",
        ]
        assert dict(_linhas(stub))["vitoria"] == VERDE_DA_CASA


class TestAOrdemDasLinhasNaoVazaParaADisputa:
    """O terceiro termo do desempate é a ORDEM DE CARGA do loader."""

    @staticmethod
    def _mesa_de_empate() -> list[Profile]:
        return [_catch_all("aaa", 9), _catch_all("bbb", 5), _catch_all("zzz", 9)]

    def test_o_tooltip_nao_recita_fila_nenhuma(self) -> None:
        stub = _stub()
        perfis = self._mesa_de_empate()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "bbb"
        stub._populate_profiles_store(perfis, None)

        tooltips = {linha[0]: linha[4] for linha in stub._profiles_store}
        assert tooltips == {"aaa": "", "bbb": "", "zzz": ""}

    def test_a_linha_no_topo_nao_inventa_vencedor(self) -> None:
        stub = _stub()
        perfis = self._mesa_de_empate()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "bbb"
        stub._populate_profiles_store(perfis, None)

        colunas = {linha[0]: linha[2] for linha in stub._profiles_store}
        assert colunas == {"aaa": "Sempre", "bbb": "Sempre", "zzz": "Sempre"}

    def test_a_coluna_zero_continua_sendo_so_o_nome(self) -> None:
        """Marcador textual ali quebraria Salvar, Ativar, Duplicar e Remover."""
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "vitoria"
        stub._populate_profiles_store(perfis, None)
        assert sorted(nome for nome, _cor in _linhas(stub)) == sorted(
            p.name for p in perfis
        )
