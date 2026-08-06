"""Fonte ÚNICA do predicado "esta `wm_class` é uma janela de jogo da Steam".

UNIFICA-PREDICADO-01 (05/08/2026). A mesma pergunta era respondida por CINCO
implementações independentes — `daemon/launch_env.py`, `profiles/manager.py`,
`profiles/simple_match.py`, `profiles/schema.py` e
`app/actions/launch_wrapper_dialog.py` — e elas já discordavam entre si: três
eram sensíveis a caixa, uma não; duas limpavam espaço, três não. A divergência
entre predicados que deveriam ser o mesmo é o buraco que o R-01 e o R-21
fecharam à mão, um de cada vez.

**A caixa é INSENSÍVEL, e isso é medido, não gosto.** `schema._casa_sem_caixa`
já documenta que a ``wm_class`` chega do X/XWayland com a caixa que o toolkit
escolheu e **muda de grafia entre backends de detecção**. Um predicado
sensível aqui reabriria o veto R-21 para uma janela que se anunciasse
``Steam_App_2111190``: o matcher de perfil casaria (ele compara sem caixa) e o
veto do catch-all NÃO reconheceria a janela como jogo — o genérico de desktop
voltaria a entrar por cima da regra do jogo.

**Por que este módulo mora em `profiles/` e não em `daemon/`.** A fonte tinha de
descer, não subir. `profiles/simple_match.py` é `profiles/` puro e é usado pelo
editor da GUI e pela CLI; se ele importasse `daemon.launch_env`, hoje não
fecharia ciclo (o `launch_env` só toca `profiles/` dentro de função), mas
ficaria a UM commit de distância de fechar
``profiles.simple_match -> daemon.launch_env -> profiles.manager ->
daemon.state_store -> daemon.launch_env``. Com a fonte aqui, o grafo tem só
``daemon -> profiles`` e ``app -> profiles``, que é a disciplina que
`profiles/sanidade.py` já descreve. Por isso este módulo **não importa nada do
projeto** — só `re`. Manter assim é o que garante que ninguém possa fechar o
ciclo por baixo.

`daemon/launch_env.py` REEXPORTA `steam_appid_from_wm_class` para que os
callsites históricos (e `tests/unit/test_wrapper_used.py`) continuem valendo.
"""
from __future__ import annotations

import re

#: `wm_class` que a Steam dá a TODA janela de jogo lançado por ela, sob Proton
#: ou nativo. IGNORECASE por medida (ver docstring do módulo).
_STEAM_APP_WC_RE = re.compile(r"^steam_app_(\d+)$", re.IGNORECASE)


def steam_appid_from_wm_class(wm_class: str | None) -> int | None:
    """Appid do jogo a partir da wm_class (`steam_app_N`), ou None.

    Insensível a caixa e tolerante a espaço em volta — as duas coisas
    explícitas, porque dois dos cinco lugares unificados aqui já faziam
    `.strip()` e a fonte não fazia; decidir isso em silêncio seria mudar
    comportamento em silêncio. Devolve `int`: quem precisa de `str` (o diálogo
    do wrapper, o editor simples) converte no callsite.
    """
    if not isinstance(wm_class, str):
        return None
    m = _STEAM_APP_WC_RE.match(wm_class.strip())
    return int(m.group(1)) if m is not None else None


__all__ = ["steam_appid_from_wm_class"]
