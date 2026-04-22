"""Aba Lightbar + Player LEDs."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto.app.actions.base import WidgetAccessMixin
from hefesto.app.ipc_bridge import led_set


class LightbarActionsMixin(WidgetAccessMixin):
    """Controla a aba Lightbar + Player LEDs."""

    _current_rgb: tuple[int, int, int] = (255, 128, 0)
    # Luminosidade em [0.0, 1.0]; 1.0 = máximo (FEAT-LED-BRIGHTNESS-01).
    _current_brightness: float = 1.0

    def install_lightbar_tab(self) -> None:
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.connect("draw", self._on_lightbar_preview_draw)
        # Seta cor inicial programaticamente (Glade não suporta inline
        # RGBA com syntax "rgb(...)" sem segfault em todas as versoes).
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            rgba = Gdk.RGBA()
            rgba.red = 1.0
            rgba.green = 128 / 255
            rgba.blue = 0.0
            rgba.alpha = 1.0
            button.set_rgba(rgba)
            self._current_rgb = (255, 128, 0)

    # --- signals lightbar ---

    def on_lightbar_color_set(self, button: Gtk.ColorButton) -> None:
        rgba = button.get_rgba()
        self._current_rgb = (
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255),
        )
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_apply(self, _btn: Gtk.Button) -> None:
        ok = led_set(self._current_rgb, brightness=self._current_brightness)
        pct = round(self._current_brightness * 100)
        self._toast_light(
            f"Cor RGB {self._current_rgb} a {pct}% aplicada"
            if ok
            else "Falha (daemon offline?)"
        )

    def on_lightbar_brightness_changed(self, scale: Gtk.Scale) -> None:
        """Slider 0-100 (%) -> atualiza luminosidade corrente e repinta prévia.

        Não aplica no hardware automaticamente; o usuário confirma via botão
        "Aplicar no controle". Assim evitamos flood de IPC durante arrasto.
        """
        raw = float(scale.get_value())
        # Clamp defensivo: GtkAdjustment já limita, mas nunca confie cego.
        pct = max(0.0, min(100.0, raw))
        self._current_brightness = pct / 100.0
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_off(self, _btn: Gtk.Button) -> None:
        self._current_rgb = (0, 0, 0)
        rgba = Gdk.RGBA()
        rgba.red = 0.0
        rgba.green = 0.0
        rgba.blue = 0.0
        rgba.alpha = 1.0
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            button.set_rgba(rgba)
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()
        ok = led_set((0, 0, 0))
        self._toast_light("Lightbar apagada" if ok else "Falha (daemon offline?)")

    # --- signals player leds ---

    def on_player_leds_preset_all(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([True] * 5)

    def on_player_leds_preset_p1(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False, False, True, False, False])

    def on_player_leds_preset_p2(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False, True, False, True, False])

    def on_player_leds_preset_none(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False] * 5)

    # --- helpers ---

    def _set_player_leds(self, pattern: list[bool]) -> None:
        for i, state in enumerate(pattern, start=1):
            checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
            if checkbox is not None:
                checkbox.set_active(state)
        self._toast_light(
            "Player LEDs: " + " ".join("x" if s else "-" for s in pattern)
        )

    def get_current_player_leds(self) -> tuple[bool, bool, bool, bool, bool]:
        states: list[bool] = []
        for i in range(1, 6):
            checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
            states.append(bool(checkbox.get_active()) if checkbox is not None else False)
        return (states[0], states[1], states[2], states[3], states[4])

    def _on_lightbar_preview_draw(
        self, widget: Gtk.DrawingArea, cairo_ctx: Any
    ) -> bool:
        alloc = widget.get_allocation()
        r, g, b = self._current_rgb
        # Pré-visualização respeita a luminosidade corrente para dar feedback
        # imediato do slider antes de aplicar no hardware.
        level = max(0.0, min(1.0, self._current_brightness))
        cairo_ctx.set_source_rgb(
            (r / 255) * level,
            (g / 255) * level,
            (b / 255) * level,
        )
        cairo_ctx.rectangle(0, 0, alloc.width, alloc.height)
        cairo_ctx.fill()
        return False

    def _toast_light(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("light")
        bar.push(ctx_id, msg)
