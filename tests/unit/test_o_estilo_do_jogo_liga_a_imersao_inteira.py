#!/usr/bin/env python3
"""O-ESTILO-DO-JOGO-LIGA-A-IMERSAO-INTEIRA-EM-TODO-MODO-01 — a receita invisível.

A escolha de 08/10/2026 (`ESCOLHAS.md`): nenhum cartão novo; o «Estilo de Jogo» é
o veículo, o «Arco» vira estilo próprio, e cada estilo leva uma receita que a
tela não mostra (`profiles/estilos_de_jogo.Receita`). O gesto aplica o que tem
motor (o ritmo e a frequência do gatilho, e o modo do Point-and-click) e guarda o
resto como dado. Vale em todo modo, de P1 a P4, no cabo e no rádio.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import trigger_specs
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileModeConfig,
    ProfileMovimentoConfig,
)

#: P1 a P4, dois no cabo e dois no rádio (faixa forjada `aa:bb:cc`)
QUATRO = [
    {"pref": f"p{n}", "uniq": f"aabbcc00000{n}", "jogador": n, "cor": cor,
     "nome": cor, "via": via.upper(), "transporte": via, "alvo": n == 1}
    for n, cor, via in ((1, "cosmic-red", "usb"), (2, "white", "bt"),
                        (3, "galactic-purple", "usb"), (4, "midnight-black", "bt"))
]


class _Ponte:
    def profile_switch(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um perfil na "pasta" de mentira; o que o gesto grava fica aqui."""
    guardado: dict[str, Any] = {
        "perfil": Profile(name="Pragmata", match=MatchAny(), priority=40),
        "salvos": [],
    }

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof
        guardado["salvos"].append(prof)

    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [guardado["perfil"]])
    monkeypatch.setattr(loader, "load_profile", lambda nome, *a, **k: guardado["perfil"])
    monkeypatch.setattr(loader, "save_profile", _save)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Pragmata", raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)
    return guardado


