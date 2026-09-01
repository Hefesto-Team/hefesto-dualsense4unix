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
    """Os valores da aba Controles, com os nomes que a página tem.

    O DESENCONTRO ERA DE PONTUAÇÃO E DE SENTIDO. O pacote emitia `mic_mudo` com
    underscore e a página tem `mic-selo` com hífen; emitia `mascara` valendo
    `uhid` — o BACKEND — e a página mostra "DualSense", que é o nome da máscara.
    Dez chaves emitidas, uma casando. Medido em 01/09/2026.
    """
    import mesa_viva

    cards = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        e = c.get("inputs") or {}
        a = c.get("audio") or {}
        sp = c.get("speaker") or {}
        rgb = c.get("lightbar_rgb") or []
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})

        # O MUDO TEM TRÊS CARAS, e o selo da tela diz qual: mudo pelo aparelho,
        # mudo pedido pelo Hefesto, e sem posse (o kernel manda).
        mudo = bool(a.get("mic_mudo"))
        posse = a.get("mic_mudo_desejado") is not None
        cards[uniq] = {
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "via": (c.get("transport") or "").upper(),
            # A MÁSCARA É O NOME QUE O JOGO VÊ, e a tradução já tem dono em
            # `mesa_viva.NOME_DA_MASCARA`. `uhid` é o backend, e é outra coisa.
            "mascara": casa.get("mascara")
                       or mesa_viva.NOME_DA_MASCARA.get(c.get("vpad_backend") or "", "—"),
            "luz-hex": "#{:02X}{:02X}{:02X}".format(*rgb[:3]) if len(rgb) >= 3 else "—",
            "mic-selo": "MUDO" if mudo else "ATIVO",
            "mic-modo": "" if posse else "sem posse",
            "alto-estado": "Mudo" if sp.get("muted") else f"{sp.get('volume', 0)}%",
            "touch-estado": "Sem toque",
            "l2": e.get("l2_raw"), "r2": e.get("r2_raw"),
        }
    return {"cards": cards, "sem_dono": {},
            "cobertura": {"pintados": sum(len(v) for v in cards.values()), "sem_dono": 0}}
