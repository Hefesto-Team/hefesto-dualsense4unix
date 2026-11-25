"""O-TIQUE-NAO-ESPERA-AS-VARREDURAS-NO-POOL-01 — a leitura do tique tem um fio próprio.

O `_poll_loop` de produção roda aqui, pelo arnês do `test_o_laco_mede_o_atraso`. Os dois
fios do pool das varreduras ficam presos, como ficam com `_gather_game_signal_inputs`, a
sonda do escritor cru e o `connect` de outro controle, e o tique segue lendo o controle
no fio `hefesto-tique`. Vale em toda mesa de cabo e rádio, de P1 a P4, e com só o P3 de pé.

Nenhum endereço real: o arnês usa a faixa forjada ``02:fe:``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import connection as cx
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from tests.unit.test_o_laco_mede_o_atraso import (
    JANELA,
    _Laco,
    _o_laco_sem_a_maquina,
    _rodar_vigiado,
    _segurar_os_fios,
)

__all__ = ["_o_laco_sem_a_maquina"]

TETO_DO_TIQUE_US = 100_000

MESAS = [
    (("usb", "usb", "usb", "usb"), None),
    (("usb", "usb", "usb", "bt"), None),
    (("bt", "usb", "usb", "usb"), None),
    (("usb", "usb", "bt", "bt"), None),
    (("usb", "bt", "bt", "bt"), None),
    (("bt", "bt", "bt", "bt"), None),
    (("usb",), (3,)),
    (("bt",), (3,)),
]
NOMES = [
    "4-cabos", "3-cabos-1-radio", "1-radio-3-cabos", "2-e-2", "1-cabo-3-radios", "4-radios",
    "so-o-p3-cabo", "so-o-p3-radio",
]


@pytest.mark.parametrize(("mesa", "posicoes"), MESAS, ids=NOMES)
def test_o_tique_segue_com_os_dois_fios_do_pool_presos(
    mesa: tuple[str, ...], posicoes: tuple[int, ...] | None,
) -> None:
    """D-2511-O-TIQUE-LE-O-CONTROLE-NUM-FIO-SO-DELE: o pool cheio não segura a leitura.

    MORDIDA: devolva a leitura do tique ao `_run_blocking`, e o corpo do tique passa de 250 ms.
    """
    daemon = _Laco(mesa, posicoes=posicoes)
    eventos: list[threading.Event] = []

    _rodar_vigiado(daemon, lambda: _segurar_os_fios(daemon, 2, eventos))

    c = daemon.contadores()
    assert c["poll.tique.pior_us"] < TETO_DO_TIQUE_US, c
    assert c["poll.laco.lentas"] == 0, c


def test_a_leitura_do_tique_corre_em_fio_proprio_uma_por_vez() -> None:
    """D-2511-O-TIQUE-LE-O-CONTROLE-NUM-FIO-SO-DELE: um fio, o mesmo em todo tique.

    MORDIDA: devolva a leitura ao `_run_blocking`, e o nome do fio deixa de ser o do tique.
    """
    daemon = _Laco(("usb", "bt", "usb", "bt"))
    estado = ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb")
    fios: list[str] = []
    juntas: list[int] = []
    em_curso = 0

    def read_state() -> ControllerState:
        nonlocal em_curso
        em_curso += 1
        juntas.append(em_curso)
        fios.append(threading.current_thread().name)
        em_curso -= 1
        return estado

    daemon.controller = SimpleNamespace(is_connected=lambda: True, read_state=read_state)

    _rodar_vigiado(daemon)

    assert len(fios) == JANELA, len(fios)
    assert {nome.rsplit("_", 1)[0] for nome in fios} == {"hefesto-tique"}, set(fios)
    assert len(set(fios)) == 1, set(fios)
    assert max(juntas) == 1, juntas


def test_a_leitura_que_dorme_nao_para_o_laco() -> None:
    """A leitura lenta aparece no corpo do tique e deixa o laço livre para as outras tarefas.

    MORDIDA: chame `read_state` direto no laço, e `poll.laco.lentas` sobe.
    """
    daemon = _Laco(("usb", "bt", "usb", "bt"))
    estado = ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="bt")
    chamadas = 0

    def read_state() -> ControllerState:
        nonlocal chamadas
        chamadas += 1
        if chamadas == 5:
            time.sleep(0.2)
        return estado

    daemon.controller = SimpleNamespace(is_connected=lambda: True, read_state=read_state)

    _rodar_vigiado(daemon)

    c = daemon.contadores()
    assert c["poll.tique.pior_us"] >= 190_000, c
    assert c["poll.laco.lentas"] == 0, c


def test_a_parada_fecha_o_fio_do_tique() -> None:
    """O fio nasce no primeiro pedido e a parada do serviço o fecha, como fecha os outros dois."""
    soltos: list[str] = []
    controle: Any = SimpleNamespace(disconnect=lambda: soltos.append("disconnect"))
    daemon = Daemon(controller=controle)

    async def corpo() -> Any:
        from concurrent.futures import ThreadPoolExecutor

        daemon._executor = ThreadPoolExecutor(max_workers=1)
        assert daemon._tick_executor is None
        nome = await daemon._run_tick_blocking(lambda: threading.current_thread().name)
        fio = daemon._tick_executor
        assert fio is not None
        await cx.soltar_o_controle(daemon)
        return nome, fio

    nome, fio = asyncio.run(corpo())

    assert nome.startswith("hefesto-tique"), nome
    assert daemon._tick_executor is None
    assert fio._shutdown is True
    assert soltos == ["disconnect"], soltos
