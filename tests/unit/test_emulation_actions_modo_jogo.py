"""FEAT-DSX-GAMEMODE-SUPPRESS-01 — os botões 'Modo jogo'/'Sair do modo jogo' da
aba Emulação chamam daemon.emulation.suppress (transitório), NÃO daemon.pause
(persistente, que renascia o daemon pausado no boot e era um kill-switch amplo).

Guard de regressão para "controle morto no jogo após reboot": antes
on_emulation_pause chamava daemon.pause; o label 'Modo jogo' nunca acertava e o
controle morria. Stubs de gi como em test_rumble_actions.py (armadilha A-12).
"""
from __future__ import annotations

import sys
import types

import pytest


def _install_gi_stubs() -> None:
    # GATE-SKIP-MASK-01: com o PyGObject real disponível, NÃO instala stubs —
    # o merge abaixo mutaria o gi REAL (sobrescreve GLib.idle_add e
    # require_version) e fazia testes de GUI pularem como "ambiente sem GTK".
    # Um stub instalado por outro módulo de teste (__spec__ None) segue
    # sendo reaproveitado para merge de atributos.
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType("gi.repository")
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )
    for cls_name in ("Builder", "Window", "Button", "Label", "Box"):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import emulation_actions  # noqa: E402


def _capture(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []

    def _fake_call_async(method, params, on_success=None, on_failure=None):
        calls.append((method, params))

    monkeypatch.setattr(emulation_actions, "call_async", _fake_call_async)
    return calls


def test_on_emulation_pause_usa_suppress_true(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture(monkeypatch)
    obj = emulation_actions.EmulationActionsMixin()
    obj.on_emulation_pause(None)
    assert calls == [("daemon.emulation.suppress", {"suppressed": True})]


def test_on_emulation_resume_usa_suppress_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture(monkeypatch)
    obj = emulation_actions.EmulationActionsMixin()
    obj.on_emulation_resume(None)
    assert calls == [("daemon.emulation.suppress", {"suppressed": False})]


def test_modo_jogo_nao_usa_daemon_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nunca mais chamar daemon.pause/resume pela GUI (persistia paused.flag)."""
    calls = _capture(monkeypatch)
    obj = emulation_actions.EmulationActionsMixin()
    obj.on_emulation_pause(None)
    obj.on_emulation_resume(None)
    methods = {m for m, _ in calls}
    assert "daemon.pause" not in methods
    assert "daemon.resume" not in methods
