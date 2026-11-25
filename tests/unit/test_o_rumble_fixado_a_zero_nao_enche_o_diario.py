"""O rumble fixado a zero não enche o diário.

Sprint O-RUMBLE-FIXADO-A-ZERO-NAO-ENCHE-O-DIARIO-01, decisão
D-2211-O-RUMBLE-FIXADO-A-ZERO-NAO-ENCHE-O-DIARIO.

Medido em 22/11/2026 (e de novo em 25/11): 536 linhas `rumble_fixado_solto_por_ociosidade
par=(0, 0)` em 4 h 30 min, uma a cada 3 a 5 s com um jogo aberto. Quem pede vibração zero pelo
`rumble.set` (o gesto de soltar de uma extensão, o `Parar`) deixa um par fixado `(0, 0)` com
carimbo, e o `reassert_rumble` o solta por ociosidade aos 3 s escrevendo a linha de motor preso.

O par `(0, 0)` fixado é silêncio deliberado: enquanto ele vive, o `apply_game_rumble` descarta o
FF do jogo no controle dele (D-0410-O-PAR-FIXADO-VENCE-O-JOGO-SO-NO-CONTROLE-DELE e
D-0410-O-PASSTHROUGH-SOLTA-O-PAR-QUE-VIBRA-DE-CADA-CONTROLE: o passthrough conserva o silêncio
deliberado). Por isso o par fica, e o que muda é a soltura: a linha de motor preso só existe para o
par que vibrava. O que se prova, com o backend e o `IpcServer` de verdade e o relógio de mentira:

1. a sequência do diário (vibração zero repetida por dez minutos, quatro donos, dois no cabo e dois
   no rádio) não escreve nenhuma linha de soltura, e o silêncio segue valendo até os 3 s;
2. o par com força, parado além do teto, é solto com UMA linha, por dono, e a linha traz o par;
3. o zero pedido com um par forte de pé silencia o controle no mesmo tique;
4. o par de um dono não mexe no de outro: o zero de um solta calado e o forte do outro conta a sua.

MORDIDA (25/11/2026): a linha de volta para todo par (sem a guarda `any(par)` em
`reassert_rumble`) reprova o primeiro caso e o quarto.
"""

from __future__ import annotations

import time as tempo_real
from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.daemon import ipc_handlers
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    TETO_DO_RUMBLE_FIXADO_S,
    pares_fixados,
    reassert_rumble,
)
from tests.unit.test_mesa_cheia_05_o_rumble_mira import _Mesa

EVENTO = "rumble_fixado_solto_por_ociosidade"
TIQUE_S = 0.2
DEZ_MINUTOS_S = 600.0
INTERVALO_DO_ZERO_S = 3.2


class _Relogio:
    """O `time` do handler com o `monotonic` na mão do teste; o resto é o real."""

    def __init__(self) -> None:
        self.agora = 0.0

    def monotonic(self) -> float:
        return self.agora

    def __getattr__(self, nome: str) -> Any:
        return getattr(tempo_real, nome)


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    r = _Relogio()
    monkeypatch.setattr(ipc_handlers, "time", r)
    return r


@pytest.fixture
def mesa(tmp_path: Path) -> _Mesa:
    m = _Mesa(tmp_path)
    for uniq in m.uniqs[2:]:
        m.handles[uniq].conType = type("CT", (), {"name": "BT"})()
    transportes = [PyDualSenseController._detect_transport(m.handles[u]) for u in m.uniqs]
    assert transportes == ["usb", "usb", "bt", "bt"], "a mesa é dois no cabo e dois no rádio"
    return m


def _tique(mesa: _Mesa, relogio: _Relogio, ate_s: float) -> None:
    while relogio.agora < ate_s:
        relogio.agora = round(relogio.agora + TIQUE_S, 3)
        reassert_rumble(mesa.daemon, relogio.agora)


def _linhas(registros: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in registros if r.get("event") == EVENTO]


