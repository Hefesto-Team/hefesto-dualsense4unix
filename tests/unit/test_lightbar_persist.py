"""Testes de persistência de brightness da lightbar — FEAT-LED-BRIGHTNESS-03."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("lightbar: persistência do brilho no perfil")

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _install_gi_stubs() -> None:
    """Instala stubs minimos de gi.repository para rodar em CI sem display."""
    try:
        import gi as _gi

        _gi.require_version("Gdk", "3.0")
        _gi.require_version("Gtk", "3.0")
        from gi.repository import Gdk as _Gdk  # noqa: F401
        return
    except Exception:
        pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]

    repo_mod = sys.modules.get("gi.repository") or types.ModuleType("gi.repository")

    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType("gi.repository.Gtk")
    for _attr in (
        "Builder", "Window", "Button", "ComboBoxText", "Switch",
        "TextView", "TextBuffer", "Scale", "DrawingArea", "ColorButton",
        "CheckButton", "TreeView", "TreeSelection", "TreeViewColumn",
        "CellRendererText", "ListStore",
        "Box", "Label", "Frame", "Entry", "RadioButton", "Stack", "TreePath",
        "ToggleButton", "MessageDialog", "MessageType", "ButtonsType",
        "ResponseType",
    ):
        if not hasattr(gtk_mod, _attr):
            setattr(gtk_mod, _attr, object)

    gobj_mod = sys.modules.get("gi.repository.GObject") or types.ModuleType("gi.repository.GObject")
    if not hasattr(gobj_mod, "TYPE_STRING"):
        gobj_mod.TYPE_STRING = str  # type: ignore[attr-defined]
    if not hasattr(gobj_mod, "TYPE_INT"):
        gobj_mod.TYPE_INT = int  # type: ignore[attr-defined]

    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType("gi.repository.GLib")
    if not hasattr(glib_mod, "timeout_add"):
        glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    if not hasattr(glib_mod, "timeout_add_seconds"):
        glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]

    gdk_mod = sys.modules.get("gi.repository.Gdk") or types.ModuleType("gi.repository.Gdk")

    class _FakeRGBA:
        red: float = 0.0
        green: float = 0.0
        blue: float = 0.0
        alpha: float = 1.0

    if not hasattr(gdk_mod, "RGBA"):
        gdk_mod.RGBA = _FakeRGBA  # type: ignore[attr-defined]

    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GObject = gobj_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    repo_mod.Gdk = gdk_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GObject"] = gobj_mod
    sys.modules["gi.repository.GLib"] = glib_mod
    sys.modules["gi.repository.Gdk"] = gdk_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str, brightness: float = 1.0) -> Profile:
    return Profile(
        name=name,
        match=MatchAny(),
        leds=LedsConfig(lightbar=(100, 200, 50), lightbar_brightness=brightness),
    )


def _make_profiles_instance(pending_brightness: float = 1.0) -> ProfilesActionsMixin:
    """Cria instância parcial de ProfilesActionsMixin sem GTK real."""
    instance = ProfilesActionsMixin.__new__(ProfilesActionsMixin)
    instance._pending_brightness = pending_brightness  # type: ignore[attr-defined]
    instance._profiles_store = MagicMock()  # type: ignore[attr-defined]
    instance._mode_advanced = False  # type: ignore[attr-defined]
    return instance


def test_brightness_persiste_no_json(isolated_profiles_dir: Path) -> None:
    """Perfil salvo com brightness=0.25 deve retornar 0.25 ao recarregar."""
    profile = _mk_profile("brilho_baixo", brightness=0.25)
    save_profile(profile)

    reloaded = load_profile("brilho_baixo")
    assert reloaded.leds.lightbar_brightness == pytest.approx(0.25)


def test_brightness_default_1(isolated_profiles_dir: Path) -> None:
    """Perfil sem lightbar_brightness explícito usa default 1.0."""
    profile = _mk_profile("full_bright")
    save_profile(profile)

    reloaded = load_profile("full_bright")
    assert reloaded.leds.lightbar_brightness == pytest.approx(1.0)


# Testes do _build_profile_from_editor: inclui _pending_brightness


# Teste do guard de refresh: on_lightbar_brightness_changed


