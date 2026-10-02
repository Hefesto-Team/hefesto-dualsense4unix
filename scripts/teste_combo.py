#!/usr/bin/env python3
"""Diagnóstico do flicker de combo no COSMIC (bug de foco/popup do cosmic-comp)."""
import itertools
import sys
import time

import pathlib
_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[1] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

JITTER = "--jitter" in sys.argv
GATE = "--gate" in sys.argv


def backend_name() -> str:
    disp = Gdk.Display.get_default()
    t = type(disp).__name__
    if "Wayland" in t:
        return "WAYLAND nativo"
    if "X11" in t:
        return "XWayland (X11)"
    return t


win = Gtk.Window(title="teste_combo")
win.set_default_size(480, 240)
win.connect("destroy", Gtk.main_quit)

box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
for m in ("set_margin_top", "set_margin_bottom", "set_margin_start", "set_margin_end"):
    getattr(box, m)(24)

modo = ("jitter 10Hz" if JITTER else "estático") + (" + GATE (fix)" if GATE else " + gate OFF")
cab = Gtk.Label()
cab.set_markup(
    f"<b>Backend:</b> {backend_name()}\n<b>Modo:</b> {modo}\n"
    "Clique o dropdown ~10x. Olhe o TERMINAL (ABRIU / fechou sozinho)."
)
box.pack_start(cab, False, False, 0)

label = Gtk.Label()
label.set_markup('<span font_family="monospace">X: 128  Y: 128</span>')
box.pack_start(label, False, False, 0)

combo = Gtk.ComboBoxText()
for x in ("Todos os controles", "Controle 1 - BT", "Controle 2 - USB"):
    combo.append_text(x)
combo.set_active(0)
box.pack_start(combo, False, False, 0)

win.add(box)
win.show_all()

print(f"=== backend={backend_name()}  jitter={JITTER}  gate={GATE} ===", flush=True)

stats = {"abriu": 0, "fechou": 0}
abriu_em = {"t": 0.0}


def on_popup(combo_, _pspec):
    shown = combo_.get_property("popup-shown")
    now = time.monotonic()
    if shown:
        stats["abriu"] += 1
        abriu_em["t"] = now
        print(f"[{time.strftime('%H:%M:%S')}] ABRIU            (#{stats['abriu']})", flush=True)
    else:
        dt = now - abriu_em["t"]
        espontaneo = dt < 0.4
        stats["fechou"] += 1
        tag = "fechou sozinho (BUG)" if espontaneo else "fechou (ok)"
        print(f"[{time.strftime('%H:%M:%S')}] {tag}  +{dt*1000:.0f}ms", flush=True)


combo.connect("notify::popup-shown", on_popup)

if JITTER:
    vals = itertools.cycle([127, 9, 128, 130, 12, 129, 100])

    def tick() -> bool:
        if GATE and Gtk.grab_get_current() is not None:
            return True
        v = next(vals)
        label.set_markup(f'<span font_family="monospace">X: {v}  Y: {v}</span>')
        return True

    GLib.timeout_add(100, tick)


def resumo() -> bool:
    print(
        f"--- RESUMO: aberturas={stats['abriu']} fechamentos={stats['fechou']} "
        "(feche a janela p/ sair) ---",
        flush=True,
    )
    return True


GLib.timeout_add_seconds(15, resumo)
Gtk.main()
