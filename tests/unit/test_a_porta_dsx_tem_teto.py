"""A-PORTA-DSX-NAO-INCHA-O-SERVICO-NEM-O-DIARIO-01 (19/11/2026): a porta 6969 tem teto.

Medido em memória com o `UdpHandler` de verdade: 20.000 datagramas PlayerLED com
máscaras distintas rendiam 20.000 contadores, 76,0 MiB no processo e 74,8 MiB de JSON em
cada `daemon.state_full`; cada instrução desconhecida escrevia uma linha no diário.

Agora o valor de fora passa por faixa antes de virar nome (PlayerLED 0-31, limiar
0-255, índice 0-3), os contadores não carregam o valor, o datagrama tem teto de
instruções, o `StateStore` tem teto de chaves e os avisos da porta se juntam no diário.

MORDIDA: tirar a faixa do PlayerLED (o `0 <= mask <= 0b11111`) e trocar o contador por
`udp.player_led.{mask}` reprova a primeira régua com mais de mil chaves `udp.*`.
"""
from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.controller import OutputSpec, ResultadoDeSaida
from hefesto_dualsense4unix.daemon import udp_server
from hefesto_dualsense4unix.daemon.state_store import (
    CONTADOR_ACIMA_DO_TETO,
    TETO_DE_CONTADORES,
    StateStore,
)
from hefesto_dualsense4unix.daemon.udp_server import (
    MAX_INSTRUCOES_POR_DATAGRAMA,
    RateLimiter,
    UdpHandler,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import logging_config

UNIQS = tuple(f"aabbcc00000{n}" for n in range(1, 5))
JOGADORES = {uniq: n for n, uniq in enumerate(UNIQS, 1)}
ENDERECO = ("127.0.0.1", 40000)


class _QuatroControles(FakeController):
    """Quatro controles na mesa, com a escrita por MAC que o backend real tem."""

    def __init__(self) -> None:
        super().__init__(transport="usb")

    def uniqs_do_destino(self) -> list[str]:
        return list(UNIQS)

    def apply_output_for(self, uniq: str, spec: OutputSpec) -> ResultadoDeSaida:
        return "escreveu"


class _Diario:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.buf = io.StringIO()
        self.agora = [1000.0]
        self.agendados: list[tuple[Any, Any]] = []
        agregado = logging_config._AGREGADO
        monkeypatch.setattr(agregado, "_janelas", {})
        monkeypatch.setattr(agregado, "_ultimas", {})
        monkeypatch.setattr(agregado, "relogio", lambda: self.agora[0])
        monkeypatch.setattr(
            agregado, "_agendar", lambda chave, janela, _s: self.agendados.append((chave, janela))
        )
        diario = structlog.wrap_logger(
            structlog.PrintLogger(file=self.buf),
            processors=logging_config.cadeia_do_diario("console", self.buf),
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
        )
        monkeypatch.setattr(agregado, "diario", diario)
        monkeypatch.setattr(udp_server, "logger", diario)
        self.agregado = agregado

    def linhas(self, evento: str) -> list[str]:
        return [linha for linha in self.buf.getvalue().splitlines() if f" {evento} " in linha]

    def fim_das_janelas(self) -> None:
        self.agora[0] += logging_config.JANELA_DO_AGREGADO_S
        agendados, self.agendados = self.agendados, []
        for chave, janela in agendados:
            self.agregado._fechar(chave, janela)


@pytest.fixture
def diario(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Diario]:
    yield _Diario(monkeypatch)


def _mesa() -> tuple[UdpHandler, StateStore]:
    store = StateStore()
    sem_limite = RateLimiter(rate_global=10**9, rate_per_ip=10**9)
    handler = UdpHandler(
        controller=_QuatroControles(), store=store, rate_limiter=sem_limite,
        jogadores=lambda: JOGADORES,
    )
    return handler, store


def _mandar(handler: UdpHandler, *instrucoes: dict[str, Any]) -> None:
    handler.handle_datagram(json.dumps({"instructions": list(instrucoes)}).encode(), ENDERECO)


def _chaves_udp(store: StateStore) -> set[str]:
    return {k for k in store.snapshot().counters if k.startswith("udp.")}


def test_dez_mil_valores_distintos_nao_criam_chaves(diario: _Diario) -> None:
    """D-1911-A-PORTA-DSX-TEM-FAIXA-E-TETO: valor de fora nunca vira nome de contador."""
    handler, store = _mesa()
    tamanho_no_milesimo = 0
    chaves_no_milesimo: set[str] = set()
    for i in range(10_000):
        _mandar(
            handler,
            {"type": 3, "parameters": [i % 8, i]},
            {"type": 4, "parameters": [i % 8, 1 + i % 2, i]},
        )
        if i == 999:
            chaves_no_milesimo = _chaves_udp(store)
            tamanho_no_milesimo = len(json.dumps(store.snapshot().counters))
    chaves = _chaves_udp(store)
    assert len(chaves) <= 16, sorted(chaves)[:20]
    assert chaves == chaves_no_milesimo
    assert len(json.dumps(store.snapshot().counters)) <= tamanho_no_milesimo + 32
    assert store.counter("udp.player_led") > 0
    assert store.counter("udp.trigger_threshold.left") > 0
    assert store.counter("udp.error.PlayerLED") > 0
    assert len(handler._indices_avisados) <= 2 * 5
    assert len(diario.linhas("udp_indice_sem_jogador")) <= 2


def test_seiscentas_instrucoes_desconhecidas_dao_duas_linhas(diario: _Diario) -> None:
    """D-1911-A-PORTA-DSX-TEM-FAIXA-E-TETO: o aviso da porta se junta numa linha por janela."""
    handler, store = _mesa()
    for i in range(600):
        _mandar(handler, {"type": 1000 + i, "parameters": []})
    assert store.counter("udp.unknown_instruction") == 600
    assert len(diario.linhas("udp_unknown_instruction")) == 1
    diario.fim_das_janelas()
    linhas = diario.linhas("udp_unknown_instruction")
    assert len(linhas) == 2 and "vezes=599" in linhas[1], linhas


def test_o_datagrama_aplica_ate_o_teto_de_instrucoes(diario: _Diario) -> None:
    """D-1911-A-PORTA-DSX-TEM-FAIXA-E-TETO: o datagrama com instruções demais aplica o teto."""
    handler, store = _mesa()
    _mandar(handler, *({"type": 3, "parameters": [0, 1]} for _ in range(100)))
    assert store.counter("udp.applied.PlayerLED") == MAX_INSTRUCOES_POR_DATAGRAMA
    assert store.counter("udp.instrucoes_demais") == 1


def test_o_store_conta_o_nome_novo_acima_do_teto_numa_chave_so() -> None:
    """D-1911-A-PORTA-DSX-TEM-FAIXA-E-TETO: o `StateStore` não passa do teto de chaves."""
    store = StateStore()
    for i in range(TETO_DE_CONTADORES + 500):
        store.bump(f"qualquer.{i}")
    assert len(store.snapshot().counters) == TETO_DE_CONTADORES + 1
    assert store.counter(CONTADOR_ACIMA_DO_TETO) == 500
    assert store.bump("qualquer.0") == 2
