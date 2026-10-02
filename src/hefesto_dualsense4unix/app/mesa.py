"""O dono único de "quem está na mesa" — na JANELA, para as onze abas.

ONDA0-Z5/T5. **O defeito de forma (F6/F3), medido em 23/08/2026**: a única
função canônica que já existia para "quantos controles" (`ContagemDeControles`
e `texto_de_contagem`, nascidas na CONTAGEM-E-COOP-01 de 29/07) morava
*dentro do mixin da aba Status* (`app/actions/status_actions.py`). Nove abas
precisam da resposta; só uma é dona do arquivo. É a mesma doença que a F3 já
tinha causado noutro fato — e essa já custou perda de dado dela em 23/08.

Este módulo não importa GTK nem IPC — é estado puro, migrado sem mudar
comportamento (mesmo corpo, mesmos testes). O molde é
`app/alvo_de_edicao.py` (23/08): módulo novo, dono único, os leitores antigos
continuam funcionando por espelho enquanto migram — aqui o espelho é literal,
``status_actions.py`` reexporta os três nomes deste módulo.

**O que este módulo NÃO faz** (fora do escopo de T5, ver ONDA0-Z5 §6):
não decide o que a tela FAZ com a contagem — isso é `_render_online`/
`_render_slow_state` (T6) e cada aba que migrar (Ondas 1-11). Ele só responde
"quantos, e quem é o primário", a partir do `state` que `daemon.state_full`
publica.
"""
from __future__ import annotations

from typing import Any


def controles_conectados(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Controles conectados (FEAT-DSX-MULTI-CONTROLLER-01).

    Vem de `state["controllers"]` (bloco do `daemon.state_full`); o primário
    é o primeiro da lista (ordem de inserção). Lista vazia se o daemon não
    expõe o bloco (versão antiga) — os renderers caem no caminho single.
    """
    controllers = state.get("controllers")
    if not isinstance(controllers, list):
        return []
    return [c for c in controllers if isinstance(c, dict) and c.get("connected")]


__all__ = [
    "controles_conectados",
]
