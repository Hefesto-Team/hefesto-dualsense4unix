"""NUNCA-TROCA-O-ALVO-01 — a janela trocava o nome no editor sozinha.

Queixa literal dela, 06/08/2026: *"clico em salvar e ele salva com um nome
aleatório ou de outro perfil"*.

Medido em bancada antes de qualquer linha de cura. `_populate_editor` reescreve
o campo Nome sem guarda nenhuma, e quem o dispara é o sinal `changed` da SELEÇÃO
da lista — que a própria janela emite programaticamente em três caminhos:

1. **O autoswitch.** Ela ativa `vitoria`, edita as abas, abre o jogo; o
   autoswitch troca para `sackboy_nativo`; ao VOLTAR para a aba Perfis o
   `switch-page` chama `_sync_selection_with_active_profile`, a seleção pula e
   o campo Nome vira `sackboy_nativo`. O Salvar seguinte gravava lá — e como
   `_edita_o_perfil_do_rascunho` compara com `_active_profile_name` (ainda
   `vitoria`), a base vinha do DISCO: a cor dela não ia para lugar nenhum.
   Medido: *"o VERDE dela foi parar em algum arquivo? NÃO — evaporou"*.
2. **O "nome aleatório".** `_populate_profiles_store` caía no PRIMEIRO da lista
   quando não havia alvo, e `_reload_profiles_store()` é chamado SEM alvo pelo
   "Recarregar lista" e pela remoção. No disco dela o primeiro arquivo é
   `acao.json` — o editor pulava para "Ação".
3. **O rodapé.** O diálogo "Salvar Perfil" nascia pré-preenchido com
   `_active_profile_name`, uma segunda variável escrita pela janela com a
   resposta do daemon; o `prompt_overwrite_existing` até abria, mas perguntando
   *"substituir sackboy_nativo?"* — o nome que a própria janela acabara de pôr.

E o vizinho **I-1**, medido junto: `on_import_profile` comparava NOME CRU
(`if nome in existentes:`) enquanto os DOIS botões de salvar já perguntam por
SLUG. Importar um `Navegacao.json` destruía a `Navegação` dela sem uma palavra
na tela.

O princípio que a cura escreve: **a janela nunca troca o alvo do Salvar sem
gesto dela.** Seleção programática atualiza a LISTA e para por aí.

Cada teste daqui MORDE: com a cura arrancada, ele reprova. A lista de qual cura
cada um morde está na docstring do próprio teste.

GTK de VERDADE (`Gtk.TreeView`/`Gtk.ListStore`): o defeito É o sinal `changed`
da seleção, e um dublê de lista não o emite — mediria o dublê, não a janela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("NUNCA-TROCA-O-ALVO-01 (o Salvar que mirava outro perfil)")

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app import gui_dialogs, ipc_bridge
from hefesto_dualsense4unix.app.actions import footer_actions as fa
from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.loader import (
    load_all_profiles,
    profiles_dir,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
)

VERDE = (0, 255, 0)


# ---------------------------------------------------------------------------
# Dublês de widget — só os do EDITOR. A lista é GTK de verdade.
# ---------------------------------------------------------------------------


class _Entry:
    def __init__(self, texto: str = "") -> None:
        self._t = texto

    def get_text(self) -> str:
        return self._t

    def set_text(self, t: str) -> None:
        self._t = t

    def set_placeholder_text(self, t: str) -> None: ...

    def set_tooltip_text(self, t: str) -> None: ...


class _Escala:
    def __init__(self) -> None:
        self._v = 0.0
        self._handlers: list[Any] = []

    def connect(self, sinal: str, handler: Any) -> None:
        if sinal == "value-changed":
            self._handlers.append(handler)

    def get_value(self) -> float:
        return self._v

    def set_value(self, v: float) -> None:
        novo = max(0.0, min(float(pa.PRIORIDADE_MAXIMA), float(v)))
        mudou = novo != self._v
        self._v = novo
        if mudou:
            for h in self._handlers:
                h(self)


class _Stack:
    def __init__(self) -> None:
        self.visivel = ""

    def set_visible_child_name(self, nome: str) -> None:
        self.visivel = nome


class _Switch:
    def __init__(self) -> None:
        self.ativo = False

    def set_active(self, a: bool) -> None:
        self.ativo = a


class _Caixa:
    def show(self) -> None: ...

    def show_all(self) -> None: ...

    def hide(self) -> None: ...

    def set_no_show_all(self, v: bool) -> None: ...


class _Seletor:
    """Mesma API por-ID do SegmentedSelector: `changed` sai de `set_active_id`."""

    def __init__(self, ativo: str = "any") -> None:
        self._id = ativo
        self._handlers: list[Any] = []

    def connect(self, sinal: str, handler: Any) -> None:
        if sinal == "changed":
            self._handlers.append(handler)

    def get_active_id(self) -> str | None:
        return self._id

    def set_active_id(self, novo: str) -> None:
        if novo == self._id:
            return
        self._id = novo
        for h in list(self._handlers):
            h(self)


# ---------------------------------------------------------------------------
# A janela: os DOIS mixins que o HefestoApp compõe, com a lista REAL do GTK
# ---------------------------------------------------------------------------


class _Janela(pa.ProfilesActionsMixin, FooterActionsMixin):  # type: ignore[misc]
    def __init__(self, draft: DraftConfig, ativo: str) -> None:
        from gi.repository import GObject, Gtk

        self.draft = draft
        self._draft_baseline: Any = draft
        self._active_profile_name = ativo
        self._profiles_cache: list[Profile] = list(load_all_profiles())
        self._duplicate_source = None
        self._new_profile = False
        self._mode_advanced = False
        self._suppress_advanced_toggle = False
        self._mode_kind_selector = None
        self._modo_tocado = False
        self._pending_brightness = 1.0
        self._regra_do_disco = None
        self._assinatura_da_regra_ao_abrir = None
        self._prioridade_do_disco = None
        self._prioridade_ao_abrir = None
        self._regra_tocada = False
        self._prioridade_tocada = False
        self.toasts: list[str] = []
        self.dialogos: list[str] = []

        # A MESMA montagem de `install_profiles_tab` (5 colunas: nome,
        # prioridade, "quando usar", peso da fonte, tooltip da disputa).
        tree = Gtk.TreeView()
        store = Gtk.ListStore(
            GObject.TYPE_STRING,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
        )
        tree.set_model(store)
        self._profiles_store = store
        self._widgets: dict[str, Any] = {
            "profiles_tree": tree,
            "profile_name_entry": _Entry(""),
            "profile_priority_scale": _Escala(),
            "profile_simple_custom_name": _Entry(""),
            "profile_window_class_entry": _Entry(""),
            "profile_title_regex_entry": _Entry(""),
            "profile_process_name_entry": _Entry(""),
            "profile_game_entry_box": _Caixa(),
            "profile_editor_stack": _Stack(),
            "profile_advanced_switch": _Switch(),
            "main_window": None,
        }
        self._aplica_a = _Seletor("any")
        self._aplica_a.connect("changed", self._on_aplica_a_changed)
        self._widgets["profile_priority_scale"].connect(
            "value-changed", self._on_prioridade_tocada
        )
        # A linha exata de `install_profiles_tab` — o que liga seleção a editor.
        tree.get_selection().connect("changed", self.on_profile_selection_changed)

    # R-08: o "há edição pendente" é o do HefestoApp REAL — é ele que decide se
    # a repintura do editor pode passar por cima do que ela não salvou.
    def _tem_edicao_pendente(self) -> bool:
        from hefesto_dualsense4unix.app.app import HefestoApp

        return bool(HefestoApp._tem_edicao_pendente(self))  # type: ignore[arg-type]

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _refresh_preview(self) -> None: ...

    def _prefill_steam_appid(self) -> None: ...

    def _notify_launch_env_refresh(self) -> None: ...

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)

    def _footer_toast(self, msg: str, context: str = "footer") -> None:
        self.toasts.append(msg)

    def _status_toast(self, contexto: str, msg: str) -> None:
        self.toasts.append(msg)

    # --- leitura de tela, para os testes falarem a língua dela ---

    def nome_no_editor(self) -> str:
        return self._get("profile_name_entry").get_text()

    def linha_selecionada(self) -> str | None:
        return self._selected_profile_name()

    def linha_em_negrito(self) -> str | None:
        for linha in self._profiles_store:
            if linha[3] == 700:
                return str(linha[0])
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sincrono(fn: Any, on_success: Any, on_failure: Any = None) -> None:
    """Worker e callback na mesma thread — a fixture de sempre da casa."""
    try:
        r = fn()
    except Exception as exc:  # pragma: no cover — só se o teste montar errado
        if on_failure is not None:
            on_failure(exc)
        return
    on_success(r)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> Path:
    """O disco dela, reduzido ao que a queixa envolve. XDG já é tmp (conftest)."""
    monkeypatch.setattr(pa, "run_in_thread", _sincrono)
    monkeypatch.setattr(ipc_bridge, "run_in_thread", _sincrono)
    monkeypatch.setattr(pa, "call_async", lambda **kw: None)
    monkeypatch.setattr(pa, "profile_switch", lambda name: False)
    monkeypatch.setattr(pa, "active_profile_name", lambda: None)

    save_profile(
        Profile(
            name="vitoria",
            match=MatchAny(),
            priority=0,
            leds=LedsConfig(lightbar=(0, 0, 255)),
        )
    )
    save_profile(
        Profile(
            name="sackboy_nativo",
            match=MatchAny(),
            priority=191,
            leds=LedsConfig(lightbar=(255, 0, 0)),
        )
    )
    save_profile(
        Profile(
            name="Pragmata",
            match=MatchCriteria(window_class=["steam_app_3357650"]),
            priority=85,
            leds=LedsConfig(lightbar=(97, 53, 131)),
        )
    )
    return profiles_dir()


def _em_disco(disco: Path, slug: str) -> dict[str, Any]:
    arquivo = disco / f"{slug}.json"
    return json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}


def _sem_dialogos(janela: _Janela, monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo diálogo vira registro + "ela clicou OK".

    Se a lista de diálogos ficar vazia é porque NENHUM apareceu na tela dela —
    e é essa a diferença entre "a janela perguntou" e "a janela fez calada".
    """
    monkeypatch.setattr(
        gui_dialogs,
        "prompt_overwrite_existing",
        lambda parent, name: janela.dialogos.append(f"SOBRESCREVER:{name}") or True,
    )
    monkeypatch.setattr(
        gui_dialogs,
        "confirm_downgrade_match_to_any",
        lambda parent, name, regra_atual=None: janela.dialogos.append(f"REGRA:{name}")
        or True,
    )
    monkeypatch.setattr(
        gui_dialogs,
        "confirm_downgrade_priority",
        lambda parent, name, de, para: janela.dialogos.append(f"PRIORIDADE:{name}")
        or True,
    )
    monkeypatch.setattr(
        janela,
        "_prompt_rename_or_copy",
        lambda antigo, novo: janela.dialogos.append(f"RENOMEAR:{antigo}->{novo}")
        or "renomear",
    )


