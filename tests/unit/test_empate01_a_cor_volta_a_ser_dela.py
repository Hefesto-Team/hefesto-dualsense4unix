"""A cor volta a ser dela — a aba Perfis para de rebaixar o que ela consertou.

Três entregas da fila crítica dos perfis, todas com evidência datada:

**SALVAR-NAO-REBAIXA-01.** `_build_profile_from_editor` terminava com um
`base.update({name, priority, match})` que sobrescrevia SEMPRE, com o que
estivesse nos widgets. Medido no disco dela: `Pragmata` era regra de jogo com
prioridade 100 em 26/07 às 23h40 e amanheceu catch-all em 27/07 às 23h04;
`vitoria.json` caiu de prioridade 100 para 0. Salvar a cor pela aba Perfis
gravava de volta a leitura empobrecida da tela.

**PERFIL-NASCE-CERTO-01.** O perfil novo nascia `match:any` e prioridade 0 —
que é a combinação que garante que ele NUNCA vale num jogo (a R-21 nega
autoridade a catch-all em janela de jogo) e perde para o catch-all dela em
todo o resto. E o teto da escala era 100, com o catch-all dela exatamente em
100: não existia número escolhível pela janela que desempatasse.

**EMPATE-01/E-1.** O `fallback` semeado pelo repositório trazia
`lightbar: [40, 40, 40]` — a olho nu, um controle apagado — e ganhava, pelo
alfabeto, de quem tinha opinião melhor.

Hermético: stubs de `gi.repository` quando falta PyGObject, widgets falsos com
a mesma API por-ID que a aba usa. Nenhum GTK real, nenhum daemon, nenhuma
escrita no ~/.config dela.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

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

from hefesto_dualsense4unix.app.actions import profiles_actions as pa  # noqa: E402
from hefesto_dualsense4unix.profiles.schema import (  # noqa: E402
    MatchAny,
    MatchCriteria,
    Profile,
)

#: appid do Pragmata, o jogo em que o defeito foi diagnosticado ao vivo.
APPID = "3357650"
WM_JOGO = f"steam_app_{APPID}"

RAIZ = Path(__file__).resolve().parents[2]
FALLBACK_JSON = RAIZ / "assets" / "profiles_default" / "fallback.json"
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"


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
    """Escala com TETO, como o `profile_priority_adj` do glade.

    O clamp não é detalhe de dublê: é o que um `GtkAdjustment` faz de verdade
    com `set_value` fora da faixa, e é por ele que uma prioridade acima do teto
    já ABRIA rebaixada no editor.
    """

    def __init__(self, value: float = 0.0, teto: float | None = None) -> None:
        self._teto = float(pa.PRIORIDADE_MAXIMA if teto is None else teto)
        self._value = 0.0
        self._handlers: list[Any] = []
        self.set_value(value)

    def connect(self, sinal: str, handler: Any) -> None:
        if sinal == "value-changed":
            self._handlers.append(handler)

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        """Emite `value-changed` como o GtkScale de verdade — inclusive quando o
        valor CLAMPADO coincide com o anterior: quem arrasta emite o sinal."""
        self._value = max(0.0, min(self._teto, float(value)))
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
        # Espelha a fiação de `install_profiles_tab`: o gesto na escala marca.
        self._widgets["profile_priority_scale"].connect(
            "value-changed", self._on_prioridade_tocada
        )
        self.toasts: list[str] = []

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return None

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


def _perfil_do_pragmata() -> Profile:
    """O perfil como ele ficou depois do conserto à mão de 26/07.

    Regra do jogo (não catch-all) e prioridade 110 — um valor que a janela, na
    época, não aceitava digitar. O `window_title_regex` junto é o que faz o
    editor simples não reconhecer o match e cair no avançado, que é o caminho
    onde o rebaixamento acontece.
    """
    return Profile(
        name="Pragmata",
        match=MatchCriteria(window_class=[WM_JOGO], window_title_regex="Pragmata"),
        priority=110,
    )


class TestSalvarNaoRebaixaARegra:
    def test_desligar_o_modo_avancado_e_salvar_preserva_a_regra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O gesto: abrir o perfil, desligar "Modo avançado", clicar Salvar.

        A página simples reaparece mostrando "Qualquer" (ela nunca escolheu
        isso — é o estado inicial daquela página) e o Salvar gravava esse
        "Qualquer" por cima da regra do jogo. É o perfil virando catch-all,
        que é exatamente o que o disco dela mostrou em 27/07 às 23h04.

        Com a cura arrancada, o match sai `MatchAny`.
        """
        monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)
        editor = _Editor()
        editor._populate_editor(_perfil_do_pragmata())
        assert editor._mode_advanced is True, "pré-condição: abriu no avançado"

        editor.on_profile_advanced_toggle(editor._get("profile_advanced_switch"), False)
        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchCriteria), (
            "a regra do jogo virou catch-all sem ela pedir — e um catch-all "
            "não tem autoridade nenhuma numa janela de jogo (R-21)"
        )
        assert salvo.match.window_class == [WM_JOGO]
        assert salvo.match.window_title_regex == "Pragmata"

    def test_mexer_na_regra_continua_valendo_na_hora(self) -> None:
        """A guarda não pode virar "nunca mais dá para mudar".

        Ela troca o alvo no editor avançado e salva: o valor NOVO manda.
        """
        editor = _Editor()
        editor._populate_editor(_perfil_do_pragmata())

        editor._get("profile_window_class_entry").set_text("steam_app_999")
        editor._get("profile_title_regex_entry").set_text("")
        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class == ["steam_app_999"]
        assert salvo.match.window_title_regex is None

    def test_escolher_qualquer_de_proposito_continua_valendo(self) -> None:
        """E rebaixar de propósito também: quem escolhe "Qualquer" recebe."""
        editor = _Editor()
        editor._populate_editor(_perfil_do_pragmata())

        editor._mode_advanced = False
        editor._aplica_a.set_active_id("browser")
        editor._aplica_a.set_active_id("any")
        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchAny)

    def test_perfil_novo_nao_herda_regra_nenhuma(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"Novo perfil" não tem valor de disco a preservar (R-09)."""
        monkeypatch.setattr(pa, "call_async", lambda **_kw: None)
        editor = _Editor()
        editor._populate_editor(_perfil_do_pragmata())

        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Outro")
        salvo = editor._build_profile_from_editor()

        assert isinstance(salvo.match, MatchAny)
        assert salvo.priority == 0


class TestSalvarNaoRebaixaAPrioridade:
    def test_prioridade_acima_do_teto_da_escala_sobrevive(self) -> None:
        """Prioridade que a escala não consegue representar não pode ser perdida.

        É o mecanismo medido com o teto em 100 e o `Pragmata` em 110: o perfil
        ABRIA já clampado na tela, e salvar gravava o número da tela. Subir o
        teto para 200 dá folga, mas não fecha a classe do defeito — quem fecha
        é a prioridade do disco sobreviver a um Salvar que não a tocou.

        Com a cura arrancada, o valor salvo é o teto.
        """
        acima = pa.PRIORIDADE_MAXIMA + 50
        editor = _Editor()
        editor._populate_editor(
            Profile(name="Pragmata", match=MatchCriteria(window_class=[WM_JOGO]),
                    priority=acima)
        )
        assert editor._get("profile_priority_scale").get_value() == pa.PRIORIDADE_MAXIMA

        salvo = editor._build_profile_from_editor()

        assert salvo.priority == acima

    def test_arrastar_ate_o_teto_num_perfil_clampado_vale(self) -> None:
        """O gesto dela vence a coincidência de valor.

        Perfil com prioridade acima do teto abre CLAMPADO: 250 no disco, 200 na
        tela. Se ela arrastar a escala e parar exatamente no teto, o valor final
        coincide com o da abertura — e comparar valores diria "não mexeu",
        devolvendo 250 ao disco. Quem desempata é a marca de gesto, emitida pelo
        próprio widget.

        Com a marca arrancada, o valor salvo volta a ser o do disco.
        """
        acima = pa.PRIORIDADE_MAXIMA + 50
        editor = _Editor()
        editor._populate_editor(
            Profile(name="Pragmata", match=MatchCriteria(window_class=[WM_JOGO]),
                    priority=acima)
        )
        escala = editor._get("profile_priority_scale")
        assert escala.get_value() == pa.PRIORIDADE_MAXIMA

        # o arrastar dela: passa por outro valor e volta ao teto
        escala.set_value(120)
        escala.set_value(pa.PRIORIDADE_MAXIMA)
        salvo = editor._build_profile_from_editor()

        assert salvo.priority == pa.PRIORIDADE_MAXIMA

    def test_abrir_o_perfil_nao_conta_como_gesto(self) -> None:
        """O `set_value` da abertura emite o sinal, e não pode contar.

        É o mesmo cuidado do `_regra_tocada`: a marca é zerada DEPOIS de
        posicionar os widgets. Sem isso, a guarda inteira morre no nascimento.
        """
        acima = pa.PRIORIDADE_MAXIMA + 50
        editor = _Editor()
        editor._populate_editor(
            Profile(name="Pragmata", match=MatchCriteria(window_class=[WM_JOGO]),
                    priority=acima)
        )

        assert editor._prioridade_tocada is False
        assert editor._build_profile_from_editor().priority == acima

    def test_mover_a_escala_continua_valendo_na_hora(self) -> None:
        editor = _Editor()
        editor._populate_editor(_perfil_do_pragmata())

        editor._get("profile_priority_scale").set_value(42)
        salvo = editor._build_profile_from_editor()

        assert salvo.priority == 42


class TestTetoDaEscalaSobeParaDuzentos:
    def test_a_constante_do_codigo(self) -> None:
        assert pa.PRIORIDADE_MAXIMA == 200

    def test_o_glade_acompanha(self) -> None:
        """O código e o glade têm de dizer o mesmo número.

        Divergir aqui é pior que não subir: a escala aceitaria um valor que o
        editor recorta em silêncio na volta.
        """
        arvore = ElementTree.parse(GLADE)
        ajuste = next(
            obj for obj in arvore.iter("object")
            if obj.get("id") == "profile_priority_adj"
        )
        upper = next(
            prop for prop in ajuste.iter("property") if prop.get("name") == "upper"
        )
        assert int(str(upper.text)) == pa.PRIORIDADE_MAXIMA

    def test_perfil_acima_de_cem_abre_com_o_valor_certo(self) -> None:
        """Com o teto antigo, um perfil em 150 abria mostrando 100."""
        editor = _Editor()
        editor._populate_editor(
            Profile(name="X", match=MatchAny(), priority=150)
        )
        assert editor._get("profile_priority_scale").get_value() == 150


class TestPerfilNasceComOJogoEmFoco:
    """PERFIL-NASCE-CERTO-01: criar com o jogo aberto É a declaração de intenção."""

    @staticmethod
    def _com_daemon_respondendo(
        monkeypatch: pytest.MonkeyPatch, wm_class: str | None
    ) -> None:
        estado = {"window_detect_last_class": wm_class}

        def fake_call_async(**kw: Any) -> None:
            on_success = kw.get("on_success")
            if on_success is not None:
                on_success(estado)

        monkeypatch.setattr(pa, "call_async", fake_call_async)

    def test_nasce_com_a_regra_do_jogo_e_acima_do_catch_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O arranjo real: catch-all dela em 100, perfil novo com o jogo aberto.

        Com a cura arrancada, ele nasce "Qualquer" com prioridade 0 — que é o
        perfil que ela criou para o Pragmata e que nunca valeu no Pragmata.
        """
        self._com_daemon_respondendo(monkeypatch, WM_JOGO)
        editor = _Editor(
            cache=[
                Profile(name="vitoria", match=MatchAny(), priority=100),
                Profile(name="fallback", match=MatchAny(), priority=0),
            ]
        )

        editor.on_profile_new(None)

        assert editor._aplica_a.get_active_id() == "steam_game"
        assert editor._get("profile_simple_custom_name").get_text() == APPID
        assert editor._get("profile_priority_scale").get_value() == 110

        salvo = editor._build_profile_from_editor()
        assert isinstance(salvo.match, MatchCriteria)
        assert salvo.match.window_class == [WM_JOGO]
        assert salvo.priority == 110
        assert not salvo.e_catch_all

    def test_sem_jogo_em_foco_nada_muda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No desktop, o perfil novo continua nascendo catch-all — e está certo."""
        self._com_daemon_respondendo(monkeypatch, "firefox")
        editor = _Editor(cache=[Profile(name="vitoria", match=MatchAny(), priority=100)])

        editor.on_profile_new(None)

        assert editor._aplica_a.get_active_id() == "any"
        assert editor._get("profile_priority_scale").get_value() == 0

    def test_nao_atropela_o_que_ela_ja_escolheu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A resposta do daemon pode chegar depois dela mexer no editor."""
        self._com_daemon_respondendo(monkeypatch, WM_JOGO)
        editor = _Editor()
        editor._new_profile = True
        editor._aplica_a.set_active_id("browser")

        aplicou = editor._aplicar_nascimento_com_jogo(
            {"window_detect_last_class": WM_JOGO}
        )

        assert aplicou is False
        assert editor._aplica_a.get_active_id() == "browser"

    def test_daemon_calado_nao_quebra_o_botao_novo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_call_async(**kw: Any) -> None:
            on_failure = kw.get("on_failure")
            if on_failure is not None:
                on_failure(RuntimeError("daemon offline"))

        monkeypatch.setattr(pa, "call_async", fake_call_async)
        editor = _Editor()

        editor.on_profile_new(None)

        assert editor._aplica_a.get_active_id() == "any"


class TestSementeSemOpiniaoSobreCor:
    """EMPATE-01/E-1: o `fallback` do repositório para de apagar o controle."""

    def test_o_fallback_semeado_nao_manda_na_cor(self) -> None:
        """Com a cura arrancada, o campo volta e o teste reprova.

        `[40, 40, 40]` num LED RGB é, a olho nu, um controle APAGADO — e era a
        semente do projeto, não configuração dela. Sem o campo, vale a cor
        automática por jogador (azul, vermelho, verde, rosa), que é o padrão
        Sony e continua certo com um, dois, três ou quatro controles.
        """
        bruto = json.loads(FALLBACK_JSON.read_text(encoding="utf-8"))
        leds = bruto.get("leds") or {}

        assert "lightbar" not in leds, (
            "o fallback voltou a ter opinião sobre a cor — e ele vence, pelo "
            "alfabeto, o perfil que tem opinião melhor"
        )

    def test_o_desenho_do_numero_do_jogador_fica(self) -> None:
        """Só uma das duas metades estava errada: acender a luz central é o
        padrão PS5 para um jogador, e continua."""
        bruto = json.loads(FALLBACK_JSON.read_text(encoding="utf-8"))
        leds = bruto.get("leds") or {}

        assert leds.get("player_leds") == [False, False, True, False, False]
