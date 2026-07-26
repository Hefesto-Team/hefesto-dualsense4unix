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

    SLOT-JOGADOR-01 — por que É ESTE que manda no título, e não o do jogador.
    Este é o número que o daemon ACENDE no aparelho: a barra de jogador do
    controle mostra o slot do registro de identidade, não o índice do co-op
    (`daemon.subsystems.coop.CoopManager._numero_exibido`, decisão R-24). O
    título tem de dizer a mesma coisa que a lâmpada que ela consegue ler na
    mão — qualquer outra escolha obrigaria a olhar a tela para descobrir o que
    o aparelho já está afirmando. É também o número da CLI, do applet, dos
    chips do cabeçalho e da cor automática da lightbar.
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    indice = entry.get("index")
    if isinstance(indice, int) and not isinstance(indice, bool):
        return indice + 1
    return 1


def _inteiro_estrito(valor: Any) -> int | None:
    """``int`` de verdade, ou ``None``. ``bool`` é recusado.

    ``True`` é ``int`` em Python: sem o guard, um payload malformado viraria
    um "jogador 1" fantasma no rótulo.
    """
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    return None


#: SLOT-JOGADOR-01 — como cada número de jogador se apresenta na tela. O
#: sufixo NOMEIA a autoridade porque o número do jogador e o "Controle N"
#: saem de espaços diferentes e, nesta casa, DIVERGEM: o co-op ancora o
#: jogador 1 no primário do backend (ordem de enumeração do hidapi) e o
#: "Controle N" sai da fila de preferência do registro de identidade
#: (NUM-01). Enquanto o rótulo era só "P1", os dois números apareciam lado a
#: lado como se respondessem à mesma pergunta — o que a CONTAGEM-01 proíbe.
#: Com "no jogo"/"no co-op" a pergunta de cada um fica escrita: "qual
#: aparelho é este" contra "que jogador ele alimenta".
SUFIXO_JOGADOR_JOGO = "P{n} no jogo"
SUFIXO_JOGADOR_COOP = "P{n} no co-op"


def sufixo_de_jogador(entry: dict[str, Any]) -> str | None:
    """Como o número de JOGADOR deste controle aparece, ou ``None``.

    Fonte ÚNICA da regra: a aba Início e a aba Status desenham o mesmo card em
    dois arquivos diferentes, e cada cópia da regra é uma chance de a janela
    voltar a dizer duas coisas sobre o mesmo controle — foi assim que a
    numeração divergiu da primeira vez (ver `numero_do_controle`).

    Ordem das fontes, e o porquê de ser esta:

    1. ``player_game`` — o número que o JOGO escreveu na barra de jogador
       deste controle (o daemon o decodifica dos cinco bits em
       `ipc_handlers._enrich_controllers_per_controller`). É o único cuja
       autoridade não é nossa, então quando existe ele vence: nenhuma opinião
       nossa sobre "que jogador é este" supera o jogo tendo dito o número.
    2. ``player`` — o nosso, do co-op (`coop.resolve_player_numbers`): o
       índice de alocação de vpad, ancorado no primário do backend. Continua
       valendo a pena mostrar, porque é o que a mantenedora precisa para saber
       qual controle move qual personagem antes de o jogo abrir — mas só com o
       "no co-op" colado, para não ser lido como o número do aparelho.
    3. ``None`` — nem o jogo numerou nem somos nós que numeramos. O card se
       identifica e cala, em vez de inventar um "P" que ninguém confirma.
    """
    numero = _inteiro_estrito(entry.get("player_game"))
    if numero is not None:
        return SUFIXO_JOGADOR_JOGO.format(n=numero)
    numero = _inteiro_estrito(entry.get("player"))
    if numero is not None:
        return SUFIXO_JOGADOR_COOP.format(n=numero)
    return None


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


__all__ = [
    "SUFIXO_JOGADOR_COOP",
    "SUFIXO_JOGADOR_JOGO",
    "WidgetAccessMixin",
    "numero_do_controle",
    "sufixo_de_jogador",
]
