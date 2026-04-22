"""Testes de persistência de brightness da lightbar — FEAT-LED-BRIGHTNESS-03.

Valida o ciclo set-brightness → save → load: o valor do slider persiste
no JSON do perfil e é recuperado ao recarregar o estado.

Não depende de GTK real (usa stubs), portanto roda em CI sem display.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stubs de gi — mesmo padrao de test_status_actions_reconnect.py
# ---------------------------------------------------------------------------


def _install_gi_stubs() -> None:
    """Instala stubs minimos de gi.repository para rodar em CI sem display.

    Complementa stubs existentes: se gi ja esta em sys.modules (instalado
    por outro modulo de teste), ainda garante que Gdk e GObject estao
    disponiveis — necessarios para lightbar_actions (Gdk.RGBA) e
    profiles_actions (GObject.TYPE_STRING).
    """
    try:
        # Ambiente com GTK real: não instala stubs.
        from gi.repository import Gdk as _Gdk  # noqa: F401
        return
    except Exception:
        pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]

    repo_mod = sys.modules.get("gi.repository") or types.ModuleType("gi.repository")

    # --- Gtk ---
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType("gi.repository.Gtk")
    for _attr in (
        "Builder", "Window", "Button", "ComboBoxText", "Switch",
        "TextView", "TextBuffer", "Scale", "DrawingArea", "ColorButton",
        "CheckButton", "TreeView", "TreeSelection", "TreeViewColumn",
        "CellRendererText", "ListStore",
    ):
        if not hasattr(gtk_mod, _attr):
            setattr(gtk_mod, _attr, object)

    # --- GObject ---
    gobj_mod = sys.modules.get("gi.repository.GObject") or types.ModuleType("gi.repository.GObject")
    if not hasattr(gobj_mod, "TYPE_STRING"):
        gobj_mod.TYPE_STRING = str  # type: ignore[attr-defined]
    if not hasattr(gobj_mod, "TYPE_INT"):
        gobj_mod.TYPE_INT = int  # type: ignore[attr-defined]

    # --- GLib ---
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType("gi.repository.GLib")
    if not hasattr(glib_mod, "timeout_add"):
        glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    if not hasattr(glib_mod, "timeout_add_seconds"):
        glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]

    # --- Gdk (necessario para Gdk.RGBA em lightbar_actions) ---
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

# Imports dependentes de gi abaixo da instalação dos stubs.
from hefesto.app.actions.lightbar_actions import LightbarActionsMixin  # noqa: E402
from hefesto.app.actions.profiles_actions import ProfilesActionsMixin  # noqa: E402
from hefesto.profiles import loader as loader_module  # noqa: E402
from hefesto.profiles.loader import load_profile, save_profile  # noqa: E402
from hefesto.profiles.schema import LedsConfig, MatchAny, Profile  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture: diretório isolado de perfis
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    # modo simples por padrão nos testes
    instance._mode_advanced = False  # type: ignore[attr-defined]
    return instance


# ---------------------------------------------------------------------------
# Testes de schema: brightness persiste no JSON
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Testes do _build_profile_from_editor: inclui _pending_brightness
# ---------------------------------------------------------------------------


def test_build_profile_inclui_pending_brightness(isolated_profiles_dir: Path) -> None:
    """_build_profile_from_editor lê _pending_brightness e inclui no perfil."""
    base_profile = _mk_profile("meu_perfil", brightness=0.8)
    save_profile(base_profile)

    instance = _make_profiles_instance(pending_brightness=0.35)

    def fake_get(widget_id: str) -> MagicMock:
        m = MagicMock()
        if widget_id == "profile_name_entry":
            m.get_text.return_value = "meu_perfil"
        elif widget_id == "profile_priority_scale":
            m.get_value.return_value = 5.0
        elif widget_id == "profile_radio_any":
            m.get_active.return_value = True
        elif widget_id == "profile_simple_custom_name":
            m.get_text.return_value = ""
        return m

    instance._get = fake_get  # type: ignore[attr-defined]

    result = instance._build_profile_from_editor()
    assert result.leds.lightbar_brightness == pytest.approx(0.35)


def test_build_profile_sem_existente_usa_pending(isolated_profiles_dir: Path) -> None:
    """Perfil novo (sem existente no disco) usa _pending_brightness."""
    instance = _make_profiles_instance(pending_brightness=0.6)

    def fake_get(widget_id: str) -> MagicMock:
        m = MagicMock()
        if widget_id == "profile_name_entry":
            m.get_text.return_value = "perfil_novo"
        elif widget_id == "profile_priority_scale":
            m.get_value.return_value = 0.0
        elif widget_id == "profile_radio_any":
            m.get_active.return_value = True
        elif widget_id == "profile_simple_custom_name":
            m.get_text.return_value = ""
        return m

    instance._get = fake_get  # type: ignore[attr-defined]

    result = instance._build_profile_from_editor()
    assert result.leds.lightbar_brightness == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Testes de _refresh_lightbar_from_state: slider atualizado pelo state_full
# ---------------------------------------------------------------------------


def test_refresh_lightbar_atualiza_slider() -> None:
    """_refresh_lightbar_from_state move o slider para o valor do state_full."""
    instance = LightbarActionsMixin.__new__(LightbarActionsMixin)
    instance._current_brightness = 1.0  # type: ignore[attr-defined]
    instance._pending_brightness = 1.0  # type: ignore[attr-defined]
    instance._refresh_guard = False  # type: ignore[attr-defined]

    scale_mock = MagicMock()
    instance._get = lambda wid: scale_mock if wid == "lightbar_brightness_scale" else None  # type: ignore[attr-defined]

    state_full: dict[str, Any] = {"leds": {"lightbar_brightness": 0.4}}
    instance._refresh_lightbar_from_state(state_full)

    scale_mock.set_value.assert_called_once_with(pytest.approx(40.0))
    assert instance._current_brightness == pytest.approx(0.4)  # type: ignore[attr-defined]
    assert instance._pending_brightness == pytest.approx(0.4)  # type: ignore[attr-defined]


def test_refresh_lightbar_default_quando_ausente() -> None:
    """Quando state_full não tem leds.lightbar_brightness, usa 1.0 (sem dimming)."""
    instance = LightbarActionsMixin.__new__(LightbarActionsMixin)
    instance._current_brightness = 0.5  # type: ignore[attr-defined]
    instance._pending_brightness = 0.5  # type: ignore[attr-defined]
    instance._refresh_guard = False  # type: ignore[attr-defined]

    scale_mock = MagicMock()
    instance._get = lambda wid: scale_mock if wid == "lightbar_brightness_scale" else None  # type: ignore[attr-defined]

    state_full: dict[str, Any] = {}
    instance._refresh_lightbar_from_state(state_full)

    scale_mock.set_value.assert_called_once_with(pytest.approx(100.0))
    assert instance._current_brightness == pytest.approx(1.0)  # type: ignore[attr-defined]


def test_refresh_guard_previne_loop() -> None:
    """on_lightbar_brightness_changed retorna imediatamente com guard ativo."""
    instance = LightbarActionsMixin.__new__(LightbarActionsMixin)
    instance._current_brightness = 0.5  # type: ignore[attr-defined]
    instance._pending_brightness = 0.5  # type: ignore[attr-defined]
    instance._refresh_guard = True  # guard ativo

    scale_mock = MagicMock()
    scale_mock.get_value.return_value = 80.0

    # Com guard ativo, o handler não deve alterar os valores.
    instance.on_lightbar_brightness_changed(scale_mock)

    assert instance._current_brightness == pytest.approx(0.5)  # type: ignore[attr-defined]
    assert instance._pending_brightness == pytest.approx(0.5)  # type: ignore[attr-defined]
