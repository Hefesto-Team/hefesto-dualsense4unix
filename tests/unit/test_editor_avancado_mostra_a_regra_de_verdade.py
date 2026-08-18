"""O "Modo avançado" mostrava três campos VAZIOS no lugar da regra do perfil.

O DEFEITO, fotografado por ela em 10/08/2026 às 04:34 — duas fotos da MESMA
tela, um segundo de diferença:

- avançado DESLIGADO: ``Aplica a: [Jogo da Steam]``, ``Nome do jogo: 3357650``;
- avançado LIGADO: os três campos crus em branco, mostrando só os
  textos-fantasma do glade (``CSV: Steam,firefox``, ``regex (re.search)``,
  ``CSV: doom.x86_64,celeste``).

E o arquivo dela, no mesmo instante, dizia
``window_class: ["steam_app_3357650"]`` — mais o ``process_name`` que a página
simples não mostra (ESCONDER-EM-VEZ-DE-SAIR-01).

A MECÂNICA: ``_populate_editor`` só escreve nos três campos crus no ramo do
match COMPLEXO; no ramo do preset simples ele mexe no seletor e no campo livre
e deixa os crus como estiverem. E ``on_profile_advanced_toggle`` só trocava a
página da stack (``_apply_editor_mode``). Ligar o avançado depois do perfil
aberto, portanto, nunca tinha de onde tirar a regra.

O PREÇO era duplo, e o segundo é pior que o primeiro:

1. a tela AFIRMAVA que o perfil não tem critério nenhum — e o
   ``exigencia_invisivel`` da própria casa manda "Ligue o Modo avançado para
   ver e mudar", ou seja, a janela mandava olhar justamente onde mentia;
2. os campos vazios são o que o ``_build_profile_from_editor`` LÊ quando o
   avançado está ligado. Apagar o que já estava vazio na tela é um gesto dela
   como outro qualquer, e o perfil do jogo dela virava outra coisa em silêncio.

A CURA: ligar o avançado transfere para os três campos a regra que o perfil TEM
agora — a mesma conta que o Salvar faz (``_regra_real_do_perfil_aberto``).

Hermético: widgets falsos com a mesma API por-ID que a aba usa; nenhum GTK
real, nenhum daemon, nenhuma escrita no ``~/.config`` dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("O editor avançado que mostrava campos vazios")

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
)

#: appid do Pragmata — o jogo em que esta família inteira de defeitos foi medida.
APPID = "3357650"
WM_JOGO = f"steam_app_{APPID}"


# ---------------------------------------------------------------------------
# Dublês de widget — a mesma API por-ID que a aba usa
# ---------------------------------------------------------------------------


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text

    def set_placeholder_text(self, text: str) -> None:
        return None

    def set_tooltip_text(self, text: str) -> None:
        return None


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._teto = float(pa.PRIORIDADE_MAXIMA)
        self._value = 0.0
        self._handlers: list[Any] = []
        self.set_value(value)

    def connect(self, sinal: str, handler: Any) -> None:
        if sinal == "value-changed":
            self._handlers.append(handler)

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        novo = max(0.0, min(self._teto, float(value)))
        mudou = novo != self._value
        self._value = novo
        if mudou:
            for handler in self._handlers:
                handler(self)


class _FakeStack:
    def __init__(self) -> None:
        self.visible_child = ""

    def set_visible_child_name(self, name: str) -> None:
        self.visible_child = name


class _FakeSwitch:
    def __init__(self) -> None:
        self.active = False

    def set_active(self, active: bool) -> None:
        self.active = active

    def get_active(self) -> bool:
        return self.active


class _FakeBox:
    """A linha "Nome do jogo:" com a doutrina de visibilidade do GTK."""

    def __init__(self) -> None:
        self.visivel = False
        self.no_show_all = True
        self.filhos_visiveis = False

    def show(self) -> None:
        self.visivel = True

    def show_all(self) -> None:
        if self.no_show_all:
            return
        self.visivel = True
        self.filhos_visiveis = True

    def set_no_show_all(self, valor: bool) -> None:
        self.no_show_all = bool(valor)

    def hide(self) -> None:
        self.visivel = False


class _FakeSelector:
    def __init__(self, active: str | None = None) -> None:
        self._active_id = active
        self._handlers: list[Any] = []

    def connect(self, signal: str, handler: Any) -> None:
        if signal == "changed":
            self._handlers.append(handler)

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        self._active_id = the_id
        for handler in list(self._handlers):
            handler(self)


class Editor(pa.ProfilesActionsMixin):
    """Editor com os métodos REAIS do mixin sobre widgets falsos."""

    def __init__(self, cache: list[Profile] | None = None) -> None:
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry(""),
            "profile_priority_scale": _FakeScale(0),
            "profile_simple_custom_name": _FakeEntry(""),
            "profile_window_class_entry": _FakeEntry(""),
            "profile_title_regex_entry": _FakeEntry(""),
            "profile_process_name_entry": _FakeEntry(""),
            "profile_game_entry_box": _FakeBox(),
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
            "main_window": object(),
        }
        self._profiles_cache: list[Profile] = list(cache or [])
        self._duplicate_source = None
        self._new_profile = False
        self._mode_advanced = False
        self._suppress_advanced_toggle = False
        self._mode_kind_selector = None
        self._aplica_a = _FakeSelector("any")
        self._aplica_a.connect("changed", self._on_aplica_a_changed)
        self._widgets["profile_priority_scale"].connect(
            "value-changed", self._on_prioridade_tocada
        )
        self.selecionado: str | None = None
        self.toasts: list[str] = []
        self.salvos: list[Profile] = []
        self.overwrite_perguntado: list[str] = []
        self.downgrade_perguntado: list[tuple[str, str | None]] = []
        self.manual_perguntado: list[tuple[str, str | None]] = []
        self.prioridade_perguntada: list[tuple[str, int, int]] = []
        self.resposta_overwrite = True
        self.resposta_downgrade = True
        self.resposta_manual = True
        self.resposta_prioridade = True

    # --- a API que o mixin usa ---

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return self.selecionado

    def _refresh_preview(self) -> None:
        return None

    def _prefill_steam_appid(self) -> None:
        return None

    def _reload_profiles_store(self, **_kw: Any) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        return None

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)

    # --- leitura dos três campos crus, na ordem do glade ---

    def campos_crus(self) -> tuple[str, str, str]:
        return (
            self._get("profile_window_class_entry").get_text(),
            self._get("profile_title_regex_entry").get_text(),
            self._get("profile_process_name_entry").get_text(),
        )

    def ligar_o_avancado(self) -> None:
        """O gesto dela: mover o switch "Modo avançado" para LIGADO."""
        switch = self._get("profile_advanced_switch")
        switch.set_active(True)
        self.on_profile_advanced_toggle(switch, True)

    def desligar_o_avancado(self) -> None:
        switch = self._get("profile_advanced_switch")
        switch.set_active(False)
        self.on_profile_advanced_toggle(switch, False)


@pytest.fixture(autouse=True)
def _sem_preferencia_no_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """`on_profile_advanced_toggle` persiste a preferência — aqui não escreve."""
    monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)


def ligar_o_save(editor: Editor, monkeypatch: pytest.MonkeyPatch) -> None:
    """`on_profile_save` real com disco, IPC e diálogos interceptados."""
    import hefesto_dualsense4unix.app.gui_dialogs as gd

    monkeypatch.setattr(
        gd,
        "prompt_overwrite_existing",
        lambda parent, name: (
            editor.overwrite_perguntado.append(name) or editor.resposta_overwrite
        ),
        raising=False,
    )
    monkeypatch.setattr(
        gd,
        "confirm_downgrade_match_to_any",
        lambda parent, name, regra_atual=None: (
            editor.downgrade_perguntado.append((name, regra_atual))
            or editor.resposta_downgrade
        ),
        raising=False,
    )
    monkeypatch.setattr(
        gd,
        "confirm_downgrade_match_to_manual",
        lambda parent, name, regra_atual=None: (
            editor.manual_perguntado.append((name, regra_atual))
            or editor.resposta_manual
        ),
        raising=False,
    )
    monkeypatch.setattr(
        gd,
        "confirm_downgrade_priority",
        lambda parent, name, de, para: (
            editor.prioridade_perguntada.append((name, de, para))
            or editor.resposta_prioridade
        ),
        raising=False,
    )
    monkeypatch.setattr(pa, "save_profile", lambda p: editor.salvos.append(p))
    monkeypatch.setattr(pa, "delete_profile", lambda n: None)
    monkeypatch.setattr(pa, "active_profile_name", lambda: None)
    monkeypatch.setattr(pa, "profile_switch", lambda n: True)
    monkeypatch.setattr(pa, "call_async", lambda **_kw: None)


def perfil_dela() -> Profile:
    """O ``Pragmata`` como estava no disco dela às 04:34 de 10/08.

    ``process_name`` junto do appid é o campo que a página simples NÃO mostra e
    que ``from_simple_choice`` preserva (ESCONDER-EM-VEZ-DE-SAIR-01) — ele é
    metade da razão de existir do modo avançado.
    """
    return Profile(
        name="Pragmata",
        match=MatchCriteria(window_class=[WM_JOGO], process_name=["PRAGMATA.exe"]),
        priority=200,
    )


def perfil_complexo() -> Profile:
    """Regra que o editor simples não sabe exprimir — abre no avançado."""
    return Profile(
        name="Navegação",
        match=MatchCriteria(
            window_class=["firefox"], window_title_regex="YouTube"
        ),
        priority=50,
    )


# ---------------------------------------------------------------------------
# 1. A foto de 04:34
# ---------------------------------------------------------------------------


class TestOAvancadoMostraORegraDoPerfilAberto:
    def test_ligar_o_avancado_mostra_o_criterio_que_esta_no_arquivo(self) -> None:
        """A foto dela, clique a clique.

        Perfil do jogo aberto (página simples, "Jogo da Steam" + 3357650) →
        mover o switch "Modo avançado" → os três campos têm de mostrar o que o
        arquivo diz, não os textos-fantasma do glade.

        MORDIDA: arranque a chamada de `_mostrar_a_regra_nos_campos_crus` em
        `on_profile_advanced_toggle` (o corpo volta a ser só
        `_apply_editor_mode`) e as duas primeiras asserções reprovam — que é
        exatamente o estado fotografado.
        """
        perfil = perfil_dela()
        editor = Editor(cache=[perfil])
        editor._populate_editor(perfil)

        # A página simples mostra o que ela viu na primeira foto.
        assert editor._selected_simple_choice() == "steam_game"
        assert editor._get("profile_simple_custom_name").get_text() == APPID

        editor.ligar_o_avancado()

        assert editor._get("profile_editor_stack").visible_child == "avancado"
        assert editor.campos_crus() == (WM_JOGO, "", "PRAGMATA.exe")

    def test_o_avancado_nao_mostra_a_regra_do_perfil_anterior(self) -> None:
        """Perfil complexo aberto, depois o do jogo: os crus não podem ficar rançosos.

        `_populate_editor` limpa a página SIMPLES ao abrir um match complexo
        (BUG-PROFILE-SIMPLE-STALE-01) e nunca limpou o contrário. Sem a cura, a
        `firefox`/`YouTube` do perfil anterior seguia nos campos crus — e ligar
        o avançado no perfil do jogo mostrava a regra de OUTRO perfil, que é
        pior que mostrar vazio: parece dado bom.

        MORDIDA: a mesma chamada arrancada; sobra `("firefox", "YouTube", "")`.
        """
        jogo = perfil_dela()
        editor = Editor(cache=[perfil_complexo(), jogo])
        editor._populate_editor(perfil_complexo())
        assert editor.campos_crus() == ("firefox", "YouTube", "")

        editor._populate_editor(jogo)
        editor.ligar_o_avancado()

        assert editor.campos_crus() == (WM_JOGO, "", "PRAGMATA.exe")

    def test_desligar_e_religar_nao_apaga_a_regra_complexa(self) -> None:
        """A cura não pode comer a regra que o avançado já mostrava.

        Um match complexo abre JÁ no avançado. Desligar o switch põe a página
        simples na frente com "Qualquer" (é o que `_populate_editor` deixa
        selecionado), e religar não pode traduzir esse "Qualquer" de volta para
        os campos crus — seria a cura apagando `firefox`/`YouTube`.

        MORDIDA: trocar o `_regra_real_do_perfil_aberto` por um
        `from_simple_choice` seco da página simples faz os três campos virarem
        `("", "", "")` aqui.
        """
        perfil = perfil_complexo()
        editor = Editor(cache=[perfil])
        editor._populate_editor(perfil)
        assert editor._mode_advanced is True

        editor.desligar_o_avancado()
        editor.ligar_o_avancado()

        assert editor.campos_crus() == ("firefox", "YouTube", "")

    def test_o_avancado_mostra_o_que_ela_acabou_de_escolher_na_simples(self) -> None:
        """Editar na página simples e ligar o avançado mostra o valor NOVO.

        A regra "de verdade" é a que o Salvar gravaria, não a que está no disco:
        se ela trocou o número do jogo, é o número novo que tem de aparecer. E o
        `process_name` do jogo ANTERIOR não vai junto — é outro jogo
        (`_process_name_a_preservar`).

        MORDIDA: fazer `_regra_real_do_perfil_aberto` devolver sempre
        `self._regra_do_disco` reprova este teste (mostraria 3357650).
        """
        perfil = perfil_dela()
        editor = Editor(cache=[perfil])
        editor._populate_editor(perfil)

        editor._get("profile_simple_custom_name").set_text("1599660")
        editor.ligar_o_avancado()

        assert editor.campos_crus() == ("steam_app_1599660", "", "")

    def test_perfil_novo_sem_alvo_nao_inventa_criterio(self) -> None:
        """"Novo perfil" + "Qualquer" + avançado: três campos vazios, e é a verdade.

        `MatchAny` não tem critério nenhum para mostrar, e a cura não pode
        inventar um (nem herdar o do perfil que estava aberto antes).

        MORDIDA: uma cura que copiasse `_regra_do_disco` sem olhar o gesto dela
        traria de volta a regra do perfil anterior nestes campos.
        """
        anterior = perfil_complexo()
        editor = Editor(cache=[anterior])
        editor._populate_editor(anterior)
        editor.on_profile_new(None)

        editor.ligar_o_avancado()

        assert editor.campos_crus() == ("", "", "")


# ---------------------------------------------------------------------------
# 2. Ligar o avançado é OLHAR, não é MEXER
# ---------------------------------------------------------------------------


class TestLigarOAvancadoNaoContaComoGestoDela:
    def test_ligar_o_avancado_e_salvar_preserva_a_regra_do_disco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guarda SALVAR-NAO-REBAIXA-01 não pode cair por causa da cura.

        `_regra_foi_mexida` compara a fotografia tirada na abertura com a de
        agora — e a cura ESCREVE nos campos crus. Sem retirar a fotografia
        depois de escrever, o simples ato de ligar o switch passaria a contar
        como "ela mexeu na regra", desarmando a guarda que existe desde 27/07.

        MORDIDA: apague o `self._assinatura_da_regra_ao_abrir = ...` do
        `_mostrar_a_regra_nos_campos_crus` e `_regra_foi_mexida()` volta a
        responder True aqui.
        """
        perfil = perfil_dela()
        editor = Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        ligar_o_save(editor, monkeypatch)

        editor.ligar_o_avancado()

        assert editor._regra_foi_mexida() is False
        editor.on_profile_save(None)
        assert len(editor.salvos) == 1
        assert editor.salvos[0].match == perfil.match
        assert editor.salvos[0].priority == 200

    def test_editar_um_campo_cru_depois_de_ligar_continua_contando(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fotografia retirada não pode virar cadeado: mexer conta.

        Ligar o avançado e ENTÃO editar um campo é gesto dela, e o Salvar tem
        de gravar o que ela escreveu.

        MORDIDA: retirar a fotografia SEMPRE (inclusive quando ela já tinha
        mexido) ou congelá-la faz este teste reprovar — o Salvar devolveria a
        regra do disco por cima do que ela digitou.
        """
        perfil = perfil_dela()
        editor = Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        ligar_o_save(editor, monkeypatch)

        editor.ligar_o_avancado()
        editor._get("profile_process_name_entry").set_text("Pragmata-Win64.exe")

        assert editor._regra_foi_mexida() is True
        editor.on_profile_save(None)
        assert len(editor.salvos) == 1
        salvo = editor.salvos[0].match
        assert isinstance(salvo, MatchCriteria)
        assert salvo.window_class == [WM_JOGO]
        assert salvo.process_name == ["Pragmata-Win64.exe"]

    def test_editar_na_simples_e_so_depois_ligar_o_avancado_grava_o_valor_dela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O gesto na página simples sobrevive à ida para o avançado.

        Ela troca o número do jogo, olha o avançado para conferir, salva. O que
        vai para o disco é o número NOVO — a fotografia só é retirada quando ela
        ainda não tinha mexido em nada.

        MORDIDA: retirar a fotografia incondicionalmente em
        `_mostrar_a_regra_nos_campos_crus` grava `steam_app_3357650` aqui.
        """
        perfil = perfil_dela()
        editor = Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        ligar_o_save(editor, monkeypatch)

        editor._get("profile_simple_custom_name").set_text("1599660")
        editor.ligar_o_avancado()
        editor.on_profile_save(None)

        assert len(editor.salvos) == 1
        salvo = editor.salvos[0].match
        assert isinstance(salvo, MatchCriteria)
        assert salvo.window_class == ["steam_app_1599660"]


# ---------------------------------------------------------------------------
# 3. O que a cura NÃO pode ter mexido
# ---------------------------------------------------------------------------


class TestOQueContinuaComoEstava:
    def test_o_toggle_continua_trocando_a_pagina_e_persistindo_a_preferencia(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A função velha do handler segue inteira (stack + `set_pref`).

        MORDIDA: mover o `_apply_editor_mode()` ou o `set_pref(...)` para
        dentro do `if state:` da cura reprova aqui — desligar o avançado
        deixaria de trocar a página e de gravar a preferência.
        """
        gravado: list[tuple[str, Any]] = []
        monkeypatch.setattr(
            pa, "set_pref", lambda k, v: gravado.append((k, v))
        )
        editor = Editor()

        editor.ligar_o_avancado()
        assert editor._mode_advanced is True
        assert editor._get("profile_editor_stack").visible_child == "avancado"

        editor.desligar_o_avancado()
        assert editor._mode_advanced is False
        assert editor._get("profile_editor_stack").visible_child == "simples"
        assert gravado == [("advanced_editor", True), ("advanced_editor", False)]

    def test_toggle_programatico_nao_mexe_em_campo_nenhum(self) -> None:
        """`_suppress_advanced_toggle` continua sendo o portão de tudo.

        `_populate_editor` chama `switch.set_active` e o GTK dispara o handler;
        com a marca armada ele tem de sair na primeira linha — sem trocar
        página, sem persistir preferência e, agora, sem escrever nos campos.

        MORDIDA: pôr o `_mostrar_a_regra_nos_campos_crus()` ACIMA do
        `if self._suppress_advanced_toggle: return False` reprova aqui — a
        repintura programática apagaria o `firefox` que o populate acabou de
        escrever.
        """
        editor = Editor()
        editor._suppress_advanced_toggle = True
        editor._get("profile_window_class_entry").set_text("firefox")

        editor.on_profile_advanced_toggle(
            editor._get("profile_advanced_switch"), True
        )

        assert editor._mode_advanced is False
        assert editor.campos_crus() == ("firefox", "", "")

    def test_perfil_so_manual_continua_abrindo_com_os_tres_campos_vazios(self) -> None:
        """R-12 item 3: o round-trip do perfil manual não pode ganhar alvo.

        `MatchManual` cai em `detect_simple_preset` → None, abre no avançado com
        os três campos em branco, e é assim que o `_build_profile_from_editor`
        volta a gravá-lo como manual. Ligar/desligar o switch não pode inventar
        critério nenhum.

        MORDIDA: fazer `_mostrar_a_regra_nos_campos_crus` cair na página
        simples quando a regra é `MatchManual` (que o seletor "Aplica a" não
        sabe exprimir) traria um preset de fábrica para estes campos.
        """
        perfil = Profile(name="Só na mão", match=MatchManual(), priority=10)
        editor = Editor(cache=[perfil])
        editor._populate_editor(perfil)
        assert editor.campos_crus() == ("", "", "")

        editor.desligar_o_avancado()
        editor.ligar_o_avancado()

        assert editor.campos_crus() == ("", "", "")

    def test_perfil_sempre_abre_o_avancado_sem_criterio(self) -> None:
        """`MatchAny` não tem o que mostrar no avançado — e não pode mentir.

        MORDIDA: um `_mostrar_a_regra_nos_campos_crus` que pulasse o `getattr`
        tolerante e lesse `regra.window_class` direto estouraria aqui com
        `AttributeError` (`MatchAny` não tem os três campos).
        """
        perfil = Profile(name="vitoria", match=MatchAny(), priority=100)
        editor = Editor(cache=[perfil])
        editor._populate_editor(perfil)
        editor.ligar_o_avancado()

        assert editor.campos_crus() == ("", "", "")
