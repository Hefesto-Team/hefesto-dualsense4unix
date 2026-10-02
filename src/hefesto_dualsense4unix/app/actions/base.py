"""Helpers compartilhados por todos os mixins da GUI."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


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

    ``player`` (o número do JOGADOR, que vem do daemon) responde uma pergunta
    diferente — "este controle está jogando agora, e como quem?" —, e por isso
    é ``None`` fora do co-op. Mas desde a MESA-CHEIA-12 (15/08/2026) ele já não
    é outro NÚMERO: `CoopManager.numeros_de_jogador()` o tira da mesma fila de
    chegada que dá o ``player_slot``, e é a mesma fila que escolhe o desenho
    aceso na barra do controle. Quando os dois existem, eles são iguais — antes
    disso divergiam, e o card dizia "jogador 2" no controle que acendia 4.
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    indice = entry.get("index")
    if isinstance(indice, int) and not isinstance(indice, bool):
        return indice + 1
    return 1


class WidgetAccessMixin:
    """Acesso comum ao `Gtk.Builder` via `self.builder`."""

    builder: Gtk.Builder

    _escolha_pendente: dict[str, str] | None = None

    _maquina_pendente: dict[str, Any] | None = None


    _RESP_DEPOIS = 210
    _RESP_FECHAR_E_ABRIR = 211


    def _toast_do_relancar(self, texto: str) -> None:
        """Onde o resultado do diálogo aparece. A aba dona pode especializar."""
        for nome in ("_toast_profile", "_status_toast_home", "_status_toast"):
            metodo = getattr(self, nome, None)
            if callable(metodo):
                with contextlib.suppress(Exception):
                    if nome == "_status_toast":
                        metodo("home", texto)
                    else:
                        metodo(texto)
                    return
        logger.info("relancar_toast_sem_destino", texto=texto)

    def _get(self, widget_id: str) -> Any:
        return self.builder.get_object(widget_id)


    def _status_toast(self, context: str, msg: str) -> None:
        """Mostra ``msg`` na statusbar, mantendo no máximo 1 mensagem por contexto."""
        bar = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id(context)
        bar.pop(ctx_id)
        bar.push(ctx_id, msg)


__all__ = ["WidgetAccessMixin", "numero_do_controle"]
