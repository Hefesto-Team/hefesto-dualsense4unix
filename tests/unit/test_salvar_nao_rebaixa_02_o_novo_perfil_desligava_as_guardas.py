"""SALVAR-NAO-REBAIXA-02 — o "Novo perfil" desligava as guardas de 27/07.

A sprint SALVAR-NAO-REBAIXA-01 pôs duas guardas em
`_build_profile_from_editor`: regra e prioridade só são reescritas quando ela
MEXEU nelas. As duas são `if <do_disco> is not None and not <foi_mexida>()`.

**O buraco (medido em 05/08).** `on_profile_new` chama
`_esquecer_a_fotografia_do_editor`, que zera `_regra_do_disco` e
`_prioridade_do_disco`. Com as duas em `None`, os dois `if` são PULADOS e os
widgets vencem — inclusive quando o Salvar vai por cima de um arquivo que
EXISTE. Um perfil `prio=200, criteria` no disco virava `prio=0, any`: o defeito
de 27/07 de volta por outra porta.

A cura é de ESCOPO. Esquecer a fotografia continua certo (perfil que não existe
não tem valor de disco a preservar); o que faltava era RELER a fotografia na
hora de salvar, quando o alvo já existe — e, para isso valer, zerar as marcas
de gesto por ÚLTIMO em `on_profile_new`, como `_populate_editor` sempre fez.

**Os dois avisos.** `confirm_downgrade_match_to_any` só dispara com o match
ORIGINAL específico — e os perfis dela JÁ ESTÃO em `MatchAny`, rebaixados pelo
defeito antigo. Para esses a janela não tinha uma palavra a dizer, e o que
ainda podia cair calado era a PRIORIDADE, que é o termo que decide qual dos
"Sempre" vence. Agora há diálogo para a queda de prioridade, e o aviso da regra
passou a cobrir também o perfil "Só manual" virando "vale para tudo".

Hermético: stubs de `gi.repository` quando falta PyGObject, widgets falsos com
a mesma API por-ID que a aba usa. Nenhum GTK real, nenhum daemon, nenhuma
escrita no ~/.config dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("SALVAR-NAO-REBAIXA-02 (o Novo perfil)")

import sys
import types
from typing import Any

import pytest

pytest.importorskip("gi")


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover - ambientes sem GTK
            pass

    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")
    gobject_mod = types.ModuleType("gi.repository.GObject")
    for nome in (
        "Builder", "Window", "Button", "CheckButton", "ComboBoxText", "Switch",
        "TreeView", "TreeViewColumn", "CellRendererText", "ListStore",
        "TreeSelection", "TreePath", "Box", "Label", "Frame", "Entry",
        "RadioButton", "Scale", "Stack", "MessageDialog", "MessageType",
        "ButtonsType", "ResponseType",
    ):
        setattr(gtk_mod, nome, object)
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    gobject_mod.TYPE_STRING = "str"  # type: ignore[attr-defined]
    gobject_mod.TYPE_INT = "int"  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.GObject"] = gobject_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
)

#: appid do Pragmata, o jogo em que a família toda de defeitos foi medida.
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
    """Escala com TETO e sinal, como o `profile_priority_adj` do glade."""

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
        # O GtkScale de verdade só emite quando o valor MUDA — e é justamente
        # por isso que o `set_value(0)` do "Novo perfil" às vezes marcava gesto
        # e às vezes não. O dublê tem de reproduzir a condição, não escondê-la.
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


class _FakeBox:
    def __init__(self) -> None:
        self.visivel = False

    def show(self) -> None:
        self.visivel = True

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


class _Editor(pa.ProfilesActionsMixin):
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
        # Registro dos diálogos e do disco.
        self.salvos: list[Profile] = []
        self.overwrite_perguntado: list[str] = []
        self.downgrade_perguntado: list[tuple[str, str | None]] = []
        self.prioridade_perguntada: list[tuple[str, int, int]] = []
        self.resposta_overwrite = True
        self.resposta_downgrade = True
        self.resposta_prioridade = True

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


def _ligar_o_save(editor: _Editor, monkeypatch: pytest.MonkeyPatch) -> None:
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


def _perfil_dela() -> Profile:
    """O perfil como ela o consertou: regra do jogo e prioridade no teto."""
    return Profile(
        name="Pragmata",
        match=MatchCriteria(window_class=[WM_JOGO]),
        priority=200,
    )


# ---------------------------------------------------------------------------
# 1. As guardas voltam a valer quando o alvo do Salvar EXISTE em disco
# ---------------------------------------------------------------------------


class TestNovoPerfilPorCimaDeUmQueExiste:
    def test_salvar_por_cima_preserva_regra_e_prioridade_do_disco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O defeito medido em 05/08, clique a clique.

        "Novo perfil" (que esquece a fotografia) → digitar o nome de um perfil
        que EXISTE → Salvar. Sem a cura, o perfil do disco (`prio=200`, regra
        do jogo) volta a ser `prio=0, any` — que é o valor que a janela mostra,
        não o que ela pediu.

        Com a cura arrancada (o `_perfil_que_o_salvar_sobrescreve` deixando de
        ser consultado), este teste reprova nas duas asserções.
        """
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        editor = _Editor(cache=[_perfil_dela()])
        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Pragmata")

        salvo = editor._build_profile_from_editor()

        assert salvo.priority == 200, (
            "a prioridade do disco foi rebaixada por um editor que nunca "
            "mostrou este perfil"
        )
        assert isinstance(salvo.match, MatchCriteria), (
            "a regra do jogo virou catch-all — e catch-all não tem autoridade "
            "nenhuma numa janela de jogo (R-21)"
        )
        assert salvo.match.window_class == [WM_JOGO]

    def test_o_nascer_do_novo_perfil_nao_conta_como_gesto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A metade da cura que mora em `on_profile_new`.

        `_esquecer_a_fotografia_do_editor` vem POR ÚLTIMO, depois de posicionar
        os widgets — a mesma ordem que `_populate_editor` sempre teve. Chamado
        antes (como estava), o `set_value(0)`/`set_active_id("any")` de
        nascimento levantava as marcas, e a guarda reabilitada acreditaria que
        ela escolheu prioridade 0 e "Qualquer".
        """
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        editor = _Editor(cache=[_perfil_dela()])
        # Estado que faz o nascimento MEXER nos dois widgets (o perfil aberto
        # antes tinha prioridade alta e regra própria).
        editor._populate_editor(_perfil_dela())
        editor._aplica_a.set_active_id("browser")

        editor.on_profile_new(None)

        assert editor._prioridade_tocada is False
        assert editor._regra_tocada is False

    def test_olhar_o_perfil_antes_de_clicar_novo_nao_o_rebaixa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A sequência inteira, com o editor VINDO de um perfil aberto.

        É a que morde as DUAS metades da cura ao mesmo tempo: ela estava
        olhando o `Pragmata` (200, regra do jogo), clica "Novo perfil" — que
        joga os widgets para 0/"Qualquer" — e salva com o mesmo nome. Se as
        marcas de gesto sobrarem do nascimento, a guarda reabilitada acredita
        nelas e o rebaixamento acontece com uma guarda ligada.
        """
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        editor = _Editor(cache=[_perfil_dela()])
        editor._populate_editor(_perfil_dela())
        assert editor._get("profile_priority_scale").get_value() == 200

        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Pragmata")
        salvo = editor._build_profile_from_editor()

        assert salvo.priority == 200
        assert isinstance(salvo.match, MatchCriteria)

    def test_a_escolha_dela_no_perfil_novo_continua_vencendo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guarda não pode virar cadeado: gesto dela manda na hora."""
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        editor = _Editor(cache=[_perfil_dela()])
        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Pragmata")

        editor._get("profile_priority_scale").set_value(42)
        editor._aplica_a.set_active_id("browser")
        salvo = editor._build_profile_from_editor()

        assert salvo.priority == 42
        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class != [WM_JOGO]

    def test_perfil_novo_com_nome_inedito_nasce_dos_widgets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem alvo em disco não há nada a preservar — o R-09 segue valendo."""
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        editor = _Editor(cache=[_perfil_dela()])
        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Outro")

        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchAny)
        assert salvo.priority == 0

    def test_o_alvo_e_achado_pelo_slug_e_nao_pelo_nome_de_exibicao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-10: "Navegacao" e "Navegação" são o MESMO arquivo."""
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        navegacao = Profile(
            name="Navegação",
            match=MatchCriteria(window_class=["firefox"]),
            priority=150,
        )
        editor = _Editor(cache=[navegacao])
        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Navegacao")

        salvo = editor._build_profile_from_editor()

        assert salvo.priority == 150
        assert isinstance(salvo.match, MatchCriteria)

    def test_nascer_com_o_jogo_em_foco_vence_o_que_esta_no_disco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PERFIL-NASCE-CERTO-01 continua de pé por cima da guarda nova.

        O prefill do jogo em foco É uma escolha do editor (ela criou o perfil
        COM o jogo aberto), então ele marca os gestos e manda — mesmo quando o
        nome digitado colide com um perfil que já existe.
        """
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        editor = _Editor(cache=[_perfil_dela()])
        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Pragmata")

        assert editor._aplicar_nascimento_com_jogo(
            {"window_detect_last_class": WM_JOGO}
        )
        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class == [WM_JOGO]
        # 200 (o catch-all mais alto do cache é 0; o `Pragmata` não é catch-all)
        # -> a folga sozinha. O que importa é ter vindo do PREFILL, não do disco.
        assert salvo.priority == pa._FOLGA_ACIMA_DO_CATCH_ALL

    def test_editar_um_perfil_da_lista_segue_pela_fotografia_de_abertura(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho da SALVAR-NAO-REBAIXA-01 não muda: ele tem fotografia."""
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        acima = pa.PRIORIDADE_MAXIMA + 50
        editor = _Editor()
        editor._populate_editor(
            Profile(
                name="Pragmata",
                match=MatchCriteria(window_class=[WM_JOGO]),
                priority=acima,
            )
        )

        salvo = editor._build_profile_from_editor()

        assert salvo.priority == acima, "a prioridade acima do teto sobreviveu"


# ---------------------------------------------------------------------------
# 2. Os dois avisos de rebaixamento
# ---------------------------------------------------------------------------


class TestQuedaDePrioridadePedeAviso:
    """A regra pura — testável sem GTK, sem disco e sem daemon."""

    def test_a_queda_medida_no_disco_dela_avisa(self) -> None:
        assert pa.queda_de_prioridade_pede_aviso(200, 0) is True

    def test_subir_nunca_avisa(self) -> None:
        assert pa.queda_de_prioridade_pede_aviso(0, 200) is False

    def test_ficar_igual_nunca_avisa(self) -> None:
        assert pa.queda_de_prioridade_pede_aviso(100, 100) is False

    def test_queda_pequena_nao_vira_ruido(self) -> None:
        """Um diálogo por ponto perdido se aprende a clicar sem ler."""
        assert pa.queda_de_prioridade_pede_aviso(100, 95) is False

    def test_a_folga_do_perfil_de_jogo_e_o_limiar(self) -> None:
        limiar = pa.QUEDA_DE_PRIORIDADE_QUE_PEDE_AVISO
        assert limiar == pa._FOLGA_ACIMA_DO_CATCH_ALL
        assert pa.queda_de_prioridade_pede_aviso(100, 100 - limiar) is True
        assert pa.queda_de_prioridade_pede_aviso(100, 101 - limiar) is False


class TestOsDoisAvisosNoSalvar:
    def _editor_com(self, perfil: Profile) -> _Editor:
        editor = _Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        return editor

    def test_baixar_a_prioridade_pergunta_e_cancelar_nao_toca_o_disco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caso dela: perfil já em `MatchAny`, prioridade caindo de 200.

        Sem o diálogo novo, este Salvar grava em silêncio — o aviso da REGRA
        não dispara (o match já é `MatchAny`, não há o que rebaixar), e a
        prioridade some sem uma palavra.
        """
        perfil = Profile(name="vitoria", match=MatchAny(), priority=200)
        editor = self._editor_com(perfil)
        _ligar_o_save(editor, monkeypatch)
        editor.resposta_prioridade = False  # ela cancela ao ver o aviso

        editor._get("profile_priority_scale").set_value(0)
        editor.on_profile_save(None)

        assert editor.prioridade_perguntada == [("vitoria", 200, 0)]
        assert editor.downgrade_perguntado == [], (
            "o aviso da regra não tem o que dizer: o match já era MatchAny"
        )
        assert editor.salvos == [], "cancelar não pode tocar o arquivo"

    def test_confirmar_a_queda_grava_o_que_ela_pediu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        perfil = Profile(name="vitoria", match=MatchAny(), priority=200)
        editor = self._editor_com(perfil)
        _ligar_o_save(editor, monkeypatch)

        editor._get("profile_priority_scale").set_value(0)
        editor.on_profile_save(None)

        assert [p.priority for p in editor.salvos] == [0]

    def test_queda_pequena_salva_sem_incomodar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        perfil = Profile(name="vitoria", match=MatchAny(), priority=100)
        editor = self._editor_com(perfil)
        _ligar_o_save(editor, monkeypatch)

        editor._get("profile_priority_scale").set_value(95)
        editor.on_profile_save(None)

        assert editor.prioridade_perguntada == []
        assert [p.priority for p in editor.salvos] == [95]

    def test_so_manual_virando_vale_para_tudo_avisa_com_a_palavra_certa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O furo do aviso da regra: só `MatchCriteria` disparava.

        Um perfil "Só manual (nunca ativa sozinho)" virando "vale para TUDO" é
        a mudança mais violenta que a aba sabe fazer, e passava calada. O
        rótulo citado é o MESMO da coluna "Quando usar" — o diálogo não pode
        chamar de "programas específicos" um perfil que a lista chama de outra
        coisa.
        """
        perfil = Profile(name="manual", match=MatchManual(), priority=10)
        editor = self._editor_com(perfil)
        _ligar_o_save(editor, monkeypatch)
        editor.resposta_downgrade = False

        # Ela desliga o avançado: a página simples reaparece em "Qualquer".
        editor._mode_advanced = False
        editor._aplica_a.set_active_id("any")
        editor._regra_tocada = True
        editor.on_profile_save(None)

        assert editor.downgrade_perguntado == [("manual", pa.LABEL_SO_MANUAL)]
        assert editor.salvos == []

    def test_o_dialogo_novo_nasce_com_o_tema_do_app(self) -> None:
        """GUI-05/P5: diálogo sem a classe abre CLARO no COSMIC (XWayland).

        A varredura por ARQUIVO de `test_gui_dialogs_theme` já cobre o módulo;
        esta é a granularidade por FUNÇÃO para o construtor novo.
        """
        import inspect

        from hefesto_dualsense4unix.app import gui_dialogs

        src = inspect.getsource(gui_dialogs.confirm_downgrade_priority)
        assert "_apply_app_theme(" in src

    def test_regra_especifica_continua_avisando_com_a_frase_de_sempre(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COR-A não regride: o caso original segue avisando."""
        perfil = Profile(
            name="Pragmata",
            match=MatchCriteria(window_class=[WM_JOGO]),
            priority=10,
        )
        editor = self._editor_com(perfil)
        _ligar_o_save(editor, monkeypatch)
        editor.resposta_downgrade = False

        editor._mode_advanced = False
        editor._aplica_a.set_active_id("any")
        editor._regra_tocada = True
        editor.on_profile_save(None)

        assert editor.downgrade_perguntado == [
            ("Pragmata", pa._MATCH_LABELS["criteria"])
        ]
        assert editor.salvos == []
