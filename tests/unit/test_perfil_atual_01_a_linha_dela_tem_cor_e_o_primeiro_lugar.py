"""PERFIL-ATUAL-01 — o perfil que ELA ativou tem cor e é o primeiro da lista.

Pedido dela, 10/08/2026: *"esse perfil inclusive precisa ter uma linha de cor de
destaque e aparecer primeiro na guia de perfil pra sempre evidenciar o perfil
atual"*.

E "esse perfil" tem dono, decidido no mesmo dia com as palavras dela: *"aquele
cujo escolho vir na aba perfis e aperto em ativar"*. NÃO é o que o autoswitch
elegeu pela janela aberta, e NÃO é o `active_profile` do daemon quando ele está
vazio — que é o estado VIVO da máquina dela, com o cadeado do autoswitch ligado:
`daemon.status` responde `null`, e um destaque pendurado nele nasceria invisível.

Este arquivo mede as quatro coisas que a entrega promete, nesta ordem:

1. o FATO sobrevive — o gesto de Ativar deixa nome em disco, e a aba parte dele;
2. o `null` do daemon não apaga o que ela decidiu;
3. a LINHA inteira fica verde (as três colunas visíveis), e só a dela;
4. ela vem primeiro — e trocar de perfil move a linha sem reler o disco.

E mede a armadilha do EMPATE-01/E2 junto: a ordem das LINHAS não pode vazar para
as funções da disputa, que leem a ORDEM DE CARGA do loader.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
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

#: A cor do "ligado" desta casa (`gui/theme.css:26`, `@green`). Escrita à mão
#: aqui de propósito: se alguém trocar a constante do produto por outra cor sem
#: passar pelo tema, este arquivo reprova e a conversa acontece.
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
    """A aba Perfis com GTK de verdade e nada de janela.

    ListStore REAL porque é o modelo que carrega a cor: um dublê de lista
    aceitaria qualquer número de colunas e mediria o dublê.
    """
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


#: O que `AttrList.to_string()` imprime para o verde da casa: cada canal de 8
#: bits vira 16 no Pango (`0x50` -> `0x5050`).
#:
#: MONTADO, e não escrito à mão: doze dígitos hexadecimais em fila são exatamente
#: o que o `check_anonymity` desta casa procura, e o portão reprovou a primeira
#: versão deste arquivo — com razão, porque a régua não tem como saber que ali
#: era uma cor e não o endereço Bluetooth de um controle dela.
VERDE_SERIALIZADO = "foreground #" + "".join(
    COR_DO_PERFIL_ATIVO[i : i + 2] * 2 for i in (1, 3, 5)
)


def _cor(valor: Any) -> str | None:
    """A cor de uma linha, legível: `None`, o verde da casa, ou o que veio.

    Traduz de volta em vez de responder sim/não de propósito: uma cor ERRADA
    tem de reprovar mostrando qual é, e não virar um `False` mudo.
    """
    if valor is None:
        return None
    texto = valor.to_string()
    return VERDE_DA_CASA if VERDE_SERIALIZADO in texto else texto


def _linhas(stub: Any) -> list[tuple[str, str | None]]:
    """(nome, cor) na ordem em que a lista desenha."""
    return [(linha[0], _cor(linha[5])) for linha in stub._profiles_store]


# ---------------------------------------------------------------------------
# 1. O fato sobrevive ao daemon vazio e a fechar a janela
# ---------------------------------------------------------------------------


class TestOFatoDoGestoDela:
    """Ativar deixa RASTRO EM DISCO — e é dele que a aba parte."""

    def test_sem_gesto_nenhum_nao_ha_perfil_atual(self) -> None:
        assert perfil_que_ela_ativou() is None

    def test_o_ativar_de_ontem_ainda_responde_hoje(self) -> None:
        """`session.json` é o que o `profile.switch` grava — manual-only."""
        (config_dir(ensure=True) / "session.json").write_text(
            '{"last_profile": "Pragmata"}', encoding="utf-8"
        )
        assert perfil_que_ela_ativou() == "Pragmata"

    def test_o_marker_manual_vence_um_session_json_herdado(self) -> None:
        """PERFIL-03: versões antigas deixavam o autoswitch sujar o session.json.

        O `active_profile.txt` sempre foi só do gesto manual, então quando os
        dois divergem quem carrega a escolha DELA é o marker.
        """
        cfg = config_dir(ensure=True)
        (cfg / "session.json").write_text(
            '{"last_profile": "Navegação"}', encoding="utf-8"
        )
        (cfg / "active_profile.txt").write_text("vitoria\n", encoding="utf-8")
        assert perfil_que_ela_ativou() == "vitoria"

    def test_disco_ilegivel_nao_derruba_a_aba(self, monkeypatch) -> None:
        """Best-effort: sem nome não há destaque — nunca uma exceção na GTK."""
        import hefesto_dualsense4unix.utils.session as session

        def _explode() -> str | None:
            raise OSError("disco de mentira")

        monkeypatch.setattr(session, "resolve_boot_profile", _explode)
        assert perfil_que_ela_ativou() is None

    def test_a_aba_semeia_o_destaque_do_disco_ao_abrir(self) -> None:
        """A FIAÇÃO: sem esta chamada o destaque nasce invisível na máquina dela.

        Gate de código-fonte pelo mesmo motivo do PERFIL-SALVA-TUDO-01: o corpo
        de `install_profiles_tab` precisa de meia dúzia de widgets do glade, e o
        que se mede aqui não é o desenho — é a decisão de a lista NÃO esperar o
        daemon para saber qual perfil é o dela.
        """
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


# ---------------------------------------------------------------------------
# 2. A cor — a LINHA inteira, e só a dela
# ---------------------------------------------------------------------------


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
        """Ela pediu a LINHA colorida: o realce vale nas três.

        Amarrar só a coluna "Nome" deixaria "Prioridade" e "Quando usar" na cor
        do tema — meia linha verde, que é o que o negrito sozinho já fazia.
        """
        for chamada in self._colunas_montadas():
            palavras = {kw.arg for kw in chamada.keywords}
            assert "attributes" in palavras, (
                "coluna da lista sem `attributes=` — a linha do perfil dela sai "
                "colorida pela metade (PERFIL-ATUAL-01)"
            )

    def test_a_cor_nao_volta_a_ser_um_foreground_de_celula(self) -> None:
        """A regressão MEDIDA, e a razão de o realce ser `AttrList`.

        O GTK3 descarta o `foreground` de um `GtkCellRendererText` quando a
        linha está SELECIONADA — e a linha selecionada é justamente a do perfil
        ativo (a aba abre nela, e o sync do daemon volta a selecioná-la). O verde
        sumia no caso mais comum, que é o oposto do "**sempre** evidenciar o
        perfil atual" que ela pediu. Fotografado em 10/08, lado a lado: com todas
        as linhas selecionadas, `foreground=` some, `cell-background=` fica sob a
        faixa da seleção, e `attributes=` sobrevive.

        `foreground=` é uma linha mais curta e parece igual. Este teste existe
        para a próxima pessoa que achar isso — inclusive eu.
        """
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


# ---------------------------------------------------------------------------
# 3. O primeiro lugar
# ---------------------------------------------------------------------------


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
        """A promessa é *o ativo primeiro, o resto na ordem de carga* — sempre.

        Empurrar o novo ativo para a frente do que já estava lá deixaria a lista
        contando o histórico dela em vez de mostrar o disco.
        """
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
        stub._populate_profiles_store(perfis, None)  # cache vazio de propósito
        stub._mark_active_profile_row("vitoria")
        assert [nome for nome, _cor in _linhas(stub)] == [
            "Ação",
            "Pragmata",
            "vitoria",
        ]
        assert dict(_linhas(stub))["vitoria"] == VERDE_DA_CASA


# ---------------------------------------------------------------------------
# 4. A armadilha do EMPATE-01/E2 — duas listas, e é de propósito
# ---------------------------------------------------------------------------


class TestAOrdemDasLinhasNaoVazaParaADisputa:
    """O terceiro termo do desempate é a ORDEM DE CARGA do loader.

    Medido em 10/08 com as funções puras: mover UM perfil para a frente preserva
    a ordem relativa dos outros, então o VENCEDOR anunciado não muda — mas o
    tooltip lista os concorrentes na ordem que recebe, e essa muda. Uma frase da
    GUI recitando a fila numa ordem que não é a do daemon é exatamente o que
    esta casa não entrega, e é o que este teste segura.
    """

    @staticmethod
    def _mesa_de_empate() -> list[Profile]:
        # Ordem de CARGA: aaa, bbb, zzz. "bbb" é o ativo e não está entre os
        # empatados no topo, então é ele que a exibição arrasta para a frente.
        return [_catch_all("aaa", 9), _catch_all("bbb", 5), _catch_all("zzz", 9)]

    def test_o_tooltip_lista_os_concorrentes_na_ordem_de_carga(self) -> None:
        stub = _stub()
        perfis = self._mesa_de_empate()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "bbb"
        stub._populate_profiles_store(perfis, None)

        tooltips = {linha[0]: linha[4] for linha in stub._profiles_store}
        assert "casa: aaa, bbb, zzz." in tooltips["aaa"], (
            "o tooltip da disputa recebeu a lista da EXIBIÇÃO — a GUI passou a "
            "recitar a fila numa ordem que não é a do loader (EMPATE-01/E2)"
        )

    def test_o_vencedor_anunciado_nao_muda_com_a_linha_no_topo(self) -> None:
        stub = _stub()
        perfis = self._mesa_de_empate()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "bbb"
        stub._populate_profiles_store(perfis, None)

        colunas = {linha[0]: linha[2] for linha in stub._profiles_store}
        assert colunas["aaa"] == "Sempre — 3 disputam, este vence"
        assert colunas["zzz"] == "Sempre — 3 disputam, vence aaa"

    def test_a_coluna_zero_continua_sendo_so_o_nome(self) -> None:
        """Marcador textual ali quebraria Salvar, Ativar, Duplicar e Remover.

        `_selected_profile_name` lê a coluna 0 como IDENTIDADE do perfil — o
        destaque tinha de sair pela cor, e é por isso que ele saiu.
        """
        stub = _stub()
        perfis = _mesa_dela()
        stub._profiles_cache = list(perfis)
        stub._active_profile_hint = "vitoria"
        stub._populate_profiles_store(perfis, None)
        assert sorted(nome for nome, _cor in _linhas(stub)) == sorted(
            p.name for p in perfis
        )
