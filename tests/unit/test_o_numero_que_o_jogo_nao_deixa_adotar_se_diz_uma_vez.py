"""O-NUMERO-QUE-O-JOGO-NAO-DEIXA-ADOTAR-SE-DIZ-UMA-VEZ-POR-MUDANCA-01 (22/11/2026).

Na noite de 21/11, `o_numero_do_jogo_nao_trocou` saiu 5971 vezes, uma a cada `sync`, sempre do
mesmo controle: a marca do jogo não muda enquanto ele não repinta, e a mesma recusa se repetia. A
recusa se diz uma vez por mudança de `(alvo, jogo, hefesto, motivo)`, por controle; some da
memória quando a marca do alvo sai do `_numero_que_o_jogo_escreveu` ou o alvo sai da mesa, e a
troca adotada também a zera.

O ensaio é o de `test_o_numero_do_jogo_vira_o_do_hefesto`: o `CoopManager` real, os leitores e os
vpads falsos e o registro de mentira. O diário é um espião no `logger` do co-op.

MORDIDA: tirar a guarda de `_a_recusa_e_nova` reprova o primeiro caso com 100 linhas em vez de 1.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from tests.unit.test_o_numero_do_jogo_vira_o_do_hefesto import (  # noqa: F401
    _daemon,
    _Registro,
    registro,
)
from tests.unit.test_steam_no_fisico_01_o_jogo_ve_p1_a_p4 import (  # noqa: F401
    P1,
    P2,
    P3,
    P4,
    nascimentos,
)

NAO_TROCOU = "o_numero_do_jogo_nao_trocou"
ADOTADO = "o_numero_do_jogo_adotado"


class _Espiao:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, dict[str, Any]]] = []

    def __getattr__(self, nivel: str) -> Any:
        def _registrar(evento: str, **kw: Any) -> None:
            self.eventos.append((nivel, evento, kw))

        return _registrar

    def de(self, evento: str) -> list[dict[str, Any]]:
        return [kw for _nivel, nome, kw in self.eventos if nome == evento]


@pytest.fixture
def espiao(monkeypatch: pytest.MonkeyPatch) -> _Espiao:
    espiao = _Espiao()
    monkeypatch.setattr(coop_mod, "logger", espiao)
    return espiao


def _mesa(reg: _Registro) -> tuple[Any, CoopManager]:
    daemon = _daemon(reg)
    gerente = CoopManager(daemon)
    daemon._coop_manager = gerente
    gerente.sync()
    daemon.display_authority = "game"
    return daemon, gerente


def _o_jogo_marca(daemon: Any, reg: _Registro, marcas: dict[str, int]) -> None:
    daemon._numero_que_o_jogo_escreveu = {
        mac: (jogo, reg.numeros[mac]) for mac, jogo in marcas.items()
    }


def _sync(gerente: CoopManager, vezes: int) -> None:
    for _ in range(vezes):
        gerente.sync(force=True)


def test_cem_sync_com_a_mesma_recusa_dizem_uma_linha(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao  # noqa: F811
) -> None:
    """D-2211-A-RECUSA-DO-NUMERO-SE-DIZ-UMA-VEZ-POR-MUDANCA."""
    daemon, gerente = _mesa(registro)
    registro.numeros = {P1: 1, P2: 2}
    _o_jogo_marca(daemon, registro, {P2: 1})
    _sync(gerente, 100)

    assert len(espiao.de(NAO_TROCOU)) == 1, espiao.de(NAO_TROCOU)
    assert espiao.de(ADOTADO) == []


def test_o_jogo_que_muda_a_marca_diz_a_segunda(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao  # noqa: F811
) -> None:
    daemon, gerente = _mesa(registro)
    registro.numeros = {P1: 1, P2: 2}
    _o_jogo_marca(daemon, registro, {P2: 1})
    _sync(gerente, 30)
    _o_jogo_marca(daemon, registro, {P2: 3})
    _sync(gerente, 30)

    assert [kw["jogo"] for kw in espiao.de(NAO_TROCOU)] == [1, 3]


def test_o_desencontro_que_volta_depois_de_o_jogo_concordar_diz_de_novo(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao  # noqa: F811
) -> None:
    """A concordância encerra a recusa: o mesmo desencontro, quando volta, é mudança nova."""
    daemon, gerente = _mesa(registro)
    registro.numeros = {P1: 1, P2: 2}
    _o_jogo_marca(daemon, registro, {P2: 1})
    _sync(gerente, 20)
    _o_jogo_marca(daemon, registro, {P2: 2})
    _sync(gerente, 20)
    _o_jogo_marca(daemon, registro, {P2: 1})
    _sync(gerente, 20)

    assert [kw["jogo"] for kw in espiao.de(NAO_TROCOU)] == [1, 1]


def test_o_pad_do_alvo_que_morre_e_renasce_com_a_mesma_marca_diz_de_novo(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao  # noqa: F811
) -> None:
    daemon, gerente = _mesa(registro)
    registro.numeros = {P1: 1, P2: 2}
    _o_jogo_marca(daemon, registro, {P2: 3})
    _sync(gerente, 20)
    assert len(espiao.de(NAO_TROCOU)) == 1

    daemon._numero_que_o_jogo_escreveu = {}
    _sync(gerente, 5)
    _o_jogo_marca(daemon, registro, {P2: 3})
    _sync(gerente, 20)
    assert len(espiao.de(NAO_TROCOU)) == 2


def test_o_alvo_que_sai_da_mesa_e_volta_com_a_mesma_marca_diz_de_novo(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao  # noqa: F811
) -> None:
    daemon, gerente = _mesa(registro)
    registro.numeros = {P1: 1, P2: 2}
    _o_jogo_marca(daemon, registro, {P2: 3})
    _sync(gerente, 20)

    gerente._teardown_player(P2)
    _sync(gerente, 20)
    assert len(espiao.de(NAO_TROCOU)) == 2, "o P2 renasceu e o desencontro é outro"


def test_tres_controles_recusados_juntos_dizem_uma_linha_por_controle(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao  # noqa: F811
) -> None:
    daemon, gerente = _mesa(registro)
    _o_jogo_marca(daemon, registro, {P2: 1, P3: 1, P4: 1})
    _sync(gerente, 100)

    linhas = espiao.de(NAO_TROCOU)
    assert len(linhas) == 3, linhas
    assert len({kw["alvo"] for kw in linhas}) == 3


def test_a_troca_adotada_zera_para_a_recusa_seguinte_se_dizer(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao  # noqa: F811
) -> None:
    daemon, gerente = _mesa(registro)
    _o_jogo_marca(daemon, registro, {P2: 1})
    _sync(gerente, 10)
    assert len(espiao.de(NAO_TROCOU)) == 1

    _o_jogo_marca(daemon, registro, {P2: 3})
    _sync(gerente, 3)
    assert len(espiao.de(ADOTADO)) == 1

    registro.numeros = {P1: 1, P2: 2, P3: 3, P4: 4}
    _o_jogo_marca(daemon, registro, {P2: 1})
    _sync(gerente, 10)
    assert len(espiao.de(NAO_TROCOU)) == 2


def test_a_troca_que_levanta_se_diz_uma_vez(
    nascimentos: list[str], registro: _Registro, espiao: _Espiao,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _quebra(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("trava")

    monkeypatch.setattr(IpcHandlersMixin, "_set_number_locked", staticmethod(_quebra))
    daemon, gerente = _mesa(registro)
    _o_jogo_marca(daemon, registro, {P2: 3})
    _sync(gerente, 100)

    avisos = [nivel for nivel, nome, _kw in espiao.eventos if nome == NAO_TROCOU]
    assert avisos == ["warning"]
