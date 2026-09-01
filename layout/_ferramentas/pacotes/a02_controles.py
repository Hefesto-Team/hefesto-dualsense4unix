#!/usr/bin/env python3
"""O pacote da aba `02` Controles — a mais servida das dez, e o MOLDE.

Ela já pintava antes deste despachante: o `controles_vivos.py` monta o pacote
dela desde 30/08, e é de lá que este arquivo tira o que sabe. O que muda é o
ENDEREÇO do conhecimento — ele sai do piloto e vira uma função com contrato, do
mesmo formato das outras nove.

TUDO O QUE ESTA ABA MOSTRA TEM DONO, e é por isso que ela foi a primeira a
viver: `inputs` (os dois analógicos, os gatilhos, os botões), `audio` (o
microfone e o alto-falante, com posse e mudo), `lightbar_rgb`, `player`,
`battery_pct`, `transport` e `vpad_backend`. Zero `sem_dono`.
"""
from __future__ import annotations

from . import Contexto, registrar


@registrar("02-controles.html")
def pacote(ctx: Contexto) -> dict:
    cards = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        e = c.get("inputs") or {}
        a = c.get("audio") or {}
        sp = c.get("speaker") or {}
        rgb = c.get("lightbar_rgb") or []
        cards[uniq] = {
            "bateria": c.get("battery_pct"),
            "via": (c.get("transport") or "").upper(),
            "mascara": c.get("vpad_backend") or "—",
            "player": c.get("player"),
            "hex": "#{:02X}{:02X}{:02X}".format(*rgb[:3]) if len(rgb) >= 3 else "—",
            "sticks": [e.get("lx"), e.get("ly"), e.get("rx"), e.get("ry")],
            "l2": e.get("l2_raw"), "r2": e.get("r2_raw"),
            "botoes": list(e.get("buttons") or []),
            # O MUDO TEM TRÊS CARAS, e o piloto já as distingue: mudo pelo
            # aparelho, mudo pedido pelo Hefesto, e sem posse (o kernel manda).
            "mic_mudo": bool(a.get("mic_mudo")),
            "mic_posse": a.get("mic_mudo_desejado") is not None,
            "alto_vol": sp.get("volume"),
            "alto_mudo": bool(sp.get("muted")),
        }
    return {"cards": cards, "sem_dono": {},
            "cobertura": {"pintados": len(cards) * 12, "sem_dono": 0}}
