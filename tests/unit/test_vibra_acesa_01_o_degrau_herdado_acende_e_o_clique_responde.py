#!/usr/bin/env python3
"""A ABA VIBRAÇÃO NO PERFIL DO USUÁRIO: o degrau herdado acende, e o clique responde.

**QUEIXA, 17/09/2026, com a foto da aba aberta:** *"o botão não tá ativo"*.
Nenhum dos três — Economia, Balanceado, Máximo — aceso, e a coluna ao lado
marcando **150%**. A tela negando a força que a mão do usuário sentia.

O PERFIL EM QUE ISSO ACONTECE é o que estas réguas montam, e ele é o dela:
DON'T SCREAM, `rumble.policy = "max"` no global, e o bloco `controllers[uniq]`
existindo **sem** a seção `rumble`. Medido no disco do usuário em 17/09: dos 29
perfis, **6** têm política global escrita e só **5** (9 entradas) têm override
por controle. *Na maioria das colunas da maioria dos perfis, a força é HERDADA*
— que é justamente o caso que a tela não sabia mostrar.

**POR QUE NÃO SE MEDE COM UM PERFIL QUE TEM OVERRIDE:** esse caso já funcionava,
e foi por medi-lo que a aba passou de 04/09 a 17/09 assim. Um override próprio
acende o degrau desde 03/09; o buraco inteiro estava na herança.

## SÃO DOIS DEFEITOS, E AS MORDIDAS SÃO SEPARADAS

**1. O degrau herdado não tinha onde acender.** `a05_vibracao` só emitia o
degrau quando aquele controle tinha política PRÓPRIA gravada no perfil; quando
herdava, emitia vazio — e o alvo `classe` do pintor apaga os três quando o valor
não casa com nenhum `data-hef-quando`.

Era **meia decisão**. A [05] dela, de 04/09, mandava a coluna sem ajuste próprio
não acender *"e passar a apontar para essa linha"* — a LINHA DE MESA, que diria
o degrau em vigor. A linha de mesa foi apagada **um dia depois**, em 05/09, por
outra decisão de produto (*"não é pra ter mesa em nada da interface"*). O contrapeso
saiu, o vazio ficou, e o estado herdado deixou de ter lugar na tela.

A cura devolve a procedência ao lugar que sobrou — o próprio botão: ele acende
(é a força que vale) e ganha a marca `degrau-herdado` na caixa dos três, que a
folha desenha com borda tracejada. **Herdado continua diferente de escolhido; o
que deixou de existir é "herdado = nada na tela".**

**2. O clique morto** (clicar o degrau que já valia não gravava, não acendia e não dizia
nada) saiu com os degraus em 20/10/2026 (O-GESTO-FORCA-DOS-DEGRAUS-DA-VIBRACAO-SAI-01): o
trilho só manda `custom`, e o arraste repetido não regrava nem fala
(:func:`test_o_arraste_da_barra_nao_ganhou_um_recibo_por_tique`).

## AS MORDIDAS, uma por defeito

* **defeito 1** — desde 20/10/2026 a «Força» é o trilho de 0 a 200%, sem degraus
  (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01), e a força herdada
  aparece no cursor: em ``a05_vibracao.pacote``, faça o ``mult-pos`` sair vazio quando a coluna
  herda e :func:`test_a_coluna_que_herda_poe_o_cursor_na_forca_em_vigor` reprova. A marca
  ``degrau-herdado`` e a régua dela saíram com os botões.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "05-vibracao.html"

UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"

GLOBAL = "max"


class PonteDeMentira:
    """Guarda o que foi pedido ao daemon. NUNCA fala com o dela."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return True

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        self.chamadas.append(f"profile_reaplicar:{nome}")
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True


def _o_perfil_dela(com_override: str | None = None) -> dict[str, Any]:
    """O perfil do usuário na forma CRUA que a pintura lê — global `max`, sem override."""
    dele: dict[str, Any] = {"leds": {"lightbar": [65, 9, 55]},
                            "speaker": {"volume": 102, "muted": False}}
    if com_override:
        dele["rumble"] = {"policy": com_override}
    return {"name": "Bancada",
            "rumble": {"policy": GLOBAL, "custom_mult": None},
            "controllers": {CHAVE: dele}}


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a05():
    from pacotes import a05_vibracao

    return a05_vibracao


