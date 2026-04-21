"""Aba Rumble: 2 sliders (weak, strong) + Aplicar + Testar 500ms + Parar."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.app.ipc_bridge import rumble_set


class RumbleActionsMixin(WidgetAccessMixin):
    """Controla a aba Rumble."""

    def install_rumble_tab(self) -> None:
        # Nada a inicializar além dos adjustments já definidos no Glade.
        pass

    def on_rumble_apply(self, _btn: Gtk.Button) -> None:
        weak, strong = self._read_scales()
        ok = rumble_set(weak, strong)
        self._toast_rumble(
            f"Rumble aplicado: weak={weak}, strong={strong}"
            if ok
            else "Falha (daemon offline?)"
        )

    def on_rumble_test_500ms(self, _btn: Gtk.Button) -> None:
        weak, strong = self._read_scales()
        if weak == 0 and strong == 0:
            weak = 160
            strong = 220
            self._set_scales(weak, strong)
        ok = rumble_set(weak, strong)
        if not ok:
            self._toast_rumble("Falha (daemon offline?)")
            return
        self._toast_rumble(f"Testando por 500 ms (weak={weak}, strong={strong})")
        GLib.timeout_add(500, self._rumble_test_stop)

    def on_rumble_stop(self, _btn: Gtk.Button) -> None:
        self._set_scales(0, 0)
        rumble_set(0, 0)
        self._toast_rumble("Rumble parado")

    # --- helpers ---

    def _read_scales(self) -> tuple[int, int]:
        weak = int(self._get("rumble_weak_scale").get_value())
        strong = int(self._get("rumble_strong_scale").get_value())
        return weak, strong

    def _set_scales(self, weak: int, strong: int) -> None:
        self._get("rumble_weak_scale").set_value(weak)
        self._get("rumble_strong_scale").set_value(strong)

    def _rumble_test_stop(self) -> bool:
        rumble_set(0, 0)
        self._set_scales(0, 0)
        self._toast_rumble("Teste encerrado (motores zerados)")
        return False

    def _toast_rumble(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("rumble")
        bar.push(ctx_id, msg)
