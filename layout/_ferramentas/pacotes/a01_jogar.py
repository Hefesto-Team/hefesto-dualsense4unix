#!/usr/bin/env python3
"""O pacote da aba `01` Jogar — a que MAIS escreve, e a única com gesto ligado.

O QUE TEM DONO, medido no `state_full` de 01/09/2026:

    active_profile      o perfil em vigor                    ← tem dono
    controllers[]       a mesa: quantos, por qual transporte ← tem dono
    battery_pct         a carga de cada um                   ← tem dono
    player              o número de cada um                  ← tem dono
    vpad_backend        a máscara que o jogo vê              ← tem dono
    emulation_suppressed  o Hefesto está fora do meio?       ← tem dono

O MODO (o chip aceso da fileira) NÃO SAI DO STATE DIRETO: quem o lê é
`mode_transition.mode_of_state`, o ponto único de leitura do modo vivo, e ele
devolve TRÊS valores — nunca um quarto. O piloto já usa isso para acender o
interruptor, e é por isso que o botão da Jogar funciona hoje.
"""
from __future__ import annotations

from . import Contexto, registrar


@registrar("01-jogar.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    usb = sum(1 for c in ctx.conectados if (c.get("transport") or "").lower() == "usb")
    bt = len(ctx.conectados) - usb
    cartoes = {}
    for c in ctx.conectados:
        cartoes[str(c.get("uniq") or "")] = {
            "jogador": f"Player {c.get('player') or '—'}",
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "mascara": c.get("vpad_backend") or "—",
        }
    return {
        "perfil": str(st.get("active_profile") or "—"),
        # A CONTAGEM SAI DOS CONECTADOS, nunca da mesa: foi o defeito que
        # apareceu quatro vezes em 31/08, e a régua de cada aba o persegue.
        "conta": f"{len(ctx.conectados)} controles:",
        "conta_b": f"{usb} USB · {bt} BT",
        "cartoes": cartoes,
        "cobertura": {"pintados": 2 + len(cartoes) * 3, "sem_dono": 0},
    }
