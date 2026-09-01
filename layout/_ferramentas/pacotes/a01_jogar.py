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
    """Os valores da aba Jogar, com os NOMES que a página tem.

    CADA CHAVE AQUI É UM `data-campo` DO `01-jogar.html`, e isso não é
    coincidência: até 01/09/2026 os dois lados foram escolhidos separadamente, e
    esta aba pintava UM valor de cinco. O pacote emitia `mascara` e a página
    tinha `identidade`; emitia `conta_b` e a página tinha `conta-b`. Nenhuma
    máquina sabia que eram a mesma coisa, e o `querySelector` de um endereço que
    não existe não levanta — devolve `null`, e a pintura escreve zero.

    `layout/_ferramentas/casamento.py` é a régua que passou a medir isso.
    """
    st = ctx.state
    cartoes = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A IDENTIDADE É `nome · via`, como o desenho a escreve ("Cosmic Red
        # · USB") — e não a máscara. Sai da MESA, que é quem já leu a cor do
        # plástico; o `conectados` cru não tem o nome do modelo.
        casa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        nome = casa.get("nome") or "—"
        via = casa.get("via") or (c.get("transport") or "").upper()
        cartoes[uniq] = {
            "jogador": f"Player {c.get('player') or '—'}",
            "bateria": f"{c.get('battery_pct')}%" if c.get("battery_pct") is not None else "—",
            "identidade": f"{nome} · {via}",
        }

    # O AVISO SAI DO MESMO EXAME DA ABA CONEXÕES, e não de uma segunda leitura:
    # `integrations/exame_da_mesa` é o dono, e duas contagens do mesmo fato
    # divergiriam no primeiro achado novo.
    achados = _do_exame()
    grave = next((a for a in achados if a["grave"]), None) or (achados[0] if achados else None)

    fora = {
        "atencao-conta": f"{len(achados)} aviso" + ("s" if len(achados) != 1 else ""),
        "cartoes": cartoes,
        "cobertura": {"pintados": 1 + len(cartoes) * 3 + (2 if grave else 0), "sem_dono": 0},
    }
    if grave:
        fora["aviso-selo"] = grave["selo"]
        fora["aviso-texto"] = grave["titulo"]
    # `perfil`, `conta` e `conta-b` NÃO saem daqui: são do cabeçalho, que é das
    # dez abas, e o dono deles é `pacotes.topo()`. Emiti-los aqui criava um
    # segundo dono — e foi assim que `conta_b` (com underscore) conviveu com o
    # `conta-b` da página sem nunca casar.
    return fora


def _do_exame() -> list[dict]:
    """Os achados do exame da mesa, ou lista vazia. Nunca levanta."""
    try:
        from . import a08_conexoes

        return [{"selo": "RÁDIO" if i["grave"] else "AVISO", **i}
                for i in a08_conexoes._exame()]
    except Exception:
        return []
