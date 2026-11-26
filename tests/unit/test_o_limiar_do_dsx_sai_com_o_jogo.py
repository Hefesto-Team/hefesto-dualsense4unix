"""D-2511-O-LIMIAR-DO-DSX-VALE-SO-ENQUANTO-O-JOGO-ESTA-EM-CENA: o limiar do gatilho sai com o jogo.

Medido antes de curar (25/11/2026), com a mesa de quatro controles do produto (dois no cabo, dois no
rádio) e o `cortar_pelo_limiar` real: com o `TriggerThreshold` em 255 num controle, o fim da sessão
do pad e o jogo que fecha deixavam o limiar no store, e o L2 em 254 e o R2 em 200 chegavam (0, 0) ao
pad; só o `ResetToUserSettings` do mod o limpava, e o mod que morre sem o reset deixava o gatilho
valendo só no fundo até reiniciar o serviço.

A cura: o `_esquecer_os_eventos_do_jogo`, que o fim da sessão e o jogo que fecha já chamam, zera
também o limiar daquele controle (ou o de todos, sem controle). Com o jogo em cena nada muda.

MORDIDA: arrancar a chamada `_esquecer_o_limiar_do_dsx` do `_esquecer_os_eventos_do_jogo` reprova os
três casos de limpeza, nomeando o controle que seguiu cortando.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from tests.unit.test_a_forca_da_vibracao_de_cada_controle_sai_de_um_funil_so import (
    UNIQS,
    _Mesa,
)

LIMIARES = (255, 250, 230, 210)
L2, R2 = 254, 200
JOGO = 9900570


@pytest.fixture
def mesa(tmp_path: Path) -> _Mesa:
    m = _Mesa(tmp_path)
    m.daemon.bus = EventBus()
    m.daemon.appid_em_cena = None
    m.daemon.identity_registry = SimpleNamespace(numero_da_lampada=lambda uniq, assign=True: 1)
    for uniq, limiar in zip(UNIQS, LIMIARES, strict=True):
        m.store.set_udp_trigger_threshold(uniq, "left", limiar)
        m.store.set_udp_trigger_threshold(uniq, "right", limiar)
    return m


def _chega(mesa: _Mesa, uniq: str) -> tuple[int, int]:
    return gp.cortar_pelo_limiar(mesa.store, uniq, L2, R2)


def _cortados(mesa: _Mesa) -> list[str]:
    return [u for u in UNIQS if _chega(mesa, u) != (L2, R2)]


def test_a_premissa_o_limiar_corta_o_que_fica_abaixo(mesa: _Mesa) -> None:
    assert _chega(mesa, UNIQS[0]) == (0, 0)
    assert _chega(mesa, UNIQS[1]) == (L2, 0)
    assert _cortados(mesa) == list(UNIQS)


@pytest.mark.parametrize("i", range(4))
def test_o_fim_da_sessao_de_um_controle_solta_so_o_limiar_dele(mesa: _Mesa, i: int) -> None:
    gp.end_game_output_session(mesa.daemon, target_uniq=UNIQS[i])

    assert _chega(mesa, UNIQS[i]) == (L2, R2), (
        f"o controle {i + 1} acabou a sessão e o limiar do DSX seguiu cortando o gatilho dele")
    outros = [u for j, u in enumerate(UNIQS) if j != i]
    for u in outros:
        limiar = mesa.store.udp_trigger_threshold_de(u)
        assert limiar == (LIMIARES[UNIQS.index(u)],) * 2, (
            f"o fim da sessão de {UNIQS[i]} mexeu no limiar de {u}: {limiar}")


def test_o_jogo_que_fecha_solta_o_limiar_de_todos(mesa: _Mesa) -> None:
    """D-2511-O-LIMIAR-DO-DSX-VALE-SO-ENQUANTO-O-JOGO-ESTA-EM-CENA: o jogo que fecha solta todos."""
    mesa.daemon.appid_em_cena = JOGO
    gp._bater_os_eventos_do_jogo(mesa.daemon)
    assert _cortados(mesa) == list(UNIQS), "premissa: com o jogo em cena o limiar corta"

    mesa.daemon.appid_em_cena = None
    gp._bater_os_eventos_do_jogo(mesa.daemon)

    assert _cortados(mesa) == [], (
        f"o jogo fechou e o limiar do DSX seguiu cortando o gatilho de {_cortados(mesa)}")


def test_com_o_jogo_em_cena_o_limiar_fica(mesa: _Mesa) -> None:
    mesa.daemon.appid_em_cena = JOGO
    for _ in range(3):
        gp._bater_os_eventos_do_jogo(mesa.daemon)

    assert mesa.store.udp_trigger_thresholds_por_controle != {}
    assert _chega(mesa, UNIQS[0]) == (0, 0), "o limiar saiu com o jogo ainda em cena"


def test_a_troca_de_jogo_solta_o_limiar_do_anterior(mesa: _Mesa) -> None:
    mesa.daemon.appid_em_cena = JOGO
    gp._bater_os_eventos_do_jogo(mesa.daemon)
    mesa.daemon.appid_em_cena = JOGO + 1
    gp._bater_os_eventos_do_jogo(mesa.daemon)

    assert _cortados(mesa) == []


def test_sem_store_ou_com_store_sem_a_api_nada_levanta() -> None:
    gp._esquecer_o_limiar_do_dsx(None, None)
    gp._esquecer_o_limiar_do_dsx(None, UNIQS[0])
    gp._esquecer_o_limiar_do_dsx(SimpleNamespace(), UNIQS[0])
    quebrado: Any = SimpleNamespace(
        set_udp_trigger_threshold=lambda *a: (_ for _ in ()).throw(ValueError("sem mac")))
    gp._esquecer_o_limiar_do_dsx(quebrado, "x")
