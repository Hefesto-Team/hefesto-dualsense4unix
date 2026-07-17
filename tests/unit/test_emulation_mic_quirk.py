"""BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01 — ligar o mic do DualSense SEM o quirk de
áudio USB ativo na SESSÃO ATUAL pode reabrir o storm -71 (o controle cai no meio
do jogo). A GUI avisa por toast ANTES de ligar (sem bloquear) e expõe o helper
estático _usb_quirk_active(), espelhando o check_usb_quirk do doctor.sh (só
/proc/cmdline e /sys/module/usbcore/parameters/quirks valem para a sessão).

Stubs de gi como em test_emulation_actions_modo_jogo.py (armadilha A-12).
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

Mixin = emulation_actions.EmulationActionsMixin


# --- _usb_quirk_active() ---------------------------------------------------


def test_usb_quirk_active_true_no_cmdline(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cmdline = tmp_path / "cmdline"
    cmdline.write_text(
        "BOOT_IMAGE=/vmlinuz usbcore.quirks=054c:0ce6:gn,054c:0df2:gn ro\n"
    )
    quirks = tmp_path / "quirks"
    quirks.write_text("")
    monkeypatch.setattr(Mixin, "_USB_QUIRK_PATHS", (str(cmdline), str(quirks)))
    assert Mixin._usb_quirk_active() is True


def test_usb_quirk_active_true_em_runtime_sysfs(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cmdline = tmp_path / "cmdline"
    cmdline.write_text("BOOT_IMAGE=/vmlinuz ro quiet\n")
    quirks = tmp_path / "quirks"
    quirks.write_text("054c:0ce6:gn\n")
    monkeypatch.setattr(Mixin, "_USB_QUIRK_PATHS", (str(cmdline), str(quirks)))
    assert Mixin._usb_quirk_active() is True


def test_usb_quirk_active_false_quando_ausente(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cmdline = tmp_path / "cmdline"
    cmdline.write_text("BOOT_IMAGE=/vmlinuz ro quiet splash\n")
    quirks = tmp_path / "quirks"
    quirks.write_text("0781:5567:bk\n")  # outro quirk qualquer
    monkeypatch.setattr(Mixin, "_USB_QUIRK_PATHS", (str(cmdline), str(quirks)))
    assert Mixin._usb_quirk_active() is False


def test_usb_quirk_active_false_quando_paths_inexistentes(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # OSError ao ler arquivos ausentes é engolido — resultado é False, sem raise.
    monkeypatch.setattr(
        Mixin, "_USB_QUIRK_PATHS", (str(tmp_path / "a"), str(tmp_path / "b"))
    )
    assert Mixin._usb_quirk_active() is False


# --- on_emulation_mic_on avisa (mas não bloqueia) --------------------------


def _wire(obj, monkeypatch):
    toasts: list[str] = []
    ran: list[tuple[str, str]] = []
    monkeypatch.setattr(obj, "_toast_emulation", lambda m: toasts.append(m))
    monkeypatch.setattr(obj, "_run_mic", lambda flag, msg: ran.append((flag, msg)))
    return toasts, ran


def test_mic_on_avisa_quando_quirk_ausente(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = Mixin()
    _toasts, ran = _wire(obj, monkeypatch)
    monkeypatch.setattr(Mixin, "_usb_quirk_active", staticmethod(lambda: False))
    obj.on_emulation_mic_on(None)
    # PROSSEGUE ligando o mic (não bloqueia)...
    assert len(ran) == 1
    flag, msg = ran[0]
    assert flag == "--enable-mic"
    # ...e o aviso persiste na mensagem FINAL (não num toast que é sobrescrito).
    # EMU-04: sem jargão ("storm -71"/nome de script) — o leigo é mandado para
    # o botão "Aplicar correções" da aba Sistema.
    assert "travar" in msg
    assert "Aplicar correções" in msg
    assert "storm" not in msg


def test_mic_on_nao_avisa_quando_quirk_ativo(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = Mixin()
    _toasts, ran = _wire(obj, monkeypatch)
    monkeypatch.setattr(Mixin, "_usb_quirk_active", staticmethod(lambda: True))
    obj.on_emulation_mic_on(None)
    assert ran == [("--enable-mic", "Mic do DualSense ligado")]  # sem aviso de storm


def test_mic_off_nunca_avisa_de_quirk(monkeypatch: pytest.MonkeyPatch) -> None:
    """on_emulation_mic_off não foi tocado: desligar o mic nunca reabre o storm."""
    obj = Mixin()
    toasts, ran = _wire(obj, monkeypatch)
    # mesmo sem quirk, desligar não dispara aviso.
    monkeypatch.setattr(Mixin, "_usb_quirk_active", staticmethod(lambda: False))
    obj.on_emulation_mic_off(None)
    assert toasts == []
    assert ran == [("--disable-source", "Mic do DualSense desligado")]
