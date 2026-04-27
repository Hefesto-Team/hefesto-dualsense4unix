"""Helpers compartilhados por todos os mixins da GUI."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class WidgetAccessMixin:
    """Acesso comum ao `Gtk.Builder` via `self.builder`.

    Todos os mixins de ação herdam daqui para usar `_get` e `_set_label`.
    """

    builder: Gtk.Builder

    def _get(self, widget_id: str) -> Any:
        return self.builder.get_object(widget_id)

    def _set_label(self, widget_id: str, text: str) -> None:
        widget = self._get(widget_id)
        if widget is not None:
            widget.set_text(text)


__all__ = ["WidgetAccessMixin"]
