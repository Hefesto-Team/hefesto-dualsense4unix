#!/usr/bin/env python3
"""O PS COM OUTRO BOTÃO NÃO VIRA PS SOZINHO (O-GESTO-DO-PS-REMOVIDO-NAO-VIRA-PS-SOZINHO-01).

Quem tira o PS + D-pad na aba Navegação para usar o PS com o D-pad no jogo ganhava a Steam na
cara a cada toque: o combo removido sai do detector, o PS solta sem `ps_combo_fired` e o
`_observe_ps_solo` o lia como PS sozinho. A cura é na origem, para todo combo, de fábrica ou novo,
removido ou não: o PS sozinho só sai quando nenhum outro botão foi apertado enquanto ele estava
segurado, como no PS5.

O que se mede, com o daemon de mentira e o `machine.declare` de verdade (o handler grava o
`maquina.json` do lar de mentira da suíte), nos quatro controles, dois no cabo e dois no rádio:

1. com o PS + D-pad removido, PS + D-pad e soltar o PS não abre a Steam, e o PS sozinho abre uma;
2. vale para o botão que nunca foi combo (PS + Cruz) e para o combo de fábrica que dispara;
3. o aperto é de cada controle: o PS + botão de um não tira o PS sozinho do outro;
4. um botão já segurado antes do PS não conta (o jogador com o gatilho apertado ainda abre a
   Steam com o toque do PS): só a borda DURANTE o PS segurado cala o toque;
5. o botão apertado e solto antes do PS não deixa marca para o toque seguinte.

MORDIDA: tirar a condição `ps_outro_botao` de `_observe_ps_solo` reprova 1, 2 e 3.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager
from tests.unit.test_o_gesto_novo_do_ps import (  # noqa: F401
    _daemon,
    _gesto,
    _Ponte,
    chamou,
    sem_steam,
)

#: Os quatro controles pela cor do plástico, na faixa sintética da casa.
CONTROLES = [
    ("aa:bb:cc:00:00:01", "usb"),  # Starlight Blue, cabo
    ("aa:bb:cc:00:00:02", "bt"),   # White, rádio
    ("aa:bb:cc:00:00:03", "usb"),  # Cosmic Red, cabo
    ("aa:bb:cc:00:00:04", "bt"),   # Galactic Purple, rádio
]


def _gerente(*, sem_ps_dpad: bool) -> HotkeyManager:
    d = _daemon()
    hotkey.start_hotkey_manager(d)
    if sem_ps_dpad:
        for linha in ("ps_cima", "ps_baixo"):
            _gesto("remover-gesto")({"linha": linha}, _Ponte(d))
        assert not {"next", "prev"} & set(d._hotkey_manager._combos_configurados()), (
            "o cenário não é o do defeito: o PS + D-pad ainda é combo do detector")
    return d._hotkey_manager


def _toque(mgr: HotkeyManager, quadros: list[list[str]], de: str, *, t0: float = 0.0) -> None:
    """Um quadro por tique de 100 ms, e o último solta tudo; os atos do combo rodam num laço."""
    async def _cena() -> None:
        t = t0
        for botoes in [*quadros, []]:
            mgr.observe(botoes, now=t, de=de)
            t += 0.1
        atual = asyncio.current_task()
        pendentes = [x for x in asyncio.all_tasks() if x is not atual]
        if pendentes:
            await asyncio.gather(*pendentes)

    asyncio.run(_cena())


def _steam_abriu(mgr: HotkeyManager, pedidos: list[str], antes: int) -> int:
    cb = mgr.on_ps_solo
    if hasattr(cb, "esperar"):
        cb.esperar(5.0)
    return len(pedidos) - antes


@pytest.mark.parametrize("mac,via", CONTROLES)
def test_o_ps_com_o_dpad_removido_nao_abre_a_steam(
        sem_steam: list[str], mac: str, via: str) -> None:  # noqa: F811
    # D-1710-O-PS-COM-OUTRO-BOTAO-NAO-E-PS-SOZINHO
    mgr = _gerente(sem_ps_dpad=True)
    _toque(mgr, [["ps"], ["ps", "dpad_up"], ["ps", "dpad_up"], ["ps"]], mac)
    _toque(mgr, [["ps"], ["ps", "dpad_down"], ["ps"]], mac, t0=1.0)
    assert _steam_abriu(mgr, sem_steam, 0) == 0, f"o PS + D-pad abriu a Steam ({via})"
    _toque(mgr, [["ps"]], mac, t0=2.0)
    assert _steam_abriu(mgr, sem_steam, 0) == 1, f"o PS sozinho deixou de abrir a Steam ({via})"


@pytest.mark.parametrize("mac,via", CONTROLES)
def test_vale_para_o_botao_que_nunca_foi_combo(
        sem_steam: list[str], mac: str, via: str) -> None:  # noqa: F811
    mgr = _gerente(sem_ps_dpad=False)
    _toque(mgr, [["ps"], ["ps", "cross"], ["ps"]], mac)
    assert _steam_abriu(mgr, sem_steam, 0) == 0, f"o PS + Cruz abriu a Steam ({via})"


@pytest.mark.parametrize("mac,via", CONTROLES)
def test_o_combo_de_fabrica_que_dispara_segue_sem_steam(
        sem_steam: list[str], chamou: list[Any], mac: str, via: str) -> None:  # noqa: F811
    mgr = _gerente(sem_ps_dpad=False)
    _toque(mgr, [["ps"]] + [["ps", "dpad_up"]] * 4 + [["ps"]], mac)
    assert _steam_abriu(mgr, sem_steam, 0) == 0, f"o combo de fábrica abriu a Steam ({via})"
    assert chamou, f"o combo de fábrica nem disparou ({via})"


def test_o_aperto_e_de_cada_controle(sem_steam: list[str]) -> None:  # noqa: F811
    mgr = _gerente(sem_ps_dpad=True)
    (a, _), (b, _), *_ = CONTROLES
    mgr.observe(["ps"], now=0.0, de=a)
    mgr.observe(["ps"], now=0.0, de=b)
    mgr.observe(["ps", "dpad_up"], now=0.05, de=a)
    mgr.observe(["ps"], now=0.1, de=a)
    mgr.observe([], now=0.15, de=a)
    assert _steam_abriu(mgr, sem_steam, 0) == 0, "o PS + D-pad de um calou o outro"
    mgr.observe([], now=0.2, de=b)
    assert _steam_abriu(mgr, sem_steam, 0) == 1, "o PS sozinho do outro controle sumiu"


def test_o_botao_segurado_antes_do_ps_nao_cala_o_toque(sem_steam: list[str]) -> None:  # noqa: F811
    mgr = _gerente(sem_ps_dpad=True)
    mac = CONTROLES[0][0]
    _toque(mgr, [["r2"], ["r2", "ps"], ["r2"]], mac)
    assert _steam_abriu(mgr, sem_steam, 0) == 1, "o gatilho já segurado calou o toque do PS"


def test_o_botao_de_antes_nao_deixa_marca(sem_steam: list[str]) -> None:  # noqa: F811
    mgr = _gerente(sem_ps_dpad=True)
    mac = CONTROLES[0][0]
    _toque(mgr, [["cross"], []], mac)
    _toque(mgr, [["ps"]], mac, t0=1.0)
    assert _steam_abriu(mgr, sem_steam, 0) == 1


def test_o_toque_seguinte_nao_herda_o_botao_do_anterior(sem_steam: list[str]) -> None:  # noqa: F811
    mgr = _gerente(sem_ps_dpad=True)
    mac = CONTROLES[0][0]
    _toque(mgr, [["ps"], ["ps", "dpad_up"], ["ps"]], mac)
    assert _steam_abriu(mgr, sem_steam, 0) == 0
    _toque(mgr, [["ps"]], mac, t0=1.0)
    assert _steam_abriu(mgr, sem_steam, 0) == 1, "a marca do toque anterior ficou"