def _abrir_no_perfil(janela: _Janela, nome: str) -> None:
    """O gesto dela: a aba abre e o editor mostra o perfil que ela ativou."""
    janela._reload_profiles_store(select_name=nome)
    assert janela.nome_no_editor() == nome


def _ela_mexe_na_cor(janela: _Janela) -> None:
    """O gesto das OUTRAS abas: elas gravam só em `self.draft` (R-08)."""
    leds = janela.draft.leds.model_copy(update={"lightbar_rgb": VERDE})
    janela.draft = janela.draft.model_copy(update={"leds": leds})
    assert janela._tem_edicao_pendente() is True


def _verde_em_disco(disco: Path) -> list[str]:
    """Em que arquivos a cor dela foi parar. Vazio = evaporou."""
    achados = []
    for arquivo in sorted(disco.glob("*.json")):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        if tuple(dados.get("leds", {}).get("lightbar") or ()) == VERDE:
            achados.append(arquivo.name)
    return achados


# ===========================================================================
# MORDIDA 1 — o autoswitch e a volta para a aba Perfis
# ===========================================================================


class TestOAutoswitchNaoTrocaOAlvo:
    """Morde a recusa de `_select_profile_by_name` + o portão de
    `on_profile_selection_changed`. Arrancar qualquer uma das duas devolve o
    campo Nome trocado sozinho e o Salvar no arquivo errado."""

    def test_o_campo_nome_nao_troca_sozinho(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        _ela_mexe_na_cor(janela)

        # Ela abre o jogo e volta para a aba Perfis: `switch-page` ->
        # `_sync_selection_with_active_profile` -> este callback.
        janela._on_daemon_status_for_sync({"active_profile": "sackboy_nativo"})

        assert janela.nome_no_editor() == "vitoria", (
            "a janela trocou o nome no editor sozinha — o Salvar seguinte grava "
            "no perfil do jogo e o trabalho dela evapora"
        )
        assert janela.linha_selecionada() == "vitoria", (
            "a barra azul pulou de linha sem gesto dela: o 'Ativar', o "
            "'Duplicar' e o 'Remover' passariam a mirar outro perfil"
        )

    def test_a_lista_continua_dizendo_qual_perfil_esta_ativo(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A recusa é da SELEÇÃO, não da informação: o negrito acompanha.

        Sem isto a cura viraria cegueira — a lista deixaria de dizer que o
        autoswitch trocou de perfil, que é justamente o que ela precisa ver.
        """
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        _ela_mexe_na_cor(janela)

        janela._on_daemon_status_for_sync({"active_profile": "sackboy_nativo"})

        assert janela.linha_em_negrito() == "sackboy_nativo"

    def test_a_cor_dela_vai_para_o_perfil_que_ela_estava_editando(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida com dente: o VERDE tem de existir em disco no fim.

        Medido antes da cura: `sackboy_nativo.json` era regravado (com a cor
        DELE, vinda do disco) e o verde não ia para arquivo nenhum.
        """
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        _ela_mexe_na_cor(janela)
        janela._on_daemon_status_for_sync({"active_profile": "sackboy_nativo"})

        antes_do_jogo = _em_disco(disco, "sackboy_nativo")
        janela.on_profile_save(None)

        assert _verde_em_disco(disco) == ["vitoria.json"], (
            "a cor dela evaporou (ou foi parar no perfil do jogo)"
        )
        assert _em_disco(disco, "sackboy_nativo") == antes_do_jogo, (
            "o Salvar gravou por cima do perfil do JOGO"
        )
        assert janela.toasts[-1] == "Perfil salvo: vitoria"

    def test_sem_edicao_pendente_a_selecao_acompanha_o_perfil_ativo(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura não pode virar cadeado.

        Sem trabalho a perder, a aba continua abrindo no perfil ATIVO — que é
        a FEAT-GUI-LOAD-LAST-PROFILE-01 inteira. Se este teste reprovar, a
        guarda parou de perguntar e passou a recusar sempre.
        """
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")

        janela._on_daemon_status_for_sync({"active_profile": "sackboy_nativo"})

        assert janela.nome_no_editor() == "sackboy_nativo"
        assert janela.linha_selecionada() == "sackboy_nativo"


# ===========================================================================
# MORDIDA 2 — o "nome aleatório": o primeiro da lista
# ===========================================================================


class TestRecarregarAListaNaoPulaParaOPrimeiro:
    """Morde a preservação da seleção em `_populate_profiles_store`. Arrancada,
    o editor volta a pular para o primeiro arquivo em ordem de carga."""

    def test_o_botao_recarregar_lista_nao_troca_o_perfil_do_editor(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        primeiro = janela._profiles_cache[0].name
        assert primeiro != "vitoria", "o disco do teste não exercita o fallback"

        janela.on_profile_reload(None)

        assert janela.nome_no_editor() == "vitoria", (
            f"o editor pulou para '{primeiro}' — o primeiro da lista — e o "
            "Salvar seguinte gravaria lá"
        )
        assert janela.linha_selecionada() == "vitoria"

    def test_recarregar_e_salvar_nao_grava_no_primeiro_da_lista(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        primeiro = janela._profiles_cache[0].name
        antes = _em_disco(disco, "pragmata")

        janela.on_profile_reload(None)
        janela.on_profile_save(None)

        assert janela.toasts[-1] == "Perfil salvo: vitoria", (
            f"o Salvar mirou '{primeiro}'"
        )
        assert _em_disco(disco, "pragmata") == antes

    def test_uma_edicao_pendente_sobrevive_a_recarga_da_lista(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A repintura reseleciona a MESMA linha — e nem isso pode repintar.

        `store.clear()` mata os iters, então alguém precisa selecionar de novo;
        essa reseleção emite `changed` igualzinho a um clique dela. Sem a marca
        de "quem mexeu foi o código", o nome que ela estava digitando some.
        """
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        # Ela está renomeando: o campo Nome já diverge do perfil aberto.
        janela._get("profile_name_entry").set_text("vitoria de casa")

        janela.on_profile_reload(None)

        assert janela.nome_no_editor() == "vitoria de casa", (
            "recarregar a lista apagou o nome que ela estava digitando"
        )

    def test_o_salvar_nao_segue_a_linha_quando_o_arquivo_dela_some(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Morde o alvo MEMORIZADO (`_alvo_do_salvar_do_editor`).

        O único caso em que a barra azul se move mesmo com a cura: o perfil
        que estava selecionado SUMIU do disco (a CLI apagou, um rename por
        fora) e a lista não tem para onde voltar — cai no primeiro. Com o
        editor sujo, ele fica mostrando o perfil que sumiu enquanto a linha
        mostra outro.

        Se o Salvar lesse o WIDGET, veria 'Pragmata' selecionado e 'vitoria'
        no campo Nome, concluiria RENAME pela R-10 e se ofereceria para APAGAR
        a Pragmata dela — um perfil que não tem nada a ver com o gesto.
        """
        from hefesto_dualsense4unix.profiles.loader import delete_profile

        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        _ela_mexe_na_cor(janela)

        delete_profile("vitoria")  # por fora da janela: CLI, rename, backup
        janela.on_profile_reload(None)
        assert janela.nome_no_editor() == "vitoria"
        assert janela.linha_selecionada() != "vitoria", (
            "o teste não exercita a divergência que quer medir"
        )

        janela.on_profile_save(None)

        assert not [d for d in janela.dialogos if d.startswith("RENOMEAR")], (
            "a janela se ofereceu para apagar um perfil que ela não tocou"
        )
        assert (disco / "pragmata.json").exists()
        assert _verde_em_disco(disco) == ["vitoria.json"]


# ===========================================================================
# MORDIDA 3 — o rodapé
# ===========================================================================


class TestORodapeNaoPropoeNomeQueElaNaoEscolheu:
    """Morde `_perfil_que_as_abas_editam` e o anúncio da reconciliação."""

    def test_o_prefill_vem_do_rascunho_e_nao_do_perfil_ativo(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """As abas mostram `vitoria`; o daemon está em `sackboy_nativo`.

        Antes, o diálogo do rodapé nascia com o nome do perfil do DAEMON — e o
        "Salvar este perfil" da aba Perfis, na mesma janela e no mesmo
        instante, mirava outro arquivo. Os dois botões discordavam.
        """
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="sackboy_nativo")

        capturado: dict[str, Any] = {}

        class _Dialogos:
            @staticmethod
            def prompt_profile_name(parent: Any, default_name: str = "") -> str | None:
                capturado["prefill"] = default_name
                return None  # ela cancela: este teste é sobre o que ela LÊ

        monkeypatch.setattr(fa, "gui_dialogs", _Dialogos)
        janela.on_save_profile()

        assert capturado["prefill"] == "vitoria", (
            "o diálogo propôs o perfil do DAEMON, não o que as abas mostram"
        )

    def test_sem_fotografia_no_rascunho_o_perfil_ativo_ainda_serve(
        self, disco: Path
    ) -> None:
        """Boot sem daemon: rascunho em defaults, sem `source_name`."""
        janela = _Janela(DraftConfig.default(), ativo="sackboy_nativo")
        assert janela._perfil_que_as_abas_editam() == "sackboy_nativo"

    def test_a_janela_anuncia_quando_ela_mesma_troca_o_alvo(self) -> None:
        """O tique de 2 Hz troca o rascunho quando não há nada a perder.

        A troca é legítima — mas movia o alvo dos DOIS botões de salvar sem
        gesto dela, e em silêncio. Era o silêncio que fazia o diálogo do rodapé
        parecer que tinha inventado um nome.
        """
        from hefesto_dualsense4unix.app.app import HefestoApp

        class _Falsa:
            def __init__(self) -> None:
                base = DraftConfig.default()
                self.draft = base
                self._draft_baseline: Any = base
                self._active_profile_name = "vitoria"
                self._draft_reload_for: str | None = None
                self._draft_reload_inflight = False
                self._draft_reload_inflight_since = 0.0
                self.toasts: list[tuple[str, str]] = []

            _tem_edicao_pendente = HefestoApp._tem_edicao_pendente

            def _status_toast(self, contexto: str, msg: str) -> None:
                self.toasts.append((contexto, msg))

            def _bootstrap_draft_async(self) -> None: ...

        falsa = _Falsa()
        HefestoApp._reconciliar_draft_com_perfil_ativo(
            falsa, {"active_profile": "sackboy_nativo"}
        )

        assert falsa.toasts, "a janela trocou o alvo do Salvar sem dizer nada"
        contexto, msg = falsa.toasts[0]
        assert contexto == "draft-reload"
        assert "sackboy_nativo" in msg
        assert "Salvar" in msg


# ===========================================================================
# MORDIDA 4 — M2: a guarda da cura falhava ABERTO
# ===========================================================================


def _quebrar_a_pergunta(janela: _Janela, monkeypatch: pytest.MonkeyPatch) -> None:
    """`_tem_edicao_pendente` deixa de saber responder.

    Não é hipótese de laboratório gratuita: a resposta sai de comparar dois
    pydantic (`self.draft != baseline`), e QUALQUER `__eq__` que estoure — um
    campo novo com comparação frágil, um dublê incompleto num caminho de
    degradação — cai aqui. O ponto não é a probabilidade; é o que a guarda
    responde quando não sabe.
    """

    def _estoura() -> bool:
        raise RuntimeError("R-08 indisponível: a comparação do rascunho estourou")

    monkeypatch.setattr(janela, "_tem_edicao_pendente", _estoura)


class TestNaoSeiEHaTrabalhoAProteger:
    """M2 (revisão adversarial de 06/08/2026): o `except` respondia ``False``.

    Uma guarda cujo único trabalho é proteger trabalho não salvo não pode ler
    *"não sei"* como *"não há nada a perder"*. Medido: com o ``return False``
    de volta, os três testes desta classe reprovam e o defeito INTEIRO
    ressuscita — o editor pula para o perfil do jogo e o Salvar grava lá.

    MORDIDA verificada em 06/08: trocado o ``return True`` por ``return False``
    em `_ha_trabalho_no_editor`, 3/3 reprovam.
    """

    def test_a_guarda_responde_sim_quando_nao_sabe_responder(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        _quebrar_a_pergunta(janela, monkeypatch)

        assert janela._ha_trabalho_no_editor() is True, (
            "o portão abriu no escuro — 'não sei' virou 'pode repintar o editor'"
        )

    def test_o_campo_nome_nao_troca_quando_a_pergunta_estoura(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        _ela_mexe_na_cor(janela)  # o VERDE entra no rascunho...
        _quebrar_a_pergunta(janela, monkeypatch)  # ...e a janela perde a memória

        janela._on_daemon_status_for_sync({"active_profile": "sackboy_nativo"})

        assert janela.nome_no_editor() == "vitoria", (
            "com a pergunta quebrada a janela trocou o nome sozinha — é o "
            "defeito inteiro de volta, pela porta do `except`"
        )
        assert janela.linha_selecionada() == "vitoria"

    def test_o_salvar_nao_vai_para_o_arquivo_errado_quando_a_pergunta_estoura(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida com dente: onde a cor dela foi parar.

        É a MESMA asserção do caminho feliz (`MORDIDA 1`), com a única
        diferença de a guarda estar cega. Se o resultado divergir, a cura só
        vale enquanto tudo funciona — que é o oposto de uma guarda.
        """
        vitoria = next(p for p in load_all_profiles() if p.name == "vitoria")
        janela = _Janela(DraftConfig.from_profile(vitoria), ativo="vitoria")
        _sem_dialogos(janela, monkeypatch)
        _abrir_no_perfil(janela, "vitoria")
        _ela_mexe_na_cor(janela)
        _quebrar_a_pergunta(janela, monkeypatch)
        janela._on_daemon_status_for_sync({"active_profile": "sackboy_nativo"})

        antes_do_jogo = _em_disco(disco, "sackboy_nativo")
        janela.on_profile_save(None)

        assert _verde_em_disco(disco) == ["vitoria.json"], (
            "a cor dela evaporou (ou foi parar no perfil do jogo) porque a "
            "guarda abriu no escuro"
        )
        assert _em_disco(disco, "sackboy_nativo") == antes_do_jogo, (
            "o Salvar gravou por cima do perfil do JOGO"
        )
        assert janela.toasts[-1] == "Perfil salvo: vitoria"


# ===========================================================================
# MORDIDA 5 — I-1: o importar comparava nome cru
# ===========================================================================


class _Chooser:
    """Dublê do `Gtk.FileChooserDialog` — o único GTK que exige tela aqui."""

    arquivo: str = ""

    def __init__(self, **kwargs: Any) -> None: ...

    def add_button(self, *a: Any) -> None: ...

    def add_filter(self, *a: Any) -> None: ...

    def set_default_response(self, *a: Any) -> None: ...

    def run(self) -> Any:
        from gi.repository import Gtk

        return Gtk.ResponseType.OK

    def get_filename(self) -> str:
        return _Chooser.arquivo

    def destroy(self) -> None: ...


class TestOImportarPerguntaPeloSlug:
    """Morde a troca de `nome in existentes` por `find_by_slug` (I-1)."""

    @staticmethod
    def _importar(
        janela: _Janela,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        perfil: Profile,
        escolha: str | None,
    ) -> list[str]:
        from gi.repository import Gtk

        arquivo = tmp_path / f"{perfil.name}.json"
        arquivo.write_text(perfil.model_dump_json(indent=2), encoding="utf-8")
        _Chooser.arquivo = str(arquivo)
        monkeypatch.setattr(Gtk, "FileChooserDialog", _Chooser)

        perguntas: list[str] = []

        from hefesto_dualsense4unix.app import gui_dialogs as gd_real

        class _Dialogos:
            # DIÁLOGO-QUE-MATA-A-JANELA-01 (06/08/2026): o seletor de arquivo
            # passou a abrir pelo envelope da casa. O dublê usa o envelope DE
            # VERDADE (só o `_Chooser` é falso) — trocá-lo por um `lambda` que
            # devolvesse OK esconderia deste teste justamente a camada nova.
            executar_dialogo = staticmethod(gd_real.executar_dialogo)

            @staticmethod
            def prompt_import_conflict(parent: Any, name: str) -> str | None:
                perguntas.append(name)
                return escolha

            @staticmethod
            def prompt_profile_name(parent: Any, default_name: str = "") -> str | None:
                return default_name

        monkeypatch.setattr(fa, "gui_dialogs", _Dialogos)
        janela.on_import_profile()
        return perguntas

    @pytest.mark.parametrize(
        ("no_disco", "importado"),
        [
            ("Navegação", "Navegacao"),
            ("Ação", "AÇÃO"),
            ("FPS", "fps"),
        ],
    )
    def test_o_acento_dela_nao_passa_batido(
        self,
        disco: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        no_disco: str,
        importado: str,
    ) -> None:
        """Importar um `Navegacao.json` destruía a `Navegação` dela, calado.

        Os dois nomes ocupam o MESMO arquivo (o slug é a identidade em disco),
        e só o `find_by_slug` responde isso.
        """
        save_profile(
            Profile(
                name=no_disco,
                match=MatchCriteria(window_class=["firefox"]),
                priority=50,
                leds=LedsConfig(lightbar=(1, 2, 3)),
            )
        )
        janela = _Janela(DraftConfig.default(), ativo="vitoria")
        antes = _em_disco(disco, pa_slug(no_disco))

        perguntas = self._importar(
            janela,
            monkeypatch,
            tmp_path,
            Profile(name=importado, match=MatchAny(), priority=7),
            escolha=None,  # ela lê a pergunta e CANCELA
        )

        assert perguntas == [no_disco], (
            f"importar '{importado}' não perguntou nada — o arquivo de "
            f"'{no_disco}' seria substituído em silêncio"
        )
        assert _em_disco(disco, pa_slug(no_disco)) == antes, (
            "o perfil dela foi destruído mesmo com ela cancelando"
        )

    def test_o_nome_novo_do_renomear_tambem_responde_pelo_slug(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Renomear para um slug ocupado entraria pela porta dos fundos."""
        save_profile(Profile(name="Ação", match=MatchAny(), priority=50))
        save_profile(Profile(name="Corrida", match=MatchAny(), priority=50))
        janela = _Janela(DraftConfig.default(), ativo="vitoria")
        antes = _em_disco(disco, pa_slug("Ação"))

        from gi.repository import Gtk

        # Ela importa um "Corrida" que colide com o "Corrida" do disco, escolhe
        # RENOMEAR — e digita um nome que ocupa o arquivo de OUTRO perfil dela.
        arquivo = tmp_path / "Corrida.json"
        arquivo.write_text(
            Profile(name="Corrida", match=MatchAny(), priority=7).model_dump_json(),
            encoding="utf-8",
        )
        _Chooser.arquivo = str(arquivo)
        monkeypatch.setattr(Gtk, "FileChooserDialog", _Chooser)

        from hefesto_dualsense4unix.app import gui_dialogs as gd_real

        class _Dialogos:
            # DIÁLOGO-QUE-MATA-A-JANELA-01 (06/08/2026): o envelope de verdade,
            # como no dublê irmão logo acima.
            executar_dialogo = staticmethod(gd_real.executar_dialogo)

            @staticmethod
            def prompt_import_conflict(parent: Any, name: str) -> str | None:
                return "renomear"

            @staticmethod
            def prompt_profile_name(parent: Any, default_name: str = "") -> str | None:
                return "AÇÃO"  # mesmo slug de quem já está lá

        monkeypatch.setattr(fa, "gui_dialogs", _Dialogos)
        janela.on_import_profile()

        assert _em_disco(disco, pa_slug("Ação")) == antes, (
            "renomear para o mesmo slug destruiu o perfil dela"
        )
        assert any("mesmo arquivo" in t for t in janela.toasts), (
            "nada na tela dela explicou por que a importação parou"
        )


def pa_slug(nome: str) -> str:
    from hefesto_dualsense4unix.profiles.slug import slugify

    return slugify(nome)
