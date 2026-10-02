"""Editor de perfis — seção "Modo" (FEAT-PROFILE-MODE-GUI-01)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o editor de perfis da janela")

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Instala stubs mínimos de ``gi.repository`` se o módulo real faltar."""
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

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")
    gobject_mod = types.ModuleType("gi.repository.GObject")

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = object  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.CheckButton = object  # type: ignore[attr-defined]
    gtk_mod.ComboBoxText = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.TreeView = object  # type: ignore[attr-defined]
    gtk_mod.TreeViewColumn = object  # type: ignore[attr-defined]
    gtk_mod.CellRendererText = object  # type: ignore[attr-defined]
    gtk_mod.ListStore = object  # type: ignore[attr-defined]
    gtk_mod.TreeSelection = object  # type: ignore[attr-defined]
    gtk_mod.TreePath = object  # type: ignore[attr-defined]
    gtk_mod.Box = object  # type: ignore[attr-defined]
    gtk_mod.Label = object  # type: ignore[attr-defined]
    gtk_mod.Frame = object  # type: ignore[attr-defined]
    gtk_mod.Entry = object  # type: ignore[attr-defined]
    gtk_mod.RadioButton = object  # type: ignore[attr-defined]
    gtk_mod.Scale = object  # type: ignore[attr-defined]
    gtk_mod.Stack = object  # type: ignore[attr-defined]
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

from hefesto_dualsense4unix.app.actions.profiles_actions import (
    ProfilesActionsMixin,
)
from hefesto_dualsense4unix.profiles.schema import Profile


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text


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


class _FakeSelector:
    """Stub do SegmentedSelector: API por-ID + "changed" emitido no set_active_id."""

    def __init__(self, active: str | None = None) -> None:
        self._active_id = active
        self._handlers: list[Any] = []

    def connect(self, signal: str, handler: Any) -> None:
        if signal == "changed":
            self._handlers.append(handler)

    def get_active_id(self) -> str | None:
        return self._active_id

    def limpar_ativo(self) -> None:
        """ESCOLHA-DELA-VENCE-01: "sem opinião" não marca botão nenhum."""
        self._active_id = None

    def set_tooltips(self, dicas: dict[str, str]) -> None:
        """Dica por botão (E4). O dublê só precisa aceitar."""
        self._dicas = dict(dicas)

    def set_active_id(self, the_id: str) -> None:
        if the_id == self._active_id:
            return
        self._active_id = the_id
        for handler in list(self._handlers):
            handler(self)


class _FakeBox:
    """Linha de opções do gamepad: registra visibilidade/sensibilidade."""

    def __init__(self) -> None:
        self.visible = True
        self.no_show_all = False
        self.sensitive = True

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_no_show_all(self, flag: bool) -> None:
        self.no_show_all = flag

    def set_sensitive(self, sensitive: bool) -> None:
        self.sensitive = sensitive


class _EditorStub(ProfilesActionsMixin):
    """Editor fake: métodos REAIS do mixin sobre widgets fake (sem GTK)."""

    def __init__(self, name: str = "perfil_teste", priority: int = 10) -> None:
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry(name),
            "profile_priority_scale": _FakeScale(priority),
            "profile_simple_custom_name": _FakeEntry(""),
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
        }
        self._profiles_cache = []
        self._duplicate_source = None
        self._mode_advanced = False
        self._aplica_a = _FakeSelector("any")

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)


def _profile_com_mode(name: str, mode: dict[str, Any] | None) -> Profile:
    data: dict[str, Any] = {
        "name": name,
        "version": 1,
        "match": {"type": "any"},
        "priority": 10,
    }
    if mode is not None:
        data["mode"] = mode
    return Profile.model_validate(data)


class TestModeOptionsVisibility:
    def test_gamepad_mostra_e_habilita_opcoes(self) -> None:
        stub = _EditorStub().com_secao_mode()

        stub._mode_kind_selector.set_active_id("gamepad")

        opts = stub._mode_gamepad_opts
        assert opts.visible is True
        assert opts.sensitive is True
        assert opts.no_show_all is False

    def test_none_esconde_e_desabilita_opcoes(self) -> None:
        stub = _EditorStub().com_secao_mode()
        stub._mode_kind_selector.set_active_id("gamepad")

        stub._mode_kind_selector.set_active_id("none")

        opts = stub._mode_gamepad_opts
        assert opts.visible is False
        assert opts.sensitive is False
        assert opts.no_show_all is True

    def test_clique_da_usuaria_sincroniza_visibilidade(self) -> None:
        """O clique no kind reflete na visibilidade das opções de gamepad."""
        stub = _EditorStub().com_secao_mode()

        stub._mode_kind_selector.set_active_id("gamepad")

        assert stub._mode_gamepad_opts.visible is True

        stub._mode_kind_selector.set_active_id("desktop")

        assert stub._mode_gamepad_opts.visible is False


