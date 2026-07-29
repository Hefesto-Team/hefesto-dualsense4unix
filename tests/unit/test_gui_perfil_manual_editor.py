"""Editor de perfis e o sentinel `{"type": "manual"}` (débito R-12 item 3).

O sentinel só serve para alguma coisa se a GUI souber escrevê-lo e lê-lo:

- editor avançado com os TRÊS campos vazios grava `MatchManual` (era um
  `MatchCriteria` vazio, que nunca casa e é indistinguível do acidente);
- abrir esse perfil e salvar de novo o mantém manual — sem o round-trip, uma
  visita à aba Perfis rebaixaria a declaração para o acidente;
- a coluna "Quando usar" diz a mesma frase do criteria vazio.

Hermético: stubs de `gi.repository` quando falta PyGObject (padrão de
`test_r12_editor_simples_gui.py`), widgets fake, nenhum GTK real construído.
"""
from __future__ import annotations

import sys
import types
from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: no lugar de `pytest.importorskip("gi")`, que ACEITA o
# stub que outro arquivo de teste planta em sys.modules — e por isso
# deixava este módulo rodar contra um GTK de mentira.
exigir_gi_real("editor manual de perfil")


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
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
)


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

    def connect(self, signal: str, handler: Any) -> None:
        return None

    def get_active_id(self) -> str | None:
        return self._active_id

    def set_active_id(self, the_id: str) -> None:
        self._active_id = the_id


class _Editor(pa.ProfilesActionsMixin):
    """Editor fake: métodos REAIS do mixin sobre widgets fake."""

    def __init__(self) -> None:
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry("coop_local"),
            "profile_priority_scale": _FakeScale(45),
            "profile_simple_custom_name": _FakeEntry(""),
            "profile_game_entry_box": _FakeBox(),
            "profile_editor_stack": _FakeStack(),
            "profile_advanced_switch": _FakeSwitch(),
            "profile_window_class_entry": _FakeEntry(""),
            "profile_title_regex_entry": _FakeEntry(""),
            "profile_process_name_entry": _FakeEntry(""),
        }
        self._profiles_cache: list[Profile] = []
        self._duplicate_source = None
        self._new_profile = False
        self._mode_advanced = True
        self._aplica_a = _FakeSelector("any")

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return None


class TestEditorAvancadoGravaOSentinel:
    def test_tres_campos_vazios_viram_manual(self) -> None:
        """Antes saía `MatchCriteria()` — a mesma inércia, sem dizer por quê."""
        ed = _Editor()

        perfil = ed._build_profile_from_editor()

        assert isinstance(perfil.match, MatchManual)
        assert perfil.matches({"wm_class": "steam_app_1599660"}) is False

    def test_um_campo_preenchido_continua_criteria(self) -> None:
        ed = _Editor()
        ed._get("profile_title_regex_entry").set_text("Sackboy")

        perfil = ed._build_profile_from_editor()

        assert isinstance(perfil.match, MatchCriteria)
        assert perfil.match.window_title_regex == "Sackboy"

    def test_round_trip_do_perfil_manual(self) -> None:
        """Abrir e salvar de novo não rebaixa a declaração para o acidente."""
        ed = _Editor()
        original = Profile(name="coop_local", match=MatchManual(), priority=45)

        ed._populate_editor(original)

        assert ed._mode_advanced is True, "manual não tem preset simples"
        assert ed._get("profile_window_class_entry").get_text() == ""
        assert isinstance(ed._build_profile_from_editor().match, MatchManual)

    def test_perfil_sempre_nao_e_confundido_com_manual(self) -> None:
        """`MatchAny` abre no editor SIMPLES — nada a ver com o sentinel."""
        ed = _Editor()

        ed._populate_editor(Profile(name="fallback", match=MatchAny()))

        assert ed._mode_advanced is False
        assert ed._get("profile_editor_stack").visible_child == "simples"


class TestColunaQuandoUsar:
    def test_manual_diz_a_mesma_frase_do_criteria_vazio(self) -> None:
        assert pa._match_label(MatchManual()) == pa.LABEL_SO_MANUAL
        assert pa._match_label(MatchCriteria()) == pa.LABEL_SO_MANUAL

    def test_contrato_antigo_por_string_segue_valendo(self) -> None:
        """A lista do daemon manda o discriminador cru pelo IPC."""
        assert pa._match_label("manual") == pa.LABEL_SO_MANUAL
        assert pa._match_label("any") == "Sempre"
        assert pa._match_label("criteria") == "Só neste programa"
