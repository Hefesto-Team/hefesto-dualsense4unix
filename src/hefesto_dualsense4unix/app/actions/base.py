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

    def _status_toast(self, context: str, msg: str) -> None:
        """Mostra ``msg`` na statusbar, mantendo no máximo 1 mensagem por contexto.

        Faz ``pop`` antes do ``push``: sem isso cada aba/área empilhava mensagens
        indefinidamente — o feedback ficava stale (a barra mostrava a primeira da
        pilha) e a pilha crescia sem limite. Com o pop, cada ``context`` guarda
        apenas a sua última mensagem. Ponto único reusado por todos os helpers
        ``_toast_*`` da GUI.
        """
        bar = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id(context)
        bar.pop(ctx_id)
        bar.push(ctx_id, msg)


__all__ = ["WidgetAccessMixin"]
