"""A saída de um controle não trava a aba Sistema.

A faixa lenta da aba 09 faz cinco leituras caras (``systemctl`` e disco):
18 ms com a máquina calma, 1.840 ms medidos com o disco disputado. A
primeira leitura é síncrona de propósito, para a primeira pintura ser
verdadeira; as releituras vão a uma thread.

A poda que roda quando um controle sai (P1 a P4, cabo ou rádio) esvaziava
a faixa, e esvaziar é o mesmo sinal da primeira pintura: as cinco leituras
voltavam a rodar dentro do laço da janela. Aqui a leitura é um dublê que
dorme 0,5 s, e o ``pacote`` depois da poda tem de sair em menos de 50 ms,
com o valor da mesa de agora chegando pela thread.
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

DORME_S = 0.5
TETO_DO_TIQUE_S = 0.05
TETO_DA_THREAD_S = 5.0


def _controle(uniq: str, jogador: int, nome: str) -> dict[str, Any]:
    return {"uniq": uniq, "pref": f"p{jogador}", "jogador": jogador,
            "nome": nome, "via": "Bluetooth", "transporte": "bt",
            "connected": True, "transport": "bt", "player_slot": jogador,
            "serial": None, "modelo": None, "cor": "white", "alvo": jogador == 1}


def _ctx(*controles: dict[str, Any]) -> pacotes.Contexto:
    lista = list(controles)
    return pacotes.Contexto(state={"controllers": lista}, mesa=lista,
                            conectados=lista)


class _JanelaDeMentira:
    """Sem ela, o painel técnico perguntaria ao systemd de quem roda a régua."""

    def _systemctl_status_text(self, unit: str) -> str:
        return "● unidade ativa"


@pytest.fixture
def faixa(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[str, ...]]]:
    """Troca as cinco leituras por um dublê lento e devolve os caches como estavam."""
    guardado: dict[str, Any] = {
        "camada1": dict(a02._CAMADA_1), "sono": dict(a02._SONO),
        "quando": a02._CAMADA_1_QUANDO[0],
        "selo": a02._CAMADA_1_SELO[0], "voo": a02._CAMADA_1_EM_VOO[0],
        "lento": dict(a09._LENTO), "lento_selo": a09._LENTO_SELO[0],
        "lento_voo": a09._LENTO_EM_VOO[0], "antes": pacotes._NA_MESA_ANTES[0],
        "vigia": (a07.VIGIA._dado, a07.VIGIA._quando, a07.VIGIA._em_curso),
    }
    a09._JANELA_ANTIGA[:] = [_JanelaDeMentira()]
    lidas: list[tuple[str, ...]] = []

    def lenta(state: Any, pode_perguntar: bool = True, mesa: Any = None) -> Any:
        time.sleep(DORME_S)
        nomes = tuple(str(c.get("nome")) for c in (mesa or []))
        lidas.append(nomes)
        return ("enabled", [], None, "online_systemd", "painel de " + ", ".join(nomes))

    monkeypatch.setattr(a09, "_ler_a_faixa_lenta", lenta)
    a09._LENTO.clear()
    a09._LENTO_EM_VOO[0] = False
    yield lidas
    fim = time.monotonic() + TETO_DA_THREAD_S
    while a09._LENTO_EM_VOO[0] and time.monotonic() < fim:
        time.sleep(0.01)
    for cache in (a02._CAMADA_1, a02._SONO, a09._LENTO):
        cache.clear()
    a02._CAMADA_1.update(guardado["camada1"])
    a02._SONO.update(guardado["sono"])
    a02._CAMADA_1_QUANDO[0] = guardado["quando"]
    a02._CAMADA_1_SELO[0] = guardado["selo"]
    a02._CAMADA_1_EM_VOO[0] = guardado["voo"]
    a09._LENTO.update(guardado["lento"])
    a09._LENTO_SELO[0] = guardado["lento_selo"]
    a09._LENTO_EM_VOO[0] = guardado["lento_voo"]
    pacotes._NA_MESA_ANTES[0] = guardado["antes"]
    a07.VIGIA._dado, a07.VIGIA._quando, a07.VIGIA._em_curso = guardado["vigia"]
    a09._JANELA_ANTIGA.clear()


def _cronometrar(ctx: pacotes.Contexto) -> float:
    comeco = time.perf_counter()
    a09.pacote(ctx)
    return time.perf_counter() - comeco


def test_o_pacote_depois_da_saida_nao_espera_a_faixa_lenta(
        faixa: list[tuple[str, ...]]) -> None:
    dois = _ctx(_controle(P1, 1, "um"), _controle(P2, 2, "dois"))
    primeira = _cronometrar(dois)
    assert primeira >= DORME_S, "a primeira pintura deixou de ser síncrona"
    assert faixa == [("um", "dois")]
    _cronometrar(dois)

    pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
    so_um = _ctx(_controle(P1, 1, "um"))
    assert pacotes.podar_o_que_saiu(so_um) == frozenset({P2})
    depois = _cronometrar(so_um)
    assert depois < TETO_DO_TIQUE_S, (
        f"o pacote depois da saída levou {depois * 1000:.0f} ms: a faixa lenta "
        "voltou a rodar no fio da janela")

    fim = time.monotonic() + TETO_DA_THREAD_S
    while a09._LENTO_EM_VOO[0] and time.monotonic() < fim:
        time.sleep(0.01)
    assert faixa[-1] == ("um",), faixa
    *_, painel = a09._faixa_lenta(so_um.state, so_um.mesa)
    assert painel == "painel de um", painel


def test_a_releitura_em_voo_com_a_mesa_de_antes_nao_volta(
        faixa: list[tuple[str, ...]]) -> None:
    """O selo descarta a leitura que saiu antes da poda."""
    dois = _ctx(_controle(P1, 1, "um"), _controle(P2, 2, "dois"))
    a09.pacote(dois)
    selo = a09._LENTO_SELO[0]
    pacotes._NA_MESA_ANTES[0] = frozenset({P1, P2})
    so_um = _ctx(_controle(P1, 1, "um"))
    pacotes.podar_o_que_saiu(so_um)
    a09._guardar_a_faixa_lenta(dois.state, dois.mesa, selo)
    assert a09._LENTO["quando"] == 0.0, "a leitura velha renovou a faixa vencida"
    a09._LENTO_EM_VOO[0] = False
    a09.pacote(so_um)
    fim = time.monotonic() + TETO_DA_THREAD_S
    while a09._LENTO_EM_VOO[0] and time.monotonic() < fim:
        time.sleep(0.01)
    *_, painel = a09._faixa_lenta(so_um.state, so_um.mesa)
    assert painel == "painel de um", painel
