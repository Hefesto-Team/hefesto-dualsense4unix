"""Helpers compartilhados por todos os mixins da GUI."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


def numero_do_controle(entry: dict[str, Any]) -> int:
    """Número com que UM controle se identifica na interface inteira.

    Fonte única da regra (COR-01/D6): é o ``player_slot`` de sessão — a
    identidade ESTÁVEL, que sobrevive a desconectar e reconectar e que a CLI e o
    applet também usam. Sem slot (controle sem MAC, registro ainda ausente) cai
    na posição 1-based da lista.

    Existia uma cópia dessa regra em cada tela, e a aba Início usava a POSIÇÃO no
    loop em vez do slot: com um controle só, ela dizia "Controle 1" enquanto o
    cabeçalho, olhando o mesmo controle, dizia "Sony 3". Duas verdades na mesma
    janela sobre qual é o "Controle 1".

    Não confundir com ``player``: aquele é o número do JOGADOR, vem do daemon, e
    só existe em co-op — fora dele o jogo vê um controle só.
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    indice = entry.get("index")
    if isinstance(indice, int) and not isinstance(indice, bool):
        return indice + 1
    return 1


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


__all__ = ["WidgetAccessMixin", "numero_do_controle"]
