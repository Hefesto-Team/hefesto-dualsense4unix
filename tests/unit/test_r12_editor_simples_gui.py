"""R-12 (auditoria 23/07) — fiação da opção "Jogo da Steam" no editor simples.

O contrato de dados está em `test_r12_editor_simples_jogo_steam.py`; aqui é o
caminho que a usuária percorre de verdade na aba Perfis:

- escolher "Jogo da Steam" mostra o campo livre e pede o NÚMERO (o mesmo widget
  serve "Jogo específico", que pede o nome do programa — sem trocar a dica, o
  rótulo do glade ("Nome do jogo:") é ambíguo para os dois);
- salvar produz `window_class=["steam_app_<id>"]`;
- reabrir o perfil volta para o editor SIMPLES com o appid no campo (sem o
  round-trip, ela cairia no editor avançado a cada visita);
- campo vazio NÃO degrada em silêncio: o save é recusado com frase de gente.

Hermético: stubs de `gi.repository` quando falta PyGObject (padrão de
`test_profiles_editor_mode.py`), widgets fake com a API por-ID do
SegmentedSelector, nenhum GTK real construído.
"""
from __future__ import annotations

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
        except Exception:  # pragma: no cover — ambientes sem GTK
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
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile  # noqa: E402

MMJ = "2111190"


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.placeholder = ""
        self.tooltip = ""

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text

    def set_placeholder_text(self, text: str) -> None:
        self.placeholder = text

    def set_tooltip_text(self, text: str) -> None:
        self.tooltip = text


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = value

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = value


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
    def __init__(self) -> None:
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry("MadJack"),
            "profile_priority_scale": _FakeScale(70),
            "profile_simple_custom_name": _FakeEntry(""),
            "profile_game_entry_box": _FakeBox(),
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
            "profile_preview_label": _FakeEntry(""),
            "main_window": object(),
        }
        self._profiles_cache: list[Profile] = []
        self._duplicate_source = None
        self._new_profile = False
        self._mode_advanced = False
        self._aplica_a = _FakeSelector("any")
        self._aplica_a.connect("changed", self._on_aplica_a_changed)
        self.toasts: list[str] = []
        self.salvos: list[Profile] = []
        self.prefills = 0

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return None

    def _refresh_preview(self) -> None:
        return None

    def _prefill_steam_appid(self) -> None:
        # A busca do appid fala IPC; aqui só registramos que foi disparada.
        self.prefills += 1

    def _reload_profiles_store(self, **_kw: Any) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        return None

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


class TestSeletorAplicaA:
    def test_opcao_existe_e_e_a_ultima(self) -> None:
        assert "steam_game" in pa._RADIO_IDS
        assert dict(pa._APLICA_A_ITEMS)["steam_game"] == "Jogo da Steam"

    def test_escolher_jogo_da_steam_mostra_o_campo_e_troca_a_dica(self) -> None:
        ed = _Editor()
        ed._aplica_a.set_active_id("steam_game")
        assert ed._get("profile_game_entry_box").visivel
        entry = ed._get("profile_simple_custom_name")
        assert entry.placeholder == "ex.: 1599660"
        assert "Steam" in entry.tooltip
        assert ed.prefills == 1, "o appid tem de vir do jogo em foco"

    def test_jogo_especifico_pede_o_programa_nao_o_numero(self) -> None:
        ed = _Editor()
        ed._aplica_a.set_active_id("game")
        entry = ed._get("profile_simple_custom_name")
        assert entry.placeholder == "ex.: eldenring"
        assert "basename" in entry.tooltip or "programa" in entry.tooltip
        assert ed.prefills == 0

    def test_contexto_sem_alvo_esconde_o_campo(self) -> None:
        ed = _Editor()
        ed._aplica_a.set_active_id("steam_game")
        ed._aplica_a.set_active_id("browser")
        assert not ed._get("profile_game_entry_box").visivel


class TestSalvarPerfilDoJogo:
    def test_build_produz_a_regra_por_appid(self) -> None:
        ed = _Editor()
        ed._aplica_a.set_active_id("steam_game")
        ed._get("profile_simple_custom_name").set_text(MMJ)

        p = ed._build_profile_from_editor()
        assert isinstance(p.match, MatchCriteria)
        assert p.match.window_class == [f"steam_app_{MMJ}"]
        assert p.name == "MadJack" and p.priority == 70

    def test_campo_vazio_recusa_o_save_com_frase_de_gente(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ed = _Editor()
        ed._aplica_a.set_active_id("steam_game")
        monkeypatch.setattr(pa, "save_profile", lambda p: ed.salvos.append(p))
        monkeypatch.setattr(pa, "active_profile_name", lambda: None)

        ed.on_profile_save(None)

        assert ed.salvos == [], (
            "antes isto virava MatchAny e nascia mais um catch-all (R-01), "
            'com o toast dizendo "Perfil salvo"'
        )
        assert ed.toasts and "número do jogo na Steam" in ed.toasts[-1], (
            "o toast tem de dizer O QUE falta, não 'Revise os campos do perfil'"
        )

    def test_preview_mostra_a_frase_em_vez_de_erro_de_programa(self) -> None:
        ed = _Editor()
        ed._aplica_a.set_active_id("steam_game")
        # `_refresh_preview` real (o stub o substitui) — chama o do mixin.
        pa.ProfilesActionsMixin._refresh_preview(ed)
        texto = ed._get("profile_preview_label").get_text()
        assert "número do jogo na Steam" in texto
        assert "preview indisponível" not in texto


class TestRoundTripNoEditor:
    def test_reabrir_o_perfil_volta_para_o_simples_com_o_appid(self) -> None:
        ed = _Editor()
        perfil = Profile(
            name="MadJack",
            match=MatchCriteria(window_class=[f"steam_app_{MMJ}"]),
            priority=70,
        )
        ed._populate_editor(perfil)

        assert ed._aplica_a.get_active_id() == "steam_game"
        assert ed._get("profile_simple_custom_name").get_text() == MMJ
        assert ed._get("profile_editor_stack").visible_child == "simples"
        assert ed._mode_advanced is False

    def test_salvar_de_novo_nao_duplica_o_prefixo(self) -> None:
        """O campo guarda o NÚMERO: se `_populate_editor` devolvesse a
        `wm_class` inteira, o Salvar seguinte gravaria
        `steam_app_steam_app_2111190` e o perfil nunca mais casaria."""
        ed = _Editor()
        perfil = Profile(
            name="MadJack",
            match=MatchCriteria(window_class=[f"steam_app_{MMJ}"]),
            priority=70,
        )
        ed._populate_editor(perfil)
        de_novo = ed._build_profile_from_editor()
        assert isinstance(de_novo.match, MatchCriteria)
        assert de_novo.match.window_class == [f"steam_app_{MMJ}"]
