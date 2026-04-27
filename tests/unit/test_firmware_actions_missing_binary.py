"""Testes do ``_INSTALL_HELP`` e do fluxo `dualsensectl` ausente na aba Firmware.

Sprint CLUSTER-INSTALL-DEPS-01: a mensagem antiga citava AUR/brew/build genérico.
A nova orienta Flathub primeiro (canônico do upstream nowrep) e GitHub como
fallback. Estes testes ancoram o conteúdo para regressão futura.

Padrão de stubs ``gi.repository`` reusa ``_install_gi_stubs`` de
``test_firmware_actions.py`` (armadilha A-12 — ``.venv`` opcionalmente sem
PyGObject).
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    """Instala stubs de ``gi.repository.{Gtk,GLib}`` (idempotente)."""
    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType(
        "gi.repository"
    )
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )

    class _ResponseType:
        OK = -5
        CANCEL = -6

    class _MessageType:
        WARNING = 1

    class _ButtonsType:
        OK_CANCEL = 4

    class _FileChooserAction:
        OPEN = 0

    for cls_name in (
        "Builder", "Window", "Button", "ToggleButton", "ComboBoxText",
        "Switch", "TextView", "TextBuffer", "Scale", "Label", "Box",
        "FileFilter", "FileChooserDialog", "MessageDialog",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    if not hasattr(gtk_mod, "ResponseType"):
        gtk_mod.ResponseType = _ResponseType  # type: ignore[attr-defined]
    if not hasattr(gtk_mod, "MessageType"):
        gtk_mod.MessageType = _MessageType  # type: ignore[attr-defined]
    if not hasattr(gtk_mod, "ButtonsType"):
        gtk_mod.ButtonsType = _ButtonsType  # type: ignore[attr-defined]
    if not hasattr(gtk_mod, "FileChooserAction"):
        gtk_mod.FileChooserAction = _FileChooserAction  # type: ignore[attr-defined]

    def _idle_add(fn: Any, *a: Any, **kw: Any) -> int:
        fn(*a, **kw)
        return 0

    glib_mod.idle_add = _idle_add  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]

    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions import firmware_actions  # noqa: E402
from hefesto_dualsense4unix.app.actions.firmware_actions import (  # noqa: E402
    _INSTALL_HELP,
)

# ---------------------------------------------------------------------------
# Conteúdo da mensagem
# ---------------------------------------------------------------------------


def test_install_help_orienta_flathub_primeiro() -> None:
    """A mensagem cita Flathub explicitamente (canônico do upstream)."""
    assert "Flathub" in _INSTALL_HELP


def test_install_help_traz_url_flathub() -> None:
    """URL completa do Flathub deve estar presente para link clicável."""
    assert "flathub.org/apps/com.github.nowrep.dualsensectl" in _INSTALL_HELP


def test_install_help_traz_url_github_como_fallback() -> None:
    """GitHub permanece como fallback de build manual."""
    assert "github.com/nowrep/dualsensectl" in _INSTALL_HELP


def test_install_help_em_pt_br() -> None:
    """Mantém PT-BR — não regredir para EN."""
    assert "não encontrado" in _INSTALL_HELP
    assert "Instale" in _INSTALL_HELP


def test_install_help_sem_termos_obsoletos() -> None:
    """Termos antigos (AUR, brew) saíram — Pop!_OS/Ubuntu/Fedora alvo."""
    assert "AUR" not in _INSTALL_HELP
    assert "brew" not in _INSTALL_HELP


# ---------------------------------------------------------------------------
# Fluxo install_firmware_tab com binário ausente
# ---------------------------------------------------------------------------


class _FakeWidget:
    """Coleta ``set_text``/``set_label``/``set_sensitive`` em listas."""

    def __init__(self) -> None:
        self.text_calls: list[str] = []
        self.label_calls: list[str] = []
        self.sensitive_calls: list[bool] = []

    def set_text(self, t: str) -> None:
        self.text_calls.append(t)

    def set_label(self, t: str) -> None:
        self.label_calls.append(t)

    def set_sensitive(self, v: bool) -> None:
        self.sensitive_calls.append(bool(v))

    def set_fraction(self, _f: float) -> None:
        pass

    def set_show_text(self, _v: bool) -> None:
        pass


class _FakeMixin:
    def __init__(self) -> None:
        self._widgets: dict[str, _FakeWidget] = {}

    def _get(self, key: str) -> _FakeWidget:
        if key not in self._widgets:
            self._widgets[key] = _FakeWidget()
        return self._widgets[key]


def _build_mixin(monkeypatch: pytest.MonkeyPatch) -> _FakeMixin:
    monkeypatch.setattr(
        firmware_actions.FirmwareUpdater,
        "is_available",
        lambda self: False,
    )
    inst = _FakeMixin()
    for name in (
        "install_firmware_tab",
        "_set_firmware_label",
        "_set_progress",
        "_set_button_enabled",
    ):
        setattr(
            inst,
            name,
            firmware_actions.FirmwareActionsMixin.__dict__[name].__get__(
                inst, type(inst)
            ),
        )
    return inst


def test_install_firmware_tab_ausente_mostra_install_help_completo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quando ``is_available()`` é ``False`` o texto exato do ``_INSTALL_HELP`` aparece."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_firmware_tab()  # type: ignore[attr-defined]

    status = mixin._widgets["firmware_status_label"]
    assert _INSTALL_HELP in status.text_calls


def test_install_firmware_tab_ausente_desabilita_tres_botoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os três botões da aba Firmware ficam não-clicáveis."""
    mixin = _build_mixin(monkeypatch)
    mixin.install_firmware_tab()  # type: ignore[attr-defined]

    for btn in ("firmware_check_btn", "firmware_browse_btn", "firmware_apply_btn"):
        widget = mixin._widgets[btn]
        assert False in widget.sensitive_calls, (
            f"{btn} deveria ter sido desabilitado"
        )
