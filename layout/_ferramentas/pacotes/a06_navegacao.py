#!/usr/bin/env python3
"""O pacote da aba `06` Navegação.

O QUE TEM DONO: quem é o PRIMÁRIO (`is_primary`) — e é ele quem navega o PC.
O daemon marca um controle como primário, e a tela já dizia isso à mão: o
`NAVEGA` do gerador tirava o MENOR número da mesa, que acerta por coincidência
enquanto o P1 estiver na frente. Agora sai do daemon.

O QUE NÃO TEM: os cinco gestos (PS+Options, PS+↑…) e as velocidades de cursor e
rolagem. Eles moram no PERFIL, não no `state_full` — e o perfil só chega à tela
por outro caminho de IPC, que esta aba ainda não tem.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Aqui estava escrito que a velocidade do cursor e da
#: rolagem "mora no perfil, não no state_full". **O daemon publica as duas**, em
#: `mouse_emulation`, junto com se a emulação está ligada e por que está
#: bloqueada — medido no daemon dela: `{"enabled": false, "speed": 6,
#: "scroll_speed": 1, "bloqueio": "desligada"}`.
#:
#: Os gestos vêm do perfil (`key_bindings`), que também tem dono. Sobra nada.
SEM_DONO: dict[str, str] = {}


@registrar("06-navegacao.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    rato = st.get("mouse_emulation") or {}
    tecla = st.get("keyboard_emulation") or {}
    p = perfil.ativo(st.get("active_profile"))
    atalhos = (p.get("key_bindings") or {}) if p else {}

    cards = {}
    for c in ctx.conectados:
        primario = bool(c.get("is_primary"))
        cards[str(c.get("uniq") or "")] = {
            "navega": "Navega o PC" if primario else "Só a janela",
            "via": (c.get("transport") or "").upper(),
        }
    return {
        "colunas": cards,
        "mesa": {
            # AS DUAS VELOCIDADES, do daemon — não do perfil. O perfil guarda o
            # que ela SALVOU; o daemon diz o que está VALENDO agora, e é o
            # segundo que a tela mostra.
            "vel-cursor": rato.get("speed"),
            "vel-rolagem": rato.get("scroll_speed"),
            "rato-ligado": bool(rato.get("enabled")),
            "rato-bloqueio": rato.get("bloqueio") or "",
            "rato-despachando": bool(rato.get("despachando")),
            "teclado-ligado": bool(tecla.get("enabled")),
            "teclado-osk": bool(tecla.get("osk_disponivel")),
            "gestos": len(atalhos),
            "gestos-lista": {k: v for k, v in list(atalhos.items())[:12]},
        },
        "sem_dono": {},
        "cobertura": {"pintados": len(cards) * 2 + 9, "sem_dono": len(SEM_DONO)},
    }
