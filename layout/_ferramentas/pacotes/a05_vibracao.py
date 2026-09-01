#!/usr/bin/env python3
"""O pacote da aba `05` Vibração.

CORRIGIDO EM 01/09/2026. O que estava aqui:

    "motor-esq: o valor por motor — o daemon publica a política da mesa, não o
     motor"

Está errado, e o próprio daemon desmente: `rumble_ff.per_vpad[]` traz
`last_weak` e `last_strong` — **os dois motores, por gamepad virtual** — além de
`ff_maior_pedido: [weak, strong]`, `rumble_no_fisico` e a contagem de plays.
Medido no daemon dela, com o DualSense no cabo.

O DualSense tem DOIS motores e eles não são "esquerdo e direito" por acaso: o
`strong` é o motor pesado e o `weak` o leve — a nomenclatura vem do protocolo de
force-feedback do evdev, e é a que o produto usa de ponta a ponta. A tela fala
"esquerdo/direito" porque é onde eles ficam no plástico.

O QUE DE FATO NÃO TEM DONO: nada. O que a aba mostra é o pedido que o JOGO fez
(o que chegou ao gamepad virtual), e não a corrente que passou no motor — isso o
aparelho não devolve. É uma ressalva sobre o SIGNIFICADO do número, não sobre a
existência dele, e a tela a carrega no `title`.
"""
from __future__ import annotations

from . import Contexto, registrar

SEM_DONO: dict[str, str] = {}


def _do_vpad(ff: dict, player) -> dict:
    """O bloco `per_vpad` daquele jogador, ou `{}`.

    Casa por `player`, não por posição na lista: a ordem do `per_vpad` é a de
    criação dos gamepads virtuais, e ela não acompanha a ordem da mesa quando um
    controle cai e volta.
    """
    for v in (ff or {}).get("per_vpad") or []:
        if v.get("player") == player:
            return v
    return {}


@registrar("05-vibracao.html")
def pacote(ctx: Contexto) -> dict:
    st = ctx.state
    ff = st.get("rumble_ff") or {}

    colunas: dict[str, dict] = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        v = _do_vpad(ff, c.get("player"))
        maior = v.get("ff_maior_pedido") or [0, 0]
        col = {
            # `e`/`d` É A LÍNGUA DA TELA, e ela vence: o desenho dela chama os
            # lados de esquerdo e direito, e `aba05._barra` endereça
            # `data-campo="motor-e"`. O pacote nascera com `esq`/`dir` e os
            # dezesseis valores caíam no vazio — zero casamentos, medido em
            # 01/09/2026.
            #
            # `strong` é o motor PESADO e fica à esquerda; `weak` é o leve, à
            # direita. A inversão é o que este assunto convida, e o
            # `aba05.LADOS` já carrega a mesma nota.
            "motor-e": v.get("last_strong", 0),
            "motor-d": v.get("last_weak", 0),
            "motor-e-pct": round(max(0, min(100, (v.get("last_strong") or 0) / 255 * 100))),
            "motor-d-pct": round(max(0, min(100, (v.get("last_weak") or 0) / 255 * 100))),
            "maior-e": maior[1] if len(maior) > 1 else 0,
            "maior-d": maior[0] if maior else 0,
            "plays": v.get("ff_play_count", 0),
            "descartados": v.get("ff_descartado_count", 0),
            # O JOGO ESTÁ COM O CONTROLE ABERTO? Sem isto, um zero em todos os
            # motores parece defeito quando é só "nenhum jogo pediu nada".
            "jogo-aberto": bool(v.get("game_open")),
            "no-fisico": v.get("rumble_no_fisico"),
        }
        colunas[uniq] = col

    return {
        "mesa": {
            "forca": st.get("rumble_policy") or "—",
            # A BARRA DA FORÇA, em porcentagem da faixa que o desenho usa. O
            # `rumble_mult_applied` é um multiplicador (0,7 = 70%), e o teto do
            # desenho é 150% — é o que `aba05.TETO` declara.
            "forca-pct": None if st.get("rumble_mult_applied") is None
                         else round(min(100, float(st["rumble_mult_applied"]) / 1.5 * 100)),
            "mult": st.get("rumble_mult_applied"),
            "custom": st.get("rumble_policy_custom_mult"),
            "tremendo": bool(st.get("rumble_active")),
            "passthrough": bool(st.get("rumble_passthrough")),
            "paradas": ff.get("paradas", 0),
        },
        "colunas": colunas,
        "sem_dono": {},
        "cobertura": {"pintados": 6 + sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }
