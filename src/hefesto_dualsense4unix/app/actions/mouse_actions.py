"""Aba Mouse: liga/desliga emulação de mouse+teclado via DualSense (FEAT-MOUSE-01)."""
# ruff: noqa: E402
from __future__ import annotations

import os
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.ipc_bridge import mouse_emulation_set
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
)

UINPUT_DEV = "/dev/uinput"

MAPPING_LEGEND = (
    "<b>Mapeamento:</b>\n"
    "Cruz (X) ou L2 → botão esquerdo\n"
    "Triângulo (△) ou R2 → botão direito\n"
    "R3 (clique no analógico direito) → botão do meio\n"
    "Círculo (○) → Enter\n"
    "Quadrado (□) → Esc\n"
    "D-pad (↑↓←→) → setas do teclado\n"
    "Analógico esquerdo → movimento do cursor\n"
    "Analógico direito → rolagem vertical e horizontal"
)


class MouseActionsMixin(WidgetAccessMixin):
    """Controla a aba Mouse."""

    # Guard para evitar loop widget->draft->refresh->widget.
    _guard_refresh: bool = False

    def _refresh_mouse_from_draft(self) -> None:
        """Popula widgets da aba Mouse a partir de self.draft.mouse.

        Protegido por _guard_refresh para não disparar handlers de signal
        durante a atualização programatica dos widgets.
        """
        if self._guard_refresh:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._guard_refresh = True
        try:
            mouse = draft.mouse
            toggle: Gtk.Switch = self._get("mouse_emulation_toggle")
            if toggle is not None:
                toggle.set_active(mouse.enabled)
            speed_scale: Gtk.Scale = self._get("mouse_speed_scale")
            if speed_scale is not None:
                speed_scale.set_value(float(mouse.speed))
            scroll_scale: Gtk.Scale = self._get("mouse_scroll_speed_scale")
            if scroll_scale is not None:
                scroll_scale.set_value(float(mouse.scroll_speed))
        finally:
            self._guard_refresh = False

    def install_mouse_tab(self) -> None:
        # mouse_legend_label foi substituído por GtkFrame estático (UI-MOUSE-CLEANUP-01).
        # Mantém compatibilidade caso o widget ainda exista em alguma versão do GLADE.
        legend = self._get("mouse_legend_label")
        if legend is not None:
            legend.set_markup(MAPPING_LEGEND)
        self._refresh_mouse_view()

    # --- handlers de UI ---

    def on_mouse_toggle_set(self, switch: Gtk.Switch, _state: Any) -> bool:
        if self._guard_refresh:
            return False
        enabled = bool(switch.get_active())
        speed = self._read_speed("mouse_speed_scale", DEFAULT_MOUSE_SPEED)
        scroll = self._read_speed("mouse_scroll_speed_scale", DEFAULT_SCROLL_SPEED)
        ok = mouse_emulation_set(enabled, speed=speed, scroll_speed=scroll)
        if not ok:
            self._toast_mouse(
                "Falha ao comunicar com o daemon. Mouse não alterado."
            )
            switch.set_active(not enabled)
            return True
        # Atualiza draft
        draft = getattr(self, "draft", None)
        if draft is not None:

            new_mouse = draft.mouse.model_copy(
                update={"enabled": enabled, "speed": speed, "scroll_speed": scroll}
            )
            self.draft = draft.model_copy(update={"mouse": new_mouse})
        status = "ligado" if enabled else "desligado"
        self._toast_mouse(f"Mouse emulado {status}")
        self._refresh_mouse_view()
        return False  # default handler aplica o estado no switch

    def on_mouse_speed_changed(self, scale: Gtk.Scale) -> None:
        if self._guard_refresh:
            return
        speed = int(scale.get_value())
        # Atualiza draft independente de estar habilitado (preserva preferência)
        draft = getattr(self, "draft", None)
        if draft is not None:

            new_mouse = draft.mouse.model_copy(update={"speed": speed})
            self.draft = draft.model_copy(update={"mouse": new_mouse})
        if not self._mouse_is_enabled():
            return
        mouse_emulation_set(True, speed=speed)

    def on_mouse_scroll_speed_changed(self, scale: Gtk.Scale) -> None:
        if self._guard_refresh:
            return
        scroll = int(scale.get_value())
        # Atualiza draft independente de estar habilitado (preserva preferência)
        draft = getattr(self, "draft", None)
        if draft is not None:

            new_mouse = draft.mouse.model_copy(update={"scroll_speed": scroll})
            self.draft = draft.model_copy(update={"mouse": new_mouse})
        if not self._mouse_is_enabled():
            return
        mouse_emulation_set(True, scroll_speed=scroll)

    # --- helpers ---

    def _read_speed(self, widget_id: str, default: int) -> int:
        w = self._get(widget_id)
        if w is None:
            return default
        return int(w.get_value())

    def _mouse_is_enabled(self) -> bool:
        toggle = self._get("mouse_emulation_toggle")
        return bool(toggle and toggle.get_active())

    def _refresh_mouse_view(self) -> None:
        label = self._get("mouse_uinput_status_label")
        if label is None:
            return
        try:
            import uinput  # noqa: F401
            module_ok = True
        except ImportError:
            module_ok = False

        dev_exists = os.path.exists(UINPUT_DEV)
        dev_writable = os.access(UINPUT_DEV, os.W_OK) if dev_exists else False

        if module_ok and dev_writable:
            label.set_markup(
                '<span foreground="#2d8">uinput disponível</span>'
            )
        elif module_ok and dev_exists:
            label.set_markup(
                '<span foreground="#d33">sem permissão em /dev/uinput — '
                'rode ./scripts/install_udev.sh</span>'
            )
        elif module_ok:
            label.set_markup(
                '<span foreground="#c90">módulo ok, /dev/uinput ausente '
                '(modprobe uinput)</span>'
            )
        else:
            label.set_markup(
                '<span foreground="#d33">python-uinput não instalado '
                '(pip install python-uinput)</span>'
            )

    def _toast_mouse(self, msg: str) -> None:
        bar: Any = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id("mouse")
        bar.push(ctx_id, msg)


__all__ = ["MAPPING_LEGEND", "UINPUT_DEV", "MouseActionsMixin"]

# "Conhece-te a ti mesmo." — Sócrates