@pytest.mark.asyncio
async def test_a_sequencia_do_diario_nao_escreve_linha_de_soltura(
    mesa: _Mesa, relogio: _Relogio
) -> None:
    """D-2211-O-RUMBLE-FIXADO-A-ZERO-NAO-ENCHE-O-DIARIO."""
    proximo = 0.0
    with capture_logs() as registros:
        while relogio.agora < DEZ_MINUTOS_S:
            if relogio.agora >= proximo:
                for uniq in mesa.uniqs:
                    await mesa.server._handle_rumble_set({"uniq": uniq, "weak": 0, "strong": 0})
                proximo += INTERVALO_DO_ZERO_S
            _tique(mesa, relogio, relogio.agora + TIQUE_S)
    linhas = _linhas(registros)
    assert not linhas, f"{len(linhas)} linhas de soltura de um par que não vibrava"


@pytest.mark.asyncio
async def test_o_silencio_do_zero_vale_ate_os_tres_segundos_e_depois_solta(
    mesa: _Mesa, relogio: _Relogio
) -> None:
    dois = mesa.uniqs[1]
    await mesa.server._handle_rumble_set({"uniq": dois, "weak": 0, "strong": 0})
    _tique(mesa, relogio, TETO_DO_RUMBLE_FIXADO_S - 1.0)
    assert dois in pares_fixados(mesa.config), "o silêncio deliberado caiu antes do teto"
    _tique(mesa, relogio, TETO_DO_RUMBLE_FIXADO_S + 1.0)
    assert dois not in pares_fixados(mesa.config), "o par zero parado além do teto não soltou"


@pytest.mark.asyncio
async def test_o_par_com_forca_parado_alem_do_teto_solta_com_uma_linha_por_dono(
    mesa: _Mesa, relogio: _Relogio
) -> None:
    dois, tres = mesa.uniqs[1], mesa.uniqs[2]
    await mesa.server._handle_rumble_set({"uniq": dois, "weak": 160, "strong": 220})
    await mesa.server._handle_rumble_set({"uniq": tres, "weak": 100, "strong": 100})
    with capture_logs() as registros:
        _tique(mesa, relogio, 10.0)
    linhas = _linhas(registros)
    assert sorted(linha["dono"] for linha in linhas) == sorted([dois, tres])
    assert {linha["par"] for linha in linhas} == {(160, 220), (100, 100)}
    assert all(linha["log_level"] == "info" for linha in linhas)


@pytest.mark.asyncio
@pytest.mark.parametrize("indice", [1, 3], ids=["cabo", "radio"])
async def test_o_zero_com_um_par_forte_de_pe_silencia_no_mesmo_tique(
    mesa: _Mesa, relogio: _Relogio, indice: int
) -> None:
    dois = mesa.uniqs[indice]
    await mesa.server._handle_rumble_set({"uniq": dois, "weak": 160, "strong": 220})
    _tique(mesa, relogio, 1.0)
    mesa.limpar_motores()
    await mesa.server._handle_rumble_set({"uniq": dois, "weak": 0, "strong": 0})
    assert mesa.motores_de(dois) == [("left", 0), ("right", 0)], "o zero não chegou ao motor"
    mesa.limpar_motores()
    _tique(mesa, relogio, 1.4)
    assert mesa.motores_de(dois), "o par zero fixado reafirma o silêncio a cada tique"
    assert all(valor == 0 for _lado, valor in mesa.motores_de(dois))
    assert pares_fixados(mesa.config)[dois][:2] == (0, 0)


@pytest.mark.asyncio
async def test_o_par_de_um_dono_nao_mexe_no_de_outro(mesa: _Mesa, relogio: _Relogio) -> None:
    dois, tres = mesa.uniqs[1], mesa.uniqs[2]
    await mesa.server._handle_rumble_set({"uniq": dois, "weak": 0, "strong": 0})
    await mesa.server._handle_rumble_set({"uniq": tres, "weak": 100, "strong": 100})
    with capture_logs() as registros:
        _tique(mesa, relogio, 10.0)
    linhas = _linhas(registros)
    assert [linha["dono"] for linha in linhas] == [tres], "só o par que vibrava conta a soltura"
    assert linhas[0]["par"] == (100, 100)
    assert dois not in pares_fixados(mesa.config)
    assert tres not in pares_fixados(mesa.config)
