"""R-12 (auditoria 23/07) — fiação da opção "Jogo da Steam" no editor simples."""
from __future__ import annotations

import sys
import types
from typing import Any


from tests.conftest import exigir_gi_real

exigir_gi_real("R12 (editor simples)")


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

from hefesto_dualsense4unix.app.actions import profiles_actions as pa

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
    """Dublê da linha "Nome do jogo:" com a doutrina de visibilidade do GTK."""

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


class _Editor(pa.ProfilesActionsMixin):

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return None

    def _refresh_preview(self) -> None:
        return None

    def _prefill_steam_appid(self) -> None:
        self.prefills += 1

    def _reload_profiles_store(self, **_kw: Any) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        return None

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


class TestSeletorAplicaA:

    def test_escolher_jogo_da_steam_mostra_o_campo_e_troca_a_dica(self) -> None:
        ed = _Editor()
        ed._aplica_a.set_active_id("steam_game")
        assert ed._get("profile_game_entry_box").visivel
        entry = ed._get("profile_simple_custom_name")
        assert "1599660" in entry.placeholder, entry.placeholder
        assert "endereço da loja" in entry.placeholder, entry.placeholder
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