@pytest.fixture
def disco_dela(monkeypatch, a05):
    """Desvia o perfil ATIVO para o dela, e o disco para a memória."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    vivo: dict[str, Any] = {"cru": _o_perfil_dela()}
    gravados: list[Any] = []

    def _ativo(_nome: str = "") -> dict[str, Any]:
        return vivo["cru"]

    def _nome_do_ativo(_state: Any = None) -> str:
        return "Bancada"

    def _load(_nome: str) -> Any:
        cru = dict(vivo["cru"])
        return Profile.model_validate({**cru, "match": {"type": "criteria"}})

    def _save(prof: Any, **_: Any) -> None:
        gravados.append(prof)

    monkeypatch.setattr(a05._perfil, "ativo", _ativo, raising=False)
    monkeypatch.setattr(a05._perfil, "nome_do_ativo", _nome_do_ativo,
                        raising=False)
    monkeypatch.setattr(loader, "load_profile", _load, raising=False)
    monkeypatch.setattr(loader, "save_profile", _save, raising=False)
    return vivo, gravados


def _ctx(pac):
    """Um tique com UM controle na mesa e a força geral do perfil do usuário."""
    return pac.Contexto(
        state={"active_profile": "Bancada", "rumble_policy": GLOBAL,
               "rumble_mult_applied": 1.5},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
               "via": "USB", "cor": "starlight-blue", "plastico": "#123456",
               "conectado": True}],
        conectados=[{"uniq": UNIQ, "player": 1, "connected": True, "index": 0,
                     "transport": "usb", "battery_pct": 90, "inputs": {}}],
        estados={})


def _coluna(pac) -> dict[str, Any]:
    """A coluna do P1 como o pacote a manda para a tela."""
    fora = pac.pacote_da_pagina(PAGINA, _ctx(pac))["colunas"]
    assert UNIQ in fora, f"a coluna do P1 sumiu do pacote: {sorted(fora)}"
    return fora[UNIQ]


NO_TRILHO_DO_GLOBAL = "150"
NO_TRILHO_DO_OVERRIDE = "30"


def test_a_coluna_que_herda_poe_o_cursor_na_forca_em_vigor(pac, disco_dela) -> None:
    """Sem override, o trilho da coluna mostra a força geral: nada de «0» nem de vazio."""
    col = _coluna(pac)
    assert col["mult-pos"] == col["mult"] == NO_TRILHO_DO_GLOBAL, (
        f"a coluna pôs o cursor em {col['mult-pos']!r} com a força geral em {GLOBAL!r} e "
        f"sem override — é a tela negando a força que a mão sente, a queixa de 17/09")
    assert "degrau" not in col and "degrau-herdado" not in col, (
        "a Força é o trilho de 0 a 200% desde 20/10/2026, e o degrau voltou à pintura")


def test_a_coluna_com_override_proprio_mostra_o_dela(pac, disco_dela) -> None:
    """O par da régua acima: com ajuste próprio, o override vence o global."""
    vivo, _ = disco_dela
    vivo["cru"] = _o_perfil_dela(com_override="economia")

    col = _coluna(pac)
    assert col["mult-pos"] == NO_TRILHO_DO_OVERRIDE, (
        f"a coluna com override próprio pôs o cursor em {col['mult-pos']!r} — a "
        f"precedência do produto é o override vencendo o global")


def test_sem_politica_nenhuma_o_trilho_nao_afirma_numero(pac, disco_dela) -> None:
    """Campo sem informação NÃO MOSTRA NADA — a regra, 02/09/2026."""
    ctx = _ctx(pac)
    ctx.state["rumble_policy"] = ""
    col = pac.pacote_da_pagina(PAGINA, ctx)["colunas"][UNIQ]
    assert col["mult-pos"] == "", f"pôs o cursor em {col['mult-pos']!r} sem política"


def test_o_arraste_da_barra_nao_ganhou_um_recibo_por_tique(
        pac, disco_dela) -> None:
    """O `custom` fica FORA do recado, e não é esquecimento."""
    fn = pac.gesto_da_pagina(PAGINA, "intensidade")
    assert fn is not None, "o gesto `intensidade` perdeu o dono"
    ctx = _ctx(pac)

    primeira = fn(ctx, {"uniq": UNIQ, "valor": "120"}, PonteDeMentira())
    segunda = fn(ctx, {"uniq": UNIQ, "valor": "120"}, PonteDeMentira())

    assert primeira is None, f"o arraste falou na primeira passagem: {primeira!r}"
    assert segunda is None, (
        f"o arraste falou na SEGUNDA passagem: {segunda!r} — o ouvinte manda o "
        f"mesmo valor duas vezes, e isto vira uma tarja por arraste")