def _aplicar(rotulo: str, mesa: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    tem = QUATRO if mesa is None else mesa
    ctx = Contexto(state={"active_profile": None}, mesa=list(tem),
                   conectados=list(tem), estados={})
    return a10_perfis.editor_estilo(ctx, {"valor": rotulo}, _Ponte())


def test_todo_estilo_de_fabrica_tem_receita_e_o_personalizado_nao() -> None:
    sem = [e.rotulo for e in ej.DE_FABRICA if e.receita_invisivel is None]
    assert not sem, f"estilos de fábrica sem receita: {sem}"
    assert ej.POR_CHAVE["personalizado"].receita_invisivel is None


def test_toda_variavel_da_receita_tem_destino() -> None:
    """Cada campo é APLICADO por um motor ou declarado como dado, nunca os dois."""
    campos = {f.name for f in dataclasses.fields(ej.Receita)}
    assert set(ej.APLICADAS) | set(ej.SO_DADO) == campos
    assert not set(ej.APLICADAS) & set(ej.SO_DADO)


def test_o_arco_e_estilo_proprio() -> None:
    arco = ej.POR_CHAVE["arco"]
    assert arco.rotulo == "Arco" and arco.gatilho == "Bow"
    assert ej.as_quatro("arco") != ej.as_quatro("acao")  # noqa-acento: chave


def test_os_ajustes_estao_na_faixa_do_dono() -> None:
    """Todo `ajustes_do_gatilho` nomeia um parâmetro do modo, dentro da faixa."""
    fora = []
    for e in ej.DE_FABRICA:
        spec = trigger_specs.get_spec(e.gatilho or "")
        faixas = {p.name: (p.min_value, p.max_value) for p in (spec.params if spec else ())}
        for nome, valor in (e.receita_invisivel.ajustes_do_gatilho if e.receita_invisivel else ()):
            lo, hi = faixas.get(nome, (1, 0))
            if not lo <= valor <= hi:
                fora.append(f"{e.rotulo}: {nome}={valor}")
    assert not fora, fora


def test_os_ajustes_da_receita_chegam_ao_gatilho(
    disco: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um Arco com tensão 3 grava tensão 3 nos dois gatilhos.

    A MORDIDA: passe `{}` ao `preset_to_positional_params` no `_com_o_estilo` e os
    dois gatilhos voltam ao padrão do dono (6).
    """
    arco = ej.POR_CHAVE["arco"]
    tenso = dataclasses.replace(arco, receita_invisivel=dataclasses.replace(
        arco.receita_invisivel, ajustes_do_gatilho=(("force", 3), ("snap", 2))))
    monkeypatch.setitem(ej.POR_ROTULO, "Arco", tenso)
    monkeypatch.setitem(ej.POR_CHAVE, "arco", tenso)
    _aplicar("Arco")
    spec = trigger_specs.get_spec("Bow")
    assert spec is not None
    esperado = trigger_specs.preset_to_positional_params(spec, {"force": 3, "snap": 2})
    prof = disco["perfil"]
    assert prof.triggers.left.mode == prof.triggers.right.mode == "Bow"
    assert list(prof.triggers.left.params) == list(prof.triggers.right.params) == esperado


@pytest.mark.parametrize("modo", [None, "gamepad", "native"])
def test_o_point_and_click_liga_a_navegacao(disco: dict[str, Any], modo: str | None) -> None:
    """De qualquer modo de partida, o Point-and-click grava a Navegação.

    A MORDIDA: tire o ramo `if receita and receita.modo` e o perfil fica no modo
    que tinha.
    """
    if modo:
        disco["perfil"] = disco["perfil"].model_copy(
            update={"mode": ProfileModeConfig(kind=modo)})
    _aplicar("Point-and-click")
    assert disco["perfil"].mode is not None
    assert disco["perfil"].mode.kind == "desktop"


def test_outro_estilo_tira_a_navegacao_que_o_point_and_click_deixou(
    disco: dict[str, Any],
) -> None:
    """A MORDIDA: tire o `elif ... == "desktop"` e o FPS fica na Navegação."""
    _aplicar("Point-and-click")
    _aplicar("FPS")
    assert disco["perfil"].mode is None


@pytest.mark.parametrize("modo", ["gamepad", "native"])
def test_estilo_sem_modo_nao_mexe_no_modo_do_jogo(disco: dict[str, Any], modo: str) -> None:
    """Vale em todo modo: o FPS não escolhe máscara nem caminho."""
    era = ProfileModeConfig(kind=modo)
    disco["perfil"] = disco["perfil"].model_copy(update={"mode": era})
    _aplicar("FPS")
    assert disco["perfil"].mode == era


@pytest.mark.parametrize("chave", ["maratona", "retro", "point_and_click"])
def test_os_tres_tambem_tem_toque_por_tiro_e_lado_do_som(chave: str) -> None:
    """A resposta de produto: «Toque por tiro e lado do som, como nos outros».

    A MORDIDA: `toque_por_tiro=False` na Maratona e isto reprova.
    """
    receita = ej.POR_CHAVE[chave].receita_invisivel
    assert receita is not None
    assert receita.toque_por_tiro and receita.lado_do_som


def test_a_luz_nunca_passa_do_teto_de_clarao() -> None:
    altas = [e.rotulo for e in ej.DE_FABRICA
             if e.receita_invisivel and e.receita_invisivel.luz_por_segundo > ej.TETO_DO_PISCAR]
    assert not altas, altas


def test_o_fps_nao_mexe_no_movimento(disco: dict[str, Any]) -> None:
    """Sem mira por giro no FPS: o que o perfil tinha no movimento fica."""
    mov = ProfileMovimentoConfig(destino="mouse", sensibilidade=9)
    disco["perfil"] = disco["perfil"].model_copy(update={"movimento": mov})
    _aplicar("FPS")
    assert disco["perfil"].movimento == mov


@pytest.mark.parametrize("rotulo", [e.rotulo for e in ej.DE_FABRICA])
def test_p1_a_p4_no_cabo_e_no_radio_tem_cores_distintas(
    disco: dict[str, Any], rotulo: str,
) -> None:
    disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
    _aplicar(rotulo)
    controles = disco["perfil"].controllers or {}
    assert set(controles) == {c["uniq"] for c in QUATRO}
    cores = [tuple(o.leds.lightbar) for o in controles.values()]
    assert len(set(cores)) == 4, f"{rotulo}: {cores}"
