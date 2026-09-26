#!/usr/bin/env python3
"""O editor da entrada grava — `mapa-das-portas.html`, o «Mapa das Conexões».

O-MAPA-DAS-CONEXOES-NO-PRODUTO-01, 26/09/2026. Até aqui um clique nesta página
chegava ao piloto como `[gesto sem dono] mapa-das-portas.html · clique · …`: a
página não tinha pacote, e o que ela declarava numa entrada sumia ao reler.

Os dois pedidos dela que isto atende:

* *«ao clicar em um desses usb mapeados eu pudesse setar que tem tal coisa lá.
  no caso o hub ou afins»* — «O que tem aqui»: Direto, Hub ou Extensor;
* a velocidade da entrada, porque o firmware da placa erra (a frente dela é
  USB 3.0 e a tabela ACPI a dava como 2.0) — «Velocidade»: USB 3.0 ou 2.0.

<!-- noqa-acento: citação literal dela -->

Os dois vão ao `maquina.json` DELA, em `mapa.portas[N]`, pelo gravador único do
Mapear (`integrations/entrada_a_entrada`), sem IPC: a declaração é dado de
quem usa, no disco dele. O produto lê de lá (`interface/arranjo_desta_maquina`
e `integrations/mapa_das_portas.velocidade_da_entrada`).

POR QUE `a12_` E ISTO NÃO É UMA ABA: é página avulsa, como a `a11` da
calibração. O prefixo é o que o `_carregar_tudo()` e as réguas varrem.

O QUE ELE NÃO FAZ: não pinta nada (a página recebe o arranjo inteiro pelo
`hefesto_vivo._entregar_o_arranjo`, e entrar em `PACOTES` faria o despachante
das dez contar onze), e não grava a entrada que o desenho monta a partir do
que ela declarou (as do hub, a ponta do extensor): essas não têm número no
disco, e o editor da página nem manda o gesto para elas.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee

from . import Contexto, gesto

PAGINA = "mapa-das-portas.html"

#: Os dois gestos do editor da entrada. Só sobe.
PISO_DA_ABA = 2

#: O «Direto» do editor: é a ausência de declaração no disco (`liga` nulo).
DIRETO = "direto"


def _a_entrada(o: dict[str, Any]) -> str:
    numero = str(o.get("entrada") or "").strip()
    if not numero:
        raise ValueError("o clique não disse qual entrada")
    return numero


def _gravou(recibo: Any) -> None:
    if not getattr(recibo, "gravou", False):
        raise RuntimeError(f"não gravei no mapa desta máquina ({recibo.motivo})")


@gesto(PAGINA, "entrada-o-que-tem", grava="declarar_a_ligacao")
def entrada_o_que_tem(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """«Direto», «Hub» ou «Extensor» na entrada — no `maquina.json` dela."""
    liga = str(o.get("liga") or "")
    if liga != DIRETO and liga not in ee.LIGACOES_DECLARAVEIS:
        raise ValueError(f"o clique não disse o que tem na entrada ({liga!r})")
    _gravou(ee.declarar_a_ligacao(_a_entrada(o), None if liga == DIRETO else liga))


@gesto(PAGINA, "entrada-velocidade", grava="declarar_a_velocidade")
def entrada_velocidade(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """USB 3.0 ou USB 2.0 na entrada — o que ela diz vence o firmware da placa."""
    try:
        usb = int(str(o.get("usb") or ""))
    except ValueError:
        raise ValueError("o clique não disse a velocidade") from None
    _gravou(ee.declarar_a_velocidade(_a_entrada(o), usb))


PONTE: set[str] = set()
METODOS: set[str] = set()
